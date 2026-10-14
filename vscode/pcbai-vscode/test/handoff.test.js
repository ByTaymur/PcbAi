// KiCad → VS Code handoff (plan AJ-5): id-only URL, single take, project match, outcome reported back.
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

const executed = [];
let answer;
let clipboard = '';
const vscode = {
  Uri: { parse: text => ({ text }), file: fsPath => ({ fsPath }) },
  env: { uriScheme: 'vscode', clipboard: { writeText: async t => { clipboard = t; } }, openExternal: async () => true },
  extensions: { getExtension: () => ({}) },
  commands: { executeCommand: async (...args) => { executed.push(args); } },
  workspace: { workspaceFolders: [{ uri: { fsPath: path.resolve('/work/motor') } }] },
  window: { showWarningMessage: async () => answer, showInformationMessage: () => {}, showErrorMessage: () => {},
    createTerminal: () => ({ show() {} }) },
};
const load = Module._load;
Module._load = function (name, ...args) { return name === 'vscode' ? vscode : load.call(this, name, ...args); };
const handoff = require('../handoff');
const agents = require('../agents');
Module._load = load;

const ID = '0f8fad5b-d9cb-469f-a165-70867728950e';
const samePath = (a, b) => path.resolve(a).toLowerCase() === path.resolve(b).toLowerCase();

function service(project, prompt = 'KiCad istemi: R5 değerini oku') {
  const calls = [];
  let taken = false;
  return { calls, serviceCall: async (urlPath, payload) => {
    calls.push([urlPath, payload]);
    if (urlPath === '/handoff/take') {
      if (taken) return { ok: false, error: { message: 'Bu devir zaten kullanıldı' } };
      taken = true;
      return { ok: true, id: payload.id, project, prompt };
    }
    return { ok: true };
  } };
}

async function main() {
  agents.detect(() => null);
  const state = new Map();
  const context = { globalState: { get: k => state.get(k), update: async (k, v) => { state.set(k, v); } } };

  assert.equal(handoff.handoffId({ path: '/handoff', query: 'id=' + ID }), ID);
  assert.equal(handoff.handoffId({ path: '/handoff', query: 'id=../../x' }), null);
  assert.equal(handoff.handoffId({ path: '/other', query: 'id=' + ID }), null);
  await assert.rejects(handoff.handle({ path: '/handoff', query: 'id=nope' }, {}), /Geçersiz/);

  // Project inside the workspace: delivered to the chosen agent (Claude Code), outcome written back once.
  const inside = service(path.resolve('/work/motor/hw/motor.kicad_pro'));
  const filled = [];
  const how = await handoff.handle({ path: '/handoff', query: 'id=' + ID },
    { ...inside, samePath, context, onPrompt: p => filled.push(p) });
  assert.equal(how, 'typed');
  assert.deepEqual(filled, ['KiCad istemi: R5 değerini oku']);
  assert.ok(executed.some(a => a[0] === 'claude-vscode.editor.open' && a[2] === 'KiCad istemi: R5 değerini oku'));
  const report = inside.calls.find(c => c[0] === '/handoff/report');
  assert.equal(report[1].outcome, 'typed');
  assert.match(report[1].message, /KiCad isteği Claude Code mesaj kutusuna yazıldı/);
  // The same id cannot be used twice.
  await assert.rejects(handoff.handle({ path: '/handoff', query: 'id=' + ID }, { ...inside, samePath, context }), /zaten kullanıldı/);

  // Other project: asks; dismissing declines without delivering.
  executed.length = 0;
  answer = undefined;
  const other = service(path.resolve('/elsewhere/psu.kicad_pro'));
  assert.equal(await handoff.handle({ path: '/handoff', query: 'id=' + ID }, { ...other, samePath, context }), 'declined');
  assert.equal(executed.length, 0);
  assert.equal(other.calls.find(c => c[0] === '/handoff/report')[1].outcome, 'declined');
  // "Klasörü aç" opens the project folder in a new window instead of delivering.
  answer = 'Klasörü aç';
  const open = service(path.resolve('/elsewhere/psu.kicad_pro'));
  assert.equal(await handoff.handle({ path: '/handoff', query: 'id=' + ID }, { ...open, samePath, context }), 'declined');
  assert.equal(executed[0][0], 'vscode.openFolder');
  // "Yine de gönder" delivers; clipboard agent reports clipboard honestly.
  executed.length = 0;
  answer = 'Yine de gönder';
  await agents.choose(context, 'clipboard');
  const anyway = service(path.resolve('/elsewhere/psu.kicad_pro'), 'başka istem');
  assert.equal(await handoff.handle({ path: '/handoff', query: 'id=' + ID }, { ...anyway, samePath, context }), 'clipboard');
  assert.equal(clipboard, 'başka istem');
  assert.equal(anyway.calls.find(c => c[0] === '/handoff/report')[1].outcome, 'clipboard');
  console.log('Handoff: id-only URI, single take, project match/ask/decline/open folder, outcome reported passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
