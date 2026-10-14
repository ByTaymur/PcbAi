// Side bar: request + chosen markers → one prompt delivered to the chosen agent (clipboard fallback).
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

const executed = [];
const warnings = [];
const viewCalls = [];
let viewFail = null;
let clipboard = '';
let provider;
const vscode = {
  Uri: { file: p => ({ fsPath: p, toString: () => p }) },
  window: { registerWebviewViewProvider: (_id, p) => { provider = p; return { dispose() {} }; },
    showWarningMessage: async (...args) => { warnings.push(args); return global.confirm; } },
  commands: { executeCommand: async (...args) => { executed.push(args); if (args[0] === 'claude-vscode.editor.open' && global.failOpen) throw new Error('no'); } },
  env: { clipboard: { writeText: async text => { clipboard = text; } } },
  extensions: { getExtension: id => (id === 'anthropic.claude-code' ? {} : undefined) },
};
const state = new Map();
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
  const eventCalls = [];
  const serviceEvents = [
    { seq: 1, time: 0, client: 'mcp:claude-code', tool: 'set_value', outcome: 'ok', change_id: 'c1' },
    { seq: 2, time: 0, client: 'builtin', tool: 'move_footprint', outcome: 'blocked', change_id: null },
  ];
  const mcpHome = require('node:fs').mkdtempSync(path.join(require('node:os').tmpdir(), 'pcbai-side-'));
  registerSidebar({ extensionPath: path.resolve(__dirname, '..'), subscriptions: [],
    globalState: { get: k => state.get(k), update: async (k, v) => { state.set(k, v); } } }, {
    sessionFor: async () => session,
    call: async name => (name === 'get_markers' ? { ok: true, markers, revision: 'r1', markers_revision: 'm1' } : { ok: false }),
    viewCall: async (name, args) => {
      viewCalls.push([name, args]);
      if (viewFail && viewFail(name, args)) return { ok: false, summary: 'Markers changed', error: { code: 'stale_markers' } };
      return args.mode === 'preview' ? { ok: true, candidate_id: 'c-' + args.n, markers_revision: args.markers_revision }
        : { ok: true, markers_revision: 'm2' };
    },
    mcpContext: () => ({ userDir: mcpHome, home: mcpHome, workspace: null }),
    events: async since => { eventCalls.push(since); return since == null ? serviceEvents : serviceEvents.filter(e => e.seq > since); },
  });
  const view = { visible: true, onDidChangeVisibility() {}, webview: {
    cspSource: 'vscode-webview:', asWebviewUri: u => u, set html(v) { this._html = v; }, get html() { return this._html; },
    onDidReceiveMessage: fn => { view.receive = fn; }, postMessage: async m => { posted.push(m); return true; } } };
  provider.resolveWebviewView(view);
  assert.ok(view.webview.html.includes("script-src 'nonce-"));
  await view.receive({ type: 'ready' });
  const loaded = posted.find(m => m.type === 'state');
  assert.equal(loaded.markers.length, 3);
  assert.deepEqual(loaded.markers.map(m => m.open), [true, true, false]);
  const list = posted.find(m => m.type === 'agents');
  assert.equal(list.selected, 'claude-code');
  assert.equal(list.items.length, 9);
  assert.deepEqual(list.items.filter(a => a.available).map(a => a.id), ['claude-code', 'clipboard']);
  assert.ok(list.items.every(a => !('cliPath' in a)));
  assert.ok(view.webview.html.includes('<select id="agent">'));
  assert.match(list.mcpMissing, /Claude Code.*MCP kaydı yok/);
  // Agent activity (AJ-7): only new events are fetched; blocked writes carry the close-the-editor hint.
  await provider.pollEvents();
  const shown = posted.filter(m => m.type === 'events').pop().items;
  assert.deepEqual(shown.map(e => e.outcome), ['ok', 'blocked']);
  assert.match(shown[0].text, /mcp:claude-code {2}set_value {2}ok · c1/);
  assert.match(shown[0].hint, /Geri al \(Revert\)/);
  assert.match(shown[1].hint, /editörünü kapatın/);
  await provider.pollEvents();
  assert.deepEqual(eventCalls, [null, 2]);
  assert.ok(view.webview.html.includes('id="activity"'));
  assert.ok(view.webview.html.includes('data-command="pcbai.connectAgents"'));
  await view.receive({ type: 'open', request: 'MOSFET bakırını büyüt', markers: [1, 2] });
  const [command, sessionId, prompt] = executed.find(a => a[0] === 'claude-vscode.editor.open');
  assert.equal(command, 'claude-vscode.editor.open');
  assert.equal(sessionId, undefined);
  assert.ok(prompt.includes('MOSFET bakırını büyüt'));
  assert.ok(prompt.includes('#1 [kart · BLDC.kicad_pcb · track net VBUS]: "bu hat 1 mm olsun"'));
  assert.ok(prompt.includes('#2 [şematik · power.kicad_sch · /r/s · symbol R5 10k] (onaysız): "<script>x</script> 4,7k"'));
  assert.ok(!prompt.includes('eski'));
  assert.ok(prompt.includes('update_marker_status'));
  assert.ok(posted.some(m => m.type === 'notice' && m.message.includes('Claude Code mesaj kutusuna yazıldı')));
  posted.length = 0;
  await view.receive({ type: 'agent', id: 'codex' });
  assert.ok(posted.some(m => m.type === 'error' && m.message.includes('kurulu değil')));
  assert.equal(state.get('pcbai.agent'), undefined);
  await view.receive({ type: 'agent', id: 'clipboard' });
  assert.equal(state.get('pcbai.agent'), 'clipboard');
  assert.equal(posted.filter(m => m.type === 'agents').pop().mcpMissing, null);
  executed.length = 0;
  await view.receive({ type: 'open', request: '', markers: [1] });
  assert.ok(clipboard.includes('bu hat 1 mm olsun'));
  assert.equal(executed.length, 0);
  assert.ok(posted.some(m => m.type === 'notice' && m.message.includes('panoya kopyalandı')));
  posted.length = 0;
  await view.receive({ type: 'open', request: '   ', markers: [] });
  assert.ok(posted.some(m => m.type === 'error'));
  assert.ok(composePrompt(session, 'x', [], {}).startsWith('PcbAi projesi: BLDC.kicad_pro'));
  // IP-2: done toggles through the user-only view tool (preview, apply) and refreshes the list.
  assert.ok(view.webview.html.includes('id="hide-done"') && view.webview.html.includes('id="delete-done"'));
  posted.length = 0;
  await view.receive({ type: 'markerStatus', n: 1 });
  assert.deepEqual(viewCalls.map(([n, a]) => [n, a.mode, a.status, a.candidate_id]),
    [['set_marker_status', 'preview', 'done', undefined], ['set_marker_status', 'apply', undefined, 'c-1']]);
  assert.deepEqual(viewCalls[0][1], { session: 's-1', document: 'BLDC.kicad_pcb', revision: 'r1', markers_revision: 'm1', mode: 'preview', n: 1, status: 'done' });
  assert.ok(posted.some(m => m.type === 'state') && posted.some(m => m.type === 'notice' && m.message.includes('#1 bitti')));
  viewCalls.length = 0;
  await view.receive({ type: 'markerStatus', n: 3 });
  assert.equal(viewCalls[0][1].status, 'open');
  const shownDone = posted.filter(m => m.type === 'state').pop().markers.find(m => m.n === 3);
  assert.equal(shownDone.open, false);
  // Delete asks first; a refusal makes no service call.
  viewCalls.length = 0; global.confirm = undefined;
  await view.receive({ type: 'markerDelete', n: 2 });
  assert.match(warnings.pop()[0], /#2 silinsin mi\? Kontrol noktası/);
  assert.equal(viewCalls.length, 0);
  global.confirm = 'Sil';
  await view.receive({ type: 'markerDelete', n: 2 });
  assert.deepEqual(viewCalls.map(([n, a]) => [n, a.mode, a.document]), [['delete_marker', 'preview', 'power.kicad_sch'], ['delete_marker', 'apply', 'power.kicad_sch']]);
  // Another client changed markers: refresh and say so, never repeat the edit.
  viewCalls.length = 0; posted.length = 0; viewFail = () => true;
  await view.receive({ type: 'markerStatus', n: 1 });
  assert.equal(viewCalls.length, 1);
  assert.ok(posted.some(m => m.type === 'state'));
  assert.ok(posted.some(m => m.type === 'error' && m.message.includes('İşaretler değişti, yenilendi')));
  // "Bitenleri sil" stops at the first failure and reports how many were deleted.
  markers.push({ n: 4, status: 'done', trusted: true, space: 'pcb', document: 'BLDC.kicad_pcb', note: 'x' });
  await view.receive({ type: 'reload' });
  viewCalls.length = 0; posted.length = 0; viewFail = (name, args) => args.candidate_id === 'c-4';
  await view.receive({ type: 'deleteDone' });
  assert.match(warnings.pop()[0], /Biten 2 işaret/);
  assert.deepEqual(viewCalls.map(([, a]) => a.n || a.candidate_id), [3, 'c-3', 4, 'c-4']);
  assert.ok(posted.some(m => m.type === 'error' && m.message.startsWith('1/2 işaret silindi; #4 silinemedi')));
  viewFail = null;
  await view.receive({ type: 'markerStatus', n: 'x' });
  // Webview script draws notes with textContent and disables the prompt box on done rows.
  const script = require('node:fs').readFileSync(path.resolve(__dirname, '../media/sidebar.js'), 'utf8');
  assert.ok(!script.includes('innerHTML'));
  assert.match(script, /box\.disabled = done/);
  console.log('Sidebar: prompt from request + chosen markers, agent picker, Claude Code input, clipboard agent passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
