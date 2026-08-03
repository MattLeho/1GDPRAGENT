import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const mocks = vi.hoisted(() => ({
  authority: { userId: 'user-a', profileId: 'profile-a' },
  query: vi.fn(),
  pipeline: vi.fn(),
  chat: vi.fn(),
  graphRun: vi.fn(),
  graphClose: vi.fn(),
}));

vi.mock('@/lib/api-session', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api-session')>();
  return { ...original, requireApiSession: vi.fn(async () => mocks.authority) };
});
vi.mock('@/lib/db', () => ({ pool: { query: mocks.query } }));
vi.mock('@/lib/ingestion/bulk', () => ({ processThroughBulkPipeline: mocks.pipeline }));
vi.mock('@/lib/rlm-agent', () => ({ getRLMAgent: () => ({ chat: mocks.chat }) }));
vi.mock('@/lib/graph', () => ({ getDriver: () => ({ session: () => ({ run: mocks.graphRun, close: mocks.graphClose }) }) }));

import { DELETE as deleteRequest } from '@/app/api/requests/[id]/route';
import { GET as getThread } from '@/app/api/request-threads/[id]/chat/route';
import { POST as processUpload } from '@/app/api/upload/process/route';
import { DELETE as deleteDocument } from '@/app/api/settings/id-documents/route';
import { POST as createGraphNode } from '@/app/api/graph/nodes/route';
import { GET as getInsightEvidence } from '@/app/api/insights/evidence/[id]/route';
import { GET as getGraph } from '@/app/api/graph/route';

function jsonRequest(url: string, method: string, body?: unknown) {
  return new NextRequest(url, {
    method,
    headers: { origin: 'https://gdpr.test', 'content-type': 'application/json', 'x-gdpr-csrf': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

describe('R1 cross-profile object isolation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.INTERNAL_API_KEY = 'r1-object-isolation-internal-key';
  });

  it('does not delete a request when the object is foreign', async () => {
    mocks.query.mockResolvedValueOnce({ rowCount: 0, rows: [] });
    const response = await deleteRequest(jsonRequest('https://gdpr.test/api/requests/foreign', 'DELETE'), {
      params: Promise.resolve({ id: 'foreign-request' }),
    });
    expect(response.status).toBe(404);
    expect(mocks.query).toHaveBeenCalledTimes(1);
    expect(mocks.query).toHaveBeenCalledWith(expect.stringMatching(/profile_id = \$2/), ['foreign-request', 'profile-a']);
  });

  it('does not read a foreign request thread or its messages', async () => {
    mocks.query.mockResolvedValueOnce({ rowCount: 0, rows: [] });
    const response = await getThread(jsonRequest('https://gdpr.test/api/request-threads/foreign/chat', 'GET'), {
      params: Promise.resolve({ id: 'foreign-thread-parent' }),
    });
    expect(response.status).toBe(404);
    expect(mocks.query).toHaveBeenCalledTimes(1);
    expect(mocks.query).toHaveBeenCalledWith(expect.stringMatching(/profile_id = \$2/), ['foreign-thread-parent', 'profile-a']);
  });

  it('does not process a foreign uploaded file', async () => {
    mocks.query.mockResolvedValueOnce({ rowCount: 0, rows: [] });
    const response = await processUpload(jsonRequest('https://gdpr.test/api/upload/process', 'POST', {
      fileId: 'foreign-file', profileId: 'profile-b',
    }));
    expect(response.status).toBe(404);
    expect(mocks.query).toHaveBeenCalledWith(expect.stringMatching(/id=\$1 AND profile_id=\$2/), ['foreign-file', 'profile-a']);
    expect(mocks.pipeline).not.toHaveBeenCalled();
  });

  it('does not delete a foreign identity document', async () => {
    mocks.query.mockResolvedValueOnce({ rowCount: 0, rows: [] });
    const response = await deleteDocument(jsonRequest('https://gdpr.test/api/settings/id-documents?id=foreign-doc', 'DELETE'));
    expect(response.status).toBe(404);
    expect(mocks.query).toHaveBeenCalledWith(expect.stringMatching(/id = \$1 AND profile_id = \$2/), ['foreign-doc', 'profile-a']);
  });

  it('forwards graph mutations with signed authority for the session profile', async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify({ ok: true }), {
      status: 200, headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    await createGraphNode(jsonRequest('https://gdpr.test/api/graph/nodes', 'POST', {
      label: 'foreign-object-probe', type: 'Person', profileId: 'profile-b',
    }));
    const init = fetchMock.mock.calls[0][1];
    const headers = new Headers(init?.headers);
    expect(headers.get('x-gdpr-profile-id')).toBe('profile-a');
    expect(headers.get('x-gdpr-internal-key')).toMatch(/^[0-9a-f]{64}$/);
  });

  it('does not let a graph query-string profileId override session authority', async () => {
    mocks.graphRun
      .mockResolvedValueOnce({ records: [{ get: () => ({ toNumber: () => 0 }) }] })
      .mockResolvedValueOnce({ records: [] })
      .mockResolvedValueOnce({ records: [] });
    const response = await getGraph(jsonRequest('https://gdpr.test/api/graph?profileId=profile-b&limit=1', 'GET'));
    expect(response.status).toBe(200);
    expect(mocks.graphRun).toHaveBeenCalled();
    for (const call of mocks.graphRun.mock.calls) {
      const params = call[1] as Record<string, unknown> | undefined;
      if (params && 'profileId' in params) expect(params.profileId).toBe('profile-a');
    }
  });

  it('forwards Insights object reads with signed authority for the session profile', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ evidence: null }), {
      status: 404, headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const response = await getInsightEvidence(jsonRequest('https://gdpr.test/api/insights/evidence/foreign', 'GET'), {
      params: Promise.resolve({ id: 'foreign-evidence' }),
    });
    expect(response.status).toBe(404);
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get('x-gdpr-profile-id')).toBe('profile-a');
    expect(headers.get('x-gdpr-internal-key')).toMatch(/^[0-9a-f]{64}$/);
  });
});
