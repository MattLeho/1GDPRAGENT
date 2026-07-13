import {backfillHistory, hasHistoryPermission, incrementalVisit} from './history.mjs';
import {assertAcknowledgement, frame, MAX_BATCH_RECORDS} from './protocol.mjs';
import {PersistentQueue} from './queue.mjs';

const queue = new PersistentQueue(chrome.storage.local);

async function settings() {
  const values = await chrome.storage.local.get(['bridgeUrl', 'pairingToken', 'connectorInstanceId', 'browserProfileConnectorId']);
  return {
    bridgeUrl: values.bridgeUrl || 'http://127.0.0.1:8001/connectors/browser/sync',
    pairingToken: values.pairingToken,
    connectorInstanceId: values.connectorInstanceId,
    browserProfileConnectorId: values.browserProfileConnectorId || values.connectorInstanceId,
  };
}

async function flush() {
  const config = await settings();
  if (!config.pairingToken || !config.connectorInstanceId) return {status: 'unpaired'};
  const pending = await queue.read();
  if (!pending.length) return {status: 'idle'};
  const records = pending.slice(0, MAX_BATCH_RECORDS);
  const message = frame(records, config.connectorInstanceId);
  const response = await fetch(config.bridgeUrl, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'Authorization': `Bearer ${config.pairingToken}`},
    body: JSON.stringify(message)
  });
  if (!response.ok) throw new Error(`local bridge returned ${response.status}`);
  const acknowledgement = assertAcknowledgement(await response.json(), message.message_id);
  await queue.acknowledge(acknowledgement.record_signatures);
  return acknowledgement;
}

async function backfill(startTime = 0) {
  const config = await settings();
  if (!config.browserProfileConnectorId) throw new Error('connector is not paired');
  const records = await backfillHistory(chrome, config.browserProfileConnectorId, {startTime});
  for (let index = 0; index < records.length; index += MAX_BATCH_RECORDS) {
    await queue.append(records.slice(index, index + MAX_BATCH_RECORDS));
    await flush();
  }
  return {queued: records.length};
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const operation = message?.type === 'BACKFILL' ? backfill(message.startTime || 0) :
    message?.type === 'FLUSH' ? flush() : Promise.reject(new Error('unknown connector operation'));
  operation.then(sendResponse, error => sendResponse({error: error.message}));
  return true;
});

chrome.history.onVisited.addListener(async item => {
  try {
    if (!(await hasHistoryPermission(chrome))) return;
    const config = await settings();
    if (!config.browserProfileConnectorId) return;
    await queue.append(await incrementalVisit(chrome, item, config.browserProfileConnectorId));
    await flush();
  } catch (error) {
    await chrome.storage.local.set({lastError: String(error), lastErrorAt: new Date().toISOString()});
  }
});

chrome.alarms.create('gdpr-agent-browser-sync', {periodInMinutes: 1});
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'gdpr-agent-browser-sync') flush().catch(async error => {
    await chrome.storage.local.set({lastError: String(error), lastErrorAt: new Date().toISOString()});
  });
});
