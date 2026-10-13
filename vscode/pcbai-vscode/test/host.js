// Runs inside a real, isolated VS Code Extension Development Host (not a vscode mock).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vscode = require('vscode');

exports.run = async function() {
  const extension = vscode.extensions.getExtension('taymur.pcbai-vscode');
  assert.ok(extension, 'Development extension not loaded');
  await extension.activate();
  const response = await vscode.commands.executeCommand('pcbai.viewEmpty');
  assert.equal(response.ready, true, 'Webview module did not send its ready message');
  assert.equal(response.threeRevision, '186');
  try {
    const board = await vscode.commands.executeCommand('pcbai.view');
    assert.equal(board?.loaded, true, 'Real board command did not load its SVGs: '+JSON.stringify(board));
    assert.ok(board.layerCount >= 3);
    fs.writeFileSync(process.env.PCBAI_HOST_RESULT, JSON.stringify({
      vscode_version: vscode.version, extension_version: extension.packageJSON.version,
      real_extension_host: true, webview_ready: true, three_revision: response.threeRevision,
      real_service_board_loaded: true, board_document: board.document, layer_count: board.layerCount,
      user_profile_isolated: true,
    }, null, 2));
  } finally { await vscode.commands.executeCommand('pcbai.stop'); }
  console.log('PcbAi real Extension Host: webview + local ES module + three.js ready');
};
