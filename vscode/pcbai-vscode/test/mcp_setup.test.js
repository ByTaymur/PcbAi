// MCP registration for every agent (plan AJ-2) against a temporary userDir/home: write, merge, broken files, backups.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const setup = require('../mcp_setup');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pcbai-mcp-'));
const userDir = path.join(tmp, 'User');
const home = path.join(tmp, 'home');
const workspace = path.join(tmp, 'ws');
fs.mkdirSync(workspace, { recursive: true });
const python = 'C:/PcbAi/.venv/Scripts/python.exe';
const root = 'C:/PcbAi';
const ALL = new Set(['openai.chatgpt', 'saoudrizwan.claude-dev', 'kilocode.kilo-code', 'rooveterinaryinc.roo-cline']);
const json = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const gs = (ext, file) => path.join(userDir, 'globalStorage', ext, 'settings', file);

try {
  const definitions = setup.bundledTools();
  const readOnly = setup.readOnlyTools(definitions);
  assert.ok(readOnly.includes('pcbai_status') && readOnly.includes('get_markers'));
  for (const writer of ['set_value', 'move_footprint', 'autoroute', 'checkpoint', 'update_marker_status']) {
    if (definitions.some(d => d.name === writer)) assert.ok(!readOnly.includes(writer), writer + ' must never be auto-approved');
  }
  assert.deepEqual(setup.readOnlyTools([{ name: 'x' }, { name: 'y', annotations: { readOnlyHint: true, destructiveHint: true } }]), []);

  // Existing user configs that must survive the merge.
  const codexToml = path.join(home, '.codex', 'config.toml');
  fs.mkdirSync(path.dirname(codexToml), { recursive: true });
  fs.writeFileSync(codexToml, 'model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x"\n\n[mcp_servers.pcbai]\ncommand = "old"\n\n[mcp_servers.pcbai.env]\nA = "1"\n\n[profiles.fast]\nmodel = "y"\n');
  const cline = gs('saoudrizwan.claude-dev', 'cline_mcp_settings.json');
  fs.mkdirSync(path.dirname(cline), { recursive: true });
  fs.writeFileSync(cline, JSON.stringify({ mcpServers: { other: { command: 'o' } } }));
  const kilo = gs('kilocode.kilo-code', 'mcp_settings.json');
  fs.mkdirSync(path.dirname(kilo), { recursive: true });
  const brokenKilo = '{ "mcpServers": { broken ';
  fs.writeFileSync(kilo, brokenKilo);

  const calls = [];
  const exec = (file, args) => { calls.push([file, ...args]); return ''; };
  const list = setup.targets({ userDir, home, workspace, claudeCli: 'C:/bin/claude.exe', installed: ALL, python, root,
    projects: ['C:/p/a.kicad_pro'], readOnly, exec });
  assert.deepEqual(list.map(t => t.id), ['claude', 'claude-user', 'codex', 'cline', 'kilo', 'roo', 'vscode']);
  const results = list.map(setup.applyTarget);
  const byId = Object.fromEntries(results.map(r => [r.id, r]));

  // Claude workspace .mcp.json carries the project list; user-level entries never do.
  const ws = json(path.join(workspace, '.mcp.json')).mcpServers.pcbai;
  assert.deepEqual(JSON.parse(ws.env.PCBAI_PROJECTS), ['C:/p/a.kicad_pro']);
  const add = calls.find(c => c.includes('add'));
  assert.ok(add && !add.some(a => a.includes('PCBAI_PROJECTS')) && add.includes('-s') && add.includes('user'));

  // Codex: pcbai table (and sub-table) replaced, other tables kept, backup made.
  const toml = fs.readFileSync(codexToml, 'utf8');
  assert.match(toml, /\[mcp_servers\.other\]/);
  assert.match(toml, /\[profiles\.fast\]/);
  assert.equal((toml.match(/\[mcp_servers\.pcbai\]/g) || []).length, 1);
  assert.ok(!toml.includes('command = "old"') && !toml.includes('[mcp_servers.pcbai.env]') && !toml.includes('PCBAI_PROJECTS'));
  assert.ok(fs.readFileSync(codexToml + setup.BACKUP, 'utf8').includes('command = "old"'));
  assert.ok(byId.codex.backup);

  // Cline merges and auto-approves only read-only tools; broken Kilo is untouched; Roo created fresh.
  const clineCfg = json(cline).mcpServers;
  assert.ok(clineCfg.other && clineCfg.pcbai);
  assert.deepEqual(clineCfg.pcbai.autoApprove, readOnly);
  assert.ok(!('PCBAI_PROJECTS' in clineCfg.pcbai.env));
  assert.equal(byId.kilo.status, 'broken');
  assert.equal(fs.readFileSync(kilo, 'utf8'), brokenKilo);
  assert.ok(!fs.existsSync(kilo + setup.BACKUP));
  assert.deepEqual(json(gs('rooveterinaryinc.roo-cline', 'mcp_settings.json')).mcpServers.pcbai.alwaysAllow, readOnly);
  assert.equal(json(path.join(userDir, 'mcp.json')).servers.pcbai.type, 'stdio');
  assert.match(setup.summary(results), /Kilo Code: JSON bozuk, dokunulmadı/);
  assert.match(setup.summary(results), /Codex: yazıldı/);

  // Broken TOML is never edited.
  const badToml = 'model = "x"\n[mcp_servers.pcbai\ncommand = 1\n';
  fs.writeFileSync(codexToml, badToml);
  const codex = setup.targets({ userDir, home, installed: ALL, python, root, readOnly }).find(t => t.id === 'codex');
  assert.equal(setup.applyTarget(codex).status, 'broken');
  assert.equal(fs.readFileSync(codexToml, 'utf8'), badToml);

  // Registration lookup per agent drives the side bar warning.
  const ctx = { userDir, home, workspace };
  assert.equal(setup.hasRegistration('claude-code', ctx), true);
  assert.equal(setup.hasRegistration('cline', ctx), true);
  assert.equal(setup.hasRegistration('kilo', ctx), false);
  assert.equal(setup.hasRegistration('codex', ctx), false);
  assert.equal(setup.hasRegistration('clipboard', ctx), null);

  // Native VS Code provider: mcp.json copy is offered for removal, provider registered only when the API exists.
  const native = setup.targets({ userDir, home, installed: new Set(), python, root, nativeVsCode: true }).find(t => t.id === 'vscode');
  assert.ok(native && /kaldırılacak/.test(native.describe));
  setup.applyTarget(native);
  assert.ok(!('pcbai' in json(path.join(userDir, 'mcp.json')).servers));
  const subs = [];
  assert.equal(setup.registerNative({}, { subscriptions: subs }, () => null), false);
  class Def { constructor(...a) { this.a = a; } }
  let provider;
  const fake = { McpStdioServerDefinition: Def, lm: { registerMcpServerDefinitionProvider: (id, p) => { provider = p; return { id }; } } };
  assert.equal(setup.registerNative(fake, { subscriptions: subs }, () => setup.serverEntry({ python, root })), true);
  const defs = provider.provideMcpServerDefinitions();
  assert.equal(defs[0].a[1], python);
  assert.ok(!('PCBAI_PROJECTS' in defs[0].a[3]));
  console.log('MCP setup: 7 targets, merge, backups, broken JSON/TOML untouched, read-only approvals, native provider passed');
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}
