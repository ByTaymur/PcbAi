// AJ-3: the extension's fallback prompt and the service's compose_agent_prompt give the same bytes for the shared
// fixtures (tests/fixtures/agent_prompt); servicePrompt prefers the service and falls back only for an older one.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { composeAgentPrompt, servicePrompt } = require('../agent_prompt');

const FIXTURES = path.resolve(__dirname, '..', '..', '..', 'tests', 'fixtures', 'agent_prompt');

async function main() {
  const files = fs.readdirSync(FIXTURES).filter(f => f.endsWith('.json')).sort();
  assert.ok(files.length >= 11);
  for (const file of files) {
    const record = JSON.parse(fs.readFileSync(path.join(FIXTURES, file), 'utf8'));
    const input = { markers: [], pages: {}, ...record.input };
    if ('error' in record) assert.throws(() => composeAgentPrompt(input), { message: record.error }, file);
    else assert.equal(composeAgentPrompt(input), record.expected, file);
  }

  const fallback = () => 'yerel';
  assert.equal(await servicePrompt(async () => ({ ok: true, prompt: 'servis' }), {}, fallback), 'servis');
  assert.equal(await servicePrompt(async () => null, {}, fallback), 'yerel');
  assert.equal(await servicePrompt(undefined, {}, fallback), 'yerel');
  assert.equal(await servicePrompt(async () => { throw new Error('HTTP 404'); }, {}, fallback), 'yerel');
  await assert.rejects(servicePrompt(async () => { throw new Error('bağlantı koptu'); }, {}, fallback), /bağlantı koptu/);
  await assert.rejects(servicePrompt(async () => ({ ok: false, error: { message: 'İşaret bulunamadı' } }), {}, fallback),
    /İşaret bulunamadı/);
  console.log(`Agent prompt: ${files.length} shared fixtures byte-equal with Python, service-first with old-service fallback passed`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
