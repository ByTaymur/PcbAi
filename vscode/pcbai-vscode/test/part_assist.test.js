const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-assist-unit-'));
const project = path.join(temporary, 'project');
fs.mkdirSync(project);
const {parseBuffer, contextAt, createAssist} = require('../part_assist');
const sha = 'a'.repeat(64);
const fixture = (symbol = 'Device:R', pin = 'R1.') => JSON.stringify({ir_version: 1, parts: [{id: 'R1', symbol, unit: 1}], connections: [[pin, '@GND']]});
const location = (text, value) => text.indexOf(JSON.stringify(value)) + JSON.stringify(value).length - 1;
const doc = text => ({version: 1, text, uri: {fsPath: path.join(project, 'test.pcbai-ir.json'), toString: () => 'file:///project/test.pcbai-ir.json'},
  getText() {return this.text;}, offsetAt: n => n, positionAt: n => n});
class MarkdownString {constructor() {this.value = '';} appendText(text) {this.value += text; return this;}}
const vscode = {MarkdownString, Hover: class {constructor(contents) {this.contents = contents;}},
  CompletionItem: class {constructor(label) {this.label = label;}}, CompletionItemKind: {Value: 1},
  Range: class {constructor(start, end) {this.start = start; this.end = end;}}};
const session = {id: 'session-one', root: project, revision: 'rev-one'};
const info = {lib_id: 'Device:R', source: 'kicad', path: 'C:/lib/Device.kicad_sym', library_sha256: sha,
  properties: {Description: '<script>evil</script> [run](command:evil)', Footprint: 'Test:R'},
  pins: [{number: '01', name: 'first', unit: 1}, {number: '1', name: 'common', unit: 0}, {number: '2', name: 'other unit', unit: 2}]};

(async () => {
  let text = fixture();
  assert.equal(contextAt(text, location(text, 'Device:R')).kind, 'symbol');
  assert.equal(contextAt(text, location(text, 'R1.')).kind, 'pin');
  const partial = '{"parts":[{"id":"R1","symbol":"Dev';
  assert.equal(contextAt(partial, partial.length).prefix, 'Dev');
  assert.equal(contextAt('{"note":"\\\"symbol\\\":\\\"Device:R\\\""}', 10), null);
  assert.equal(parseBuffer('{"parts":[],"parts":[]}'), null);
  assert.equal(parseBuffer('{"parts":[],}'), null);
  assert.equal(parseBuffer('{/*comment*/"parts":[]}'), null);
  assert.equal(parseBuffer('x'.repeat(1024 * 1024 + 1)), null);
  assert.equal(parseBuffer('{"note":' + '['.repeat(20) + '1' + ']'.repeat(20) + '}'), null);
  assert.equal(parseBuffer('{"note":"' + 'x'.repeat(4097) + '"}'), null);
  assert.equal(parseBuffer('{"note":"\\ud800"}'), null);
  assert.ok(parseBuffer('{"note":"\\ud83d\\ude00"}'));
  assert.ok(parseBuffer('{"__proto__":{"polluted":true}}'));
  assert.equal({}.polluted, undefined);
  let library = info, calls = [], current = {...session};
  const options = {sessionFor: async () => current, call: async (name, args) => {
    calls.push([name, args]);
    if (name === 'search_parts') return {ok: true, parts: [{lib_id: 'Device:R', description: 'Resistor', library_sha256: sha}]};
    return {ok: true, part: args.kind === 'footprint' ? {lib_id: 'Test:R', sha256: sha, source: 'kicad', pads: []} : library};
  }};
  const assist = createAssist(vscode, options);
  const document = doc(text);
  let items = await assist.completions(document, location(text, 'R1.'));
  assert.deepEqual(items.map(p => p.label).sort(), ['R1.01', 'R1.1']);
  assert.equal(items[0].insertText, 'R1.01');
  assert.equal(items[0].range.start, text.indexOf('R1.') );
  text = fixture('Wrong:R', 'R1.99'); document.text = text; document.version++;
  items = await assist.completions(document, location(text, 'R1.99'));
  assert.equal(items.length, 2, 'Wrong pin has literal local alternatives');
  assert.ok(items.every(item => item.filterText.startsWith('R1.99')));
  items = await assist.completions(document, location(text, 'Wrong:R'));
  assert.equal(items[0].label, 'Device:R', 'Wrong library has real local alternative');
  text = fixture(); document.text = text; document.version++;
  const hover = await assist.hover(document, location(text, 'Device:R'));
  assert.equal(hover.contents.isTrusted, false); assert.equal(hover.contents.supportHtml, false);
  assert.match(hover.contents.value, /command:evil/); // Raw data goes ONLY through appendText.
  assert.match(hover.contents.value, /SHA-256/);
  library = {...info, library_sha256: 'b'.repeat(64), properties: {Description: 'Changed library'}};
  assert.match((await assist.hover(document, location(text, 'Device:R'))).contents.value, /Changed library/);
  assert.ok(calls.filter(c => c[0] === 'part_info').length >= 4, 'Cache never bypasses fresh SHA reads');
  assert.deepEqual(await assist.completions(document, location(text, 'R1.'), {isCancellationRequested: true}), []);
  const changing = createAssist(vscode, {...options, call: async () => {document.version++; return {ok: true, part: info};}});
  assert.deepEqual(await changing.completions(document, location(text, 'R1.')), []);
  const switching = createAssist(vscode, {...options, call: async () => {current = {...session, id: 'session-two'}; return {ok: true, part: info};}});
  assert.equal(await switching.hover(document, location(text, 'Device:R')), undefined);
  current = {...session, root: 'C:/elsewhere'};
  assert.deepEqual(await assist.completions(document, location(text, 'R1.')), []);
  current = {...session};
  const outside = path.join(temporary, 'outside'); fs.mkdirSync(outside);
  const junction = path.join(project, 'escape');
  fs.symlinkSync(outside, junction, process.platform === 'win32' ? 'junction' : 'dir');
  const escaped = doc(text); escaped.uri.fsPath = path.join(junction, 'test.pcbai-ir.json');
  const before = calls.length;
  assert.deepEqual(await assist.completions(escaped, location(text, 'R1.')), []);
  assert.equal(calls.length, before, 'Junction escape cannot trigger library access');
  const dangling = path.join(project, 'dangling');
  fs.symlinkSync(path.join(temporary, 'not-yet-existing'), dangling, process.platform === 'win32' ? 'junction' : 'dir');
  escaped.uri.fsPath = path.join(dangling, 'new.pcbai-ir.json');
  assert.deepEqual(await assist.completions(escaped, location(text, 'R1.')), []);
  assert.equal(calls.length, before, 'Dangling junction cannot establish a project scope');
  console.log('IR bounds/context, literal pins/units, safe hover, fresh SHA and stale buffer/session fences passed');
})().catch(error => {console.error(error); process.exitCode = 1;}).finally(() => {
  assert.ok(path.resolve(temporary).startsWith(path.resolve(os.tmpdir()) + path.sep));
  fs.rmSync(temporary, {recursive: true, force: true});
});
