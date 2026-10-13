// Bounded IR data and read-only library assistance. No eval, executable Markdown or project writes.
const path = require('node:path');
const fs = require('node:fs');
const MAX_BYTES = 1024 * 1024;
const MAX_NODES = 20000;
const MAX_DEPTH = 16;

function parseBuffer(text) {
  if (typeof text !== 'string' || Buffer.byteLength(text, 'utf8') > MAX_BYTES) return null;
  let cursor = 0, count = 0;
  const strings = [];
  const ws = () => { while (/\s/.test(text[cursor] || '') && cursor < text.length) cursor++; };
  function value(location, depth) {
    if (++count > MAX_NODES || depth > MAX_DEPTH) throw Error('IR exceeds limits');
    ws();
    const start = cursor, ch = text[cursor];
    if (ch === '"') {
      cursor++;
      let escaped = false, closed = false;
      while (cursor < text.length) {
        const c = text[cursor++];
        if (!escaped && c === '"') {closed = true; break;}
        if (!escaped && c === '\\') escaped = true; else escaped = false;
      }
      const complete = closed;
      const raw = text.slice(start, cursor);
      let decoded;
      try { decoded = JSON.parse(complete ? raw : raw + '"'); } catch (_) { throw Error('Invalid string'); }
      if (decoded.length > 4096 || /[\x00-\x1f\x7f-\x9f]/.test(decoded) ||
          [...decoded].some(c => c.codePointAt(0) >= 0xd800 && c.codePointAt(0) <= 0xdfff)) throw Error('String exceeds limits');
      const node = {type: 'string', start, end: cursor, complete, value: decoded, path: location};
      strings.push(node);
      return node;
    }
    if (ch === '{' || ch === '[') {
      cursor++;
      const object = ch === '{';
      const node = {type: object ? 'object' : 'array', fields: new Map(), items: []};
      const close = object ? '}' : ']';
      ws();
      if (text[cursor] === close) {cursor++; return node;}
      while (cursor < text.length) {
        let key = node.items.length;
        if (object) {
          if (text[cursor] !== '"') throw Error('Expected key');
          const name = value([], depth + 1);
          name.key = true;
          if (!name.complete) return node;
          key = name.value;
          if (node.fields.has(key)) throw Error('Duplicate key');
          ws();
          if (cursor === text.length) return node;
          if (text[cursor++] !== ':') throw Error('Expected colon');
        }
        ws();
        if (cursor === text.length) return node;
        const child = value([...location, key], depth + 1);
        if (object) node.fields.set(key, child); else node.items.push(child);
        ws();
        if (cursor === text.length) return node;
        if (text[cursor] === close) {cursor++; return node;}
        if (text[cursor++] !== ',') throw Error('Expected comma');
        ws();
        if (text[cursor] === close) throw Error('Trailing comma');
      }
      return node;
    }
    const match = /^(?:-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null)/.exec(text.slice(cursor));
    if (!match) throw Error('Expected value');
    cursor += match[0].length;
    const scalar = JSON.parse(match[0]);
    if (typeof scalar === 'number' && !Number.isFinite(scalar)) throw Error('Nonfinite number');
    return {type: 'scalar', value: scalar};
  }
  try {
    const root = value([], 0);
    ws();
    if (cursor !== text.length || root.type !== 'object') return null;
    return {root, strings};
  } catch (_) {return null;}
}

const field = (node, name) => node?.type === 'object' ? node.fields.get(name) : undefined;
const literal = (node, name) => field(node, name)?.value;
function contextAt(text, offset) {
  const parsed = parseBuffer(text);
  if (!parsed) return null;
  const node = parsed.strings.find(s => !s.key && offset >= s.start + 1 && offset <= s.end - (s.complete ? 1 : 0));
  if (!node) return null;
  let prefix;
  try {prefix = JSON.parse('"' + text.slice(node.start + 1, offset) + '"');} catch (_) {return null;}
  const parts = field(parsed.root, 'parts')?.items || [];
  const [section, index, key] = node.path;
  if (section === 'parts' && Number.isInteger(index) && node.path.length === 3 && ['symbol', 'footprint'].includes(key)) {
    return {kind: key, node, prefix, symbol: literal(parts[index], 'symbol'), unit: field(parts[index], 'unit') ? literal(parts[index], 'unit') : 1};
  }
  if (section === 'connections' && node.path.length === 3 && Number.isInteger(index) && Number.isInteger(key)) {
    const endpoint = node.value;
    const dot = endpoint.indexOf('.');
    if (dot < 1) return null;
    const id = endpoint.slice(0, dot);
    const matching = parts.filter(p => literal(p, 'id') === id);
    if (matching.length !== 1) return null;
    return {kind: 'pin', node, prefix, id, symbol: literal(matching[0], 'symbol'),
      unit: field(matching[0], 'unit') ? literal(matching[0], 'unit') : 1, pin: endpoint.slice(dot + 1)};
  }
  return null;
}

