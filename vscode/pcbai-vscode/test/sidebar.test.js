// Side bar: request + chosen markers → one prompt opened in a new Claude Code tab (clipboard fallback).
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

const executed = [];
let clipboard = '';
let provider;
const vscode = {
  Uri: { file: p => ({ fsPath: p, toString: () => p }) },
  window: { registerWebviewViewProvider: (_id, p) => { provider = p; return { dispose() {} }; } },
  commands: { executeCommand: async (...args) => { executed.push(args); if (args[0] === 'claude-vscode.editor.open' && global.failOpen) throw new Error('no'); } },
  env: { clipboard: { writeText: async text => { clipboard = text; } } },
};
const load = Module._load;
Module._load = function (name, ...args) { return name === 'vscode' ? vscode : load.call(this, name, ...args); };
const { registerSidebar, composePrompt } = require('../sidebar_view');
Module._load = load;

async function main() {
  const session = { id: 's-1', project: 'BLDC.kicad_pro', root: 'C:/p' };
  const markers = [
    { n: 1, status: 'open', trusted: true, space: 'pcb', document: 'BLDC.kicad_pcb', note: 'bu hat 1 mm olsun',
      target_item: { type: 'track', net: 'VBUS' }, layer: 'F.Cu' },
    { n: 2, status: 'open', trusted: false, space: 'sch', document: 'power.kicad_sch', sheet: '/r/s', note: '<script>x</script> 4,7k',
      target_item: { type: 'symbol', reference: 'R5', value: '10k' } },
    { n: 3, status: 'done', trusted: true, space: 'pcb', document: 'BLDC.kicad_pcb', note: 'eski' },
  ];
  const posted = [];
  registerSidebar({ extensionPath: path.resolve(__dirname, '..'), subscriptions: [] }, {
    sessionFor: async () => session,
    call: async name => (name === 'get_markers' ? { ok: true, markers } : { ok: false }),
  });
  const view = { visible: true, onDidChangeVisibility() {}, webview: {
    cspSource: 'vscode-webview:', asWebviewUri: u => u, set html(v) { this._html = v; }, get html() { return this._html; },
    onDidReceiveMessage: fn => { view.receive = fn; }, postMessage: async m => { posted.push(m); return true; } } };
  provider.resolveWebviewView(view);
  assert.ok(view.webview.html.includes("script-src 'nonce-"));
  await view.receive({ type: 'ready' });
  const state = posted.find(m => m.type === 'state');
  assert.equal(state.markers.length, 3);
  assert.deepEqual(state.markers.map(m => m.open), [true, true, false]);
  await view.receive({ type: 'open', request: 'MOSFET bakırını büyüt', markers: [1, 2] });
  const [command, sessionId, prompt] = executed.find(a => a[0] === 'claude-vscode.editor.open');
  assert.equal(command, 'claude-vscode.editor.open');
  assert.equal(sessionId, undefined);
  assert.ok(prompt.includes('MOSFET bakırını büyüt'));
  assert.ok(prompt.includes('#1 [kart · BLDC.kicad_pcb · track net VBUS]: "bu hat 1 mm olsun"'));
  assert.ok(prompt.includes('#2 [şematik · power.kicad_sch · /r/s · symbol R5 10k] (onaysız): "<script>x</script> 4,7k"'));
  assert.ok(!prompt.includes('eski'));
  assert.ok(prompt.includes('update_marker_status'));
  global.failOpen = true;
  await view.receive({ type: 'open', request: '', markers: [1] });
  assert.ok(clipboard.includes('bu hat 1 mm olsun'));
  posted.length = 0;
  await view.receive({ type: 'open', request: '   ', markers: [] });
  assert.ok(posted.some(m => m.type === 'error'));
  assert.ok(composePrompt(session, 'x', [], {}).startsWith('PcbAi projesi: BLDC.kicad_pro'));
  console.log('Sidebar: prompt from request + chosen markers, Claude Code tab, clipboard fallback passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
