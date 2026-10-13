// PcbAi VS Code extension: starts the local PcbAi service and calls its tools. Plain JavaScript, no dependencies.
// The service API is the same one the MCP proxy uses: loopback HTTP + bearer token from <state>/service.json.
const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

let output;
let statusItem;
let extensionContext;

function stateDir() {
  if (process.env.PCBAI_STATE_DIR) return process.env.PCBAI_STATE_DIR;
  return path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), '.local', 'share'), 'PcbAi');
}

function settings() {
  const cfg = vscode.workspace.getConfiguration('pcbai');
  let root = cfg.get('root') || process.env.PCBAI_ROOT || '';
  if (!root) {
    try {
      root = JSON.parse(fs.readFileSync(path.join(__dirname, 'defaults.json'), 'utf8')).root || '';
    } catch (_) { /* not packaged with a default */ }
  }
  if (!root || !fs.existsSync(path.join(root, 'pcbai'))) {
    throw new Error('PcbAi klasörü bulunamadı. Ayarlardan "pcbai.root" değerini PcbAi deposuna ayarlayın.');
  }
  const venv = process.platform === 'win32' ? path.join(root, '.venv', 'Scripts', 'python.exe')
    : path.join(root, '.venv', 'bin', 'python');
  const python = cfg.get('python') || process.env.PCBAI_PYTHON || venv;
  if (!fs.existsSync(python)) throw new Error(`Servis Python'u yok: ${python}. README kurulum adımlarını çalıştırın.`);
  return { root, python };
}

// Windows paths compare case-insensitively; VS Code gives "c:\" where Python gives "C:\".
function samePath(a, b) {
  const norm = (p) => path.resolve(p).replace(/[\\/]+$/, '');
  return process.platform === 'win32' ? norm(a).toLowerCase() === norm(b).toLowerCase() : norm(a) === norm(b);
}

function readInfo() {
  const info = JSON.parse(fs.readFileSync(path.join(stateDir(), 'service.json'), 'utf8'));
  if (!Number.isInteger(info.port) || info.port < 1 || info.port > 65535) throw new Error('Geçersiz servis portu');
  if (typeof info.token !== 'string' || info.token.length < 32) throw new Error('Geçersiz servis belirteci');
  return info;
}

