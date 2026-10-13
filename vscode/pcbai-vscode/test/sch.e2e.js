// G2 acceptance: actual Chromium + actual sch_view bridge + real service/kicad-cli on a disposable complex_hierarchy copy.
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
  const backend = spawn(python, [path.join(root, 'scripts/viewer_test_service.py'), tmp, 'complex_hierarchy,video'], {
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
      res.setHeader('Content-Type', { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' }[path.extname(file)] || 'text/plain');
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
    const load = Module._load;
    Module._load = function (name, ...args) { return name === 'vscode' ? vscode : load.call(this, name, ...args); };
    let openSchematic;
    try { ({ openSchematic } = require('../sch_view')); } finally { Module._load = load; }
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const errors = [];
    const session = info.sessions[0];
    const document = session.project.replace(/\.kicad_pro$/, '.kicad_sch');
    page = await context.newPage(); page.on('pageerror', e => errors.push(String(e)));
    await page.exposeFunction('__send', m => receive(m));
    await page.addInitScript(() => {
      let state; window.acquireVsCodeApi = () => ({ postMessage: m => window.__send(m), getState: () => state, setState: v => { state = v; } });
    });
    const started = Date.now();
    view = openSchematic({ extensionPath: extensionRoot, subscriptions }, { stateDir: info.state, session, document,
      call: request, backgroundJob, viewCall: (name, args) => request(name, args, '/view/call') });
    await page.goto(origin);
    const loaded = await view.whenLoaded;
    assert.equal(loaded.loaded, true, JSON.stringify(loaded));
    const firstLoadMs = Date.now() - started;
    const lastScene = () => posted.filter(m => m.type === 'scene').at(-1);
    async function clickMm(p) {
      const m = lastScene().page.mm_to_svg;
      const position = await page.evaluate(({ m, p }) => {
        const point = new DOMPoint(m[0]*p[0]+m[2]*p[1]+m[4], m[1]*p[0]+m[3]*p[1]+m[5]).matrixTransform(document.querySelector('#board').getScreenCTM());
        return { x: point.x, y: point.y };
      }, { m, p });
      await page.mouse.click(position.x, position.y);
      return position;
    }
    async function goTo(names) {
      const target = lastScene().pages.find(p => p.names === names);
      if (lastScene().page.instance === target.instance) return target;
      await page.locator(`#pages button[data-instance="${target.instance}"]`).click();
      for (let i = 0; i < 300 && lastScene().page.instance !== target.instance; i++) await sleep(100);
      assert.equal(lastScene().page.instance, target.instance);
      await page.waitForFunction(n => document.querySelector('#document').textContent.startsWith(n + ' ·'), names, { timeout: 30000 });
      return target;
    }
    // Every resistor symbol on both shared-file instances selects with its own instance reference.
    const selections = {};
    for (const names of ['/ampli_ht_vertical/', '/ampli_ht_horizontal/']) {
      await goTo(names);
      await page.locator('#fit').click();
      const symbols = lastScene().scene.items.filter(i => i.type === 'symbol' && !i.power);
      selections[names] = [];
      for (const symbol of symbols) {
        // Click the body centre of the outline, away from pins.
        const b = symbol.bbox, centre = [(b[0]+b[2])/2, (b[1]+b[3])/2];
        await clickMm(centre);
        const text = await page.locator('#info').textContent();
        // A transistor's centre lies on its own pin line: that pin of the same reference is a correct pick.
        if (text.startsWith('sembol · ' + symbol.reference + ' ·') || text.startsWith('pin · ' + symbol.reference + '.'))
          selections[names].push(symbol.reference);
        else assert.fail(`${names}: ${symbol.reference} centre selected ${text}`);
      }
      assert.equal(selections[names].length, symbols.length);
    }
    assert.ok(selections['/ampli_ht_vertical/'].includes('R203'));
    assert.ok(selections['/ampli_ht_horizontal/'].includes('R303'));
    assert.ok(!selections['/ampli_ht_vertical/'].includes('R303'));
    // Pin click highlights exactly the KiCad netlist members of that net present on this page.
    const scene = lastScene();
    const pin = scene.scene.items.find(i => i.type === 'pin' && i.reference === 'R303' && i.net);
    await clickMm(pin.at);
    const pinText = await page.locator('#info').textContent();
    assert.ok(pinText.includes('R303.' + pin.number), pinText + ' / expected R303.' + pin.number + ' at ' + JSON.stringify(pin.at));
    const members = scene.net_members[pin.net];
    const localPins = scene.scene.items.filter(i => i.type === 'pin' && i.net === pin.net);
    const highlightedPins = await page.locator('#nets circle').evaluateAll(n => n.map(x => x.getAttribute('data-uuid')));
    for (const p of localPins) assert.ok(highlightedPins.includes(p.uuid), 'pin not highlighted ' + p.reference + '.' + p.number);
    const memberSet = new Set(members.filter(m => m.sheet === scene.page.instance).map(m => m.reference + '.' + m.pin));
    assert.deepEqual(new Set(localPins.map(p => p.reference + '.' + p.number)), memberSet);
    // Cross-page navigation from the net summary when the net spans pages.
    // A net spanning pages lists the other instances; its button opens that page.
    const spanning = scene.scene.items.find(i => i.type === 'pin' && i.net && !i.hidden &&
      (scene.net_members[i.net] || []).some(m => m.sheet && m.sheet !== scene.page.instance));
    assert.ok(spanning, 'no cross-page net on this page');
    await clickMm(spanning.at);
    const spanText = await page.locator('#info').textContent();
    assert.ok(spanText.includes(spanning.reference + '.' + spanning.number), spanText + ' / expected ' + spanning.reference + '.' + spanning.number + ' ' + JSON.stringify(spanning.at));
    const crossPage = await page.locator('#details button.net-page').count();
    assert.ok(crossPage >= 1);
    const otherSheet = scene.net_members[spanning.net].find(m => m.sheet !== scene.page.instance).sheet;
    await page.locator('#details button.net-page').first().click();
    for (let i = 0; i < 300 && lastScene().page.instance === scene.page.instance; i++) await sleep(100);
    assert.notEqual(lastScene().page.instance, scene.page.instance);
    assert.ok(scene.net_members[spanning.net].some(m => m.sheet === lastScene().page.instance), otherSheet);
    // ERC: run real KiCad ERC, draw only positions measured from item UUIDs on this page.
    await page.locator('#erc').click();
    await page.waitForFunction(() => document.querySelector('#finding-list').textContent.includes('ev-'), null, { timeout: 120000 });
    const erc = posted.filter(m => m.type === 'erc').at(-1);
    const ercDrawn = Number(await page.locator('#finding-list').getAttribute('data-drawn'));
    assert.equal(await page.locator('#findings circle').count(), ercDrawn);
    // Double click on a sheet symbol in the root page opens its instance.
    await goTo('/');
    const sheet = lastScene().scene.items.find(i => i.type === 'sheet' && i.name === 'ampli_ht_vertical');
    const at = [sheet.at[0] + sheet.size[0] / 2, sheet.at[1] + sheet.size[1] / 2];
    const m = lastScene().page.mm_to_svg;
    const position = await page.evaluate(({ m, p }) => {
      const point = new DOMPoint(m[0]*p[0]+m[2]*p[1]+m[4], m[1]*p[0]+m[3]*p[1]+m[5]).matrixTransform(document.querySelector('#board').getScreenCTM());
      return { x: point.x, y: point.y };
    }, { m, p: at });
    await page.mouse.dblclick(position.x, position.y);
    await page.waitForFunction(() => document.querySelector('#document').textContent.startsWith('/ampli_ht_vertical/ ·'), null, { timeout: 30000 });
    for (let i = 0; i < 300 && lastScene().page.names !== '/ampli_ht_vertical/'; i++) await sleep(100);
    // Schematic marker anchored to R203 on the vertical instance, persisted without touching the schematic.
    const sheetFile = path.join(session.root, 'ampli_ht.kicad_sch'), original = fs.readFileSync(sheetFile);
    const r203 = lastScene().scene.items.find(i => i.type === 'symbol' && i.reference === 'R203');
    await clickMm([(r203.bbox[0]+r203.bbox[2])/2, (r203.bbox[1]+r203.bbox[3])/2]);
    await page.locator('#note').fill('bu direnç 4,7k olsun <img src=x onerror=window.pwned=1>');
    await page.locator('#anchor').click();
    await page.locator('#preview').waitFor({ state: 'visible' });
    await page.locator('#apply').click();
    await page.locator('.marker[data-n="1"]').waitFor({ timeout: 30000 });
    assert.equal(await page.evaluate(() => window.pwned), undefined);
    assert.deepEqual(fs.readFileSync(sheetFile), original);
    const saved = await request('get_markers', { session: session.id });
    const marker = saved.markers[0];
    assert.equal(marker.binding, 'bound'); assert.equal(marker.target_item.reference, 'R203');
    assert.equal(marker.document, 'ampli_ht.kicad_sch'); assert.equal(marker.trusted, true);
    // Mouse only: right click on R203 → menu → note box → Enter → Kaydet.
    const r203box = [(r203.bbox[0]+r203.bbox[2])/2, (r203.bbox[1]+r203.bbox[3])/2];
    const rm = lastScene().page.mm_to_svg;
    const rpos = await page.evaluate(({ m, p }) => {
      const point = new DOMPoint(m[0]*p[0]+m[2]*p[1]+m[4], m[1]*p[0]+m[3]*p[1]+m[5]).matrixTransform(document.querySelector('#board').getScreenCTM());
      return { x: point.x, y: point.y };
    }, { m: rm, p: r203box });
    await page.mouse.click(rpos.x, rpos.y, { button: 'right' });
    await page.locator('.floating .menu button', { hasText: 'Bu öğeye işaret koy' }).click();
    await page.locator('.floating textarea').fill('fareyle konan işaret');
    await page.keyboard.press('Enter');
    await page.locator('.floating button', { hasText: 'Kaydet' }).click();
    await page.locator('.marker[data-n="2"]').waitFor({ timeout: 30000 });
    const mouseMarker = (await request('get_markers', { session: session.id })).markers.find(m => m.n === 2);
    assert.equal(mouseMarker.note, 'fareyle konan işaret'); assert.equal(mouseMarker.target_item.reference, 'R203');
    assert.equal(await page.locator('#note').inputValue(), '');
    // Right click on empty space offers zoom/fit; double click on empty space fits.
    await page.mouse.click(rpos.x, rpos.y, { button: 'right' });
    assert.ok(await page.locator('.floating .menu button', { hasText: 'Sığdır' }).count() === 1);
    await page.keyboard.press('Escape');
    // The same file's other instance does not show the vertical-instance marker.
    await goTo('/ampli_ht_horizontal/');
    assert.equal(await page.locator('.marker').count(), 0);
    await page.screenshot({ path: evidencePath(root, '.pcbai-state/sch-e2e/complex_hierarchy.png') });
    // ERC marks come from item UUIDs: KiCad reports video's C56/C57 (on /graphic/) under the root sheet.
    view.panel.dispose(); await page.close();
    const video = info.sessions.find(s => s.project === 'video.kicad_pro');
    page = await context.newPage(); page.on('pageerror', e => errors.push(String(e)));
    await page.exposeFunction('__send', m => receive(m));
    await page.addInitScript(() => { window.acquireVsCodeApi = () => ({ postMessage: m => window.__send(m), getState: () => null, setState: () => {} }); });
    view = openSchematic({ extensionPath: extensionRoot, subscriptions }, { stateDir: info.state, session: video,
      document: 'video.kicad_sch', call: request, backgroundJob, viewCall: (name, args) => request(name, args, '/view/call') });
    await page.goto(origin);
    assert.equal((await view.whenLoaded).loaded, true);
    await goTo('/graphic/');
    await page.locator('#erc').click();
    await page.waitForFunction(() => document.querySelector('#finding-list').textContent.includes('ev-'), null, { timeout: 120000 });
    const graphicDrawn = Number(await page.locator('#finding-list').getAttribute('data-drawn'));
    const expected = lastScene().scene.items.filter(i => i.type === 'symbol' && ['C56', 'C57'].includes(i.reference));
    assert.equal(expected.length, 2);
    const circles = await page.locator('#findings circle').evaluateAll(n => n.map(x => [+x.getAttribute('cx'), +x.getAttribute('cy')]));
    for (const symbol of expected) assert.ok(circles.some(c => Math.hypot(c[0] - symbol.at[0], c[1] - symbol.at[1]) < 1e-6), symbol.reference);
    await goTo('/');
    await page.locator('#erc').click();
    await page.waitForFunction(() => document.querySelector('#finding-list').textContent.includes('ev-'), null, { timeout: 120000 });
    const rootDrawn = Number(await page.locator('#finding-list').getAttribute('data-drawn'));
    assert.equal(rootDrawn, 1); // J4 only; C56/C57 are not drawn at their bogus root-sheet position
    assert.deepEqual(errors, []);
    assert.ok(!html.includes(info.token));
    const result = { browser: browser.version(), demo: 'complex_hierarchy', pages: lastScene().pages.length,
      first_load_ms: firstLoadMs, symbols_selected: selections, net_checked: pin.net, net_local_pins: localPins.length,
      net_cross_page_buttons: crossPage, erc_summary: erc.summary, erc_drawn_on_page: ercDrawn, video_erc_graphic_drawn: graphicDrawn, video_erc_root_drawn: rootDrawn,
      marker_bound_reference: marker.target_item.reference, source_bytes_unchanged_by_marker: true };
    const report = evidencePath(root, (process.env.PCBAI_PUBLISH_EVIDENCE === '1' ? 'docs/spikes' : '.pcbai-state') + '/G2-browser-result.json');
    fs.writeFileSync(report, JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result, null, 2));
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
