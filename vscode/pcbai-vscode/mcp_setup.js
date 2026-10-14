// CadAI mcp_setup.js@da608c7'ten uyarlandı (CadAI vscode/cadai-vscode/mcp_setup.js).
// "MCP'yi ajanlara bağla" (plan AJ-2): register the pcbai MCP server with every installed agent.
// - Each writer merges into the agent's own config and keeps everything else.
// - A config that cannot be parsed (JSON or TOML) is never touched; every written file gets a *.pcbai-bak copy first.
// - User-level registrations (Claude -s user, Codex, Cline, Kilo, Roo, VS Code mcp.json) never carry PCBAI_PROJECTS:
//   they join the running service; only the workspace .mcp.json carries the workspace's project list.
// - Auto-approved tools come from the tool registry's readOnlyHint, never from a hand-kept list.
'use strict';

const cp = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const NAME = 'pcbai';
const BACKUP = '.pcbai-bak';

class BrokenConfig extends Error {
  constructor(kind, file, detail) { super(`${kind} bozuk: ${file}${detail ? ' (' + detail + ')' : ''}`); this.kind = kind; }
}

/** Tool definitions shipped with the extension (mcp_tools.json, kept equal to the registry by tests/test_mcp_setup.py). */
function bundledTools(dir = __dirname) {
  return JSON.parse(fs.readFileSync(path.join(dir, 'mcp_tools.json'), 'utf8')).tools
    .map(t => ({ name: t.name, annotations: { readOnlyHint: t.readOnlyHint, destructiveHint: t.destructiveHint } }));
}

/** Names safe to auto-approve: readOnlyHint true and not destructive. A tool without annotations is never listed. */
function readOnlyTools(definitions) {
  return definitions.filter(d => d && d.annotations && d.annotations.readOnlyHint === true && d.annotations.destructiveHint !== true)
    .map(d => d.name).sort();
}

function readJson(file) {
  if (!fs.existsSync(file)) return {};
  const text = fs.readFileSync(file, 'utf8');
  if (!text.trim()) return {};
  try {
    const value = JSON.parse(text.replace(/^﻿/, ''));
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('nesne değil');
    return value;
  } catch (e) { throw new BrokenConfig('JSON', file, e.message); }
}

function writeJson(file, obj) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(obj, null, 2) + '\n');
}

function upsertJson(file, key, entry, name = NAME) {
  const obj = readJson(file);
  if (obj[key] !== undefined && (typeof obj[key] !== 'object' || Array.isArray(obj[key]))) throw new BrokenConfig('JSON', file, `"${key}" nesne değil`);
  obj[key] = Object.assign({}, obj[key], { [name]: entry });
  writeJson(file, obj);
}

/**
 * Lenient structural TOML check (no parser dependency): outside multi-line strings and arrays every line is blank, a
 * comment, a [table]/[[array]] header or a key = value. Anything else means we cannot safely edit the file.
 */
