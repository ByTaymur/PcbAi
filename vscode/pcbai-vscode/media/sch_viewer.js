// Schematic webview: KiCad's own page SVG underneath, PcbAi's measured scene on top. File text is shown as text only.
const vscode = acquireVsCodeApi();
const $ = id => document.getElementById(id);
const board = $('board');
const NS = 'http://www.w3.org/2000/svg';
let data = null, selected = null, mode = 'select', points = [], pan = null, editingMarker = null;

// Tool drawer: open by default on wide panels, remembered per panel; the drawing always keeps the free space.
function savedState() { return vscode.getState() || {}; }
function setPanel(open) {
  document.body.classList.toggle('panel-hidden', !open);
  vscode.setState({ ...savedState(), panel: open });
  window.dispatchEvent(new Event('resize'));
}
setPanel(savedState().panel ?? window.innerWidth > 760);
document.getElementById('panel-toggle').addEventListener('click', () => setPanel(document.body.classList.contains('panel-hidden')));

function send(type, fields = {}) {
  vscode.postMessage({ type, generation: data?.generation, revision: data?.revision, ...fields });
}
function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
function matrix(m, [x, y]) { return [m[0]*x+m[2]*y+m[4], m[1]*x+m[3]*y+m[5]]; }
const toSvg = p => matrix(data.page.mm_to_svg, p);
function pointer(event) {
  const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(board.getScreenCTM().inverse());
  return matrix(data.page.svg_to_mm, [p.x, p.y]);
}
const box = () => board.getAttribute('viewBox').split(/\s+/).map(Number);
const setBox = b => board.setAttribute('viewBox', b.join(' '));
function fit() {
  if (!data) return;
  const b = data.page.viewbox;
  setBox([b[0]-b[2]*.03, b[1]-b[3]*.03, b[2]*1.06, b[3]*1.06]);
}
function segment(p, a, b) {
  const dx=b[0]-a[0], dy=b[1]-a[1], t=Math.max(0, Math.min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy || 1)));
  return Math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy);
}
function hit(p) {
  if (!data) return [];
  const rank = { pin: 0, sheet_pin: 1, junction: 2, label: 3, wire: 4, bus: 5, no_connect: 6, symbol: 7, sheet: 8 };
  // Tolerances follow the screen: ~6 px to hit, ~3 px counts as "on it" (a zoomed-out page is ~0.7 mm per px).
  const px = box()[2] / Math.max(board.clientWidth, 1);
  const tol = Math.min(Math.max(.6, 6 * px), 3), results = [];
  for (const i of data.scene.items) {
    const b = i.bbox;
    if (p[0] < b[0]-tol || p[1] < b[1]-tol || p[0] > b[2]+tol || p[1] > b[3]+tol) continue;
    let d;
    if (['wire', 'bus', 'pin'].includes(i.type)) d = Math.min(...i.points.slice(1).map((q, k) => segment(p, i.points[k], q)));
    else if (['junction', 'no_connect', 'sheet_pin'].includes(i.type)) d = Math.hypot(p[0]-i.at[0], p[1]-i.at[1]);
    else d = Math.hypot(Math.max(b[0]-p[0], 0, p[0]-b[2]), Math.max(b[1]-p[1], 0, p[1]-b[3]));
    if (d <= tol) results.push({ i, d });
  }
  // Within a small radius the item type decides (pin before wire before symbol), farther away the distance does.
  // Specific items (pin, wire, label…) win over the symbol/sheet box that contains them; among those, a very
  // close hit is ranked by type (pin before wire), a farther one by distance.
  const area = r => ['symbol', 'sheet'].includes(r.i.type) ? 1 : 0;
  const near = r => r.d <= Math.max(.15, 3 * px) ? 0 : 1;
  results.sort((a, b) => area(a) - area(b) || near(a) - near(b) || (near(a) ? a.d - b.d : 0) || rank[a.i.type] - rank[b.i.type] || a.d - b.d);
  return results.map(r => r.i);
}
const names = { symbol: 'sembol', pin: 'pin', wire: 'tel', bus: 'bus', label: 'etiket', junction: 'bağlantı',
  no_connect: 'bağlantısız', sheet: 'alt sayfa', sheet_pin: 'sayfa pini' };
