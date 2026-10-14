// KiCad → VS Code handoff (plan AJ-5): vscode://taymur.pcbai-vscode/handoff?id=<uuid>.
// The URL carries only the id; the prompt is taken once from the service, delivered to the agent chosen in the side
// bar, and the outcome is written back so the KiCad window can show it. A prompt for a project that is not open in
// this window is never delivered without asking.
const vscode = require('vscode');
const path = require('node:path');
const agents = require('./agents');

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function handoffId(uri) {
  if (!uri || uri.path !== '/handoff') return null;
  const id = new URLSearchParams(uri.query || '').get('id');
  return id && ID.test(id) ? id : null;
}

function inWorkspace(project, folders, samePath) {
  const dir = path.dirname(project);
  return (folders || []).some(f => {
    const rel = path.relative(f.uri.fsPath, dir);
    return samePath(f.uri.fsPath, dir) || (rel && !rel.startsWith('..') && !path.isAbsolute(rel));
  });
}

/**
 * api: { serviceCall(path, payload) → service JSON, samePath, onPrompt(prompt) (fills the side bar request box),
 *        context (globalState for the chosen agent) }
 */
async function handle(uri, api) {
  const id = handoffId(uri);
  if (!id) throw new Error('Geçersiz PcbAi devir bağlantısı');
  const taken = await api.serviceCall('/handoff/take', { id });
  if (!taken.ok) throw new Error((taken.error && taken.error.message) || 'Devir alınamadı');
  const report = (outcome, message) => api.serviceCall('/handoff/report', { id, outcome, message }).catch(() => null);
  if (!inWorkspace(taken.project, vscode.workspace.workspaceFolders, api.samePath)) {
    const choice = await vscode.window.showWarningMessage(
      `KiCad'den gelen istem ${path.basename(taken.project)} projesi için; bu VS Code penceresinde bu proje açık değil.`,
      { modal: true }, 'Yine de gönder', 'Klasörü aç');
    if (choice === 'Klasörü aç') {
      await report('declined', 'Proje klasörü VS Code\'da açılıyor; istemi KiCad penceresinden yeniden gönderin.');
      await vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(path.dirname(taken.project)), { forceNewWindow: true });
      return 'declined';
    }
    if (choice !== 'Yine de gönder') {
      await report('declined', 'VS Code\'da kullanıcı devri reddetti (proje bu pencerede açık değil).');
      return 'declined';
    }
  }
  if (api.onPrompt) await api.onPrompt(taken.prompt);
  try {
    const agent = agents.current(api.context);
    const how = await agents.open(agent, taken.prompt, path.dirname(taken.project));
    const message = agents.describe(agent, how, 'KiCad isteği');
    await report(how, message);
    vscode.window.showInformationMessage(message);
    return how;
  } catch (error) {
    await report('failed', error.message);
    throw error;
  }
}

function register(context, api) {
  if (!vscode.window.registerUriHandler) return false;
  context.subscriptions.push(vscode.window.registerUriHandler({
    handleUri: uri => handle(uri, { ...api, context }).catch(error => vscode.window.showErrorMessage('PcbAi devri: ' + error.message)),
  }));
  return true;
}

module.exports = { handle, handoffId, inWorkspace, register };
