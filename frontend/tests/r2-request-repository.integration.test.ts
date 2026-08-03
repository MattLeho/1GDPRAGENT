import { randomUUID } from 'node:crypto';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { Pool } from 'pg';
import { RequestRepository } from '../lib/requests/repository';
import { RequestService } from '../lib/requests/service';

const databaseUrl = process.env.R2_TEST_DATABASE_URL;
const run = databaseUrl ? describe : describe.skip;

run('R2 request repository executes against PostgreSQL', () => {
    const pool = new Pool({ connectionString: databaseUrl });
    const repository = new RequestRepository(pool);
    const service = new RequestService(repository);
    const profileId = randomUUID();
    const otherProfileId = randomUUID();

    beforeAll(async () => {
        const database = await pool.query<{ name: string }>('SELECT current_database() AS name');
        if (!database.rows[0]?.name.startsWith('r2_')) {
            throw new Error('R2_TEST_DATABASE_URL must target a disposable database whose name starts with r2_');
        }
        await pool.query(
            'INSERT INTO profiles(id,identity_name) VALUES ($1,$2),($3,$4)',
            [profileId, 'R2 integration profile', otherProfileId, 'R2 other profile'],
        );
    });

    afterAll(async () => {
        await pool.end();
    });

    it('executes every canonical request-domain repository query with profile isolation', async () => {
        const request = await service.create(profileId, {
            company_name: 'R2 Query Company', company_url: 'https://r2.example',
            domain: 'r2.example', request_type: 'access', notes: 'created by integration test',
        });
        const disposable = await service.create(profileId, {
            company_name: 'Disposable', domain: 'delete.example', request_type: 'access',
        });
        await service.create(otherProfileId, {
            company_name: 'Other Profile Company', domain: 'r2.example', request_type: 'access',
        });

        expect(await service.get(profileId, request.id)).toMatchObject({ id: request.id, profile_id: profileId });
        expect(await service.get(otherProfileId, request.id)).toBeNull();
        expect((await service.list(profileId, { search: 'Query', status: 'draft', sort: 'company_asc' }))[0]?.id).toBe(request.id);
        expect(await service.history(profileId, 'r2.example', disposable.id)).toHaveLength(1);
        expect((await service.counts(profileId)).total).toBe(2);
        expect(await service.contactedCompanyNames(profileId, ['R2 Query Company'])).toEqual([]);
        expect(await service.updateProgress(profileId, request.id, 33)).toMatchObject({ progress: 33 });
        expect(await service.updateNotes(profileId, request.id, 'updated')).toMatchObject({ notes: 'updated' });

        const at = (day: number) => `2024-02-${String(day).padStart(2, '0')}T12:00:00.000Z`;
        await service.transition(profileId, { request_id: request.id, next_state: 'ready_for_review', actor: 'integration', reason: 'reviewed', transitioned_at: at(1) });
        await service.transition(profileId, { request_id: request.id, next_state: 'sent', actor: 'integration', reason: 'sent', evidence_reference: 'message:1', transitioned_at: at(2), sent_at: at(2), controller_received_at: at(3), deadline_at: '2024-03-03T12:00:00.000Z', deadline_basis: 'explicit controller receipt' });
        await service.transition(profileId, { request_id: request.id, next_state: 'awaiting_response', actor: 'integration', reason: 'delivery recorded', transitioned_at: at(3) });
        await service.transition(profileId, { request_id: request.id, next_state: 'response_received', actor: 'integration', reason: 'response artefact received', evidence_reference: 'received-data:pending', transitioned_at: at(20), response_received_at: at(20) });
        await service.transition(profileId, { request_id: request.id, next_state: 'processing_response', actor: 'integration', reason: 'processing started', transitioned_at: at(21) });
        await service.transition(profileId, { request_id: request.id, next_state: 'completed', actor: 'integration', reason: 'local processing completed', transitioned_at: at(22), completed_at: at(22) });
        expect(await service.contactedCompanyNames(profileId, ['R2 Query Company'])).toEqual(['r2 query company']);

        await service.appendEvent(profileId, { request_id: request.id, event_type: 'evidence_note', description: 'manual evidence', occurred_at: at(22), actor: 'integration', reason: 'recorded evidence', evidence_reference: 'note:1' });
        expect((await service.events(profileId, request.id)).length).toBe(7);
        await service.appendMessage(profileId, request.id, 'company', 'response body');
        expect(await service.messages(profileId, request.id)).toHaveLength(1);
        await service.appendChatMessage(profileId, request.id, 'user', 'what happened?');
        expect(await service.chat(profileId, request.id)).toHaveLength(1);
        const received = await service.addReceivedData(profileId, request.id, { file_name: 'response.zip', file_size_mb: 1.5, file_path: '/evidence/response.zip' });
        expect(received).not.toBeNull();
        expect(await service.receivedData(profileId, request.id)).toHaveLength(1);
        expect(await service.getOwnedReceivedData(profileId, received!.id)).toMatchObject({ id: received!.id });
        expect(await service.getOwnedReceivedData(otherProfileId, received!.id)).toBeNull();
        expect(await service.addRequestDetail(profileId, request.id, 'recipient', 'encrypted')).toBe(true);
        expect(await service.requestDetails(profileId, request.id)).toHaveLength(1);
        expect((await service.reviewItems(profileId)).messages).toHaveLength(1);
        expect(await service.context(profileId, request.id)).toMatchObject({ id: request.id, received_file_count: 1 });
        expect((await service.dashboard(profileId)).counts.total).toBe('2');
        expect(await service.delete(profileId, disposable.id)).toBe(true);
        expect(await service.delete(otherProfileId, request.id)).toBe(false);
    });
});
