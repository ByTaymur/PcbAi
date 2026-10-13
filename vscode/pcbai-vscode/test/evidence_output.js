const fs = require('node:fs');
const path = require('node:path');

function evidencePath(root, relative) {
  root = fs.realpathSync(root);
  const target = path.resolve(root, relative);
  if (!target.startsWith(root + path.sep)) throw new Error('Evidence path escapes repository');
  for (let entry = target; entry !== root; entry = path.dirname(entry)) {
    let info;
    try { info = fs.lstatSync(entry); } catch (error) { if (error.code === 'ENOENT') continue; throw error; }
    if (info.isSymbolicLink() || (info.isFile() && info.nlink > 1)) {
      throw new Error('Evidence path contains a link: ' + entry);
    }
  }
  fs.mkdirSync(path.dirname(target), {recursive: true});
  return target;
}

module.exports = {evidencePath};
