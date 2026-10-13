Vendored for offline VS Code webviews. Built by `scripts/build_three_vendor.mjs` from the sibling CadAI
checkout's node_modules (read only; nothing in CadAI is changed):

- `three-bundle.js`: three.js 0.186.1 with OrbitControls and GLTFLoader, and three-mesh-bvh 0.9.15.
- Both MIT notices are distributed alongside the bundle and inside the VSIX.
- G0 imports `REVISION` to verify local module loading; G4 (`viewer3d.js`) uses GLTFLoader/OrbitControls.

No CDN, remote imports, dynamic downloads or service credentials are used in the webview.
