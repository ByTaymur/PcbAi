// Agent catalogue (plan AJ-1): detection, saved choice, every delivery path and the long terminal prompt file.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const os = require('node:os');
const path = require('node:path');

const executed = [];
const opened = [];
const terminals = [];
let clipboard = '';
let failing = new Set();
let installed = new Set();
const vscode = {
  Uri: { parse: text => ({ text }) },
  env: { uriScheme: 'vscode', clipboard: { writeText: async text => { clipboard = text; } },
    openExternal: async uri => { opened.push(uri.text); return !failing.has('uri'); } },
  extensions: { getExtension: id => (installed.has(id) ? {} : undefined) },
  commands: { executeCommand: async (...args) => { executed.push(args); if (failing.has(args[0])) throw new Error('no command'); } },
  window: { createTerminal: options => { const t = { options, shown: false, show() { t.shown = true; } }; terminals.push(t); return t; } },
};
const load = Module._load;
Module._load = function (name, ...args) { return name === 'vscode' ? vscode : load.call(this, name, ...args); };
const agents = require('../agents');
Module._load = load;

function reset() { executed.length = 0; opened.length = 0; terminals.length = 0; clipboard = ''; failing = new Set(); }

async function main() {
  const state = new Map();
  const context = { subscriptions: [], globalState: { get: k => state.get(k), update: async (k, v) => { state.set(k, v); } } };

  // Nothing installed: only the clipboard is offered and chosen.
  agents.detect(() => null);
  assert.equal(agents.current(context).id, 'clipboard');
  assert.deepEqual(agents.list().filter(a => a.available).map(a => a.id), ['clipboard']);

  // Preference order, then the saved choice; an uninstalled saved choice falls back instead of failing.
  installed = new Set(['openai.chatgpt', 'kilocode.kilo-code', 'github.copilot-chat']);
  agents.detect(name => (name === 'claude' ? 'C:/bin/claude.exe' : null));
  assert.equal(agents.current(context).id, 'codex');
  await agents.choose(context, 'claude-cli');
  assert.equal(agents.current(context).id, 'claude-cli');
  await assert.rejects(agents.choose(context, 'cline'), /kurulu değil/);
  await assert.rejects(agents.choose(context, 'nope'), /Bilinmeyen/);
  state.set(agents.STATE_KEY, 'roo');
  assert.equal(agents.current(context).id, 'codex');
  const summary = agents.summary(context);
  assert.equal(summary.items.length, 9);
  assert.ok(summary.items.every(a => Object.keys(a).sort().join() === 'available,detail,id,label'));

  const byId = id => agents.list().find(a => a.id === id);
  const prompt = 'PcbAi projesi: X\n\n"R5" 4,7k olsun';

  // Claude Code: measured command first, then primaryEditor, then the deep link, then clipboard + focus.
  installed.add('anthropic.claude-code'); agents.detect(() => null);
  reset();
  assert.equal(await agents.open(byId('claude-code'), prompt), 'typed');
  assert.deepEqual(executed[0], ['claude-vscode.editor.open', undefined, prompt]);
  reset(); failing = new Set(['claude-vscode.editor.open']);
  assert.equal(await agents.open(byId('claude-code'), prompt), 'typed');
  assert.equal(executed[1][0], 'claude-vscode.primaryEditor.open');
  reset(); failing = new Set(['claude-vscode.editor.open', 'claude-vscode.primaryEditor.open']);
  assert.equal(await agents.open(byId('claude-code'), prompt), 'typed');
  assert.equal(opened[0], 'vscode://anthropic.claude-code/open?prompt=' + encodeURIComponent(prompt));
  assert.equal(clipboard, '');
  reset(); failing = new Set(['claude-vscode.editor.open', 'claude-vscode.primaryEditor.open', 'uri']);
  assert.equal(await agents.open(byId('claude-code'), prompt), 'clipboard');
  assert.equal(clipboard, prompt);
  assert.equal(executed.at(-1)[0], 'claude-vscode.focus');

  // Codex: deep link plus clipboard, reported as such.
  reset();
  assert.equal(await agents.open(byId('codex'), prompt), 'typed+clipboard');
  assert.ok(opened[0].startsWith('vscode://openai.chatgpt/?prompt='));
  assert.equal(clipboard, prompt);

  // Panel agents: clipboard + focus; Copilot: chat query left for the user to send.
  reset();
  assert.equal(await agents.open(byId('kilo'), prompt), 'clipboard');
  assert.equal(executed[0][0], 'kilo-code.new.plusButtonClicked');
  reset();
  assert.equal(await agents.open(byId('copilot'), prompt), 'typed');
  assert.deepEqual(executed[0], ['workbench.action.chat.open', { query: prompt, isPartialQuery: true }]);
  reset();
  assert.equal(await agents.open(byId('clipboard'), prompt), 'clipboard');
  assert.equal(executed.length, 0);
  reset();
  assert.equal(await agents.open(byId('kilo'), null), 'opened');
  assert.equal(clipboard, '');

  // Terminal CLI: argv without a shell, one line, cwd = project root.
  agents.detect(name => (name === 'claude' ? 'C:/bin/claude.exe' : null));
  reset();
  assert.equal(await agents.open(byId('claude-cli'), prompt, 'C:/p'), 'sent');
  assert.equal(terminals[0].options.shellPath, 'C:/bin/claude.exe');
  assert.deepEqual(terminals[0].options.shellArgs, ["PcbAi projesi: X | 'R5' 4,7k olsun"]);
  assert.equal(terminals[0].options.cwd, 'C:/p');
  assert.ok(terminals[0].shown);
  assert.equal(agents.cliSafe('-rf'), ' -rf');

  // A prompt longer than a command line goes to .pcbai-state/prompts under the project, intact.
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-agents-'));
  try {
    const long = 'x'.repeat(agents.CLI_MAX + 1) + '\n"son"';
    const argument = agents.cliArgument(long, root);
    const file = argument.match(/dosyada: (.+\.md) —/)[1];
    assert.ok(file.startsWith(path.join(root, '.pcbai-state', 'prompts')));
    assert.equal(fs.readFileSync(file, 'utf8'), long);
    assert.ok(argument.length < 500);
    const old = path.join(path.dirname(file), 'old.md');
    fs.writeFileSync(old, 'x'); fs.utimesSync(old, new Date(0), new Date(0));
    agents.cliArgument(long, root);
    assert.ok(!fs.existsSync(old));
  } finally { fs.rmSync(root, { recursive: true, force: true }); }

  // User-facing sentences never claim delivery that did not happen.
  assert.match(agents.describe(byId('claude-cli'), 'sent'), /terminalde başlatıldı/);
  assert.match(agents.describe(byId('kilo'), 'clipboard'), /panoya kopyalandı ve Kilo Code açıldı/);
  assert.match(agents.describe(byId('clipboard'), 'clipboard', '#2 isteği'), /^#2 isteği panoya kopyalandı/);
  assert.match(agents.describe(byId('codex'), 'typed+clipboard'), /panoda da var/);

  // A host without terminal/extension APIs (browser e2e mocks) offers only the clipboard.
  const window = vscode.window, extensions = vscode.extensions;
  delete vscode.window; delete vscode.extensions;
  try { agents.detect(() => 'C:/bin/claude.exe'); assert.equal(agents.current(undefined).id, 'clipboard'); }
  finally { vscode.window = window; vscode.extensions = extensions; }
  console.log('Agents: detection, saved choice, Claude Code/Codex/panel/Copilot/terminal/clipboard delivery, long prompt file passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
