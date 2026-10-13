// Run with Node or VS Code's Electron in ELECTRON_RUN_AS_NODE mode.
// Exercises the real command against a local mock service; no user settings/projects.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const Module = require('node:module');

async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-extension-test-'));
  const commands = new Map();
  const subscriptions = [];
  const panels = [];
  const errors = [];
  const lines = [];
  const project = path.join(root, 'Test.kicad_pro');
  const state = path.join(root, 'state');
  const exportsRoot = path.join(state, 'exports');
  fs.mkdirSync(exportsRoot, { recursive: true });
  const artifact = path.join(exportsRoot, 'render.png');
  let artifactPath = artifact;
  fs.writeFileSync(artifact, Buffer.from([137, 80, 78, 71]));
  const token = 'private-token-that-must-never-reach-webview';
  process.env.PCBAI_STATE_DIR = state;
  const document = 'board"><script>BAD</script>.kicad_pcb';
  const session = { id: 's-test', project: 'Test.kicad_pro', root, revision: 'a'.repeat(64), documents: [document] };
  const submitted = [];
  const partCalls = [];
  const opened = [];
  const server = http.createServer((req, res) => {
    assert.equal(req.headers.authorization, 'Bearer ' + token);
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      let response;
      if (req.url === '/health') response = { name: 'pcbai', instance: 'test-instance', projects: [project], version: '0.1.2' };
      else {
        const call = JSON.parse(body);
        if (call.name === 'pcbai_status') response = { ok: true, sessions: [session] };
        else if (call.name === 'search_parts') {partCalls.push(call); response = {ok: true, parts: [{lib_id: 'Test:R', description: '<script>data</script>'}]};}
        else if (call.name === 'part_info') {partCalls.push(call); response = {ok: true, part: {lib_id: 'Test:R', library_sha256: 'a'.repeat(64), properties: {Footprint: 'Test:R'}}};}
        else if (call.name === 'verify_part') {partCalls.push(call); response = {ok: true, pin_pad_match: true, stock_verified: false};}
        else if (call.name === 'start_job') {
          submitted.push(call.arguments);
          response = { ok: true, job: { job_id: 'job-test' } };
        } else if (call.name === 'job_status') {
          const tool = submitted.at(-1).tool;
          response = { ok: true, job: { status: 'completed', result: {
            ok: true, path: artifactPath, target: { revision: session.revision }, evidence_id: 'ev-test',
            dimensions: { width: 1192, height: 884 }, measurements: [{ quantity: 'board_width', value: 52.07, unit: 'mm' }],
            tool,
          } } };
        } else throw new Error('Unexpected command ' + call.name);
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(response));
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  fs.writeFileSync(path.join(state, 'service.json'), JSON.stringify({ port: server.address().port, token, instance: 'test-instance' }));
  const uri = (fsPath) => ({ fsPath, toString: () => fsPath });
  const vscode = {
    workspace: { findFiles: async () => [uri(project)], openTextDocument: async options => {opened.push(options); return options;} },
    commands: { registerCommand: (name, callback) => { commands.set(name, callback); return { dispose() {} }; } },
    StatusBarAlignment: { Left: 1 }, ViewColumn: { Beside: 2 }, Uri: { file: uri },
    window: {
      createOutputChannel: () => ({ appendLine: (line) => lines.push(line), show() {}, dispose() {} }),
      createStatusBarItem: () => ({ show() {}, dispose() {} }),
      showErrorMessage: (error) => errors.push(error),
      showInputBox: async () => 'resistor',
      showQuickPick: async items => items[0],
      showTextDocument: async document => document,
      createWebviewPanel: (_id, _title, _column, options) => {
        const panel = { options, webview: { cspSource: 'vscode-webview:', asWebviewUri: uri, html: '' } };
        panels.push(panel);
        return panel;
      },
    },
  };
  const originalLoad = Module._load;
  Module._load = function(name, ...args) { return name === 'vscode' ? vscode : originalLoad.call(this, name, ...args); };
  try {
    const extension = require('./extension.js');
    Module._load = originalLoad;
    extension.activate({ subscriptions });
    await commands.get('pcbai.render')();
    assert.deepEqual(errors, []);
    assert.equal(submitted[0].revision, session.revision);
    assert.equal(submitted[0].document, document);
    assert.equal(panels[0].options.enableScripts, false);
    assert.equal(panels[0].options.localResourceRoots[0].fsPath, fs.realpathSync(exportsRoot));
    assert.ok(panels[0].webview.html.includes('&lt;script&gt;BAD&lt;/script&gt;'));
    assert.ok(panels[0].webview.html.includes("default-src 'none'"));
    assert.ok(!panels[0].webview.html.includes('<script>'));
    assert.ok(!panels[0].webview.html.includes(token));
    await commands.get('pcbai.stats')();
    assert.deepEqual(errors, []);
    assert.ok(lines.some((line) => line.includes('52.07 mm')));
    await commands.get('pcbai.searchParts')();
    assert.deepEqual(errors, []);
    assert.deepEqual(partCalls.map(c => c.name), ['search_parts', 'part_info', 'verify_part']);
    assert.equal(JSON.parse(opened[0].content).pin_pad.stock_verified, false);
    assert.equal(opened[0].language, 'json');
    // A service artifact outside exports is rejected before creating a panel.
    artifactPath = path.join(root, 'outside.png');
    fs.writeFileSync(artifactPath, 'outside');
    await commands.get('pcbai.render')();
    assert.equal(panels.length, 1);
    assert.equal(errors.length, 1);
    console.log('VS Code mock: render/stats commands, revision, CSP and text escaping passed');
  } finally {
    Module._load = originalLoad;
    for (const subscription of subscriptions) subscription.dispose();
    await new Promise((resolve) => server.close(resolve));
    const resolved = path.resolve(root);
    assert.equal(path.dirname(resolved), path.resolve(os.tmpdir()));
    fs.rmSync(resolved, { recursive: true, force: true });
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
