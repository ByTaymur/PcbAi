// External engine candidates: credentials and immutable targets stay in the extension host.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { artifactUri } = require('./board_view');

const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function html(webview, media) {
  const nonce = crypto.randomBytes(24).toString('base64');
  const uri = name => escape(webview.asWebviewUri(vscode.Uri.file(path.join(media, name))).toString());
  return `<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${escape(webview.cspSource)}; style-src ${escape(webview.cspSource)}; script-src 'nonce-${nonce}'; connect-src 'none'; base-uri 'none'; form-action 'none';">
    <link rel="stylesheet" href="${uri('engine.css')}"></head><body><h1>Motor önizlemesi</h1>
    <p id="status">Aday görselleri hazırlanıyor…</p><div class="boards"><section><h2>Önce</h2><div id="before"></div></section>
    <section><h2>Sonra</h2><div id="after"></div></section></div><table><thead><tr><th>Ölçü</th><th>Önce</th><th>Sonra</th></tr></thead><tbody id="metrics"></tbody></table>
    <p id="evidence"></p><p id="blockers" role="alert"></p><button id="apply" disabled>Bu adayı uygula</button>
    <button id="cancel">Vazgeç</button><p id="error" role="alert"></p>
    <script nonce="${nonce}" src="${uri('engine.js')}"></script></body></html>`;
}

function openEngineView(context, options) {
  const viewsRoot = path.join(options.stateDir, 'views');
  fs.mkdirSync(viewsRoot, { recursive: true });
  const media = path.join(context.extensionPath, 'media');
  const preview = options.preview;
  const target = { ...preview.target };
  const panel = vscode.window.createWebviewPanel('pcbai.engine', 'PcbAi · Motor önizlemesi', vscode.ViewColumn.Beside,
    { enableScripts: true, localResourceRoots: [vscode.Uri.file(media), vscode.Uri.file(viewsRoot)] });
  let disposed = false, busy = false, ready = false;
  panel.webview.html = html(panel.webview, media);
  const check = response => { if (!response.ok) throw new Error(response.summary); return response; };
  const post = value => disposed ? Promise.resolve(false) : panel.webview.postMessage(value);
  const subscription = panel.webview.onDidReceiveMessage(async message => {
    if (!message || typeof message !== 'object' || busy || disposed) return;
    if (!['ready', 'apply', 'cancel'].includes(message.type) || Object.keys(message).some(k => k !== 'type')) return;
    busy = true;
    try {
      if (message.type === 'ready' && !ready) {
        ready = true;
        const images = check(await options.call('engine_preview', { ...target, candidate_id: preview.candidate_id }));
        const adapt = render => ({ bbox: render.bbox, mm_to_svg: render.mm_to_svg, viewbox: render.viewbox,
          layers: render.layers.map(layer => ({ name: layer.name, uri: artifactUri(panel.webview, viewsRoot, layer.path) })) });
        await post({ type: 'preview', before: adapt(images.before), after: adapt(images.after), preview });
      } else if (message.type === 'apply' && ready) {
        if (preview.blockers?.length) throw new Error('Bu aday doğrulama kapısını geçmedi.');
        const done = check(await options.call(options.tool, { ...target, mode: 'apply', candidate_id: preview.candidate_id }));
        ready = false;
        await post({ type: 'applied', summary: done.summary, checkpoint: done.checkpoint?.id, evidence: done.change_id });
      } else if (message.type === 'cancel') {
        check(await options.call('discard_candidate', { ...target, candidate_id: preview.candidate_id }));
        panel.dispose();
      }
    } catch (error) { await post({ type: 'error', message: error.message }); }
    finally { busy = false; }
  });
  panel.onDidDispose(() => { disposed = true; subscription.dispose(); });
  context.subscriptions.push(panel);
  return panel;
}

module.exports = { openEngineView, html };
