const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const tm = require('vscode-textmate');
const onig = require('vscode-oniguruma');
const root = path.join(__dirname, '..');
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
(async () => {
  await onig.loadWASM(fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm')).buffer);
  const raw = read('syntaxes/kicad-dru.tmLanguage.json');
  const registry = new tm.Registry({onigLib: Promise.resolve({createOnigScanner: p => new onig.OnigScanner(p), createOnigString: s => new onig.OnigString(s)}), loadGrammar: async () => raw});
  const grammar = await registry.loadGrammar('source.kicad-dru');
  const scopes = line => grammar.tokenizeLine(line).tokens.map(t => t.scopes.join(' ')).join('\n');
  assert.match(scopes('(rule "demo"'), /keyword.control/);
  assert.match(scopes('  (constraint clearance (min 0.2mm))'), /storage.type.constraint/);
  assert.match(scopes('  (constraint clearance (min 0.2mm))'), /constant.numeric/);
  const condition = scopes(`  (condition "A.NetClass == 'Default' && B.Type != 'Via'")`);
  assert.match(condition, /variable.other.property/);
  assert.match(condition, /keyword.operator.logical/);
  const comment = scopes('# (rule "no") 0.2mm');
  assert.match(comment, /comment.line/);
  assert.doesNotMatch(comment, /keyword.control|constant.numeric/);
  assert.doesNotMatch(scopes('"rule clearance # 0.2mm"'), /keyword.control|comment.line|constant.numeric/);
  const cfg = read('language-configuration/kicad-dru.json');
  assert.ok(new RegExp(cfg.folding.markers.start).test('(rule "example"'));
  assert.ok(new RegExp(cfg.folding.markers.end).test(') # end'));
  const snippets = read('snippets/kicad-dru.json');
  assert.equal(Object.keys(snippets).length, 5);
  for (const snippet of Object.values(snippets)) {
    const text = snippet.body.join('\n').replace(/\$\{\d+:([^}]+)\}/g, '$1').replace(/\$\d+/g, '');
    assert.ok(text.startsWith('(rule '));
    assert.equal([...text].filter(c => c === '(').length, [...text].filter(c => c === ')').length);
  }
  console.log('DRU real TextMate/Oniguruma scopes, folding and 5 snippets passed');
})().catch(e => {console.error(e); process.exitCode = 1;});
