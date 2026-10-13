// Rebuilds vscode/pcbai-vscode/media/vendor/three-bundle.js: three.js + OrbitControls + GLTFLoader (G4) +
// three-mesh-bvh as one ES module without bare imports (webview CSP, no import maps).
// Reads the sibling CadAI checkout's node_modules (esbuild, three, three-mesh-bvh) READ-ONLY; writes only here.
//   node scripts/build_three_vendor.mjs [path-to-CadAI/vscode/cadai-vscode]
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const source = resolve(process.argv[2] || join(root, '..', 'CadAI', 'vscode', 'cadai-vscode'));
const modules = join(source, 'node_modules');
const pkg = name => JSON.parse(readFileSync(join(modules, name, 'package.json'), 'utf8'));
const { build } = await import(pathToFileURL(join(modules, 'esbuild', 'lib', 'main.js')).href);
const vendor = join(root, 'vscode', 'pcbai-vscode', 'media', 'vendor');
const out = join(vendor, 'three-bundle.js');

const entry = `
export * from 'three';
export { OrbitControls } from 'three/addons/controls/OrbitControls.js';
export { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
export { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh';
`;

await build({
  stdin: { contents: entry, resolveDir: source, sourcefile: 'pcbai-three-entry.js' },
  bundle: true, format: 'esm', minify: true, target: 'es2022', legalComments: 'none', outfile: out,
  absWorkingDir: source,
});
const banner = `/* PcbAi vendor bundle — three.js ${pkg('three').version} (MIT, Copyright 2010-2026 Three.js Authors) with `
  + `OrbitControls and GLTFLoader, and three-mesh-bvh ${pkg('three-mesh-bvh').version} (MIT, Copyright Garrett Johnson). `
  + 'Licenses: THREE_LICENSE.txt, THREE_MESH_BVH_LICENSE.txt. Built by scripts/build_three_vendor.mjs from the '
  + 'sibling CadAI checkout (read only). */\n';
writeFileSync(out, banner + readFileSync(out, 'utf8'));
for (const [name, file] of [['three', 'THREE_LICENSE.txt'], ['three-mesh-bvh', 'THREE_MESH_BVH_LICENSE.txt']]) {
  writeFileSync(join(vendor, file), readFileSync(join(modules, name, 'LICENSE'), 'utf8'));
}
console.log('wrote', out);