function request(info, method, urlPath, payload, timeout = 150000) {
  return new Promise((resolve, reject) => {
    const body = payload === undefined ? undefined : Buffer.from(JSON.stringify(payload), 'utf8');
    const headers = { Authorization: 'Bearer ' + info.token };
    if (body) Object.assign(headers, { 'Content-Type': 'application/json', 'Content-Length': body.length });
    const req = http.request({ host: '127.0.0.1', port: info.port, path: urlPath, method, headers, timeout }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        try {
          const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
          if (res.statusCode !== 200) reject(new Error(data.error || `HTTP ${res.statusCode}`));
          else resolve(data);
        } catch (e) { reject(e); }
      });
    });
    req.on('timeout', () => req.destroy(new Error('Servis yanıt vermedi (zaman aşımı)')));
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function health() {
  try {
    const info = readInfo();
    const h = await request(info, 'GET', '/health', undefined, 2000);
    return h.name === 'pcbai' && h.instance === info.instance ? { info, health: h } : null;
  } catch (_) {
    return null;
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function startService(projects) {
  const { root, python } = settings();
  const args = ['-m', 'pcbai', 'serve'];
  for (const p of projects) args.push('--project', p);
  const env = Object.assign({}, process.env, { PYTHONPATH: root });
  const child = spawn(python, args, { cwd: root, env, detached: true, stdio: 'ignore', windowsHide: true });
  child.unref();
  for (let i = 0; i < 120; i++) {
    await sleep(100);
    const live = await health();
    if (live) return live;
  }
  throw new Error('PcbAi servisi başlamadı. Hatayı görmek için terminalde: python -m pcbai serve --project <proje>');
}

async function stopService() {
  const live = await health();
  if (!live) return false;
  await request(live.info, 'POST', '/shutdown', {}, 3000);
  for (let i = 0; i < 50 && (await health()); i++) await sleep(100);
  return true;
}

// KiCad's own settings name the project open in the KiCad window and the recent ones (kicad.json, read only).
function kicadProjects() {
  const base = process.env.KICAD_CONFIG_HOME ||
    (process.platform === 'win32' ? path.join(process.env.APPDATA || os.homedir(), 'kicad') : path.join(os.homedir(), '.config', 'kicad'));
  try {
    const versions = fs.readdirSync(base).filter((v) => /^\d+\.\d+$/.test(v))
      .sort((a, b) => parseFloat(b) - parseFloat(a));
    for (const version of versions) {
      const file = path.join(base, version, 'kicad.json');
      if (!fs.existsSync(file)) continue;
      const system = JSON.parse(fs.readFileSync(file, 'utf8')).system || {};
      const usable = (list) => (Array.isArray(list) ? list : [])
        .filter((p) => typeof p === 'string' && p.endsWith('.kicad_pro') && fs.existsSync(p));
      return { open: usable(system.open_projects), recent: usable(system.file_history) };
    }
  } catch (_) { /* no KiCad settings: fall back to the file picker */ }
  return { open: [], recent: [] };
}

// Projects in the workspace; otherwise the project open in KiCad (or a chosen one), remembered for next time.
async function workspaceProjects() {
  const uris = await vscode.workspace.findFiles('**/*.kicad_pro', '**/{node_modules,.git,.venv,.tools,.pcbai-state}/**', 50);
  if (uris.length) return uris.map((u) => u.fsPath).sort();
  const state = extensionContext && extensionContext.globalState;
  const remembered = state && state.get('pcbai.project');
  const { open, recent } = kicadProjects();
  if (open.length === 1 && (!remembered || samePath(remembered, open[0]))) {
    if (state) await state.update('pcbai.project', open[0]);
    return [open[0]];
  }
  const seen = [];
  const items = [];
  const add = (file, description) => {
    if (seen.some((p) => samePath(p, file))) return;
    seen.push(file);
    items.push({ label: path.basename(file, '.kicad_pro'), description, detail: file, file });
  };
  for (const file of open) add(file, "KiCad'de açık");
  if (remembered && fs.existsSync(remembered)) add(remembered, 'son kullanılan');
  for (const file of recent) add(file, 'KiCad son projeler');
  items.push({ label: '$(folder-opened) Dosya seç…', description: '.kicad_pro', file: null });
  const picked = await vscode.window.showQuickPick(items, { placeHolder: 'PcbAi hangi KiCad projesiyle çalışsın?' });
  if (!picked) throw new Error('İptal edildi');
  let file = picked.file;
  if (!file) {
    const chosen = await vscode.window.showOpenDialog({ canSelectMany: false, filters: { 'KiCad projesi': ['kicad_pro'] },
      openLabel: 'Bu projeyi kullan' });
    if (!chosen || !chosen.length) throw new Error('İptal edildi');
    file = chosen[0].fsPath;
  }
  if (state) await state.update('pcbai.project', file);
  return [file];
}

// Make sure a service runs with every wanted project registered. Restarting drops pending previews, so ask first.
async function ensureService(projects) {
  let live = await health();
  if (live) {
    const registered = live.health.projects || [];
    const missing = projects.filter((p) => !registered.some((r) => samePath(r, p)));
    if (!missing.length) return live;
    const choice = await vscode.window.showWarningMessage(
      `PcbAi servisi bu projeyi tanımıyor: ${missing.map((p) => path.basename(p)).join(', ')}. ` +
      'Servis projeyle birlikte yeniden başlatılsın mı? Bekleyen önizlemeler silinir.', { modal: true }, 'Yeniden başlat');
    if (choice !== 'Yeniden başlat') throw new Error('İptal edildi');
    await stopService();
    return startService([...registered, ...missing]);
  }
  return startService(projects);
}

async function call(name, args = {}) {
  const live = await health();
  if (!live) throw new Error('PcbAi servisi çalışmıyor');
  return request(live.info, 'POST', '/call', { name, arguments: args });
}

async function backgroundJob(tool, session, document, options = {}) {
  const submitted = await call('start_job', { session: session.id, document, revision: session.revision, tool, ...options });
  if (!submitted.ok) throw new Error(submitted.summary);
  const deadline = Date.now() + Math.max(300000, ((options.timeout_seconds || 0) + 180) * 1000);
  while (Date.now() < deadline) {
    const response = await call('job_status', { job_id: submitted.job.job_id });
    if (!response.ok) throw new Error(response.summary);
    if (['completed', 'failed'].includes(response.job.status)) {
      const result = response.job.result;
      if (!result.ok) throw new Error(result.summary);
      return result;
    }
    await sleep(100);
  }
  throw new Error('İş sürüyor; job_status ile izleyebilirsiniz: ' + submitted.job.job_id);
}

async function engineCommand(tool) {
  const session = await pickSession();
  const document = await pickDocument(session, '.kicad_pcb');
  const inventory = await call('route_engines');
  if (!inventory.ok) throw new Error(inventory.summary);
  const engines = inventory.engines.filter(e => e.available && (tool !== 'autoplace' || e.placement_path));
  if (!engines.length) throw new Error('Uygun motor yok. pcbai doctor ve isteğe bağlı motor kurulumu adımlarını kontrol edin.');
  const selected = await vscode.window.showQuickPick(engines.map(e => ({ label: e.engine, description: e.version, engine: e.engine })),
    { placeHolder: 'Önizleme motorunu seç' });
  if (!selected) return;
  const budget = await vscode.window.showInputBox({ prompt: 'En uzun motor çalışma süresi (saniye)', value: '120',
    validateInput: value => /^\d+$/.test(value) && Number(value) >= 30 && Number(value) <= 3600 ? undefined : '30–3600 arasında tam sayı girin' });
  if (budget === undefined) return;
  const options = selected.engine === 'freerouting' ? { passes: 5, threads: 1 } : tool === 'autoroute' ?
    { work: 3000000, threads: 1, variants: 1 } : { placement_mode: 'routable' };
  const preview = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification,
    title: tool === 'autoroute' ? 'Rota adayı hazırlanıyor' : 'Yerleşim adayı hazırlanıyor' },
    () => backgroundJob(tool, session, document, { mode: 'preview', engine: selected.engine, options, timeout_seconds: Number(budget) }));
  return require('./engine_view').openEngineView(extensionContext, { stateDir: stateDir(), tool, preview, call });
}

