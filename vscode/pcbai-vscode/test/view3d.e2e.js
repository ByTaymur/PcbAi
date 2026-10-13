// G4 acceptance: actual Chromium (software WebGL = slow GPU) + actual view3d bridge + real service/kicad-cli GLB.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const Module = require('node:module');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');
const { evidencePath } = require('./evidence_output');

const extensionRoot = path.resolve(__dirname, '..');
const root = path.resolve(extensionRoot, '../..');
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-viewer-'));
  const python = process.env.PCBAI_TEST_PYTHON || 'python';
  const backend = spawn(python, [path.join(root, 'scripts/viewer_test_service.py'), tmp, 'ecc83,interf_u,pic_programmer'], {
    cwd: root, shell: false, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'], env: process.env });
  let stderr = ''; backend.stderr.on('data', b => stderr += b);
  const deadline = setTimeout(() => backend.kill(), 360000);
  let browser, server, info, view, page; const subscriptions = [];
  try {
    for (let i = 0; i < 150 && !fs.existsSync(path.join(tmp, 'backend.json')); i++) {
      if (backend.exitCode !== null) throw new Error(stderr); await sleep(100);
    }
    info = JSON.parse(fs.readFileSync(path.join(tmp, 'backend.json')));
    async function request(name, args = {}, route = '/call') {
      const result = await fetch(`http://127.0.0.1:${info.port}${route}`, { method: 'POST',
        headers: { Authorization: 'Bearer ' + info.token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, arguments: args }), signal: AbortSignal.timeout(150000) });
      return result.json();
    }
    async function backgroundJob(tool, session, document) {
      const submitted = await request('start_job', { tool, session: session.id, document, revision: session.revision });
      assert.equal(submitted.ok, true, JSON.stringify(submitted));
      for (let i = 0; i < 1500; i++) {
        const response = await request('job_status', { job_id: submitted.job.job_id });
        if (['completed', 'failed'].includes(response.job.status)) {
          assert.equal(response.job.result.ok, true, JSON.stringify(response.job.result)); return response.job.result;
        }
        await sleep(100);
      }
      throw new Error('Background job timeout');
    }
    const resources = new Map(); let html = '', receive; const posted = [];
    server = http.createServer((req, res) => {
      if (req.url === '/') { res.setHeader('Content-Type', 'text/html'); res.end(html); return; }
      const file = resources.get(req.url);
      if (!file) { res.writeHead(404); res.end(); return; }
      res.setHeader('Content-Type', { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.glb': 'model/gltf-binary' }[path.extname(file)] || 'text/plain');
      res.end(fs.readFileSync(file));
    });
    await new Promise(r => server.listen(0, '127.0.0.1', r));
    const origin = `http://127.0.0.1:${server.address().port}`;
    const uri = p => ({ fsPath: p, toString: () => p });
    const makeUri = resource => {
      const file = resource.fsPath;
      const url = file.startsWith(path.join(extensionRoot, 'media') + path.sep)
        ? '/media/' + path.relative(path.join(extensionRoot, 'media'), file).replaceAll('\\', '/')
        : '/views/' + path.relative(info.state, file).replaceAll('\\', '/');
      resources.set(url, file);
      return { toString: () => origin + url };
    };
    const vscode = { Uri: { file: uri }, ViewColumn: { Beside: 2 }, env: { clipboard: { writeText: async text => { vscode.clipboard = text; } } },
      window: { createWebviewPanel: () => {
        let dispose = () => {};
        return { webview: { cspSource: origin, asWebviewUri: makeUri,
          onDidReceiveMessage: fn => { receive = fn; return { dispose() {} }; },
          postMessage: async message => { posted.push(message); if (page) await page.evaluate(m => window.dispatchEvent(new MessageEvent('message', { data: m })), message); return true; },
          set html(value) { html = value; }, get html() { return html; } },
          onDidDispose: fn => { dispose = fn; }, dispose: () => dispose() };
      } } };
    makeUri(uri(path.join(extensionRoot, 'media', 'vendor', 'three-bundle.js'))); // module-relative import
    const load = Module._load;
    Module._load = function (name, ...args) { return name === 'vscode' ? vscode : load.call(this, name, ...args); };
    let open3d;
    try { ({ open3d } = require('../view3d')); } finally { Module._load = load; }
    browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const errors = [], results = [];
    for (const session of info.sessions) {
      const document = session.project.replace(/\.kicad_pro$/, '.kicad_pcb');
      const original = fs.readFileSync(path.join(session.root, document));
      page = await context.newPage(); page.on('pageerror', e => errors.push(String(e)));
      const consoleLines = []; page.on('console', m => consoleLines.push(m.text()));
      await page.exposeFunction('__send', m => receive(m));
      await page.addInitScript(() => { window.acquireVsCodeApi = () => ({ postMessage: m => window.__send(m), getState: () => null, setState: () => {} }); });
      const started = Date.now();
      view = open3d({ extensionPath: extensionRoot, subscriptions }, { stateDir: info.state, session, document, call: request, backgroundJob });
      await page.goto(origin);
      const loaded = await view.whenLoaded;
      if (!loaded.loaded) console.error('DEBUG', JSON.stringify(posted.map(m => m.type === 'model' ? { type: 'model', uri: m.uri } : m)), consoleLines);
      assert.equal(loaded.loaded, true, JSON.stringify(loaded) + ' ' + await page.locator('#error').textContent());
      const loadMs = Date.now() - started;
      const model = posted.filter(m => m.type === 'model').at(-1);
      await page.evaluate(() => window.pcbaiView3d.view('top'));
      let correct = 0, other = 0, none = 0, covered = 0; const misses = [];
      for (const reference of model.components) {
        const point = await page.evaluate(r => window.pcbaiView3d.screenPoint(r), reference);
        if (!point) { covered++; continue; } // fully hidden under taller parts from this camera
        await page.mouse.click(point.x, point.y);
        const got = await page.evaluate(() => window.pcbaiView3d.selected());
        if (got === reference) correct++; else { if (got) other++; else none++; misses.push([reference, got]); }
      }
      assert.equal(correct, model.components.length - covered, `${session.project}: ${JSON.stringify(misses)}`);
      assert.ok(covered <= model.components.length * 0.3, `${session.project}: ${covered} covered`);
      // Hiding components: the same click no longer selects anything.
      if (model.components.length) {
        const reference = model.components[0];
        const point = await page.evaluate(r => window.pcbaiView3d.screenPoint(r), reference);
        await page.locator('#components').uncheck();
        await page.mouse.click(point.x, point.y);
        assert.equal(await page.evaluate(() => window.pcbaiView3d.selected()), null);
        await page.locator('#components').check();
      }
      for (const name of ['bottom', 'iso']) await page.locator(`[data-view="${name}"]`).click();
      await page.screenshot({ path: evidencePath(root, '.pcbai-state/view3d-e2e/' + path.basename(session.root) + '.png') });
      assert.deepEqual(fs.readFileSync(path.join(session.root, document)), original);
      results.push({ demo: path.basename(session.root), renderer: loaded.renderer, load_ms: loadMs, components: model.components.length,
        without_model: model.without_model.length, clicked_correct: correct, clicked_other: other, clicked_none: none, covered_from_top: covered,
        substitutions: model.substitutions, glb_mb: +(model.bytes / 1e6).toFixed(1), source_unchanged: true });
      view.panel.dispose(); await page.close(); page = null; view = null;
    }
    assert.deepEqual(errors, []);
    const report = evidencePath(root, (process.env.PCBAI_PUBLISH_EVIDENCE === '1' ? 'docs/spikes' : '.pcbai-state') + '/G4-browser-result.json');
    fs.writeFileSync(report, JSON.stringify({ browser: browser.version(), webgl: 'swiftshader (software)', boards: results }, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    if (view) view.panel.dispose(); for (const s of subscriptions) s.dispose();
    if (browser) await browser.close(); if (server) await new Promise(r => server.close(r));
    if (info) await fetch(`http://127.0.0.1:${info.port}/shutdown`, { method: 'POST', headers: { Authorization: 'Bearer ' + info.token }, signal: AbortSignal.timeout(5000) }).catch(() => {});
    if (backend.exitCode === null) { await Promise.race([new Promise(r => backend.on('exit', r)), sleep(5000)]); if (backend.exitCode === null) backend.kill(); }
    clearTimeout(deadline);
    assert.equal(path.dirname(path.resolve(tmp)), path.resolve(os.tmpdir())); fs.rmSync(tmp, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
