const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vscode = require('vscode');
exports.run = async () => {
  const extension = vscode.extensions.getExtension('taymur.pcbai-vscode');
  assert.ok(extension);
  await extension.activate();
  const uri = vscode.Uri.file(path.join(process.env.PCBAI_TEST_WORKSPACE, 'example.kicad_dru'));
  fs.writeFileSync(uri.fsPath, '(version 1)\n');
  const doc = await vscode.workspace.openTextDocument(uri);
  assert.equal(doc.languageId, 'kicad-dru');
  const editor = await vscode.window.showTextDocument(doc);
  editor.selection = new vscode.Selection(1, 0, 1, 0);
  await vscode.commands.executeCommand('editor.action.insertSnippet', {langId: 'kicad-dru', name: 'Clearance example'});
  assert.match(doc.getText(), /constraint clearance \(min 0.2mm\)/);
  const ranges = await vscode.commands.executeCommand('vscode.executeFoldingRangeProvider', uri);
  assert.ok(ranges.some(r => r.end > r.start));
  const result = {vscode: vscode.version,
    extension: extension.packageJSON.version, packaged_extension: true, dru_language: doc.languageId,
    snippet_inserted: true, folding: true, isolated: true};
  if (extension.packageJSON.contributes.jsonValidation) {
    const irUri = vscode.Uri.file(path.join(process.env.PCBAI_TEST_WORKSPACE, 'test.pcbai-ir.json'));
    const makeIR = (symbol, unit = 1, pin = 'R1.', footprint = '') => JSON.stringify({ir_version: 1, requirements: {}, rails: {}, blocks: [], parts: [{id: 'R1', symbol, unit, footprint}], connections: [[pin, '@GND']]});
    fs.writeFileSync(irUri.fsPath, makeIR('Device:R'));
    const ir = await vscode.workspace.openTextDocument(irUri);
    const irEditor = await vscode.window.showTextDocument(ir);
    const set = async text => {await irEditor.edit(edit => edit.replace(new vscode.Range(ir.positionAt(0), ir.positionAt(ir.getText().length)), text));};
    const at = value => ir.positionAt(ir.getText().indexOf(JSON.stringify(value)) + JSON.stringify(value).length - 1);
    const complete = async value => {
      const response = await vscode.commands.executeCommand('vscode.executeCompletionItemProvider', irUri, at(value));
      return response.items.filter(item => item.detail?.includes('SHA '));
    };
    const hovering = async value => {
      const hovers = await vscode.commands.executeCommand('vscode.executeHoverProvider', irUri, at(value));
      return hovers.flatMap(h => h.contents).find(c => c.value?.replace(/\\/g, '').includes('SHA-256:'));
    };
    const markdownText = value => value.replace(/\\/g, '').replace(/&nbsp;/g, ' ');
    const acceptAlternative = async (value, read, proposed) => {
      irEditor.selection = new vscode.Selection(at(value), at(value));
      await vscode.commands.executeCommand('editor.action.triggerSuggest');
      const deadline = Date.now() + 6000;
      while (read() === value && Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 150));
        await vscode.commands.executeCommand('acceptSelectedSuggestion');
      }
      assert.ok(read() !== value && proposed.includes(read()), 'Actual widget alternative was not accepted: ' + read());
    };
    let items = await complete('Device:R');
    assert.ok(items.some(item => item.label === 'Device:R'), 'Real local symbol completion absent');
    let hover = await hovering('Device:R');
    assert.ok(hover); assert.equal(hover.isTrusted, false); assert.equal(hover.supportHtml, false);
    await set(makeIR('Test:Multi', 1));
    items = await complete('R1.');
    assert.deepEqual(items.map(i => i.label).sort(), ['R1.01', 'R1.1']);
    await set(makeIR('Test:Multi', 2));
    items = await complete('R1.');
    assert.deepEqual(items.map(i => i.label).sort(), ['R1.01', 'R1.2']);
    items = await complete('');
    assert.ok(items.some(i => i.label === 'Test:Multi'), 'Actual symbol footprint alternative absent');
    hover = await hovering('Test:Multi');
    const oldSHA = markdownText(hover.value).match(/SHA-256: ([a-f0-9]{64})/)[1];
    const library = process.env.PCBAI_TEST_LIBRARY;
    fs.writeFileSync(library, fs.readFileSync(library, 'utf8').replace('Private multi-unit fixture', 'Changed local metadata <script>evil</script> [run](command:evil)'));
    hover = await hovering('Test:Multi');
    assert.ok(markdownText(hover.value).includes('Changed local metadata'));
    assert.ok(hover.value.includes('\\[run\\]'), 'Untrusted command Markdown must be escaped as text');
    assert.notEqual(markdownText(hover.value).match(/SHA-256: ([a-f0-9]{64})/)[1], oldSHA);
    await set(makeIR('Wrong:R'));
    const proposed = (await complete('Wrong:R')).map(item => item.label);
    await acceptAlternative('Wrong:R', () => JSON.parse(ir.getText()).parts[0].symbol, proposed);
    await set(makeIR('Test:Multi', 1, 'R1.99'));
    await acceptAlternative('R1.99', () => JSON.parse(ir.getText()).connections[0][0], ['R1.01', 'R1.1']);
    await set(makeIR('Device:R'));
    for (let i = 0; i < 3; i++) await complete('Device:R');
    const warm = [];
    for (let i = 0; i < 10; i++) {
      const started = performance.now();
      assert.ok((await complete('Device:R')).some(item => item.label === 'Device:R'));
      warm.push(performance.now() - started);
    }
    const ordered = [...warm].sort((a, b) => a - b);
    Object.assign(result, {ir_real_service: true, symbols: true, literal_pins: true, multi_unit: true, alternative_widget_accept: true, wrong_pin_widget_accept: true, unsafe_markdown_escaped: true,
      footprint_source: true, library_sha_refresh: true, warm_ms: warm, warm_p95_ms: ordered[Math.ceil(ordered.length * .95) - 1],
      warmup_queries: 3, corpus: 'Private copied KiCad libraries plus Test multi-unit fixture',
      library_files: Number(process.env.PCBAI_LIBRARY_FILES), library_bytes: Number(process.env.PCBAI_LIBRARY_BYTES),
      preload_seconds: Number(process.env.PCBAI_PRELOAD_SECONDS || 0),
      processor: process.env.PROCESSOR_IDENTIFIER});
  }
  fs.writeFileSync(process.env.PCBAI_HOST_RESULT, JSON.stringify(result, null, 2));
};