async function pickDocument(session, suffix) {
  const documents = (session.documents || []).filter((name) => name.endsWith(suffix));
  if (!documents.length) throw new Error('Projede bu tür belge yok: ' + suffix);
  if (documents.length === 1) return documents[0];
  const selected = await vscode.window.showQuickPick(documents, { placeHolder: 'Hangi KiCad belgesi?' });
  if (!selected) throw new Error('İptal edildi');
  return selected;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderHtml(webview, imageUri, document, revision, dimensions) {
  return `<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${escapeHtml(webview.cspSource)}; style-src 'unsafe-inline';">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>Kart önizlemesi</title>
    <style>body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:24px}
    img{display:block;max-width:100%;height:auto;margin:20px auto}p{color:var(--vscode-descriptionForeground)}</style>
    </head><body><h2>${escapeHtml(document)}</h2><p>Kaydedilmiş kart · ${escapeHtml(dimensions.width)} × ${escapeHtml(dimensions.height)} px</p>
    <img src="${escapeHtml(imageUri)}" alt="${escapeHtml(document)} kart önizlemesi">
    <p>Revizyon ${escapeHtml(revision.slice(0, 12))} · Görüntüyü yenilemek için komutu tekrar çalıştırın.</p></body></html>`;
}

async function pickSession() {
  const projects = await workspaceProjects();
  if (!projects.length) throw new Error('KiCad projesi bulunamadı');
  await ensureService(projects);
  const status = await call('pcbai_status');
  const sessions = (status.sessions || []).filter((s) => projects.some((p) => samePath(path.join(s.root, s.project), p)));
  if (!sessions.length) throw new Error('Servis seçilen projeyi kaydetmedi');
  if (sessions.length === 1) return sessions[0];
  const picked = await vscode.window.showQuickPick(
    sessions.map((s) => ({ label: s.project, description: s.root, session: s })), { placeHolder: 'Hangi KiCad projesi?' });
  if (!picked) throw new Error('İptal edildi');
  return picked.session;
}

function rootDocument(session, suffix) {
  const stem = session.project.replace(/\.kicad_pro$/, '');
  const docs = session.documents || [];
  return docs.find((d) => d === stem + suffix) || docs.find((d) => d.endsWith(suffix));
}

function printFindings(response) {
  output.appendLine(`  ${response.ok ? response.summary : 'HATA: ' + response.summary}` +
    (response.evidence_id ? `  (kanıt ${response.evidence_id})` : ''));
  for (const w of response.warnings || []) output.appendLine(`  ! ${w}`);
  for (const f of response.findings || []) {
    output.appendLine(`  [${f.severity}] ${f.type}: ${f.description}${f.sheet ? '  sayfa ' + f.sheet : ''}`);
    for (const item of f.items || []) {
      const at = item.pos ? ` (${item.pos.x}, ${item.pos.y} mm)` : '';
      output.appendLine(`      • ${item.description}${at}`);
    }
  }
}

async function refreshStatus() {
  const live = await health();
  if (live) {
    statusItem.text = '$(circuit-board) PcbAi';
    statusItem.tooltip = `PcbAi ${live.health.version} çalışıyor\n` + (live.health.projects || []).join('\n');
  } else {
    statusItem.text = '$(circuit-board) PcbAi: kapalı';
    statusItem.tooltip = 'PcbAi servisi çalışmıyor. Tıklayın: başlat';
  }
  statusItem.command = live ? 'pcbai.status' : 'pcbai.start';
}

const commands = {
  'pcbai.autoroute': () => engineCommand('autoroute'),
  'pcbai.autoplace': () => engineCommand('autoplace'),
  async 'pcbai.viewEmpty'() {
    const view = require('./board_view').openView(extensionContext, { stateDir: stateDir() });
    return view.whenReady;
  },
  async 'pcbai.view'() {
    const session = await pickSession();
    const document = await pickDocument(session, '.kicad_pcb');
    const viewCall = async (name, args) => {
      const live = await health();
      if (!live) throw new Error('PcbAi servisi çalışmıyor');
      return request(live.info, 'POST', '/view/call', { name, arguments: args });
    };
    const view = require('./board_view').openView(extensionContext,
      { stateDir: stateDir(), session, document, call, backgroundJob, viewCall });
    return view.whenLoaded;
  },
  async 'pcbai.view3d'() {
    const session = await pickSession();
    const document = await pickDocument(session, '.kicad_pcb');
    const view = require('./view3d').open3d(extensionContext, { stateDir: stateDir(), session, document, call, backgroundJob });
    return view.whenLoaded;
  },
  async 'pcbai.schematic'() {
    const session = await pickSession();
    const document = session.project.replace(/\.kicad_pro$/, '.kicad_sch');
    if (!(session.documents || []).includes(document)) throw new Error('Projenin kök şematiği yok: ' + document);
    const viewCall = async (name, args) => {
      const live = await health();
      if (!live) throw new Error('PcbAi servisi çalışmıyor');
      return request(live.info, 'POST', '/view/call', { name, arguments: args });
    };
    const view = require('./sch_view').openSchematic(extensionContext,
      { stateDir: stateDir(), session, document, call, backgroundJob, viewCall });
    return view.whenLoaded;
  },
  async 'pcbai.start'() {
    const live = await ensureService(await workspaceProjects());
    vscode.window.showInformationMessage(`PcbAi çalışıyor: ${(live.health.projects || []).length} proje`);
  },
  async 'pcbai.stop'() {
    vscode.window.showInformationMessage((await stopService()) ? 'PcbAi servisi durdu' : 'PcbAi servisi zaten kapalı');
  },
  async 'pcbai.status'() {
    const live = await health();
    output.show(true);
    if (!live) { output.appendLine('PcbAi servisi çalışmıyor.'); return; }
    const status = await call('pcbai_status');
    output.appendLine(`PcbAi ${status.version} · PID ${live.health.pid}`);
    for (const s of status.sessions || []) output.appendLine(`  ${s.id}  ${path.join(s.root, s.project)}  (${s.mode})`);
  },
  async 'pcbai.check'() {
    const session = await pickSession();
    output.show(true);
    output.appendLine(`\n${session.project} — kaydedilmiş dosyalar denetleniyor (açık editördeki kaydedilmemiş değişiklikler görülmez)`);
    const sch = rootDocument(session, '.kicad_sch');
    const pcb = rootDocument(session, '.kicad_pcb');
    const lines = [];
    if (sch) {
      output.appendLine(`ERC · ${sch}`);
      const r = await call('erc', { session: session.id, document: sch });
      printFindings(r);
      lines.push(r.ok ? r.summary : 'ERC çalışmadı');
    }
    if (pcb) {
      output.appendLine(`DRC · ${pcb}`);
      const r = await call('drc', { session: session.id, document: pcb, parity: Boolean(sch) });
      printFindings(r);
      lines.push(r.ok ? r.summary : 'DRC çalışmadı');
    }
    if (!lines.length) throw new Error('Projede şematik ya da kart dosyası yok');
    vscode.window.showInformationMessage(lines.join(' · '));
  },
  async 'pcbai.pdf'() {
    const session = await pickSession();
    const sch = rootDocument(session, '.kicad_sch');
    if (!sch) throw new Error('Projede şematik yok');
    const r = await call('schematic_pdf', { session: session.id, document: sch });
    if (!r.ok) throw new Error(r.summary);
    await vscode.env.openExternal(vscode.Uri.file(r.path));
  },
  async 'pcbai.render'() {
    const session = await pickSession();
    const document = await pickDocument(session, '.kicad_pcb');
    const response = await backgroundJob('render_board', session, document, { width: 1200, height: 900 });
    const exportsRoot = fs.realpathSync(path.join(stateDir(), 'exports'));
    const artifact = fs.realpathSync(response.path);
    const relative = path.relative(exportsRoot, artifact);
    if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || path.extname(artifact) !== '.png') {
      throw new Error('Kart görüntüsü PcbAi çıktı klasörünün dışında');
    }
    const panel = vscode.window.createWebviewPanel('pcbai.board', 'PcbAi · ' + document, vscode.ViewColumn.Beside,
      { enableScripts: false, localResourceRoots: [vscode.Uri.file(exportsRoot)] });
    const uri = panel.webview.asWebviewUri(vscode.Uri.file(artifact));
    panel.webview.html = renderHtml(panel.webview, uri.toString(), document, response.target.revision, response.dimensions);
  },
  async 'pcbai.stats'() {
    const session = await pickSession();
    const document = await pickDocument(session, '.kicad_pcb');
    const response = await backgroundJob('board_stats', session, document);
    output.show(true);
    output.appendLine(`\n${document} — kayıtlı kart ölçümleri (kanıt ${response.evidence_id})`);
    for (const measure of response.measurements) output.appendLine(`  ${measure.quantity}: ${measure.value} ${measure.unit}`);
  },
  async 'pcbai.addMcp'() {
    const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
    if (!folder) throw new Error('Açık çalışma alanı yok');
    const { root, python } = settings();
    const projects = (await workspaceProjects()).map((p) => path.resolve(p));
    const file = path.join(folder.uri.fsPath, '.mcp.json');
    let config = { mcpServers: {} };
    if (fs.existsSync(file)) {
      config = JSON.parse(fs.readFileSync(file, 'utf8')); // invalid JSON stops here: never overwrite the user's file
      config.mcpServers = config.mcpServers || {};
    }
    const entry = { command: python, args: ['-m', 'mcp_server.pcbai_mcp'],
      env: { PYTHONPATH: root, PCBAI_PROJECTS: JSON.stringify(projects) } };
    if (config.mcpServers.pcbai && JSON.stringify(config.mcpServers.pcbai) !== JSON.stringify(entry)) {
      const choice = await vscode.window.showWarningMessage('.mcp.json içinde farklı bir "pcbai" kaydı var. Değiştirilsin mi?',
        { modal: true }, 'Değiştir');
      if (choice !== 'Değiştir') return;
    }
    config.mcpServers.pcbai = entry;
    fs.writeFileSync(file, JSON.stringify(config, null, 2) + '\n', 'utf8');
    vscode.window.showInformationMessage(`PcbAi MCP kaydı yazıldı (${projects.length} proje). Claude Code'u yeniden başlatın.`);
  },
};

