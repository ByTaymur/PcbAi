// AI agents the user can hand a PcbAi prompt to (plan AJ-1). Every agent uses the same `pcbai` MCP tools; this module
// only decides where the conversation happens and how the prepared prompt gets there.
// Adapted from CadAI vscode/cadai-vscode/agents.js @ 1878212: PcbAi keeps the measured `claude-vscode.editor.open`
// path first, adds the saved choice and writes very long terminal prompts to a file under .pcbai-state/prompts.
'use strict';

const vscode = require('vscode');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const AGENTS = [
  { id: 'claude-code', label: 'Claude Code', detail: 'mesaj kutusuna yazılır', ext: 'anthropic.claude-code',
    focus: ['claude-vscode.focus', 'claude-vscode.sidebar.open', 'claude-vscode.editor.openLast'],
    // (sessionId, initialPrompt): new conversation with the prompt in the input box; Claude Code never auto-sends.
    prefill: { commands: ['claude-vscode.editor.open', 'claude-vscode.primaryEditor.open'], args: p => [undefined, p],
      uri: (s, p) => `${s}://anthropic.claude-code/open?prompt=${encodeURIComponent(p)}` } },
  { id: 'claude-cli', label: 'Claude Code (terminal)', detail: 'mesaj doğrudan gönderilir', cli: 'claude' },
  { id: 'codex', label: 'Codex', detail: 'mesaj kutusuna yazılır', ext: 'openai.chatgpt', focus: ['chatgpt.openSidebar'],
    // Undocumented route of the Codex extension: the text also goes to the clipboard as a fallback.
    prefill: { uri: (s, p) => `${s}://openai.chatgpt/?prompt=${encodeURIComponent(p)}`, alsoClipboard: true } },
  { id: 'codex-cli', label: 'Codex (terminal)', detail: 'mesaj doğrudan gönderilir', cli: 'codex' },
  { id: 'cline', label: 'Cline', detail: 'VS Code paneli', ext: 'saoudrizwan.claude-dev',
    focus: ['cline.focusChatInput', 'claude-dev.SidebarProvider.focus'] },
  { id: 'kilo', label: 'Kilo Code', detail: 'VS Code paneli', ext: 'kilocode.kilo-code',
    focus: ['kilo-code.new.plusButtonClicked', 'kilo-code.SidebarProvider.focus'] },
  { id: 'roo', label: 'Roo Code', detail: 'VS Code paneli', ext: 'rooveterinaryinc.roo-cline', focus: ['roo-cline.SidebarProvider.focus'] },
  { id: 'copilot', label: 'GitHub Copilot Chat', detail: 'VS Code sohbeti', ext: 'github.copilot-chat', chat: true },
  { id: 'clipboard', label: 'Sadece panoya kopyala', detail: 'istediğin yere yapıştır' },
];

const PREFERENCE = ['claude-code', 'codex', 'cline', 'kilo', 'copilot', 'roo', 'claude-cli', 'codex-cli', 'clipboard'];
const STATE_KEY = 'pcbai.agent';
// Windows command lines are limited to 32767 characters; stay well below and hand longer prompts over as a file.
const CLI_MAX = 7000;

function cliFallbacks(name) {
  const home = os.homedir();
  const local = process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local');
  if (name === 'claude') return [path.join(home, '.local', 'bin', process.platform === 'win32' ? 'claude.exe' : 'claude')];
  if (name === 'codex') {
    const base = path.join(local, 'OpenAI', 'Codex', 'bin');
    try {
      return fs.readdirSync(base).map(d => path.join(base, d, 'codex.exe')).filter(p => fs.existsSync(p))
        .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
    } catch (_) { return []; }
  }
  return [];
}

// Only real executables: npm .cmd/.ps1 shims would need a shell to run.
function findCli(name) {
  try {
    const out = cp.execFileSync(process.platform === 'win32' ? 'where.exe' : 'which', [name],
      { encoding: 'utf8', timeout: 3000, windowsHide: true });
    const hits = out.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    const exe = hits.find(h => /\.exe$/i.test(h)) || (process.platform !== 'win32' ? hits[0] : null);
    if (exe) return exe;
  } catch (_) { /* not on PATH */ }
  return cliFallbacks(name).find(p => fs.existsSync(p)) || null;
}

let cache = null;

function detect(finder = findCli) {
  cache = AGENTS.map(a => {
    let available = a.id === 'clipboard';
    let cliPath = null;
    // An agent is offered only when this host can reach it (terminal API, extension registry).
    if (a.ext) available = Boolean(vscode.extensions?.getExtension(a.ext));
    if (a.cli && vscode.window?.createTerminal) { cliPath = finder(a.cli); available = Boolean(cliPath); }
    return { ...a, available, cliPath };
  });
  return cache;
}

function list() { return cache || detect(); }

function defaultAgent(agents) {
  for (const id of PREFERENCE) if (agents.some(a => a.id === id && a.available)) return id;
  return 'clipboard';
}

function current(context) {
  const agents = list();
  const saved = context?.globalState?.get(STATE_KEY);
  return agents.find(a => a.id === saved && a.available) || agents.find(a => a.id === defaultAgent(agents));
}

