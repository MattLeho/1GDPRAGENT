import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import {
    RequestRepository,
    type RequestDatabase,
    type RequestDatabaseClient,
    type RequestQueryResult,
} from '@/lib/requests/repository';
import { RequestService } from '@/lib/requests/service';
import type { Request } from '@/lib/requests/types';

const requestRow = {
    id: 'request-a', profile_id: 'profile-a', company_name: 'Example', company_url: null,
    domain: 'example.test', request_type: 'access', status: 'draft', progress: 0,
    notes: null, deadline_basis: null, created_at: '2024-01-01T00:00:00.000Z',
    updated_at: '2024-01-01T00:00:00.000Z', sent_at: null,
    controller_received_at: null, identity_requested_at: null, identity_verified_at: null,
    clarification_requested_at: null, clarification_resolved_at: null,
    response_received_at: null, completed_at: null, deadline_at: null,
    extension_notified_at: null, extension_deadline_at: null, next_action_at: null,
} satisfies Request;

function result<Row>(rows: Row[]): RequestQueryResult<Row> {
    return { rows, rowCount: rows.length };
}

type TestQuery = (sql: string, values?: readonly unknown[]) => Promise<RequestQueryResult<unknown>>;
type TestQueryMock = ReturnType<typeof vi.fn<TestQuery>>;

function queryReturning<Row>(rows: Row[]): TestQueryMock {
    return vi.fn<TestQuery>(async () => result(rows));
}

function databaseWith(query: TestQueryMock = queryReturning([])): RequestDatabase & { query: TestQueryMock } {
    return {
        query: query as unknown as RequestDatabase['query'],
        connect: vi.fn(async () => { throw new Error('connect not configured'); }),
    } as unknown as RequestDatabase & { query: TestQueryMock };
}

