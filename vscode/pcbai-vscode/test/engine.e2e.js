// Real Chromium and engine_view bridge. Fixture backend checks exact immutable apply args and text safety.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const Module = require('node:module');
const { chromium } = require('playwright');
const { evidencePath } = require('./evidence_output');

async function main() {
  const root = path.resolve(__dirname, '../../..');
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-engine-ui-'));
  const viewRoot = path.join(tmp, 'views'); fs.mkdirSync(viewRoot);
  const svg = path.join(viewRoot, 'board.svg');
  fs.writeFileSync(svg, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><rect x="1" y="1" width="18" height="18" fill="#253c32" stroke="#f2cc8f"/></svg>');
  const resources = new Map(); let html = '', receive, page, panel, disposed = false;
  const calls = [];
  const server = http.createServer((req, res) => {
    if (req.url === '/') { res.setHeader('Content-Type', 'text/html'); res.end(html); return; }
    const file = resources.get(req.url);
    if (!file) { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' }[path.extname(file)]);
    res.end(fs.readFileSync(file));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const vscode = { ViewColumn: { Beside: 2 }, Uri: { file: fsPath => ({ fsPath }) }, window: {
    createWebviewPanel: () => panel = { webview: { cspSource: origin,
      asWebviewUri: uri => { const route = '/resource/' + resources.size; resources.set(route, uri.fsPath); return { toString: () => origin + route }; },
      set html(value) { html = value; }, postMessage: message => page.evaluate(m => window.dispatchEvent(new MessageEvent('message', { data: m })), message),
      onDidReceiveMessage: fn => { receive = fn; return { dispose() {} }; } },
      onDidDispose: fn => { panel.didDispose = fn; }, dispose: () => { disposed = true; panel.didDispose?.(); } }
  } };
  const originalLoad = Module._load;
  Module._load = function (name, ...args) { return name === 'vscode' ? vscode : originalLoad.call(this, name, ...args); };
  let browser;
  try {
    const { openEngineView } = require('../engine_view');
    const target = { session: 's-fixture', document: 'Test.kicad_pcb', revision: 'a'.repeat(64) };
    const preview = { target, candidate_id: 'candidate-fixture', summary: '<script>window.BAD=1</script>',
      blockers: [], preview_evidence_id: 'ev-fixture', engine_run: { seconds: 1 },
      diagnostic_markers: [{ points_mm: [[5, 10]], note: '<script>window.BAD=2</script>' }],
      drc_before: { errors: 14 }, drc_after: { errors: 0 }, engine_metrics: {
        before: { via_count: 0, length_mm: 0 }, after: { via_count: 2, length_mm: 22 },
        moved_count: 0, unconnected_before: 14, unconnected_after: 0 } };
    const render = { bbox: [0, 0, 20, 20], viewbox: [0, 0, 20, 20], mm_to_svg: [1, 0, 0, 1, 0, 0],
      layers: [{ name: 'F.Cu', path: svg }] };
    openEngineView({ extensionPath: path.resolve(__dirname, '..'), subscriptions: [] }, { stateDir: tmp, tool: 'autoroute', preview,
      call: async (name, args) => { calls.push({ name, args });
        if (name === 'engine_preview') return { ok: true, before: render, after: render };
        if (name === 'autoroute') return { ok: true, summary: 'Applied', checkpoint: { id: 'cp-fixture' }, change_id: 'ev-change' };
        if (name === 'discard_candidate') return { ok: true };
        throw new Error('Unexpected call: ' + name);
      } });
    browser = await chromium.launch({ headless: true }); page = await browser.newPage({ viewport: { width: 1100, height: 800 } });
    await page.exposeFunction('hostMessage', m => receive(m));
    await page.addInitScript(() => { window.acquireVsCodeApi = () => ({ postMessage: m => window.hostMessage(m) }); });
    await page.goto(origin);
    await page.waitForFunction(() => document.querySelectorAll('#metrics tr').length === 5);
    assert.equal(await page.evaluate(() => window.BAD), undefined);
    assert.equal(await page.locator('#before img').count(), 1);
    assert.equal(await page.locator('#after img').count(), 1);
    assert.equal(await page.locator('#after .diagnostic').evaluate(el => el.style.left), '25%');
    assert.equal(await page.locator('#after .diagnostic').evaluate(el => el.style.top), '50%');
    await receive({ type: 'apply', candidate_id: 'other', revision: 'b'.repeat(64) });
    assert.equal(calls.filter(c => c.name === 'autoroute').length, 0);
    await page.screenshot({ path: evidencePath(root, '.pcbai-state/engine-ui-preview.png') });
    await page.locator('#apply').click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Applied');
    assert.deepEqual(calls.find(c => c.name === 'autoroute').args, { ...target, mode: 'apply', candidate_id: preview.candidate_id });
    assert.equal(await page.locator('#apply').isDisabled(), true);
    // A blocked candidate must never reach the mutating tool even if the webview sends an apply message.
    preview.blockers = ['outside_board'];
    disposed = false;
    openEngineView({ extensionPath: path.resolve(__dirname, '..'), subscriptions: [] }, { stateDir: tmp, tool: 'autoroute', preview,
      call: async (name, args) => { calls.push({ name, args }); return { ok: true, before: render, after: render }; } });
    await page.goto(origin); await page.waitForFunction(() => document.querySelectorAll('#metrics tr').length === 5);
    await receive({ type: 'apply' });
    assert.equal(calls.filter(c => c.name === 'autoroute').length, 1);
    await page.locator('#cancel').click(); await page.waitForTimeout(100); assert.equal(disposed, true);
    fs.writeFileSync(evidencePath(root, '.pcbai-state/engine-ui-result.json'), JSON.stringify({
      real_chromium: true, backend: 'fixture', side_by_side: true, measurements: true, exact_candidate_applied: true,
      blocked_apply_rejected: true, forged_target_rejected: true, html_data_not_executed: true }, null, 2));
    console.log('Engine UI: real Chromium preview, measurements, exact candidate apply, blockers and text safety passed');
  } finally {
    Module._load = originalLoad;
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
