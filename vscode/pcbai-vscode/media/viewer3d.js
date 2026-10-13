// 3D webview (G4): KiCad's GLB, orbit/zoom, top/bottom/iso, component visibility, click → reference.
import { AmbientLight, Box3, Color, DirectionalLight, GLTFLoader, OrbitControls, PerspectiveCamera, Raycaster, REVISION,
  Scene, Vector2, Vector3, WebGLRenderer } from './vendor/three-bundle.js';

const vscode = acquireVsCodeApi();
const $ = id => document.getElementById(id);
const canvas = $('canvas');
let renderer = null, scene, camera, controls, model = null, data = null, selected = null;
let components = new Map(), normalAxis = 'y', box = null, lost = false;

// Tool drawer: open by default on wide panels, remembered per panel; the drawing always keeps the free space.
function savedState() { return vscode.getState() || {}; }
function setPanel(open) {
  document.body.classList.toggle('panel-hidden', !open);
  vscode.setState({ ...savedState(), panel: open });
  window.dispatchEvent(new Event('resize'));
}
setPanel(savedState().panel ?? window.innerWidth > 760);
document.getElementById('panel-toggle').addEventListener('click', () => setPanel(document.body.classList.contains('panel-hidden')));

function makeRenderer() {
  // Progressive start: full quality first, then a low-power, no-antialias context for weak/software GPUs.
  for (const options of [{ antialias: true }, { antialias: false, powerPreference: 'low-power' },
    { antialias: false, powerPreference: 'low-power', failIfMajorPerformanceCaveat: false }]) {
    try {
      const made = new WebGLRenderer({ canvas, ...options });
      made.setPixelRatio(Math.min(window.devicePixelRatio || 1, options.antialias ? 2 : 1));
      return { renderer: made, mode: options.antialias ? 'full' : 'low-power' };
    } catch (_) { /* try the next, cheaper context */ }
  }
  return null;
}

function setup() {
  const made = makeRenderer();
  if (!made) { $('error').textContent = 'WebGL açılamadı; 3B görünüm bu makinede kullanılamıyor. 2B kart görünümü çalışır.'; return false; }
  renderer = made.renderer; renderer.info.mode = made.mode;
  scene = new Scene(); scene.background = new Color(0x11161e);
  scene.add(new AmbientLight(0xffffff, 1.4));
  const sun = new DirectionalLight(0xffffff, 2.2); sun.position.set(1, 2, 1.5); scene.add(sun);
  const back = new DirectionalLight(0xffffff, 0.8); back.position.set(-1, -2, -1); scene.add(back);
  camera = new PerspectiveCamera(35, 1, 0.0001, 100);
  controls = new OrbitControls(camera, canvas);
  controls.addEventListener('change', draw);
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); lost = true; $('error').textContent = 'WebGL bağlamı kayboldu; geri gelince yeniden çizilecek.'; });
  canvas.addEventListener('webglcontextrestored', () => { lost = false; $('error').textContent = ''; resize(); });
  new ResizeObserver(resize).observe(canvas.parentElement);
  return true;
}

function resize() {
  if (!renderer) return;
  const { clientWidth: w, clientHeight: h } = canvas.parentElement;
  renderer.setSize(Math.max(w, 1), Math.max(h, 1), false);
  camera.aspect = Math.max(w, 1) / Math.max(h, 1); camera.updateProjectionMatrix(); draw();
}
function draw() { if (renderer && !lost) renderer.render(scene, camera); }

function view(name) {
  if (!box) return;
  const center = box.getCenter(new Vector3()), size = box.getSize(new Vector3());
  const span = Math.max(size.x, size.y, size.z), distance = span * 1.9;
  const normal = new Vector3(normalAxis === 'x' ? 1 : 0, normalAxis === 'y' ? 1 : 0, normalAxis === 'z' ? 1 : 0);
  const direction = name === 'top' ? normal.clone() : name === 'bottom' ? normal.clone().negate()
    : normal.clone().multiplyScalar(0.8).add(new Vector3(normalAxis === 'x' ? 0 : 0.6, 0, normalAxis === 'z' ? 0 : 0.6)).normalize();
  // Looking along the board normal, "up" is in the board plane; in the iso view it is the normal itself.
  if (name === 'iso') camera.up.copy(normal);
  else camera.up.set(0, normalAxis === 'y' ? 0 : 1, normalAxis === 'y' ? -1 : 0);
  camera.position.copy(center).addScaledVector(direction, distance);
  camera.near = span / 1000; camera.far = span * 20; camera.updateProjectionMatrix();
  controls.target.copy(center); controls.update(); draw();
}

function shown(object) {
  for (let node = object; node; node = node.parent) if (!node.visible) return false;
  return true;
}

function owner(object) {
  for (let node = object; node; node = node.parent) if (components.has(node.name) && components.get(node.name) === node) return node.name;
  return null;
}