// Session for the side bar without prompts: the running service's session of the remembered/KiCad/workspace project.
async function sessionFor(interactive, change = false) {
  if (change && extensionContext) await extensionContext.globalState.update('pcbai.project', undefined);
  if (interactive) return pickSession();
  const live = await health();
  if (!live) return null;
  const status = await call('pcbai_status');
  const sessions = status.sessions || [];
  const wanted = [];
  const remembered = extensionContext && extensionContext.globalState.get('pcbai.project');
  if (remembered) wanted.push(remembered);
  wanted.push(...kicadProjects().open);
  for (const uri of await vscode.workspace.findFiles('**/*.kicad_pro', '**/{node_modules,.git,.venv,.tools,.pcbai-state}/**', 20)) {
    wanted.push(uri.fsPath);
  }
  for (const file of wanted) {
    const match = sessions.find((s) => samePath(path.join(s.root, s.project), file));
    if (match) return match;
  }
  return sessions.length === 1 ? sessions[0] : null;
}

function activate(context) {
  extensionContext = context;
  output = vscode.window.createOutputChannel('PcbAi');
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  statusItem.show();
  context.subscriptions.push(output, statusItem);
  if (vscode.window.registerWebviewViewProvider) {
    require('./sidebar_view').registerSidebar(context, { call, sessionFor });
  }
  for (const [name, fn] of Object.entries(commands)) {
    context.subscriptions.push(vscode.commands.registerCommand(name, async () => {
      try {
        return await fn();
      } catch (e) {
        output.appendLine('PcbAi: ' + e.message);
        if (e.message !== 'İptal edildi') vscode.window.showErrorMessage('PcbAi: ' + e.message);
        return { ok: false, error: e.message };
      } finally {
        refreshStatus();
      }
    }));
  }
  const timer = setInterval(refreshStatus, 15000);
  context.subscriptions.push({ dispose: () => clearInterval(timer) });
  refreshStatus();
}

function deactivate() {}

module.exports = { activate, deactivate, samePath, renderHtml };