function checkToml(text, file = 'config.toml') {
  let depth = 0;
  let multi = null;
  const bad = (i, why) => new BrokenConfig('TOML', file, `satır ${i + 1}${why ? ': ' + why : ''}`);
  const scan = (s, i) => {
    for (let j = 0; j < s.length; j++) {
      const c = s[j];
      if (c === '#') return;
      if (s.startsWith('"""', j) || s.startsWith("'''", j)) {
        const q = s.slice(j, j + 3);
        const end = s.indexOf(q, j + 3);
        if (end < 0) { multi = q; return; }
        j = end + 2; continue;
      }
      if (c === '"' || c === "'") {
        let k = j + 1;
        while (k < s.length && s[k] !== c) k += c === '"' && s[k] === '\\' ? 2 : 1;
        if (k >= s.length) throw bad(i, 'kapanmayan dize');
        j = k; continue;
      }
      if (c === '[' || c === '{') depth++;
      if (c === ']' || c === '}') { depth--; if (depth < 0) throw bad(i); }
    }
  };
  const lines = text.replace(/^﻿/, '').split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (multi) {
      const end = line.indexOf(multi);
      if (end < 0) continue;
      multi = null; scan(line.slice(end + 3), i); continue;
    }
    if (depth > 0) { scan(line, i); continue; }
    const bare = line.trim();
    if (!bare || bare.startsWith('#')) continue;
    if (/^\[\[?[^\[\]=]+\]\]?\s*(#.*)?$/.test(bare)) continue;
    const eq = bare.indexOf('=');
    if (eq <= 0 || !/^[A-Za-z0-9_\-."' ]+$/.test(bare.slice(0, eq)) || !bare.slice(eq + 1).trim()) throw bad(i);
    scan(bare.slice(eq + 1), i);
  }
  if (depth !== 0 || multi) throw new BrokenConfig('TOML', file, 'kapanmayan parantez/dize');
}

function tomlString(s) {
  return s.includes("'") || /[\r\n]/.test(s) ? JSON.stringify(s) : `'${s}'`;
}

/** Replace (or append) [mcp_servers.pcbai] (and its sub-tables) in Codex's config.toml; everything else stays. */
function upsertCodexToml(file, command, args, env = {}, name = NAME) {
  const text = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
  checkToml(text, file);
  const out = [];
  let skipping = false;
  for (const line of text.split(/\r?\n/)) {
    const header = line.match(/^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$/);
    if (header) {
      const h = header[1].replace(/["']/g, '');
      skipping = h === `mcp_servers.${name}` || h.startsWith(`mcp_servers.${name}.`);
      if (skipping && (out[out.length - 1] || '').startsWith('# PcbAi:')) out.pop();
    }
    if (!skipping) out.push(line);
  }
  while (out.length && out[out.length - 1].trim() === '') out.pop();
  if (out.length) out.push('');
  out.push('# PcbAi: KiCad tools (sessions, ERC/DRC, markers, preview/apply edits)', `[mcp_servers.${name}]`,
    `command = ${tomlString(command)}`, `args = [${args.map(tomlString).join(', ')}]`,
    ...(Object.keys(env).length ? [`env = { ${Object.entries(env).map(([k, v]) => `${k} = ${tomlString(v)}`).join(', ')} }`] : []),
    'startup_timeout_sec = 30', 'tool_timeout_sec = 900', '');
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, out.join('\n'));
}

/** The server command. `projects` only for the workspace .mcp.json; user-level entries pass none. */
function serverEntry({ python, root, projects }) {
  const env = { PYTHONPATH: root };
  if (projects) env.PCBAI_PROJECTS = JSON.stringify(projects);
  return { command: python, args: ['-m', 'mcp_server.pcbai_mcp'], env };
}

function backup(file) {
  if (!fs.existsSync(file)) return null;
  const copy = file + BACKUP;
  fs.copyFileSync(file, copy);
  return copy;
}

/**
 * Targets for one machine. Paths are injected so tests run against a temporary userDir/home:
 * userDir = VS Code's User folder, home = the user's home, workspace = first workspace folder (or null),
 * claudeCli = claude executable (or null), installed = Set of extension ids, readOnly = tool names to auto-approve,
 * exec = execFileSync replacement for tests. Returns [{id, label, describe, file, apply()}].
 */
function targets({ userDir, home = os.homedir(), workspace = null, claudeCli = null, installed = new Set(), python, root,
  projects = [], readOnly = [], nativeVsCode = false, exec = cp.execFileSync }) {
  const user = serverEntry({ python, root });
  const gs = (ext, file) => path.join(userDir, 'globalStorage', ext, 'settings', file);
  const list = [];
  if (workspace) {
    const file = path.join(workspace, '.mcp.json');
    list.push({ id: 'claude', agents: ['claude-code', 'claude-cli'], label: 'Claude Code (çalışma alanı)', describe: file, file, kind: 'JSON',
      apply: () => upsertJson(file, 'mcpServers', serverEntry({ python, root, projects }), NAME) });
  }
  if (claudeCli) {
    list.push({ id: 'claude-user', agents: ['claude-code', 'claude-cli'], label: 'Claude Code (kullanıcı)',
      describe: `${path.basename(claudeCli)} mcp add -s user ${NAME}`, file: null,
      apply: () => {
        try { exec(claudeCli, ['mcp', 'remove', '-s', 'user', NAME], { stdio: 'ignore', timeout: 30000, windowsHide: true }); } catch (_) { /* not there */ }
        const envFlags = Object.entries(user.env).flatMap(([k, v]) => ['-e', `${k}=${v}`]);
        exec(claudeCli, ['mcp', 'add', '-s', 'user', ...envFlags, NAME, '--', user.command, ...user.args], { stdio: 'pipe', timeout: 30000, windowsHide: true });
      } });
  }
  const codexToml = path.join(home, '.codex', 'config.toml');
  if (installed.has('openai.chatgpt') || fs.existsSync(path.dirname(codexToml))) {
    list.push({ id: 'codex', agents: ['codex', 'codex-cli'], label: 'Codex', describe: codexToml, file: codexToml, kind: 'TOML',
      apply: () => upsertCodexToml(codexToml, user.command, user.args, user.env) });
  }
  const entry = key => ({ ...user, timeout: 900, disabled: false, [key]: readOnly.slice() });
  for (const [ext, id, label, file, key] of [
    ['saoudrizwan.claude-dev', 'cline', 'Cline', gs('saoudrizwan.claude-dev', 'cline_mcp_settings.json'), 'autoApprove'],
    ['kilocode.kilo-code', 'kilo', 'Kilo Code', gs('kilocode.kilo-code', 'mcp_settings.json'), 'alwaysAllow'],
    ['rooveterinaryinc.roo-cline', 'roo', 'Roo Code', gs('rooveterinaryinc.roo-cline', 'mcp_settings.json'), 'alwaysAllow'],
  ]) {
    if (installed.has(ext)) list.push({ id, agents: [id], label, describe: file, file, kind: 'JSON', apply: () => upsertJson(file, 'mcpServers', entry(key)) });
  }
  // VS Code's own MCP support (Copilot agent mode). With the native provider an mcp.json copy would list it twice.
  const vscodeMcp = path.join(userDir, 'mcp.json');
  if (!nativeVsCode) {
    list.push({ id: 'vscode', agents: ['copilot'], label: 'VS Code / GitHub Copilot', describe: vscodeMcp, file: vscodeMcp, kind: 'JSON',
      apply: () => upsertJson(vscodeMcp, 'servers', { type: 'stdio', ...user }) });
  } else {
    let present = false;
    try { present = NAME in (readJson(vscodeMcp).servers || {}); } catch (_) { /* unreadable: leave it alone */ }
    if (present) {
      list.push({ id: 'vscode', agents: ['copilot'], label: 'VS Code / GitHub Copilot', file: vscodeMcp, kind: 'JSON',
        describe: 'PcbAi yerel API ile kayıtlı; mcp.json içindeki kopya kaldırılacak',
        apply: () => { const obj = readJson(vscodeMcp); delete obj.servers[NAME]; writeJson(vscodeMcp, obj); } });
    }
  }
  return list;
}

/** Validate, back up, apply. A broken config is reported and left byte-for-byte as it was. */
function applyTarget(target) {
  try {
    if (target.file && fs.existsSync(target.file)) {
      if (target.kind === 'JSON') readJson(target.file);
      if (target.kind === 'TOML') checkToml(fs.readFileSync(target.file, 'utf8'), target.file);
    }
    const copy = target.file ? backup(target.file) : null;
    target.apply();
    return { id: target.id, label: target.label, status: 'written', backup: copy };
  } catch (e) {
    if (e instanceof BrokenConfig) return { id: target.id, label: target.label, status: 'broken', kind: e.kind, message: e.message };
    return { id: target.id, label: target.label, status: 'error', message: e.message };
  }
}

function summary(results) {
  return results.map(r => `${r.label}: ${r.status === 'written' ? 'yazıldı'
    : r.status === 'broken' ? `${r.kind} bozuk, dokunulmadı` : 'hata — ' + r.message}`).join(', ');
}

/** Whether an agent (agents.js id) already has a pcbai entry. null = not applicable (clipboard). */
function hasRegistration(agentId, { userDir, home = os.homedir(), workspace = null, nativeVsCode = false }) {
  const json = (file, key) => { try { return NAME in (readJson(file)[key] || {}); } catch (_) { return false; } };
  const gs = (ext, file) => path.join(userDir, 'globalStorage', ext, 'settings', file);
  switch (agentId) {
    case 'claude-code': case 'claude-cli':
      return Boolean(workspace && json(path.join(workspace, '.mcp.json'), 'mcpServers')) || json(path.join(home, '.claude.json'), 'mcpServers');
    case 'codex': case 'codex-cli':
      try { return /^\s*\[\s*mcp_servers\.["']?pcbai["']?\s*\]/m.test(fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8')); } catch (_) { return false; }
    case 'cline': return json(gs('saoudrizwan.claude-dev', 'cline_mcp_settings.json'), 'mcpServers');
    case 'kilo': return json(gs('kilocode.kilo-code', 'mcp_settings.json'), 'mcpServers');
    case 'roo': return json(gs('rooveterinaryinc.roo-cline', 'mcp_settings.json'), 'mcpServers');
    case 'copilot': return nativeVsCode || json(path.join(userDir, 'mcp.json'), 'servers');
    default: return null;
  }
}

/** VS Code >= 1.101: register through vscode.lm when the API exists at runtime (engines stays ^1.90). */
function registerNative(vscode, context, entry) {
  if (!vscode.lm || typeof vscode.lm.registerMcpServerDefinitionProvider !== 'function' || !vscode.McpStdioServerDefinition) return false;
  const provider = {
    provideMcpServerDefinitions: () => {
      const e = entry();
      return e ? [new vscode.McpStdioServerDefinition('PcbAi', e.command, e.args, e.env)] : [];
    },
  };
  context.subscriptions.push(vscode.lm.registerMcpServerDefinitionProvider(NAME, provider));
  return true;
}

module.exports = { NAME, BACKUP, BrokenConfig, bundledTools, readOnlyTools, readJson, upsertJson, checkToml, upsertCodexToml,
  serverEntry, targets, applyTarget, summary, hasRegistration, registerNative };