function highlight(reference) {
  if (selected) components.get(selected)?.traverse(node => { if (node.isMesh && node.userData.original) { node.material = node.userData.original; delete node.userData.original; } });
  selected = reference;
  if (reference) components.get(reference)?.traverse(node => {
    if (!node.isMesh) return;
    node.userData.original = node.material;
    node.material = Array.isArray(node.material) ? node.material.map(m => tint(m)) : tint(node.material);
  });
  $('info').textContent = reference ? 'Seçili: ' + reference : 'Seçim yok';
  $('details').textContent = reference ? reference + ' (3B modeli olan bileşen)' : 'Bir bileşene tıklayın.';
  draw();
}
function tint(material) {
  const copy = material.clone();
  if (copy.emissive) copy.emissive = new Color(0x2a7f7a);
  return copy;
}

function load(message) {
  data = message;
  $('empty').hidden = false; $('empty').textContent = 'Model yükleniyor…';
  new GLTFLoader().load(message.uri, gltf => {
    if (model) scene.remove(model);
    model = gltf.scene; scene.add(model); highlight(null);
    components = new Map();
    const wanted = new Set(message.components);
    model.traverse(node => { if (wanted.has(node.name) && !components.has(node.name)) components.set(node.name, node); });
    box = new Box3().setFromObject(model);
    // The board normal is the thinnest axis of the board body alone: tall parts (valves, connectors) can make
    // the whole model thicker than it is wide.
    const body = new Box3();
    model.traverse(node => { if (node.isMesh && !owner(node)) body.expandByObject(node); });
    const size = (body.isEmpty() ? box : body).getSize(new Vector3());
    normalAxis = size.x <= size.y && size.x <= size.z ? 'x' : size.y <= size.z ? 'y' : 'z';
    $('empty').hidden = true; $('document').textContent = message.document;
    $('revision').textContent = 'Kaydedilmiş dosya · ' + message.revision.slice(0, 12);
    const info = $('model-info'); info.replaceChildren();
    for (const line of [`${components.size} seçilebilir bileşen`, `${message.without_model.length} bileşenin 3B modeli yok`
        + (message.without_model.length ? ': ' + message.without_model.slice(0, 12).join(', ') : ''),
      `${(message.bytes / 1e6).toFixed(1)} MB GLB · ${renderer.info.mode === 'full' ? 'tam' : 'düşük güç'} WebGL`]
      .concat(message.substitutions ? [`${message.substitutions} eski model yolu görüntü için kurulu kütüphaneye yönlendirildi`] : [])) {
      const row = document.createElement('p'); row.textContent = line; info.append(row);
    }
    $('components').checked = true;
    resize(); view('iso');
    vscode.postMessage({ type: 'modelReady', generation: message.generation, renderer: renderer.info.mode, components: components.size });
  }, undefined, error => { $('error').textContent = '3B model yüklenemedi: ' + (error?.message || error); });
}

window.addEventListener('message', event => {
  const m = event.data;
  if (m?.type === 'model' && renderer) load(m);
  else if (m?.type === 'busy' || m?.type === 'error') $('error').textContent = m.message;
});
canvas.addEventListener('click', event => {
  if (!model) return;
  const rect = canvas.getBoundingClientRect();
  const pointer = new Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  const ray = new Raycaster(); ray.setFromCamera(pointer, camera);
  // three.js ray casting ignores parent visibility, so hidden components are filtered here.
  const hit = ray.intersectObject(model, true).find(h => shown(h.object));
  const reference = hit ? owner(hit.object) : null;
  highlight(reference);
  if (reference) vscode.postMessage({ type: 'select', reference });
});
for (const button of document.querySelectorAll('[data-view]')) button.addEventListener('click', () => view(button.dataset.view));
$('components').addEventListener('change', () => { for (const node of components.values()) node.visible = $('components').checked; if (!$('components').checked) highlight(null); draw(); });
$('refresh').addEventListener('click', () => vscode.postMessage({ type: 'refresh' }));
// Read-only test/automation probe: a screen point where the component is the first visible surface, or null
// when other geometry fully covers it from this camera.
window.pcbaiView3d = Object.freeze({
  screenPoint(reference) {
    const node = components.get(reference); if (!node) return null;
    const b = new Box3().setFromObject(node), rect = canvas.getBoundingClientRect(), ray = new Raycaster();
    const up = camera.position[normalAxis] > box.getCenter(new Vector3())[normalAxis];
    const axes = ['x', 'y', 'z'].filter(a => a !== normalAxis);
    for (const [u, v] of [[.5, .5], [.3, .3], [.7, .3], [.3, .7], [.7, .7], [.5, .2], [.5, .8], [.2, .5], [.8, .5]]) {
      const point = new Vector3();
      point[axes[0]] = b.min[axes[0]] + (b.max[axes[0]] - b.min[axes[0]]) * u;
      point[axes[1]] = b.min[axes[1]] + (b.max[axes[1]] - b.min[axes[1]]) * v;
      point[normalAxis] = up ? b.max[normalAxis] : b.min[normalAxis];
      const ndc = point.clone().project(camera);
      ray.setFromCamera(new Vector2(ndc.x, ndc.y), camera);
      const hit = ray.intersectObject(model, true).find(h => shown(h.object));
      if (hit && owner(hit.object) === reference) {
        return { x: rect.left + (ndc.x + 1) / 2 * rect.width, y: rect.top + (1 - ndc.y) / 2 * rect.height };
      }
    }
    return null;
  },
  selected: () => selected, view,
});
if (setup()) vscode.postMessage({ type: 'ready', threeRevision: REVISION });
