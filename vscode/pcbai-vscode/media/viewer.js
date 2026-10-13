import { REVISION } from './vendor/three-bundle.js';

const vscode = acquireVsCodeApi();
const $ = id => document.getElementById(id);
const board = $('board');
const NS = 'http://www.w3.org/2000/svg';
let data = null, selected = null, mode = 'select', points = [], pan = null;
let editingMarker = null;
const visibleLayers = new Set();
const initialState = vscode.getState() || {};

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
function matrix(m, [x,y]) { return [m[0]*x+m[2]*y+m[4], m[1]*x+m[3]*y+m[5]]; }
function toSvg(point) { return matrix(data.render.mm_to_svg, point); }
function pointer(event) {
  const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(board.getScreenCTM().inverse());
  return matrix(data.render.svg_to_mm, [p.x, p.y]);
}
function box() { return board.getAttribute('viewBox').split(/\s+/).map(Number); }
function setBox(b) { board.setAttribute('viewBox', b.join(' ')); }
function fit() {
  if (!data) return;
  const b = data.render.viewbox;
  setBox([b[0]-b[2]*.06, b[1]-b[3]*.06, b[2]*1.12, b[3]*1.12]);
}
function polygonInside(p, poly) {
  let yes = false;
  for (let i=0,j=poly.length-1;i<poly.length;j=i++) {
    const a=poly[i], b=poly[j];
    if ((a[1]>p[1]) !== (b[1]>p[1]) && p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]) yes=!yes;
  }
  return yes;
}
function distance(p, poly) {
  let best=Infinity;
  for(let i=1;i<poly.length;i++) {
    const a=poly[i-1],b=poly[i],dx=b[0]-a[0],dy=b[1]-a[1];
    const t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy || 1)));
    best=Math.min(best,Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy));
  }
  return best;
}
function isVisible(i) {
  const own=i.layers || [i.layer];
  return [...visibleLayers].some(l => own.includes(l) || own.includes('*.Cu') && l.endsWith('.Cu') ||
    own.includes('F&B.Cu') && ['F.Cu','B.Cu'].includes(l));
}
function hit(p) {
  if (!data) return null;
  const priority={pad:0,via:1,track:2,footprint:3,edge:4,zone:5}, results=[];
  const tol=Math.min(.5, box()[2]/Math.max(board.clientWidth,1)*5);
  for(const i of data.scene.items) {
    if(!isVisible(i)) continue;
    const b=i.bbox;
    if(p[0]<b[0]-tol || p[1]<b[1]-tol || p[0]>b[2]+tol || p[1]>b[3]+tol) continue;
    let d=0;
    if(['track','edge'].includes(i.type)) d=Math.max(0,distance(p,i.points)-i.width/2);
    else if(i.type==='zone') d=i.polygons.some(q=>(!q.layer || visibleLayers.has(q.layer)) && polygonInside(p,q.points)) ? 0 : Infinity;
    else if(i.type==='via' || i.type==='pad' && i.shape==='circle') d=Math.max(0,Math.hypot(p[0]-i.at[0],p[1]-i.at[1])-i.size[0]/2);
    else if(i.type==='pad' && ['oval','roundrect'].includes(i.shape)) {
      const angle=-i.rotation*Math.PI/180,dx=p[0]-i.at[0],dy=p[1]-i.at[1];
      const x=dx*Math.cos(angle)+dy*Math.sin(angle),y=-dx*Math.sin(angle)+dy*Math.cos(angle);
      const [w,h]=i.size,r=Math.min(w,h)*(i.shape==='oval'?.5:i.roundrect_ratio);
      const qx=Math.abs(x)-w/2+r,qy=Math.abs(y)-h/2+r;
      d=Math.max(0,Math.hypot(Math.max(qx,0),Math.max(qy,0))+Math.min(Math.max(qx,qy),0)-r);
    } else if(i.type==='pad') d=polygonInside(p,i.polygon) ? 0 : distance(p,[...i.polygon,i.polygon[0]]);
    else d=Math.hypot(Math.max(b[0]-p[0],0,p[0]-b[2]),Math.max(b[1]-p[1],0,p[1]-b[3]));
    if(d<=tol) results.push({i,d});
  }
  const rank=i=>i.type==='footprint' && Math.hypot(p[0]-i.at[0],p[1]-i.at[1])<=.2 ? -1 : priority[i.type];
  results.sort((a,b)=>a.d-b.d || rank(a.i)-rank(b.i));
  return results.map(r=>r.i);
}
function describe(i) {
  return i ? [i.reference,i.type,i.number && 'pad '+i.number,i.value,i.net,i.layer,
    i.at.map(v=>v.toFixed(2)).join('; ')+' mm'].filter(Boolean).join(' · ') : 'Seçim yok';
}
function select(i) {
  selected=i; $('info').textContent=describe(i); $('info').dataset.uuid=i?.uuid || '';
  $('selection').replaceChildren();
  $('choices').hidden=true;
  if(i) {
    const a=toSvg(i.bbox.slice(0,2)),b=toSvg(i.bbox.slice(2));
    $('selection').append(svg('rect',{x:a[0],y:a[1],width:b[0]-a[0],height:b[1]-a[1],fill:'none',stroke:'#7ff5e8','stroke-width':.2}));
  }
}
function setMode(m) {
  mode=m; points=[]; $('draft').replaceChildren();
  if(m!=='select') {editingMarker=null;$('edit-preview').hidden=true;}
  for(const b of document.querySelectorAll('[data-tool]')) b.classList.toggle('active',b.dataset.tool===m);
  $('instruction').textContent=m==='select' ? 'Tıkla: seç · Sürükle: kaydır · Tekerlek: yakınlaştır · Oklar / + − / 0: gezin, sığdır' :
    m==='area' ? 'Alan köşelerini tıklayın, sonra Alanı bitir. Esc: iptal.' : m==='line' ? 'Çizginin iki ucunu tıklayın. Esc: iptal.' : 'İşaret konumunu tıklayın. Esc: iptal.';
}
function draftPreview(kind, pts, anchor) {
  if(!$('note').value.trim()) { askNote(()=>draftPreview(kind,pts,anchor)); return; }
  const marker={kind,space:'pcb',points_mm:pts,note:$('note').value};
  if(anchor) { marker.anchor={type:anchor.type,uuid:anchor.uuid}; marker.layer=anchor.layer || [...visibleLayers][0]; }
  send('markerPreview',{marker}); setMode('select');
}
function drawMarkers() {
  $('marker-shapes').replaceChildren(); $('marker-list').replaceChildren();
  for(const m of data?.markers || []) {
    const pts=m.points_mm.map(toSvg), color=m.trusted ? '#ffd476' : '#f78b8b';
    const p=pts[0];
    if(pts.length>1) $('marker-shapes').append(svg(m.kind==='area'?'polygon':'polyline',{
      points:pts.map(p=>p.join(',')).join(' '),fill:m.kind==='area'?'#ffd47633':'none',stroke:color,'stroke-width':.2}));
    $('marker-shapes').append(svg('circle',{cx:p[0],cy:p[1],r:.8,fill:color}),
      svg('text',{x:p[0],y:p[1]+.3,'text-anchor':'middle','font-size':.85,fill:'#151a20'},m.n));
    const item=document.createElement('div');item.className='marker';item.dataset.n=m.n;
    const name=document.createElement('strong');name.textContent='#'+m.n;
    const badge=document.createElement('span');badge.className='badge';badge.textContent=' · '+m.status+' · '+m.binding+(m.trusted?'':' · onaysız');
    const note=document.createElement('p');note.textContent=m.note;
    item.append(name,badge,note);
    if(m.reason || m.evidence_id) {const reason=document.createElement('p');reason.textContent=[m.reason,m.evidence_id].filter(Boolean).join(' · ');item.append(reason);}
    for(const [label,action] of [['Göster',()=>{select(null);const b=box(),p=toSvg(m.points_mm[0]);setBox([p[0]-b[2]/2,p[1]-b[3]/2,b[2],b[3]]);}],
      ['Düzenle',()=>{editingMarker=m;$('note').value=m.note;$('edit-preview').hidden=false;$('note').focus();
        $('instruction').textContent='#'+m.n+' notunu düzenleyip Notu önizle düğmesine basın.';}],
      ['Sil',()=>send('markerPreview',{n:m.n,delete:true})],['Ajana sor',()=>send('ask',{n:m.n})]]) {
      const button=document.createElement('button');button.textContent=label;button.addEventListener('click',action);item.append(button);
    }
    $('marker-list').append(item);
  }
}
function drawFindings(findings, summary, evidence) {
  $('findings').replaceChildren();$('finding-list').replaceChildren();
  const title=document.createElement('p');title.textContent=summary+' · '+evidence;$('finding-list').append(title);
  for(const finding of findings) {
    const row=document.createElement('p');row.textContent=finding.severity+': '+finding.description;$('finding-list').append(row);
    for(const item of finding.items || []) if(Number.isFinite(item.pos?.x) && Number.isFinite(item.pos?.y)) {
      const p=toSvg([item.pos.x,item.pos.y]);
      $('findings').append(svg('circle',{cx:p[0],cy:p[1],r:1,fill:'none',stroke:finding.severity==='error'?'#ff647a':'#ffd476','stroke-width':.25}));
    }
  }
}
window.addEventListener('message',event=>{
  const m=event.data;
  if(m?.type==='scene') {
    const first=!data; const oldVisible=new Set(visibleLayers);data=m;select(null);setMode('select');editingMarker=null;$('edit-preview').hidden=true;
    $('error').textContent=(m.scene.warnings || []).join('\n');$('document').textContent=m.document;
    $('revision').textContent='Kaydedilmiş dosya · '+m.revision.slice(0,12);$('empty').hidden=true;$('preview').hidden=true;
    $('images').replaceChildren();$('layers').replaceChildren();visibleLayers.clear();
    for(const layer of m.render.layers) {
      const enabled=first ? (initialState.layers ? initialState.layers.includes(layer.name) : !layer.name.includes('.Fab') && !layer.name.startsWith('B.')) : oldVisible.has(layer.name);
      if(enabled) visibleLayers.add(layer.name);
      const b=m.render.viewbox;const image=svg('image',{href:layer.uri,x:b[0],y:b[1],width:b[2],height:b[3],preserveAspectRatio:'none'});
      image.hidden=!enabled;image.setAttribute('display',enabled?'inline':'none');image.dataset.layer=layer.name;$('images').append(image);
      const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=enabled;input.dataset.layer=layer.name;
      input.addEventListener('change',()=>{if(input.checked)visibleLayers.add(layer.name);else visibleLayers.delete(layer.name);
        image.setAttribute('display',input.checked?'inline':'none');select(null);vscode.setState({...savedState(),layers:[...visibleLayers]});});
      label.append(input,document.createTextNode(' '+layer.name));$('layers').append(label);
    }
    $('findings').replaceChildren();$('finding-list').textContent='Henüz çalıştırılmadı';drawMarkers();if(first)fit();
    const generation=m.generation,revision=m.revision;
    Promise.all(m.render.layers.map(layer=>new Promise((resolve,reject)=>{
      const image=new Image();image.onload=resolve;image.onerror=()=>reject(new Error('Katman SVG yüklenemedi: '+layer.name));image.src=layer.uri;
    }))).then(()=>vscode.postMessage({type:'sceneReady',generation,revision,layerCount:m.render.layers.length}))
      .catch(error=>{$('error').textContent=error.message;});
  } else if(m?.type==='markers' && data && m.generation===data.generation) {
    data.markers=m.markers;data.markers_revision=m.markers_revision;drawMarkers();$('preview').hidden=true;editingMarker=null;$('edit-preview').hidden=true;
  } else if(m?.type==='preview' && data && m.generation===data.generation) {
    $('preview').hidden=false;confirmPreview(m.deleting ? 'İşaret silinsin mi?' : 'Kaydedilecek: '+m.marker.note);
    $('preview-text').textContent=m.deleting ? 'İşaret silinecek.' : 'Kaydedilecek not: '+m.marker.note+'\n'+m.marker.points_mm.map(p=>p.map(v=>v.toFixed(2)).join('; ')+' mm').join('\n');
  } else if(m?.type==='drc' && data && m.generation===data.generation) drawFindings(m.findings,m.summary,m.evidence);
  else if(m?.type==='error') { $('error').textContent=m.message; $('preview').hidden=true; }
  else if(m?.type==='notice') $('error').textContent=m.message;
});
board.addEventListener('wheel',event=>{
  if(!data)return;event.preventDefault();const p=toSvg(pointer(event)),b=box(),factor=event.deltaY>0?1.12:1/1.12;
  if(b[2]*factor<.05 || b[2]*factor>1e5)return;
  setBox([p[0]-(p[0]-b[0])*factor,p[1]-(p[1]-b[1])*factor,b[2]*factor,b[3]*factor]);
},{passive:false});
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
board.addEventListener('pointermove',event=>{
  if(!data)return;
  if(pan) {
    if(!pan.active && Math.hypot(event.clientX-pan.x,event.clientY-pan.y)>=4){pan.active=true;board.setPointerCapture(pan.id);board.classList.add('panning');}
    if(pan.active){dragged=true;panTo(event);return;}
  }
  const p=pointer(event);$('cursor').textContent=p.map(v=>v.toFixed(2)).join('; ')+' mm';
  const item=hit(p)[0];board.setAttribute('aria-description',describe(item));
  if(!selected)$('info').textContent=describe(item);
});
board.addEventListener('click',event=>{
  if(dragged){dragged=false;return;}
  if(!data || event.altKey || event.button!==0)return;
  const p=pointer(event);
  if(mode==='select') {
    const items=hit(p);select(items[0] || null);
    const choices=$('choices');choices.replaceChildren();
    for(const item of items) {const option=document.createElement('option');option.value=item.uuid;option.textContent=describe(item);choices.append(option);}
    choices.hidden=items.length<2;
  }
  else if(mode==='point')draftPreview('point',[p]);
  else {points.push(p);$('draft').replaceChildren(svg('polyline',{points:points.map(toSvg).map(p=>p.join(',')).join(' '),fill:'none',stroke:'#77cfcc','stroke-width':.2}));
    if(mode==='line' && points.length===2)draftPreview('line',[...points]);}
});
for(const b of document.querySelectorAll('[data-tool]'))b.addEventListener('click',()=>setMode(b.dataset.tool));
$('fit').addEventListener('click',fit);$('refresh').addEventListener('click',()=>send('refresh'));
$('finish').addEventListener('click',()=>{if(mode==='area' && points.length>=3)draftPreview('area',[...points]);});
$('anchor').addEventListener('click',()=>{if(selected)draftPreview('item',[selected.at],selected);else $('error').textContent='Önce bir öğe seçin.';});
$('apply').addEventListener('click',()=>{send('markerApply');$('preview').hidden=true;});
$('cancel').addEventListener('click',()=>{send('markerCancel');$('preview').hidden=true;});
$('drc').addEventListener('click',()=>send('drc'));
$('edit-preview').addEventListener('click',()=>{
  if(!editingMarker)return;const m=editingMarker;
  const marker={kind:m.kind,space:m.space,points_mm:m.points_mm,note:$('note').value};
  if(m.layer)marker.layer=m.layer;if(m.anchor)marker.anchor=m.anchor;
  send('markerPreview',{n:m.n,marker,approve:$('approve').checked});
});
board.addEventListener('dblclick',event=>{if(data && !hit(pointer(event)).length)fit();});
$('choices').addEventListener('change',()=>{select(data.scene.items.find(i=>i.uuid===$('choices').value));$('choices').hidden=$('choices').options.length<2;});
window.addEventListener('keydown',event=>{if(event.key==='Escape'){setMode('select');$('preview').hidden=true;send('markerCancel');}});
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
send('ready',{threeRevision:REVISION});
