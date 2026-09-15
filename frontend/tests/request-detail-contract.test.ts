import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (relativePath: string) => fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8');

describe('request detail truthfulness contract', () => {
  it('uses recorded deadline evidence instead of inventing a 30-day countdown', () => {
    const modal = source('components/requests/RequestDetailModal.tsx');
    expect(modal).toContain('request.deadline_at');
    expect(modal).toContain('Deadline not established');
    expect(modal).not.toContain('(daysPassed / 30)');
    expect(modal).not.toContain('30 - daysPassed');
  });

  it('rolls back optimistic chat state before suppressing an auth redirect error', () => {
    const modal = source('components/requests/RequestDetailModal.tsx');
    const catchBlock = modal.slice(modal.indexOf('const sendChatMessage'), modal.indexOf('if (!request) return null'));
    expect(catchBlock.indexOf('prev.filter(item => item !== optimisticMessage)'))
      .toBeLessThan(catchBlock.indexOf('shouldSuppressProtectedRequestError(error)'));
  });

  it('does not return raw server exception details to the browser', () => {
    const route = source('app/api/request-threads/[id]/chat/route.ts');
    expect(route).not.toContain('details: String(error)');
    expect(route).toContain("error: 'Failed to process message'");
  });

  it('remounts request-local UI state when the selected request changes', () => {
    const grid = source('components/requests/RequestsGrid.tsx');
    expect(grid).toContain("key={selectedRequest?.id ?? 'no-request'}");
  });

  it('makes the owned route the primary record while retaining a labelled quick workspace', () => {
    const card = source('components/requests/RequestCard.tsx');
    const modal = source('components/requests/RequestDetailModal.tsx');

    expect(card).toContain('href={`/dashboard/requests/${request.id}`}');
    expect(card).toContain('Open request');
    expect(card).toContain('aria-label={`Quick view ${request.company_name}`}');
    expect(modal).toContain('Open full request');
    expect(modal).toContain('href={`/dashboard/requests/${request.id}`}');
  });

  it('uses recorded upload state without fake deletion, progress, or duplicate ingestion claims', () => {
    const modal = source('components/requests/RequestDetailModal.tsx');
    const scanRoute = source('app/api/upload/scan/route.ts');

    expect(modal).not.toContain('Math.random()');
    expect(modal).not.toContain('handleDeleteFile');
    expect(modal).not.toContain('Add to knowledge graph');
    expect(modal).not.toContain("method: 'PUT'");
    expect(modal).toContain("body: JSON.stringify({ requestId: request.id })");
    expect(scanRoute).toContain('requestId');
    expect(scanRoute).toContain('pendingReceivedData(authority.profileId, requestId)');
  });

  it('rejects invalid request identifiers before querying UUID columns', () => {
    const page = source('app/dashboard/requests/[id]/page.tsx');
    expect(page).toContain('UUID_PATTERN.test(id)');
    expect(page.indexOf('UUID_PATTERN.test(id)')).toBeLessThan(page.indexOf('Promise.all(['));
  });

  it('loads the owned request once and exposes only server-backed actions', () => {
    const page = source('app/dashboard/requests/[id]/page.tsx');
    expect(page.match(/getRequestById\(id\)/g)).toHaveLength(1);
    expect(page).not.toContain('Open Data Export');
    expect(page).not.toContain('/api/upload?requestId=');
    expect(page).not.toContain('<Download');
    expect(page).toContain("await updateRequestStatus(request.id, 'completed')");
    expect(page).toContain('No server-backed request actions are currently available for this status.');
  });

  it('reflows the direct detail header and tabs on narrow screens', () => {
    const page = source('app/dashboard/requests/[id]/page.tsx');
    expect(page).toContain('flex min-w-0 flex-col items-start gap-4 sm:flex-row');
    expect(page).toContain('break-words text-2xl');
    expect(page).toContain('grid-cols-1 gap-1 sm:grid-cols-3');
    expect(page).toContain('px-4 sm:px-6');
  });
});