function describe(i) {
  if (!i) return 'Seçim yok';
  const parts = [names[i.type] || i.type];
  if (i.type === 'symbol') parts.push(i.reference, i.value);
  if (i.type === 'pin') parts.push(i.reference + '.' + i.number, i.name);
  if (['label', 'sheet_pin'].includes(i.type)) parts.push(i.text);
  if (i.type === 'sheet') parts.push(i.name);
  if ('net' in i) parts.push(i.net ? 'net ' + i.net : 'net bilinmiyor');
  parts.push(i.at.map(v => v.toFixed(2)).join('; ') + ' mm');
  return parts.filter(Boolean).join(' · ');
}
function drawNet(net) {
  $('nets').replaceChildren();
  if (!net) return;
  for (const i of data.scene.items) {
    if (i.net !== net) continue;
    if (['wire', 'bus', 'pin'].includes(i.type)) $('nets').append(svg('polyline', { points: i.points.map(toSvg).map(p => p.join(',')).join(' '),
      fill: 'none', stroke: '#ff9f1c', 'stroke-width': .45, 'stroke-opacity': .85, 'data-uuid': i.uuid }));
    if (['pin', 'label', 'sheet_pin'].includes(i.type)) {
      const p = toSvg(i.at);
      $('nets').append(svg('circle', { cx: p[0], cy: p[1], r: .7, fill: '#ff9f1c', 'fill-opacity': .7, 'data-uuid': i.uuid }));
    }
  }
}
function details(i) {
  const panel = $('details');
  panel.replaceChildren();
  if (!i) { panel.textContent = 'Seçim yok'; return; }
  const rows = [['Tür', names[i.type] || i.type]];
  if (i.type === 'symbol') rows.push(['Referans', i.reference], ['Değer', i.value], ['Kütüphane', i.lib_id], ['Birim', i.unit], ['Footprint', i.footprint]);
  if (i.type === 'pin') rows.push(['Pin', i.reference + '.' + i.number], ['Ad', i.name], ['Elektrik türü', i.electrical]);
  if (['label', 'sheet_pin'].includes(i.type)) rows.push(['Metin', i.text], ['Tür', i.kind || i.electrical]);
  if (i.type === 'sheet') rows.push(['Sayfa', i.name], ['Dosya', i.file]);
  if ('net' in i) rows.push(['Net', i.net || 'bilinmiyor (netlistte pin yok)']);
  for (const [key, value] of rows) if (value !== undefined && value !== '') {
    const row = el('p'); row.append(el('strong', key + ': '), document.createTextNode(String(value))); panel.append(row);
  }
  if (i.type === 'sheet') {
    const go = el('button', 'Alt sayfaya git'); go.dataset.instance = i.instance;
    go.addEventListener('click', () => openPage(i.instance)); panel.append(go);
  }
  if (i.net) {
    const members = data.net_members[i.net] || [], here = data.page.instance;
    const local = data.scene.items.filter(x => x.type === 'pin' && x.net === i.net).length;
    const elsewhere = new Map();
    for (const m of members) if (m.sheet && m.sheet !== here) elsewhere.set(m.sheet, (elsewhere.get(m.sheet) || 0) + 1);
    const summary = el('p', `Bu sayfada ${local} pin · netlistte toplam ${members.length} pin`); summary.id = 'net-summary';
    panel.append(summary);
    for (const [instance, count] of elsewhere) {
      const page = data.pages.find(p => p.instance === instance);
      const go = el('button', `${page ? page.names : instance}: ${count} pin`); go.className = 'net-page';
      go.addEventListener('click', () => openPage(instance)); panel.append(go);
    }
  }
}
function select(i) {
  selected = i; $('info').textContent = describe(i); $('info').dataset.uuid = i?.uuid || '';
  $('selection').replaceChildren(); $('choices').hidden = true;
  details(i); drawNet(i?.net);
  if (i) {
    const a = toSvg(i.bbox.slice(0, 2)), b = toSvg(i.bbox.slice(2));
    $('selection').append(svg('rect', { x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(b[0]-a[0]),
      height: Math.abs(b[1]-a[1]), fill: 'none', stroke: '#7ff5e8', 'stroke-width': .25 }));
  }
}
function openPage(instance) { $('error').textContent = 'Sayfa yükleniyor…'; send('page', { instance }); }
function drawPages() {
  $('pages').replaceChildren();
  for (const p of data.pages) {
    const depth = p.names.split('/').filter(Boolean).length;
    const button = el('button', (p.names === '/' ? 'Kök' : p.names.split('/').filter(Boolean).at(-1)) + ' · ' + p.number);
    button.style.marginLeft = (depth * 14) + 'px'; button.dataset.instance = p.instance; button.title = p.names + ' · ' + p.document;
    button.classList.toggle('active', p.instance === data.page.instance);
    button.addEventListener('click', () => openPage(p.instance));
    $('pages').append(button);
  }
  const parent = data.page.instance.split('/').slice(0, -1).join('/');
  $('up').disabled = !data.pages.some(p => p.instance === parent);
  $('up').onclick = () => openPage(parent);
}
function setMode(m) {
  mode = m; points = []; $('draft').replaceChildren();
  if (m !== 'select') { editingMarker = null; $('edit-preview').hidden = true; }
  for (const b of document.querySelectorAll('[data-tool]')) b.classList.toggle('active', b.dataset.tool === m);
  $('instruction').textContent = m === 'select' ? 'Tıkla: seç · Çift tıkla: alt sayfa · Sürükle: kaydır · Tekerlek: yakınlaştır · Oklar / + − / 0' :
    m === 'area' ? 'Alan köşelerini tıklayın, sonra Alanı bitir. Esc: iptal.' : 'İşaret konumunu tıklayın. Esc: iptal.';
}
function draftPreview(kind, pts, anchor) {
  if (!$('note').value.trim()) { askNote(() => draftPreview(kind, pts, anchor)); return; }
  const marker = { kind, space: 'sch', points_mm: pts, note: $('note').value };
  if (anchor) marker.anchor = { type: anchor.type, uuid: anchor.uuid };
  send('markerPreview', { marker }); setMode('select');
}
function drawMarkers() {
  $('marker-shapes').replaceChildren(); $('marker-list').replaceChildren();
  for (const m of data?.markers || []) {
    const pts = m.points_mm.map(toSvg), color = m.trusted ? '#ffd476' : '#f78b8b', p = pts[0];
    if (pts.length > 1) $('marker-shapes').append(svg('polygon', { points: pts.map(q => q.join(',')).join(' '), fill: '#ffd47633', stroke: color, 'stroke-width': .25 }));
    $('marker-shapes').append(svg('circle', { cx: p[0], cy: p[1], r: 1.2, fill: color }),
      svg('text', { x: p[0], y: p[1] + .45, 'text-anchor': 'middle', 'font-size': 1.3, fill: '#151a20' }, m.n));
    const item = el('div', undefined, 'marker'); item.dataset.n = m.n;
    const target = m.target_item ? ' · ' + [m.target_item.reference, m.target_item.number && 'pin ' + m.target_item.number, m.target_item.value].filter(Boolean).join(' ') : '';
    item.append(el('strong', '#' + m.n), el('span', ' · ' + m.status + ' · ' + m.binding + target + (m.trusted ? '' : ' · onaysız'), 'badge'), el('p', m.note));
    if (m.reason || m.evidence_id) item.append(el('p', [m.reason, m.evidence_id].filter(Boolean).join(' · ')));
    for (const [label, action] of [
      ['Göster', () => { const b = box(), q = toSvg(m.points_mm[0]); setBox([q[0]-b[2]/2, q[1]-b[3]/2, b[2], b[3]]); }],
      ['Düzenle', () => { editingMarker = m; $('note').value = m.note; $('edit-preview').hidden = false; $('note').focus(); }],
      ['Sil', () => send('markerPreview', { n: m.n, delete: true })], ['Ajana sor', () => send('ask', { n: m.n })]]) {
      const button = el('button', label); button.addEventListener('click', action); item.append(button);
    }
    $('marker-list').append(item);
  }
}
function drawFindings(findings, summary, evidence) {
  $('findings').replaceChildren(); $('finding-list').replaceChildren();
  $('finding-list').append(el('p', summary + ' · ' + evidence));
  const byUuid = new Map(data.scene.items.filter(i => i.uuid).map(i => [i.uuid, i]));
  // Measured on KiCad 10.0.4: ERC JSON positions are not sheet mm (100x smaller) and some findings name the
  // wrong sheet (video: C56 on /graphic/ reported under /). Only an item UUID found on this page places a mark.
  let drawn = 0, unplaced = 0, shown = 0;
  for (const f of findings) {
    const items = (f.items || []).map(item => byUuid.get(item.uuid)).filter(Boolean);
    if (f.sheet !== data.page.names && !items.length) continue;
    shown++;
    $('finding-list').append(el('p', f.severity + ': ' + f.description));
    unplaced += (f.items || []).length - items.length;
    for (const match of items) {
      const p = toSvg(match.at); drawn++;
      $('findings').append(svg('circle', { cx: p[0], cy: p[1], r: 1.6, fill: 'none', stroke: f.severity === 'error' ? '#ff647a' : '#ffd476', 'stroke-width': .35 }));
    }
  }
  if (findings.length - shown) $('finding-list').append(el('p', `${findings.length - shown} bulgu diğer sayfalarda.`));
  if (unplaced) $('finding-list').append(el('p', `${unplaced} öğe bu sayfada bulunamadı; çizilmedi.`));
  $('finding-list').dataset.drawn = drawn;
}
window.addEventListener('message', event => {
  const m = event.data;
  if (m?.type === 'scene') {
    const samePage = data && data.page.instance === m.page.instance;
    data = m; setMode('select'); editingMarker = null; $('edit-preview').hidden = true; $('preview').hidden = true;
    $('error').textContent = (m.scene.warnings || []).join('\n');
    $('document').textContent = m.page.names + ' · ' + m.document;
    $('revision').textContent = 'Kaydedilmiş dosya · ' + m.revision.slice(0, 12); $('empty').hidden = true;
    const b = m.page.viewbox;
    $('images').replaceChildren(svg('image', { href: m.page.uri, x: b[0], y: b[1], width: b[2], height: b[3], preserveAspectRatio: 'none' }));
    $('findings').replaceChildren(); $('finding-list').textContent = 'Henüz çalıştırılmadı';
    drawPages(); drawMarkers(); select(null);
    if (!samePage) fit();
    vscode.setState({ ...savedState(), sheet: m.page.instance });
    const image = new Image();
    image.onload = () => vscode.postMessage({ type: 'sceneReady', generation: m.generation, revision: m.revision });
    image.onerror = () => { $('error').textContent = 'Sayfa SVG yüklenemedi'; };
    image.src = m.page.uri;
  } else if (m?.type === 'markers' && data && m.generation === data.generation) {
    data.markers = m.markers; data.markers_revision = m.markers_revision; drawMarkers(); $('preview').hidden = true;
  } else if (m?.type === 'preview' && data && m.generation === data.generation) {
    $('preview').hidden = false;
    confirmPreview(m.deleting ? 'İşaret silinsin mi?' : 'Kaydedilecek: ' + m.marker.note);
    $('preview-text').textContent = m.deleting ? 'İşaret silinecek.' : 'Kaydedilecek not: ' + m.marker.note;
  } else if (m?.type === 'erc' && data && m.generation === data.generation) drawFindings(m.findings, m.summary, m.evidence);
  else if (m?.type === 'error') { $('error').textContent = m.message; $('preview').hidden = true; }
  else if (m?.type === 'notice' || m?.type === 'busy') $('error').textContent = m.message;
});
board.addEventListener('wheel', event => {
  if (!data) return; event.preventDefault();
  const p = toSvg(pointer(event)), b = box(), factor = event.deltaY > 0 ? 1.12 : 1 / 1.12;
  if (b[2] * factor < .5 || b[2] * factor > 1e5) return;
  setBox([p[0]-(p[0]-b[0])*factor, p[1]-(p[1]-b[1])*factor, b[2]*factor, b[3]*factor]);
}, { passive: false });
// Navigation: drag with any mouse button pans (a press that moves < 4 px stays a click/selection);
// wheel zooms at the cursor; arrows pan, + / - zoom, 0 fits.
let dragged = false;
function panTo(event) {
  const a = new DOMPoint(pan.x, pan.y).matrixTransform(pan.m), b = new DOMPoint(event.clientX, event.clientY).matrixTransform(pan.m);
  setBox([pan.b[0] + a.x - b.x, pan.b[1] + a.y - b.y, pan.b[2], pan.b[3]]);
}
board.addEventListener('pointerdown', event => {
  if (!data) return;
  pan = { x: event.clientX, y: event.clientY, b: box(), m: board.getScreenCTM().inverse(), id: event.pointerId,
    active: event.button !== 0 || event.altKey };
  dragged = false;
  if (pan.active) { event.preventDefault(); board.setPointerCapture(event.pointerId); board.classList.add('panning'); }
});
board.addEventListener('pointerup', event => {
  if (!pan) return;
  if (pan.active && board.hasPointerCapture(event.pointerId)) board.releasePointerCapture(event.pointerId);
  board.classList.remove('panning');
  pan = null;
});
board.addEventListener('pointercancel', () => { pan = null; board.classList.remove('panning'); });
board.addEventListener('contextmenu', event => event.preventDefault());
function zoomBy(factor) {
  const b = box(), cx = b[0] + b[2] / 2, cy = b[1] + b[3] / 2;
  if (b[2] * factor < .05 || b[2] * factor > 1e5) return;
  setBox([cx - b[2] * factor / 2, cy - b[3] * factor / 2, b[2] * factor, b[3] * factor]);
}
window.addEventListener('keydown', event => {
  if (!data || /^(TEXTAREA|INPUT|SELECT)$/.test(event.target?.tagName || '')) return;
  const b = box(), step = event.shiftKey ? .5 : .15;
  const moves = { ArrowLeft: [-b[2] * step, 0], ArrowRight: [b[2] * step, 0], ArrowUp: [0, -b[3] * step], ArrowDown: [0, b[3] * step] };
  if (moves[event.key]) { event.preventDefault(); setBox([b[0] + moves[event.key][0], b[1] + moves[event.key][1], b[2], b[3]]); }
  else if (event.key === '+' || event.key === '=') zoomBy(1 / 1.25);
  else if (event.key === '-' || event.key === '_') zoomBy(1.25);
  else if (event.key === '0') fit();
});
board.addEventListener('pointermove', event => {
  if (!data) return;
  if (pan) {
    if (!pan.active && Math.hypot(event.clientX - pan.x, event.clientY - pan.y) >= 4) {
      pan.active = true; board.setPointerCapture(pan.id); board.classList.add('panning');
    }
    if (pan.active) { dragged = true; panTo(event); return; }
  }
  const p = pointer(event); $('cursor').textContent = p.map(v => v.toFixed(2)).join('; ') + ' mm';
  if (!selected) $('info').textContent = describe(hit(p)[0]);
});
board.addEventListener('click', event => {
  if (dragged) { dragged = false; return; }
  if (!data || event.altKey || event.button !== 0) return;
  const p = pointer(event);
  if (mode === 'select') {
    const items = hit(p); select(items[0] || null);
    const choices = $('choices'); choices.replaceChildren();
    for (const item of items) { const option = el('option', describe(item)); option.value = item.uuid; choices.append(option); }
    choices.hidden = items.length < 2;
  } else if (mode === 'point') draftPreview('point', [p]);
  else { points.push(p); $('draft').replaceChildren(svg('polyline', { points: points.map(toSvg).map(q => q.join(',')).join(' '), fill: 'none', stroke: '#77cfcc', 'stroke-width': .25 })); }
});
board.addEventListener('dblclick', event => {
  if (!data) return;
  const sheet = hit(pointer(event)).find(i => i.type === 'sheet');
  if (sheet) openPage(sheet.instance);
  else if (!hit(pointer(event)).length) fit();
});
for (const b of document.querySelectorAll('[data-tool]')) b.addEventListener('click', () => setMode(b.dataset.tool));
$('fit').addEventListener('click', fit); $('refresh').addEventListener('click', () => send('refresh'));
$('finish').addEventListener('click', () => { if (mode === 'area' && points.length >= 3) draftPreview('area', [...points]); });
$('anchor').addEventListener('click', () => { if (selected?.uuid) draftPreview('item', [selected.at], selected); else $('error').textContent = 'Önce kimliği olan bir öğe seçin.'; });
$('apply').addEventListener('click', () => { send('markerApply'); $('preview').hidden = true; });
$('cancel').addEventListener('click', () => { send('markerCancel'); $('preview').hidden = true; });
$('erc').addEventListener('click', () => { $('finding-list').textContent = 'ERC çalışıyor…'; send('erc'); });
$('edit-preview').addEventListener('click', () => {
  if (!editingMarker) return; const m = editingMarker;
  const marker = { kind: m.kind, space: 'sch', points_mm: m.points_mm, note: $('note').value };
  if (m.anchor) marker.anchor = m.anchor;
  send('markerPreview', { n: m.n, marker, approve: $('approve').checked });
});
$('choices').addEventListener('change', () => { select(data.scene.items.find(i => i.uuid === $('choices').value)); });
window.addEventListener('keydown', event => { if (event.key === 'Escape') { setMode('select'); $('preview').hidden = true; send('markerCancel'); } });
// Mouse-first use: right click opens a context menu for whatever is under the cursor; marker notes are typed
// in a small box next to the cursor and the preview is confirmed there too. Text is set with textContent only.
let lastPointer = { x: 40, y: 40 };
board.addEventListener('pointermove', event => { lastPointer = { x: event.clientX, y: event.clientY }; });
const floating = document.createElement('div'); floating.className = 'floating'; floating.hidden = true;
document.body.append(floating);
function closeFloating() { floating.hidden = true; floating.replaceChildren(); }
function place(x, y) {
  floating.hidden = false;
  const w = floating.offsetWidth, h = floating.offsetHeight;
  floating.style.left = Math.max(4, Math.min(x, window.innerWidth - w - 4)) + 'px';
  floating.style.top = Math.max(4, Math.min(y, window.innerHeight - h - 4)) + 'px';
}
function askNote(then) {
  closeFloating();
  const title = document.createElement('strong'); title.textContent = 'İşaret notu';
  const text = document.createElement('textarea'); text.rows = 3; text.maxLength = 4096; text.value = $('note').value;
  text.placeholder = 'Örn. bu hat 1 mm olsun';
  const ok = document.createElement('button'); ok.textContent = 'Önizle'; ok.className = 'primary';
  const cancel = document.createElement('button'); cancel.textContent = 'Vazgeç';
  const row = document.createElement('div'); row.className = 'row'; row.append(ok, cancel);
  floating.append(title, text, row);
  place(lastPointer.x + 8, lastPointer.y + 8);
  text.focus();
  const submit = () => { if (!text.value.trim()) { text.focus(); return; } $('note').value = text.value; closeFloating(); then(); };
  ok.addEventListener('click', submit);
  cancel.addEventListener('click', () => { closeFloating(); setMode('select'); });
  text.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(); } });
}
function confirmPreview(message) {
  closeFloating();
  const text = document.createElement('p'); text.textContent = message;
  const ok = document.createElement('button'); ok.textContent = 'Kaydet'; ok.className = 'primary';
  const cancel = document.createElement('button'); cancel.textContent = 'Vazgeç';
  const row = document.createElement('div'); row.className = 'row'; row.append(ok, cancel);
  floating.append(text, row);
  place(lastPointer.x + 8, lastPointer.y + 8);
  ok.addEventListener('click', () => { closeFloating(); $('apply').click(); $('note').value = ''; });
  cancel.addEventListener('click', () => { closeFloating(); $('cancel').click(); });
}
function openMenu(x, y, entries) {
  closeFloating();
  const menu = document.createElement('div'); menu.className = 'menu';
  for (const entry of entries) {
    if (entry === '-') { menu.append(document.createElement('hr')); continue; }
    const button = document.createElement('button'); button.textContent = entry[0]; button.disabled = entry[2] === false;
    button.addEventListener('click', () => { closeFloating(); entry[1](); });
    menu.append(button);
  }
  floating.append(menu);
  place(x, y);
}
function zoomAt(p, factor) {
  const q = toSvg(p), b = box();
  setBox([q[0] - (q[0] - b[0]) * factor, q[1] - (q[1] - b[1]) * factor, b[2] * factor, b[3] * factor]);
}
board.addEventListener('contextmenu', event => {
  event.preventDefault();
  if (!data) return;
  if (dragged) { dragged = false; return; }
  lastPointer = { x: event.clientX, y: event.clientY };
  const p = pointer(event);
  if (mode === 'area' && points.length >= 3) { draftPreview('area', [...points]); return; }
  if (mode === 'line' || mode === 'area' || mode === 'point') { setMode('select'); return; }
  const item = hit(p)[0];
  const entries = [];
  if (item) {
    entries.push(['Seç: ' + describe(item), () => select(item)]);
    if (item.uuid) entries.push(['Bu öğeye işaret koy…', () => { select(item); askNote(() => draftPreview('item', [item.at], item)); }]);
    if (item.type === 'sheet' && typeof openPage === 'function') entries.push(['Alt sayfaya git', () => openPage(item.instance)]);
  }
  entries.push(['Buraya işaret koy…', () => askNote(() => draftPreview('point', [p]))]);
  if (document.querySelector('[data-tool="line"]')) entries.push(['Çizgi işareti çiz (2 tık)', () => setMode('line')]);
  entries.push(['Alan işareti çiz (sağ tık: bitir)', () => setMode('area')]);
  entries.push('-');
  entries.push(['Buraya yakınlaştır', () => zoomAt(p, 1 / 2)], ['Uzaklaştır', () => zoomAt(p, 2)], ['Sığdır', fit]);
  if ($('up')) entries.push(['Üst sayfa', () => $('up').click(), !$('up').disabled]);
  entries.push('-');
  if ($('drc')) entries.push(['DRC çalıştır', () => { setPanel(true); $('drc').click(); }]);
  if ($('erc')) entries.push(['ERC çalıştır', () => { setPanel(true); $('erc').click(); }]);
  entries.push(['Yenile', () => $('refresh').click()]);
  entries.push([document.body.classList.contains('panel-hidden') ? 'Paneli aç' : 'Paneli kapat',
    () => setPanel(document.body.classList.contains('panel-hidden'))]);
  openMenu(event.clientX, event.clientY, entries);
});
document.addEventListener('pointerdown', event => { if (!floating.hidden && !floating.contains(event.target)) closeFloating(); }, true);
window.addEventListener('keydown', event => { if (event.key === 'Escape') closeFloating(); });
send('ready');