describe('R2 canonical request repository', () => {
    it('materializes state transitions so the volatile function executes once', async () => {
        const query = queryReturning([requestRow]);
        const repository = new RequestRepository(databaseWith(query));
        await repository.transition('profile-a', {
            request_id: 'request-a', next_state: 'ready_for_review', actor: 'tester',
            reason: 'reviewed', transitioned_at: '2024-01-01T00:00:00Z',
        });
        expect(query.mock.calls[0]?.[0]).toContain('WITH transitioned AS MATERIALIZED');
    });

    it('parameterizes dynamic list filters and always scopes the profile', async () => {
        const database = databaseWith(queryReturning([requestRow]));
        const repository = new RequestRepository(database);

        await repository.list('profile-a', {
            search: "Acme%' OR TRUE --",
            status: 'awaiting_response',
            sort: 'company_asc',
            limit: 25,
            offset: 5,
        });

        const [sql, values] = database.query.mock.calls[0];
        expect(sql).toContain('profile_id = $1');
        expect(sql).toContain('ILIKE $2');
        expect(sql).toContain('status = $3');
        expect(sql).toContain('ORDER BY company_name ASC');
        expect(sql).not.toContain("Acme%' OR TRUE --");
        expect(values).toEqual(['profile-a', "%Acme%' OR TRUE --%", 'awaiting_response', 25, 5]);
    });

    it('contains no compatibility-view dependency', () => {
        const source = readFileSync(path.join(process.cwd(), 'lib/requests/repository.ts'), 'utf8');
        expect(source).not.toContain(['access', 'requests'].join('_'));
    });

    it('returns null when profile ownership does not resolve', async () => {
        const database = databaseWith();
        const repository = new RequestRepository(database);

        await expect(repository.get('profile-a', 'foreign-request')).resolves.toBeNull();
        const [sql, values] = database.query.mock.calls[0];
        expect(sql).toMatch(/id = \$1 AND profile_id = \$2/);
        expect(values).toEqual(['foreign-request', 'profile-a']);
    });

    it('proves parent and child profile ownership for child reads', async () => {
        const database = databaseWith();
        const repository = new RequestRepository(database);

        await repository.events('profile-a', 'request-a');
        await repository.messages('profile-a', 'request-a');
        await repository.chat('profile-a', 'request-a');
        await repository.receivedData('profile-a', 'request-a');
        await repository.getOwnedReceivedData('profile-a', 'file-a');
        await repository.context('profile-a', 'request-a');

        for (const [sql, values] of database.query.mock.calls) {
            expect(sql).toContain('requests');
            expect(sql).toMatch(/profile_id\s*=\s*\$2|profile_id\s*=\s*r\.profile_id/);
            expect(values).toContain('profile-a');
        }
    });

    it('creates only from explicit lifecycle inputs and preserves them as parameters', async () => {
        const database = databaseWith(queryReturning([requestRow]));
        const service = new RequestService(new RequestRepository(database));

        await service.create('profile-a', {
            company_name: ' Example ', request_type: 'access', status: 'draft', progress: 110,
            controller_received_at: '2024-01-31T00:00:00.000Z',
            deadline_at: '2024-02-29T00:00:00.000Z', deadline_basis: 'recorded receipt',
        });

        const [sql, values] = database.query.mock.calls[0];
        expect(sql.split('RETURNING')[0]).not.toMatch(/\bcreated_at\b|\bupdated_at\b/);
        expect(values).toContain('2024-01-31T00:00:00.000Z');
        expect(values).toContain('2024-02-29T00:00:00.000Z');
        expect(values).toContain(100);
    });

    it('propagates complete transition metadata to migration 031 function', async () => {
        const transitioned = { ...requestRow, status: 'sent' as const, sent_at: '2024-01-02T00:00:00.000Z' };
        const database = databaseWith(queryReturning([transitioned]));
        const service = new RequestService(new RequestRepository(database));

        await service.transition('profile-a', {
            request_id: 'request-a', next_state: 'sent', actor: ' user:1 ', reason: ' approved send ',
            evidence_reference: 'outbound:42', transitioned_at: '2024-01-02T00:00:00.000Z',
            sent_at: '2024-01-02T00:00:00.000Z', next_action_at: '2024-02-01T00:00:00.000Z',
        });

        const [sql, values] = database.query.mock.calls[0];
        expect(sql).toContain('transition_request_state');
        expect(values?.slice(0, 7)).toEqual([
            'request-a', 'profile-a', 'sent', 'user:1', 'approved send', 'outbound:42',
            '2024-01-02T00:00:00.000Z',
        ]);
        expect(values?.[7]).toBe('2024-01-02T00:00:00.000Z');
        expect(values?.[19]).toBe('2024-02-01T00:00:00.000Z');
    });

    it.each([
        [{ actor: ' ', reason: 'reason' }, 'actor is required'],
        [{ actor: 'actor', reason: ' ' }, 'reason is required'],
        [{ actor: 'actor', reason: 'reason', next_state: 'invented' }, 'Unknown canonical request state'],
    ])('rejects invalid transition input before SQL %#', async (override, message) => {
        const database = databaseWith();
        const service = new RequestService(new RequestRepository(database));
        const command = {
            request_id: 'request-a', next_state: 'sent', actor: 'actor', reason: 'reason',
            transitioned_at: '2024-01-02T00:00:00.000Z',
        } as Parameters<RequestService['transition']>[1];
        Object.assign(command, override);

        expect(() => service.transition('profile-a', command)).toThrow(message);
        expect(database.query).not.toHaveBeenCalled();
    });

    it('clamps operational progress in the service', async () => {
        const database = databaseWith(queryReturning([requestRow]));
        const service = new RequestService(new RequestRepository(database));

        await service.updateProgress('profile-a', 'request-a', -12.8);
        expect(database.query.mock.calls[0][1]).toEqual([0, 'request-a', 'profile-a']);
    });

    it('commits and releases a transactional owned delete', async () => {
        const query = vi.fn()
            .mockResolvedValueOnce(result([]))
            .mockResolvedValueOnce(result([{ id: 'request-a' }]))
            .mockResolvedValueOnce(result([{ id: 'request-a' }]))
            .mockResolvedValueOnce(result([]));
        const client = { query, release: vi.fn() } as RequestDatabaseClient;
        const database: RequestDatabase = { query: vi.fn(), connect: vi.fn(async () => client) };

        await expect(new RequestRepository(database).delete('profile-a', 'request-a')).resolves.toBe(true);
        expect(query.mock.calls.map(call => call[0].trim())).toEqual([
            'BEGIN', expect.stringMatching(/^SELECT id FROM requests/),
            expect.stringMatching(/^DELETE FROM requests/), 'COMMIT',
        ]);
        expect(client.release).toHaveBeenCalledOnce();
    });

    it('rolls back without deleting when ownership fails', async () => {
        const query = vi.fn()
            .mockResolvedValueOnce(result([]))
            .mockResolvedValueOnce(result([]))
            .mockResolvedValueOnce(result([]));
        const client = { query, release: vi.fn() } as RequestDatabaseClient;
        const database: RequestDatabase = { query: vi.fn(), connect: vi.fn(async () => client) };

        await expect(new RequestRepository(database).delete('profile-a', 'foreign')).resolves.toBe(false);
        expect(query.mock.calls.map(call => call[0].trim())).toEqual([
            'BEGIN', expect.stringMatching(/^SELECT id FROM requests/), 'ROLLBACK',
        ]);
        expect(query.mock.calls.some(call => /^DELETE/.test(call[0].trim()))).toBe(false);
        expect(client.release).toHaveBeenCalledOnce();
    });

    it('rolls back and releases when deletion fails', async () => {
        const failure = new Error('delete failed');
        const query = vi.fn()
            .mockResolvedValueOnce(result([]))
            .mockResolvedValueOnce(result([{ id: 'request-a' }]))
            .mockRejectedValueOnce(failure)
            .mockResolvedValueOnce(result([]));
        const client = { query, release: vi.fn() } as RequestDatabaseClient;
        const database: RequestDatabase = { query: vi.fn(), connect: vi.fn(async () => client) };

        await expect(new RequestRepository(database).delete('profile-a', 'request-a')).rejects.toThrow(failure);
        expect(query.mock.calls.at(-1)?.[0]).toBe('ROLLBACK');
        expect(client.release).toHaveBeenCalledOnce();
    });

    it('exposes deadline screening without using operational timestamps', () => {
        const service = new RequestService(new RequestRepository(databaseWith()));
        const screened = service.screenDeadline('profile-a', {
            ...requestRow,
            controller_received_at: '2024-01-31T00:00:00.000Z',
            updated_at: '2099-01-01T00:00:00.000Z',
        }, '2024-02-01T00:00:00.000Z');

        expect(screened.deadline_state).toBe('known');
        expect(screened.deadline_at).toBe('2024-02-29T00:00:00.000Z');
        expect(screened.input_dates).not.toHaveProperty('updated_at');
    });
});
