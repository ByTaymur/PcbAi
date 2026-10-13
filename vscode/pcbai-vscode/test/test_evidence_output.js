const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {evidencePath} = require('./evidence_output');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-evidence-'));
try {
  const published = evidencePath(root, 'docs/spikes/result.json');
  fs.writeFileSync(published, 'published');
  const audit = evidencePath(root, '.pcbai-state/result.json');
  fs.linkSync(published, audit);
  assert.throws(() => evidencePath(root, '.pcbai-state/result.json'), /link/);
  fs.unlinkSync(audit);
  fs.rmdirSync(path.dirname(audit));
  fs.symlinkSync(path.dirname(published), path.dirname(audit), process.platform === 'win32' ? 'junction' : 'dir');
  assert.throws(() => evidencePath(root, '.pcbai-state/result.json'), /link/);
  assert.throws(() => evidencePath(root, '../escape.json'), /escapes/);
  assert.equal(fs.readFileSync(published, 'utf8'), 'published');
  fs.unlinkSync(path.dirname(audit));
  console.log('Published evidence protected from hardlinks and junctions');
} finally {
  fs.rmSync(root, {recursive: true, force: true});
}
