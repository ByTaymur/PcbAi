// Schematic view bridge. Same rules as board_view: the extension owns credentials and targets; the webview can
// only ask for bounded actions on the page instances the service reported.
const vscode = require('vscode');
const agents = require('./agents');
const { schAskPrompt, servicePrompt } = require('./agent_prompt');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { artifactUri } = require('./board_view');

function escape(value) {
  return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function viewHtml(webview, mediaRoot) {
  const nonce = crypto.randomBytes(24).toString('base64');
  const uri = name => escape(webview.asWebviewUri(vscode.Uri.file(path.join(mediaRoot, name))).toString());
  return `<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${escape(webview.cspSource)}; style-src ${escape(webview.cspSource)}; script-src 'nonce-${nonce}'; connect-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none';">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>PcbAi · Şematik</title>
    <link rel="stylesheet" href="${uri('viewer.css')}"></head><body class="sch">
    <header><strong>PcbAi · Şematik</strong><span id="document">Görünüm hazırlanıyor</span>
      <button id="up" title="Üst sayfaya çık">Üst sayfa</button><button id="refresh">Yenile</button><button id="fit">Sayfaya sığdır</button><button id="panel-toggle" title="Araç panelini aç/kapat">☰ Panel</button></header>
    <nav id="pages" aria-label="Sayfa ağacı"></nav>
    <main><section id="viewport"><svg id="board" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Şematik görünümü">
      <g id="images"></g><g id="nets"></g><g id="findings"></g><g id="selection"></g><g id="marker-shapes"></g><g id="draft"></g>
    </svg><p id="empty">Şematik görünümü hazırlanıyor.</p></section>
    <aside><h2>Seçim</h2><div id="details">Bir sembole, pine, tele ya da etikete tıklayın. Alt sayfaya girmek için sayfa kutusuna çift tıklayın.</div>
      <h2>İşaretler</h2><div class="tools"><button data-tool="select">Seç</button><button data-tool="point">Nokta</button>
      <button data-tool="area">Alan</button><button id="finish">Alanı bitir</button></div>
      <button id="anchor">Seçili öğeye işaret koy</button><p id="instruction">Tıkla: seç · Sürükle: kaydır · Tekerlek: yakınlaştır · Oklar / + − / 0: gezin, sığdır</p>
      <label for="note">İşaret notu</label><textarea id="note" maxlength="4096" rows="3"></textarea>
      <button id="edit-preview" hidden>Notu önizle</button>
      <label><input type="checkbox" id="approve"> İçe aktarılmış notu onaylıyorum</label>
      <div id="preview" hidden><p id="preview-text"></p><button id="apply">Önizlemeyi uygula</button><button id="cancel">Vazgeç</button></div>
      <div id="marker-list"></div><h2>ERC bulguları</h2><button id="erc">ERC çalıştır</button><div id="finding-list">Henüz çalıştırılmadı</div>
    </aside></main><footer><span id="info">Seçim yok</span><select id="choices" aria-label="Çakışan öğeler" hidden></select><span id="cursor"></span><span id="revision">Kaydedilmiş dosya</span></footer>
    <p id="error" role="alert"></p><script nonce="${nonce}" type="module" src="${uri('sch_viewer.js')}"></script></body></html>`;
}

function openSchematic(context, options) {
  const media = path.join(context.extensionPath, 'media');
  const viewsRoot = path.join(options.stateDir, 'views');
  const session = options.session;
  const document = options.document; // root schematic: the hierarchy is resolved from it
  fs.mkdirSync(viewsRoot, { recursive: true });
  const panel = vscode.window.createWebviewPanel('pcbai.schematic', 'PcbAi · Şematik', vscode.ViewColumn.Beside,
    { enableScripts: true, localResourceRoots: [vscode.Uri.file(media), vscode.Uri.file(viewsRoot)] });
  let disposed = false, busy = false, ready = false, revision = session.revision;
  let pages = [], current = options.sheet || null, lastMarkers = '', preview = null, generation = 0, timer;
  const post = value => disposed ? Promise.resolve(false) : panel.webview.postMessage(value);
  const page = () => pages.find(p => p.instance === current);
  const check = response => { if (!response.ok) throw new Error(response.summary); return response; };
  let resolveLoaded;
  const whenLoaded = new Promise(resolve => { resolveLoaded = resolve; });
  const loadDeadline = setTimeout(() => resolveLoaded({ loaded: false }), 90000);

  async function markers() {
    const response = check(await options.call('get_markers', { session: session.id }));
    if (response.revision !== revision) return null;
    lastMarkers = response.markers_revision;
    const p = page();
    return response.markers.filter(m => m.space === 'sch' && m.document === p.document &&
      (m.sheet ? m.sheet === p.instance : p.instance.split('/').length === 2));
  }

  async function loadPage(instance) {
    current = pages.some(p => p.instance === instance) ? instance : pages[0].instance;
    preview = null;
    const requestGeneration = ++generation;
    const scene = check(await options.call('scene_sch', { session: session.id, document, revision, sheet: current }));
    const list = await markers();
    if (list === null) throw new Error('Şematik yüklenirken değişti; yeniden yenileyin');
    const p = page();
    await post({ type: 'scene', generation: requestGeneration, document: p.document, revision,
      page: { ...p, uri: artifactUri(panel.webview, viewsRoot, p.path) },
      pages: pages.map(({ instance, names, number, document: file }) => ({ instance, names, number, document: file })),
      scene: scene.scene, net_members: scene.net_members, markers: list, markers_revision: lastMarkers });
  }

  async function refresh(force = false) {
    if (busy || disposed || !ready) return;
    busy = true;
    try {
      const status = check(await options.call('pcbai_status'));
      const live = status.sessions.find(s => s.id === session.id);
      if (!live) throw new Error('Şematik oturumu artık kayıtlı değil');
      const changed = force || revision !== live.revision || generation === 0;
      revision = live.revision;
      if (changed) {
        await post({ type: 'busy', message: 'Şematik yenileniyor…' });
        const rendered = await options.backgroundJob('render_sch', { ...session, revision }, document);
        pages = rendered.render.pages;
        await loadPage(current || pages[0].instance);
      } else if (pages.length) {
        const before = lastMarkers;
        const list = await markers();
        if (list !== null && before !== lastMarkers) {
          preview = null;
          await post({ type: 'markers', generation, markers: list, markers_revision: lastMarkers });
        }
      }
    } catch (error) { await post({ type: 'error', message: error.message }); }
    finally { busy = false; }
  }

  context.subscriptions.push(panel.webview.onDidReceiveMessage(async message => {
    let ownsBusy = false, refreshNeeded = false;
    try {
      if (!message || typeof message !== 'object' || disposed) return;
      if (message.type === 'ready' && !ready) { ready = true; await refresh(); return; }
      if (message.type === 'sceneReady' && message.generation === generation && message.revision === revision) {
        clearTimeout(loadDeadline);
        resolveLoaded({ loaded: true, document, revision, sheet: current, pages: pages.length }); return;
      }
      if (message.type === 'refresh') { await refresh(true); return; }
      const until = Date.now() + 30000;
      while (busy && !disposed && Date.now() < until) await new Promise(resolve => setTimeout(resolve, 50));
      if (disposed) return;
      if (busy) throw new Error('Görünüm işlemi sürüyor; biraz sonra tekrar deneyin.');
      if (message.generation !== generation || message.revision !== revision) throw new Error('Görünüm değişti; işlemi güncel sayfada tekrar deneyin.');
      busy = true; ownsBusy = true;
      const p = page();
      const target = { session: session.id, document: p.document, revision };
      if (message.type === 'page' && typeof message.instance === 'string') {
        if (!pages.some(x => x.instance === message.instance)) throw new Error('Sayfa bu hiyerarşide yok');
        await loadPage(message.instance);
      } else if (message.type === 'markerPreview') {
        const args = { ...target, markers_revision: lastMarkers, mode: 'preview' };
        if (message.n !== undefined) args.n = message.n;
        if (!message.delete) {
          args.marker = { ...message.marker, space: 'sch', sheet: p.instance };
          args.approve_untrusted = message.approve === true;
        }
        const tool = message.delete ? 'delete_marker' : 'set_marker';
        const response = check(await options.viewCall(tool, args));
        preview = { tool, args: { ...target, markers_revision: lastMarkers, mode: 'apply', candidate_id: response.candidate_id }, generation };
        await post({ type: 'preview', generation, marker: response.marker, deleting: Boolean(message.delete) });
      } else if (message.type === 'markerApply' && preview && preview.generation === generation) {
        check(await options.viewCall(preview.tool, preview.args));
        preview = null; refreshNeeded = true;
      } else if (message.type === 'markerStatus' && Number.isInteger(message.n) && ['open', 'done'].includes(message.status)) {
        // The user's own tick: reversible, so preview and apply at once (agents still need change evidence).
        const args = { ...target, markers_revision: lastMarkers, mode: 'preview', n: message.n, status: message.status };
        const response = check(await options.viewCall('set_marker_status', args));
        check(await options.viewCall('set_marker_status', { ...target, markers_revision: response.markers_revision, mode: 'apply',
          candidate_id: response.candidate_id }));
        refreshNeeded = true;
      } else if (message.type === 'markerCancel') {
        preview = null;
      } else if (message.type === 'erc') {
        const response = await options.backgroundJob('erc', { ...session, revision }, document);
        await post({ type: 'erc', generation, findings: response.findings, summary: response.summary, evidence: response.evidence_id });
      } else if (message.type === 'ask' && Number.isInteger(message.n)) {
        const ask = { space: 'sch', n: message.n, document: p.document, sheet_names: p.names };
        const prompt = await servicePrompt(options.agentPrompt, { session: session.id, marker: ask },
          () => schAskPrompt(session, p.document, p.names, message.n));
        await post({ type: 'notice', message: await agents.deliver(context, prompt, session.root, `#${message.n} isteği`) });
      }
    } catch (error) { preview = null; await post({ type: 'error', message: error.message }); }
    finally {
      if (ownsBusy) busy = false;
      if (refreshNeeded) await refresh(); // markers live outside the project revision
    }
  }));
  panel.onDidDispose(() => { disposed = true; clearInterval(timer); clearTimeout(loadDeadline); resolveLoaded({ loaded: false }); });
  timer = setInterval(() => refresh(), 500); // G5: change detection is a cheap revision hash
  context.subscriptions.push({ dispose: () => { clearInterval(timer); clearTimeout(loadDeadline); panel.dispose(); } });
  panel.webview.html = viewHtml(panel.webview, media);
  return { panel, whenLoaded };
}

module.exports = { openSchematic, viewHtml };
