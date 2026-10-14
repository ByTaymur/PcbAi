// Side bar panel: actions, the user's request and the open project markers, composed into one agent prompt.
// The prompt goes to the agent chosen in the panel (agents.js) or to the clipboard.
const vscode = require('vscode');
const agents = require('./agents');
const { composePrompt, describeMarker, composeAgentPrompt, servicePrompt } = require('./agent_prompt');
const path = require('node:path');
const crypto = require('node:crypto');

const ACTIONS = [
  ['pcbai.view', 'Kart 2B'], ['pcbai.schematic', 'Şematik'], ['pcbai.view3d', '3B'],
  ['pcbai.check', 'ERC + DRC'], ['pcbai.pdf', 'Şematik PDF'], ['pcbai.stats', 'Kart ölçüleri'],
  ['pcbai.autoroute', 'Otomatik rota (önizle)'], ['pcbai.autoplace', 'Otomatik yerleşim (önizle)'],
  ['pcbai.searchParts', 'Yerel parça ara'],
  ['pcbai.connectAgents', 'Ajan için MCP ekle'], ['pcbai.status', 'Servis durumu'], ['pcbai.stop', 'Servisi durdur'],
];

function escape(value) {
  return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const EVENTS_MS = 2000;
const EVENTS_SHOWN = 50;

// One line per event; the hint repeats the service's guidance for a blocked write or an applied change.
function eventRow(event) {
  const time = new Date((event.time || 0) * 1000).toTimeString().slice(0, 8);
  const hint = event.outcome === 'blocked'
    ? 'Ajan değişiklik yapmak istiyor: kartı kaydedip KiCad editörünü kapatın, sonra ajana devam deyin.'
    : event.outcome === 'ok' && event.change_id ? "Dosya değişti: KiCad'de Dosya → Geri al (Revert) ile yeniden yükleyin." : '';
  return { seq: event.seq, text: `${time}  ${event.client}  ${event.tool}  ${event.outcome}${event.change_id ? ' · ' + event.change_id : ''}`,
    outcome: String(event.outcome || ''), hint };
}

class SidebarProvider {
  constructor(context, api) {
    this.context = context; this.api = api; this.view = null; this.state = null; this.eventsSince = null;
  }

  async pollEvents() {
    const events = await this.api.events(this.eventsSince);
    if (!events || !events.length) return;
    this.eventsSince = events[events.length - 1].seq;
    await this.post({ type: 'events', items: events.slice(-EVENTS_SHOWN).map(eventRow) });
  }

  resolveWebviewView(view) {
    this.view = view;
    view.webview.options = { enableScripts: true, localResourceRoots: [vscode.Uri.file(path.join(this.context.extensionPath, 'media'))] };
    view.webview.html = this.html(view.webview);
    view.webview.onDidReceiveMessage(message => this.receive(message).catch(error => this.post({ type: 'error', message: error.message })));
    view.onDidChangeVisibility(() => { if (view.visible) this.load(false); });
    // Agent activity (AJ-7): poll the service's event log while the panel is open.
    if (this.api.events) {
      const timer = setInterval(() => { if (view.visible) this.pollEvents().catch(() => {}); }, EVENTS_MS);
      if (timer.unref) timer.unref();
      if (view.onDidDispose) view.onDidDispose(() => clearInterval(timer));
      this.context.subscriptions.push({ dispose: () => clearInterval(timer) });
    }
  }

  postAgents() {
    const summary = agents.summary(this.context);
    return this.post({ type: 'agents', ...summary, mcpMissing: this.mcpMissing(summary.selected) });
  }

  // Warn (not block) when the selected agent has no pcbai MCP entry: the prompt would reach an agent without tools.
  mcpMissing(id) {
    if (!this.api.mcpContext) return null;
    try {
      if (require('./mcp_setup').hasRegistration(id, this.api.mcpContext()) !== false) return null;
    } catch (_) { return null; }
    const agent = agents.list().find(a => a.id === id);
    return `${agent ? agent.label : id} için pcbai MCP kaydı yok — "Ajan için MCP ekle" ile bağla.`;
  }

  // KiCad handoff (AJ-5): show the prompt that arrived in the request box.
  setRequest(text) { return this.post({ type: 'request', text: String(text).slice(0, 8000) }); }

  post(message) { return this.view ? this.view.webview.postMessage(message) : Promise.resolve(false); }

  html(webview) {
    const nonce = crypto.randomBytes(18).toString('base64');
    const uri = name => escape(webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, 'media', name))).toString());
    const actions = ACTIONS.map(([command, label]) => `<button data-command="${command}">${escape(label)}</button>`).join('');
    return `<!doctype html><html lang="tr"><head><meta charset="utf-8">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${escape(webview.cspSource)}; script-src 'nonce-${nonce}';">
      <link rel="stylesheet" href="${uri('sidebar.css')}"></head><body>
      <div class="project"><span id="project">Proje seçilmedi</span><button id="pick" class="link">değiştir</button></div>
      <div class="actions">${actions}</div>
      <div class="agent"><strong>YAPAY ZEKÂ</strong><label for="agent">Ajan</label><select id="agent"></select><p id="mcp" class="warn" hidden></p></div>
      <label for="request">Ajana isteğin</label>
      <textarea id="request" rows="6" maxlength="8000" placeholder="Örn. güç katındaki MOSFET'lerin soğutma bakırını büyüt, DRC temiz kalsın"></textarea>
      <div class="row"><strong>İşaretler</strong><button id="reload" class="link">yenile</button></div>
      <div class="row tools"><label><input type="checkbox" id="hide-done"> Bitenleri gizle</label><button id="delete-done" class="link" title="Bitmiş işaretleri sil (onay sorulur)">Bitenleri sil</button></div>
      <div id="markers"><p class="muted">Servis kapalı ya da işaret yok.</p></div>
      <div class="send"><button id="open" class="primary">Ajana gönder</button><button id="copy">Kopyala</button></div>
      <details><summary>Oluşan istem</summary><pre id="preview"></pre></details>
      <details id="activity-box"><summary>Ajan etkinliği</summary><ol id="activity" class="activity"></ol></details>
      <p id="message" class="muted"></p>
      <script nonce="${nonce}" src="${uri('sidebar.js')}"></script></body></html>`;
  }

  async load(interactive, change = false) {
    await this.postAgents(); // the choice may have changed through the PcbAi: Ajan seç command
    try {
      const session = await this.api.sessionFor(interactive, change);
      if (!session) { await this.post({ type: 'state', project: null, markers: [], pages: {} }); return; }
      const response = await this.api.call('get_markers', { session: session.id });
      if (!response.ok) throw new Error(response.summary);
      const pages = {};
      for (const marker of response.markers) if (marker.sheet && !pages[marker.sheet]) pages[marker.sheet] = marker.sheet;
      this.state = { session, markers: response.markers, pages, revision: response.revision,
        markersRevision: response.markers_revision };
      await this.post({ type: 'state', project: session.project, root: session.root,
        markers: response.markers.map(m => ({ n: m.n, status: m.status, text: describeMarker(m, pages), open: m.status === 'open',
          closedBy: m.closed_by || null, evidence: m.evidence_id || null })) });
    } catch (error) {
      if (error.message !== 'İptal edildi') await this.post({ type: 'error', message: error.message });
    }
  }

  // One marker edit through the user-only view channel: preview, then apply the same candidate.
  async markerEdit(tool, marker, extra) {
    const { session, revision, markersRevision } = this.state;
    const target = { session: session.id, document: marker.document, revision };
    const check = response => {
      if (response && response.ok) return response;
      const error = new Error(response?.summary || response?.error?.message || 'İşaret güncellenemedi');
      error.code = response?.error?.code;
      throw error;
    };
    const preview = check(await this.api.viewCall(tool, { ...target, markers_revision: markersRevision, mode: 'preview', n: marker.n, ...extra }));
    const applied = check(await this.api.viewCall(tool, { ...target, markers_revision: preview.markers_revision, mode: 'apply',
      candidate_id: preview.candidate_id }));
    this.state.markersRevision = applied.markers_revision;
    return applied;
  }

  // Another client changed the markers or the project: refresh, never repeat the edit.
  async markerFailed(error) {
    const stale = error.code === 'stale_markers' || error.code === 'stale_revision';
    await this.load(false);
    return this.post({ type: 'error', message: stale ? 'İşaretler değişti, yenilendi. İşlemi tekrar seçin.' : error.message });
  }

  async markerAction(message) {
    if (!this.state) throw new Error('Önce bir KiCad projesi seçin');
    if (!this.api.viewCall) throw new Error('PcbAi servisi çalışmıyor');
    const find = n => this.state.markers.find(m => m.n === n);
    if (message.type === 'markerStatus') {
      const marker = find(message.n);
      if (!marker) return this.markerFailed({ code: 'stale_markers' });
      const status = marker.status === 'done' ? 'open' : 'done';
      try { await this.markerEdit('set_marker_status', marker, { status }); } catch (error) { return this.markerFailed(error); }
      await this.load(false);
      return this.post({ type: 'notice', message: `#${marker.n} ${status === 'done' ? 'bitti olarak işaretlendi' : 'yeniden açıldı'}.` });
    }
    const targets = message.type === 'markerDelete' ? [find(message.n)].filter(Boolean)
      : this.state.markers.filter(m => m.status === 'done');
    if (!targets.length) return this.markerFailed({ code: message.type === 'markerDelete' ? 'stale_markers' : 'none', message: 'Biten işaret yok.' });
    const question = targets.length === 1 ? `#${targets[0].n} silinsin mi? Kontrol noktası alınır.`
      : `Biten ${targets.length} işaret silinsin mi? Her silmeden önce kontrol noktası alınır.`;
    if (await vscode.window.showWarningMessage(question, { modal: true }, 'Sil') !== 'Sil') return;
    let deleted = 0;
    for (const marker of targets) {
      try { await this.markerEdit('delete_marker', marker, {}); deleted += 1; } catch (error) {
        await this.load(false);
        return this.post({ type: 'error', message: `${deleted}/${targets.length} işaret silindi; #${marker.n} silinemedi: ` +
          (error.code === 'stale_markers' ? 'işaretler değişti, yenilendi.' : error.message) });
      }
    }
    await this.load(false);
    return this.post({ type: 'notice', message: targets.length === 1 ? `#${targets[0].n} silindi.` : `${deleted} işaret silindi.` });
  }

  async receive(message) {
    if (!message || typeof message !== 'object') return;
    if (message.type === 'ready') return this.load(false);
    if (message.type === 'agent' && typeof message.id === 'string') {
      const agent = await agents.choose(this.context, message.id);
      await this.postAgents();
      return this.post({ type: 'notice', message: `Ajan: ${agent.label} — ${agent.detail}.` });
    }
    if (message.type === 'reload') return this.load(true);
    if (['markerStatus', 'markerDelete', 'deleteDone'].includes(message.type)) {
      if (message.type !== 'deleteDone' && !Number.isInteger(message.n)) return;
      return this.markerAction(message);
    }
    if (message.type === 'pick') return this.load(true, true);
    if (message.type === 'command' && ACTIONS.some(([command]) => command === message.command)) {
      await vscode.commands.executeCommand(message.command);
      return this.load(false);
    }
    if (message.type === 'compose' || message.type === 'open' || message.type === 'copy') {
      if (!this.state) await this.load(true);
      if (!this.state) throw new Error('Önce bir KiCad projesi seçin');
      const args = { request: typeof message.request === 'string' ? message.request : '',
        marker_ids: (message.markers || []).filter(Number.isInteger) };
      const { session, markers, pages } = this.state;
      const prompt = await servicePrompt(this.api.agentPrompt, { session: session.id, ...args },
        () => composeAgentPrompt({ session, markers, pages, ...args }));
      await this.post({ type: 'preview', prompt });
      if (message.type === 'copy') {
        await vscode.env.clipboard.writeText(prompt);
        await this.post({ type: 'notice', message: 'İstem panoya kopyalandı.' });
      } else if (message.type === 'open') {
        await this.post({ type: 'notice', message: await agents.deliver(this.context, prompt, this.state.session.root) });
      }
    }
  }
}

function registerSidebar(context, api) {
  const provider = new SidebarProvider(context, api);
  agents.watch(context, () => provider.postAgents());
  context.subscriptions.push(vscode.window.registerWebviewViewProvider('pcbai.actions', provider,
    { webviewOptions: { retainContextWhenHidden: true } }));
  return provider;
}

module.exports = { registerSidebar, composePrompt, describeMarker, eventRow };