function inProject(document, session) {
  if (!session?.id || !session.revision || !session.root || !document.uri?.fsPath) return false;
  try {
    const root = fs.realpathSync.native(session.root);
    let ancestor = path.resolve(document.uri.fsPath);
    const suffix = [];
    for (let i = 0; i < 256; i++) {
      try {
        ancestor = fs.realpathSync.native(ancestor);
        const relative = path.relative(root, path.join(ancestor, ...suffix.reverse()));
        return relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative);
      } catch (error) {
        if (error.code !== 'ENOENT') return false;
        // A dangling link/reparse point is an existing object, never an ordinary missing suffix.
        try {fs.lstatSync(ancestor); return false;} catch (lookupError) {
          if (lookupError.code !== 'ENOENT') return false;
        }
        const parent = path.dirname(ancestor);
        if (parent === ancestor) return false;
        suffix.push(path.basename(ancestor)); ancestor = parent;
      }
    }
  } catch (_) {return false;}
  return false;
}
const scopeKey = s => `${s?.id || ''}:${s?.revision || ''}:${s?.root || ''}`;
const plain = value => String(value ?? '').replace(/[\x00-\x1f\x7f-\x9f]/g, ' ').slice(0, 4096);

function createAssist(vscode, options) {
  // Cache only presentation data after a FRESH library response proves its SHA; never bypass library reads.
  const cache = new Map();
  async function inspect(document, position, token, work) {
    const version = document.version, uri = document.uri.toString();
    const ctx = contextAt(document.getText(), document.offsetAt(position));
    if (!ctx || token?.isCancellationRequested) return null;
    const session = await options.sessionFor(false, document);
    if (!inProject(document, session)) return null;
    const scope = scopeKey(session);
    const response = await work(ctx);
    const current = scopeKey(await options.sessionFor(false, document));
    if (token?.isCancellationRequested || document.version !== version || document.uri.toString() !== uri || current !== scope) return null;
    return {ctx, response, version, uri, sessionKey: scope, scope: `${uri}:${version}:${scope}`};
  }
  async function fresh(document, answer, token) {
    const current = scopeKey(await options.sessionFor(false, document));
    return !token?.isCancellationRequested && document.version === answer.version && document.uri.toString() === answer.uri && current === answer.sessionKey;
  }
  async function part(ctx) {
    if (typeof ctx.symbol !== 'string' || !ctx.symbol.includes(':')) return null;
    const output = await options.call('part_info', {lib_id: ctx.symbol, kind: 'symbol'});
    return output?.ok ? output.part : null;
  }
  async function completions(document, position, token) {
    try {
      const answer = await inspect(document, position, token, async ctx => {
        if (ctx.kind === 'symbol') {
          const query = ctx.prefix.includes(':') ? ctx.prefix.split(':').slice(1).join(':') : ctx.prefix;
          if (!query.trim()) return {parts: []};
          return options.call('search_parts', {query: query.slice(0, 512), limit: 100});
        }
        return {part: await part(ctx)};
      });
      if (!answer) return [];
      const {ctx, response} = answer;
      let entries = [];
      if (ctx.kind === 'symbol') entries = response?.ok ? (response.parts || []).map(p => ({label: p.lib_id, detail: p.description, sha: p.library_sha256})) : [];
      else if (ctx.kind === 'footprint') {
        const fp = response?.part?.properties?.Footprint;
        if (fp) {
          const checked = await options.call('part_info', {lib_id: fp, kind: 'footprint'});
          if (!(await fresh(document, answer, token))) return [];
          if (checked?.ok) entries = [{label: fp, detail: 'Sembolün yerel Footprint alanı', sha: checked.part.sha256}];
        }
      } else if (Number.isInteger(ctx.unit) && ctx.unit > 0) {
        const pins = response?.part?.pins || [];
        entries = pins.filter(p => p.unit === 0 || p.unit === ctx.unit).map(p => ({label: `${ctx.id}.${p.number}`, detail: p.name, sha: response.part.library_sha256}));
      }
      // Symbol/pin responses were fenced by inspect; footprint's extra lookup was fenced above.
      if (token?.isCancellationRequested || document.version !== answer.version || document.uri.toString() !== answer.uri) return [];
      entries = entries.filter(e => typeof e.label === 'string' && /^[a-f0-9]{64}$/.test(e.sha || ''));
      const matching = entries.filter(e => e.label.toLowerCase().startsWith(ctx.prefix.toLowerCase()));
      const alternatives = matching.length === 0;
      if (matching.length) entries = matching;
      const seen = new Set();
      return entries.filter(e => !seen.has(e.label) && seen.add(e.label)).map(entry => {
        const item = new vscode.CompletionItem(plain(entry.label), vscode.CompletionItemKind.Value);
        item.insertText = JSON.stringify(entry.label).slice(1, -1);
        item.filterText = alternatives ? ctx.prefix + ' ' + entry.label : entry.label;
        const exactName = ctx.kind === 'symbol' && entry.label.split(':').pop() === ctx.prefix.split(':').pop();
        item.sortText = (exactName ? '0000' : '0001') + entry.label;
        item.range = new vscode.Range(document.positionAt(ctx.node.start + 1), document.positionAt(ctx.node.end - (ctx.node.complete ? 1 : 0)));
        item.detail = (alternatives ? 'Yerel alternatif · ' : '') + plain(entry.detail) + ' · SHA ' + entry.sha.slice(0, 12);
        return item;
      });
    } catch (_) {return [];}
  }
  async function hover(document, position, token) {
    try {
      const answer = await inspect(document, position, token, async ctx => {
        if (ctx.kind !== 'footprint') return part(ctx);
        const output = await options.call('part_info', {lib_id: ctx.node.value, kind: 'footprint'});
        return output?.ok ? output.part : null;
      });
      if (!answer?.response || !/^[a-f0-9]{64}$/.test(answer.response.library_sha256 || answer.response.sha256 || '')) return undefined;
      const {ctx, response: info, scope} = answer;
      const pins = (info.pins || []).filter(p => (p.unit === 0 || p.unit === ctx.unit) && (ctx.kind !== 'pin' || p.number === ctx.pin));
      const sha = info.library_sha256 || info.sha256;
      const text = [info.lib_id, info.properties?.Description, `Kaynak: ${info.source} · ${info.path}`,
        `SHA-256: ${sha}`, `Birim: ${ctx.unit}`, ...pins.map(p => `${p.number}: ${p.name} (${p.electrical_type})`),
        ...(info.pads || []).map(p => `Pad ${p.number}: ${p.type} (${p.shape})`),
        'Pin/pad eşleşmesi stok, datasheet veya üretim kabulü değildir.'].map(plain).join('\n');
      const key = `${scope}:${info.lib_id}:${sha}:${ctx.kind}:${ctx.pin || ''}:${ctx.unit}`;
      if (!cache.has(key)) {
        const markdown = new vscode.MarkdownString();
        markdown.isTrusted = false; markdown.supportHtml = false;
        markdown.appendText(text);
        cache.set(key, markdown);
        if (cache.size > 64) cache.delete(cache.keys().next().value);
      }
      return new vscode.Hover(cache.get(key));
    } catch (_) {return undefined;}
  }
  return {completions, hover};
}

function register(context, options) {
  const vscode = require('vscode');
  const assist = createAssist(vscode, options);
  const selector = ['file', 'untitled'].flatMap(scheme => ['**/*.pcbai-ir.json', '**/*.pcbai.json'].map(pattern => ({scheme, language: 'json', pattern})));
  context.subscriptions.push(vscode.languages.registerCompletionItemProvider(selector, {provideCompletionItems: assist.completions}, '"', '.', ':'),
    vscode.languages.registerHoverProvider(selector, {provideHover: assist.hover}));
}
module.exports = {parseBuffer, contextAt, inProject, createAssist, register};
