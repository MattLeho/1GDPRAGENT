const fields = ['bridgeUrl', 'connectorInstanceId', 'pairingToken'];
const status = document.querySelector('#status');
const current = await chrome.storage.local.get(fields);
for (const key of fields) if (current[key]) document.querySelector(`#${key}`).value = current[key];
document.querySelector('#save').onclick = async () => {
  await chrome.storage.local.set(Object.fromEntries(fields.map(key => [key, document.querySelector(`#${key}`).value.trim()])));
  status.textContent = 'Pairing saved locally in the extension profile.';
};
document.querySelector('#permission').onclick = async () => {
  status.textContent = (await chrome.permissions.request({permissions: ['history']})) ? 'History permission enabled.' : 'History permission was not granted.';
};
for (const [id, type] of [['backfill', 'BACKFILL'], ['sync', 'FLUSH']]) {
  document.querySelector(`#${id}`).onclick = async () => { status.textContent = JSON.stringify(await chrome.runtime.sendMessage({type}), null, 2); };
}
