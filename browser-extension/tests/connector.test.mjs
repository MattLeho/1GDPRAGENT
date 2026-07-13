import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {backfillHistory} from '../src/history.mjs';
import {frame, toBrowserVisitRecord, visitPayload} from '../src/protocol.mjs';
import {PersistentQueue} from '../src/queue.mjs';

test('visit signatures are deterministic and preserve required history semantics', async () => {
  const visit = {
    url: 'https://example.test/path?q=1', visitId: '42', visitTime: 1710000000000,
    transitionType: 'link', referringVisitId: '41', isLocal: true,
    browserProfileConnectorId: 'browser-profile-1'
  };
  const first = await toBrowserVisitRecord(visit);
  const repeated = await toBrowserVisitRecord(visit);
  assert.equal(first.record_signature, repeated.record_signature);
  assert.equal(first.record_signature, '3de7d0c0990a209c9a06d0e38ceef1bdb1de5f9d5a8933613b93e397b8750d4d');
  assert.equal(first.data_class, 'browser.visit');
  assert.deepEqual(first.required_permissions, ['history.read']);
  assert.deepEqual(JSON.parse(new TextDecoder().decode(visitPayload(visit))), {
    browser_profile_connector_id: 'browser-profile-1', referring_visit_id: '41',
    transition_type: 'link', url: 'https://example.test/path?q=1', visit_id: '42',
    visit_time: '2024-03-09T16:00:00.000Z'
  });
});

test('history backfill is permission gated and deterministic', async () => {
  const denied = {
    permissions: {contains: async () => false},
    history: {search: async () => { throw new Error('must not read'); }}
  };
  await assert.rejects(() => backfillHistory(denied, 'profile-1'), /explicitly granted/);

  const chromeApi = {
    permissions: {contains: async () => true},
    history: {
      search: async () => [{url: 'https://b.test'}, {url: 'https://a.test'}],
      getVisits: async ({url}) => [{visitId: url.includes('a.') ? '1' : '2', visitTime: 10, transition: 'typed'}]
    }
  };
  const records = await backfillHistory(chromeApi, 'profile-1');
  assert.equal(records.length, 2);
  assert.ok(records.every(record => record.source_metadata.browser_profile_connector_id === 'profile-1'));
});

test('bounded persistent queue deduplicates and only removes acknowledged records', async () => {
  const state = {};
  const storage = {get: async key => ({[key]: state[key]}), set: async value => Object.assign(state, value)};
  const queue = new PersistentQueue(storage, 'queue', 2);
  await queue.append([{record_signature: 'a'}, {record_signature: 'a'}, {record_signature: 'b'}]);
  assert.deepEqual((await queue.read()).map(item => item.record_signature), ['a', 'b']);
  await assert.rejects(() => queue.append([{record_signature: 'c'}]), /queue is full/);
  assert.equal(await queue.acknowledge(['a']), 1);
  assert.deepEqual((await queue.read()).map(item => item.record_signature), ['b']);
});

test('framing is versioned, bounded and source contains no page-content capture', async () => {
  const message = frame([{record_signature: 'a'}], 'connector-1', '00000000-0000-4000-8000-000000000001');
  assert.equal(message.version, 1);
  assert.equal(message.connector_instance_id, 'connector-1');
  assert.throws(() => frame([], 'connector-1'), /1-250/);
  const sources = await Promise.all(['history.mjs', 'protocol.mjs', 'service-worker.mjs'].map(
    name => readFile(resolve(import.meta.dirname, '..', 'src', name), 'utf8')
  ));
  const joined = sources.join('\n');
  for (const forbidden of ['document.body', 'innerHTML', 'password', 'creditCard', 'cookies']) {
    assert.equal(joined.includes(forbidden), false, `unexpected page capture primitive: ${forbidden}`);
  }
});
