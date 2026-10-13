// 3D view bridge (G4). The extension owns credentials; the webview receives one revision-bound local GLB URI.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function escape(value) {
  return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function viewHtml(webview, mediaRoot) {
  const nonce = crypto.randomBytes(24).toString('base64');
  const uri = name => escape(webview.asWebviewUri(vscode.Uri.file(path.join(mediaRoot, name))).toString());
  const source = escape(webview.cspSource);
  // connect-src is limited to the webview's own local resource origin: GLTFLoader fetches the local GLB only.
  return `<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${source} blob: data:; style-src ${source}; script-src 'nonce-${nonce}'; connect-src ${source}; font-src 'none'; base-uri 'none'; form-action 'none';">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>PcbAi · 3B</title>
    <link rel="stylesheet" href="${uri('viewer.css')}"></head><body class="three">
    <header><strong>PcbAi · 3B</strong><span id="document">Model hazırlanıyor</span>
      <button data-view="top">Üst</button><button data-view="bottom">Alt</button><button data-view="iso">İzometrik</button>
      <label><input type="checkbox" id="components" checked> Bileşenler</label><button id="refresh">Yenile</button><button id="panel-toggle" title="Araç panelini aç/kapat">☰ Panel</button></header>
    <main><section id="viewport"><canvas id="canvas" aria-label="Kartın 3B görünümü"></canvas>
      <p id="empty">KiCad 3B modeli hazırlanıyor…</p></section>
      <aside><h2>Seçim</h2><div id="details">Bir bileşene tıklayın.</div><h2>Model</h2><div id="model-info"></div></aside></main>
    <footer><span id="info">Seçim yok</span><span id="revision">Kaydedilmiş dosya</span></footer>
    <p id="error" role="alert"></p><script nonce="${nonce}" type="module" src="${uri('viewer3d.js')}"></script></body></html>`;
}

function glbUri(webview, viewsRoot, file) {
  const root = fs.realpathSync(viewsRoot);
  const artifact = fs.realpathSync(file);
  const relative = path.relative(root, artifact);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || path.extname(artifact) !== '.glb') {
    throw new Error('GLB PcbAi görünüm klasörünün dışında');
  }
  return webview.asWebviewUri(vscode.Uri.file(artifact)).toString();
}

function open3d(context, options) {
  const media = path.join(context.extensionPath, 'media');
  const viewsRoot = path.join(options.stateDir, 'views');
  const { session, document } = options;
  fs.mkdirSync(viewsRoot, { recursive: true });
  const panel = vscode.window.createWebviewPanel('pcbai.board3d', 'PcbAi · 3B', vscode.ViewColumn.Beside,
    { enableScripts: true, localResourceRoots: [vscode.Uri.file(media), vscode.Uri.file(viewsRoot)] });
  let disposed = false, busy = false, ready = false, revision = session.revision, generation = 0, timer;
  const post = value => disposed ? Promise.resolve(false) : panel.webview.postMessage(value);
  let resolveLoaded;
  const whenLoaded = new Promise(resolve => { resolveLoaded = resolve; });
  const deadline = setTimeout(() => resolveLoaded({ loaded: false }), 180000);

  async function refresh(force = false) {
    if (busy || disposed || !ready) return;
    busy = true;
    try {
      const status = await options.call('pcbai_status');
      if (!status.ok) throw new Error(status.summary);
      const live = status.sessions.find(s => s.id === session.id);
      if (!live) throw new Error('Kart oturumu artık kayıtlı değil');
      if (!force && generation && live.revision === revision) return;
      revision = live.revision;
      const requestGeneration = ++generation;
      await post({ type: 'busy', message: requestGeneration > 1 ? 'Kart değişti; 3B model yenileniyor…' : 'KiCad 3B modeli üretiliyor…' });
      const response = await options.backgroundJob('render_3d', { ...session, revision }, document);
      const render = response.render;
      await post({ type: 'model', generation: requestGeneration, document, revision, uri: glbUri(panel.webview, viewsRoot, render.path),
        components: render.components, without_model: render.without_model, bytes: render.bytes,
        substitutions: render.display_model_substitutions });
    } catch (error) { await post({ type: 'error', message: error.message }); }
    finally { busy = false; }
  }

  context.subscriptions.push(panel.webview.onDidReceiveMessage(async message => {
    if (!message || typeof message !== 'object' || disposed) return;
    if (message.type === 'ready' && !ready) { ready = true; await refresh(); return; }
    if (message.type === 'refresh') { await refresh(true); return; }
    if (message.type === 'modelReady' && message.generation === generation) {
      clearTimeout(deadline);
      resolveLoaded({ loaded: true, document, revision, renderer: message.renderer, components: message.components });
    }
    if (message.type === 'select' && typeof message.reference === 'string') options.onSelect?.(message.reference);
  }));
  panel.onDidDispose(() => { disposed = true; clearInterval(timer); clearTimeout(deadline); resolveLoaded({ loaded: false }); });
  timer = setInterval(() => refresh(), 1000);
  context.subscriptions.push({ dispose: () => { clearInterval(timer); clearTimeout(deadline); panel.dispose(); } });
  panel.webview.html = viewHtml(panel.webview, media);
  return { panel, whenLoaded };
}

module.exports = { open3d, viewHtml, glbUri };
