// The extension owns service credentials and targets. The webview can only request bounded view actions.
const vscode = require('vscode');
const agents = require('./agents');
const { boardAskPrompt, servicePrompt } = require('./agent_prompt');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function escape(value) {
  return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function viewHtml(webview, mediaRoot) {
  const nonce = crypto.randomBytes(24).toString('base64');
  const uri = name => escape(webview.asWebviewUri(vscode.Uri.file(path.join(mediaRoot, name))).toString());
  return `<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${escape(webview.cspSource)}; style-src ${escape(webview.cspSource)}; script-src 'nonce-${nonce}'; connect-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none';">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>PcbAi · Kart</title>
    <link rel="stylesheet" href="${uri('viewer.css')}"></head><body>
    <header><strong>PcbAi · Kart</strong><span id="document">Görünüm hazırlanıyor</span>
      <button id="refresh">Yenile</button><button id="fit">Karta sığdır</button><button id="panel-toggle" title="Araç panelini aç/kapat">☰ Panel</button></header>
    <div id="layers" aria-label="Katmanlar"></div>
    <main><section id="viewport"><svg id="board" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Kart görünümü">
      <g id="images"></g><g id="findings"></g><g id="selection"></g><g id="marker-shapes"></g><g id="draft"></g>
    </svg><p id="empty">Kart görünümü hazır. Kartı açmak için PcbAi: Kart 2B görünümünü aç komutunu kullanın.</p></section>
    <aside><h2>İşaretler</h2><div class="tools"><button data-tool="select">Seç</button><button data-tool="point">Nokta</button>
      <button data-tool="line">Çizgi</button><button data-tool="area">Alan</button><button id="finish">Alanı bitir</button></div>
      <button id="anchor">Seçili öğeye işaret koy</button><p id="instruction">Tıkla: seç · Sürükle: kaydır · Tekerlek: yakınlaştır · Oklar / + − / 0: gezin, sığdır</p>
      <label for="note">İşaret notu</label><textarea id="note" maxlength="4096" rows="3"></textarea>
      <button id="edit-preview" hidden>Notu önizle</button>
      <label><input type="checkbox" id="approve"> İçe aktarılmış notu onaylıyorum</label>
      <div id="preview" hidden><p id="preview-text"></p><button id="apply">Önizlemeyi uygula</button><button id="cancel">Vazgeç</button></div>
      <div id="marker-list"></div><h2>DRC bulguları</h2><button id="drc">DRC çalıştır</button><div id="finding-list">Henüz çalıştırılmadı</div>
    </aside></main><footer><span id="info">Seçim yok</span><select id="choices" aria-label="Çakışan öğeler" hidden></select><span id="cursor"></span><span id="revision">Kaydedilmiş dosya</span></footer>
    <p id="error" role="alert"></p><script nonce="${nonce}" type="module" src="${uri('viewer.js')}"></script></body></html>`;
}

function artifactUri(webview, viewsRoot, file) {
  const root = fs.realpathSync(viewsRoot);
  const artifact = fs.realpathSync(file);
  const relative = path.relative(root, artifact);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || path.extname(artifact) !== '.svg') {
    throw new Error('SVG PcbAi görünüm klasörünün dışında');
  }
  return webview.asWebviewUri(vscode.Uri.file(artifact)).toString();
}

