import {toBrowserVisitRecord} from './protocol.mjs';

export async function hasHistoryPermission(chromeApi) {
  return (await chromeApi.permissions.contains({permissions: ['history']})) === true;
}

export async function requestHistoryPermission(chromeApi) {
  return (await chromeApi.permissions.request({permissions: ['history']})) === true;
}

export async function backfillHistory(chromeApi, browserProfileConnectorId, {startTime = 0, maxResults = 10000} = {}) {
  if (!(await hasHistoryPermission(chromeApi))) throw new Error('history permission has not been explicitly granted');
  const items = await chromeApi.history.search({text: '', startTime, maxResults});
  const visits = [];
  for (const item of items) {
    if (!item.url) continue;
    for (const visit of await chromeApi.history.getVisits({url: item.url})) {
      visits.push(await toBrowserVisitRecord({
        ...visit, url: item.url, transitionType: visit.transition,
        browserProfileConnectorId,
      }));
    }
  }
  return visits.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at) || a.source_record_id.localeCompare(b.source_record_id));
}

export async function incrementalVisit(chromeApi, historyItem, browserProfileConnectorId) {
  if (!(await hasHistoryPermission(chromeApi)) || !historyItem.url) return [];
  const visits = await chromeApi.history.getVisits({url: historyItem.url});
  const latest = visits.sort((a, b) => b.visitTime - a.visitTime)[0];
  return latest ? [await toBrowserVisitRecord({
    ...latest, url: historyItem.url, transitionType: latest.transition,
    browserProfileConnectorId,
  })] : [];
}