async function choose(context, id) {
  const agent = list().find(a => a.id === id);
  if (!agent) throw new Error('Bilinmeyen ajan');
  if (!agent.available) throw new Error(`${agent.label} kurulu değil`);
  await context.globalState.update(STATE_KEY, id);
  return agent;
}

// What the webview needs: no paths or executables.
function summary(context) {
  const selected = current(context).id;
  return { selected, items: list().map(({ id, label, detail, available }) => ({ id, label, detail, available })) };
}

async function tryCommands(ids) {
  for (const id of ids || []) {
    try { await vscode.commands.executeCommand(id); return true; } catch (_) { /* next */ }
  }
  return false;
}

// Newlines and double quotes do not survive Windows command lines; a leading '-' would be read as an option.
function cliSafe(text) {
  const one = text.replace(/"/g, "'").replace(/\r?\n+/g, ' | ');
  return one.startsWith('-') ? ' ' + one : one;
}

// A prompt too long for a command line goes to <cwd>/.pcbai-state/prompts/<id>.md; old files are removed after a day.
function promptFile(cwd, prompt) {
  const dir = path.join(cwd, '.pcbai-state', 'prompts');
  fs.mkdirSync(dir, { recursive: true });
  const now = Date.now();
  for (const name of fs.readdirSync(dir)) {
    const file = path.join(dir, name);
    try { if (now - fs.statSync(file).mtimeMs > 86400000) fs.unlinkSync(file); } catch (_) { /* in use */ }
  }
  const file = path.join(dir, crypto.randomUUID() + '.md');
  fs.writeFileSync(file, prompt, { encoding: 'utf8', flag: 'wx' });
  return file;
}

function cliArgument(prompt, cwd) {
  const one = cliSafe(prompt);
  if (one.length <= CLI_MAX || !cwd) return one;
  const file = promptFile(cwd, prompt);
  return `PcbAi isteğim uzun olduğu için şu dosyada: ${file} — dosyayı oku ve içindeki isteği uygula.`;
}

/**
 * Open the agent with an optional prompt. Returns how it was delivered: 'sent' (the agent already has it), 'typed'
 * (in the input box, the user presses Enter), 'typed+clipboard', 'clipboard' (user pastes) or 'opened' (no prompt).
 */
async function open(agent, prompt, cwd) {
  if (agent.cli) {
    if (!agent.cliPath) throw new Error(`${agent.label} bulunamadı`);
    const term = vscode.window.createTerminal({ name: `PcbAi · ${agent.label}`, shellPath: agent.cliPath,
      shellArgs: prompt ? [cliArgument(prompt, cwd)] : [], cwd });
    term.show();
    return prompt ? 'sent' : 'opened';
  }
  if (agent.chat) {
    await vscode.commands.executeCommand('workbench.action.chat.open', prompt ? { query: prompt, isPartialQuery: true } : undefined);
    return prompt ? 'typed' : 'opened';
  }
  if (agent.prefill && prompt) {
    const pf = agent.prefill;
    if (pf.alsoClipboard) await vscode.env.clipboard.writeText(prompt);
    for (const command of pf.commands || []) {
      try { await vscode.commands.executeCommand(command, ...pf.args(prompt)); return 'typed'; } catch (_) { /* next */ }
    }
    if (pf.uri) {
      // openExternal on VS Code's own scheme is handled in-process by the target extension's URI handler.
      const scheme = (vscode.env && vscode.env.uriScheme) || 'vscode';
      try {
        if (await vscode.env.openExternal(vscode.Uri.parse(pf.uri(scheme, prompt)))) return pf.alsoClipboard ? 'typed+clipboard' : 'typed';
      } catch (_) { /* clipboard below */ }
    }
  }
  if (prompt) await vscode.env.clipboard.writeText(prompt);
  if (agent.focus) await tryCommands(agent.focus);
  return prompt ? 'clipboard' : 'opened';
}

// The sentence shown to the user for each delivery result; never claims "sent" when the text is on the clipboard.
function describe(agent, how, what = 'İstem') {
  if (how === 'sent') return `${what} ${agent.label} ile terminalde başlatıldı.`;
  if (how === 'typed') return `${what} ${agent.label} mesaj kutusuna yazıldı; kontrol edip Enter'a basın.`;
  if (how === 'typed+clipboard') return `${what} ${agent.label} mesaj kutusuna yazıldı; görünmüyorsa Ctrl+V (metin panoda da var).`;
  if (how === 'clipboard') {
    return agent.id === 'clipboard' ? `${what} panoya kopyalandı; istediğiniz ajana Ctrl+V ile yapıştırın.`
      : `${what} panoya kopyalandı ve ${agent.label} açıldı; sohbet kutusuna Ctrl+V ile yapıştırıp gönderin.`;
  }
  return `${agent.label} açıldı.`;
}

// One call for the views: deliver to the chosen agent and return the user-facing sentence.
async function deliver(context, prompt, cwd, what) {
  const agent = current(context);
  return describe(agent, await open(agent, prompt, cwd), what);
}

function watch(context, onChange) {
  if (!vscode.extensions?.onDidChange) return;
  context.subscriptions.push(vscode.extensions.onDidChange(() => { detect(); if (onChange) onChange(); }));
}

module.exports = { AGENTS, PREFERENCE, STATE_KEY, CLI_MAX, detect, list, defaultAgent, current, choose, summary, open,
  describe, deliver, watch, cliSafe, cliArgument, findCli };