function openView(context, options) {
  const media = path.join(context.extensionPath, 'media');
  const viewsRoot = path.join(options.stateDir, 'views');
  const session = options.session;
  // Empty G0 panels must not turn an uninitialized private state directory into an unmanaged one.
  if (session) fs.mkdirSync(viewsRoot, { recursive: true });
  const panel = vscode.window.createWebviewPanel('pcbai.interactiveBoard', 'PcbAi · Kart 2B', vscode.ViewColumn.Beside,
    { enableScripts: true, localResourceRoots: session ? [vscode.Uri.file(media), vscode.Uri.file(viewsRoot)] : [vscode.Uri.file(media)] });
  const document = options.document;
  let disposed = false, busy = false, ready = false, revision = session?.revision;
  let lastMarkers = '', preview = null, generation = 0;
  let timer;
  const post = value => disposed ? Promise.resolve(false) : panel.webview.postMessage(value);
  const target = () => ({ session: session.id, document, revision });
  const check = response => { if (!response.ok) throw new Error(response.summary); return response; };
  const deadline = setTimeout(() => resolveReady({ ready: false }), 15000);
  let resolveReady;
  const whenReady = new Promise(resolve => { resolveReady = resolve; });
  let resolveLoaded;
  const whenLoaded = new Promise(resolve => { resolveLoaded = resolve; });
  const loadDeadline = setTimeout(() => resolveLoaded({ loaded: false }), 45000);

  async function refresh(force = false) {
    if (!session || busy || disposed || !ready) return;
    busy = true;
    try {
      const status = check(await options.call('pcbai_status'));
      const current = status.sessions.find(s => s.id === session.id);
      if (!current) throw new Error('Kart oturumu artık kayıtlı değil');
      const changed = force || revision !== current.revision || generation === 0;
      revision = current.revision;
      if (changed) {
        preview = null;
        const requestGeneration = ++generation;
        if (requestGeneration > 1) await post({ type: 'notice', message: 'Kart değişti; yenileniyor (eski görüntü gösteriliyor)…' });
        const scene = check(await options.call('scene_pcb', target()));
        const rendered = await options.backgroundJob('render_pcb', { ...session, revision }, document);
        const markers = check(await options.call('get_markers', { session: session.id }));
        if (markers.revision !== revision) throw new Error('Kart yüklenirken değişti; yeniden yenileyin');
        lastMarkers = markers.markers_revision;
        const render = rendered.render;
        const layers = render.layers.map(layer => ({ name: layer.name, uri: artifactUri(panel.webview, viewsRoot, layer.path) }));
        await post({ type: 'scene', generation: requestGeneration, document, revision, scene: scene.scene,
          render: { ...render, layers }, markers: markers.markers.filter(m => m.document === document), markers_revision: lastMarkers });
      } else {
        const markers = check(await options.call('get_markers', { session: session.id }));
        if (markers.revision !== revision) return; // next poll loads the changed board
        if (lastMarkers !== markers.markers_revision) {
          lastMarkers = markers.markers_revision;
          preview = null;
          await post({ type: 'markers', generation, markers: markers.markers.filter(m => m.document === document), markers_revision: lastMarkers });
        }
      }
    } catch (error) { await post({ type: 'error', message: error.message }); }
    finally { busy = false; }
  }

  context.subscriptions.push(panel.webview.onDidReceiveMessage(async message => {
    let ownsBusy = false, refreshNeeded = false;
    try {
      if (!message || typeof message !== 'object') return;
      if (message.type === 'ready' && !ready) {
        ready = true;
        clearTimeout(deadline);
        resolveReady({ ready: true, threeRevision: message.threeRevision });
        if (!session) { clearTimeout(loadDeadline); resolveLoaded({ loaded: true, empty: true }); }
        await refresh();
        return;
      }
      if (!session || disposed) return;
      if (message.type === 'sceneReady' && message.generation === generation && message.revision === revision) {
        clearTimeout(loadDeadline); resolveLoaded({ loaded: true, document, revision, layerCount: message.layerCount }); return;
      }
      if (message.type === 'refresh') { await refresh(true); return; }
      const until = Date.now() + 30000;
      while (busy && !disposed && Date.now() < until) await new Promise(resolve => setTimeout(resolve, 50));
      if (disposed) return;
      if (busy) throw new Error('Görünüm işlemi sürüyor; biraz sonra tekrar deneyin.');
      if (message.generation !== generation || message.revision !== revision) throw new Error('Görünüm değişti; işlemi güncel kartta tekrar önizleyin.');
      busy = true; ownsBusy = true;
      if (message.type === 'markerPreview') {
        const args = { ...target(), markers_revision: lastMarkers, mode: 'preview' };
        if (message.n !== undefined) args.n = message.n;
        if (!message.delete) { args.marker = message.marker; args.approve_untrusted = message.approve === true; }
        const tool = message.delete ? 'delete_marker' : 'set_marker';
        const response = check(await options.viewCall(tool, args));
        preview = { tool, args: { ...target(), markers_revision: lastMarkers, mode: 'apply', candidate_id: response.candidate_id },
          generation };
        await post({ type: 'preview', generation, marker: response.marker, deleting: Boolean(message.delete) });
      } else if (message.type === 'markerApply' && preview && preview.generation === generation) {
        check(await options.viewCall(preview.tool, preview.args));
        preview = null;
        refreshNeeded = true;
      } else if (message.type === 'markerStatus' && Number.isInteger(message.n) && ['open', 'done'].includes(message.status)) {
        // The user's own tick: reversible, so preview and apply at once (agents still need change evidence).
        const args = { ...target(), markers_revision: lastMarkers, mode: 'preview', n: message.n, status: message.status };
        const response = check(await options.viewCall('set_marker_status', args));
        check(await options.viewCall('set_marker_status', { ...target(), markers_revision: response.markers_revision, mode: 'apply',
          candidate_id: response.candidate_id }));
        refreshNeeded = true;
      } else if (message.type === 'markerCancel') {
        preview = null;
      } else if (message.type === 'drc') {
        const response = await options.backgroundJob('drc', { ...session, revision }, document);
        await post({ type: 'drc', generation, findings: response.findings, summary: response.summary, evidence: response.evidence_id });
      } else if (message.type === 'ask' && Number.isInteger(message.n)) {
        const ask = { space: 'pcb', n: message.n, document };
        const prompt = await servicePrompt(options.agentPrompt, { session: session.id, marker: ask }, async () => {
          const markers = check(await options.call('get_markers', { session: session.id }));
          if (!markers.markers.find(m => m.n === message.n && m.document === document)) throw new Error('İşaret bulunamadı');
          return boardAskPrompt(session, document, message.n);
        });
        await post({ type: 'notice', message: await agents.deliver(context, prompt, session.root, `#${message.n} isteği`) });
      }
    } catch (error) { preview = null; await post({ type: 'error', message: error.message }); }
    finally { if (ownsBusy) busy = false; if (refreshNeeded) await refresh(); }
  }));
  panel.onDidDispose(() => { disposed = true; clearInterval(timer); clearTimeout(deadline); clearTimeout(loadDeadline);
    resolveReady({ ready: false }); resolveLoaded({ loaded: false }); });
  timer = setInterval(() => refresh(), 500); // G5: change detection is a cheap revision hash
  context.subscriptions.push({ dispose: () => { clearInterval(timer); clearTimeout(deadline); clearTimeout(loadDeadline); panel.dispose(); } });
  panel.webview.html = viewHtml(panel.webview, media);
  return { panel, whenReady, whenLoaded };
}

module.exports = { openView, viewHtml, artifactUri };
