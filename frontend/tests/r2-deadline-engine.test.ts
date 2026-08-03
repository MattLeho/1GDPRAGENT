import { describe, expect, it } from 'vitest';
import { screenRequestDeadline } from '@/lib/requests/deadline';

const evaluationAt = '2024-01-15T12:00:00.000Z';

describe('R2 deterministic request deadline screening', () => {
    it.each([
        ['ordinary month boundary', '2024-04-30T12:00:00.000Z', '2024-05-30T12:00:00.000Z', '2024-05-01T00:00:00.000Z'],
        ['January 31 clamps to leap-year February end', '2024-01-31T12:00:00.000Z', '2024-02-29T12:00:00.000Z', evaluationAt],
        ['January 31 clamps to non-leap February end', '2023-01-31T12:00:00.000Z', '2023-02-28T12:00:00.000Z', '2023-02-01T00:00:00.000Z'],
        ['leap day advances to March 29', '2024-02-29T12:00:00.000Z', '2024-03-29T12:00:00.000Z', evaluationAt],
        ['month end clamps into April', '2024-03-31T12:00:00.000Z', '2024-04-30T12:00:00.000Z', evaluationAt],
    ])('%s', (_label, receivedAt, expectedDeadline, evaluatedAt) => {
        const result = screenRequestDeadline({
            controller_received_at: receivedAt,
            evaluationAt: evaluatedAt,
        });

        expect(result.deadline_state).toBe('known');
        expect(result.deadline_at).toBe(expectedDeadline);
        expect(result.human_review_required).toBe(false);
    });

    it('returns paused_identity while identity verification is unresolved', () => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            identity_requested_at: '2024-01-15T00:00:00.000Z',
            evaluationAt: '2024-03-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe('paused_identity');
        expect(result.deadline_at).toBeNull();
        expect(result.uncertainties).toContain('Identity verification pause is unresolved.');
        expect(result.human_review_required).toBe(true);
    });

    it('conservatively restarts screening from resolved identity verification', () => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            identity_requested_at: '2024-01-15T00:00:00.000Z',
            identity_verified_at: '2024-01-20T00:00:00.000Z',
            evaluationAt: '2024-02-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe('known');
        expect(result.deadline_at).toBe('2024-02-20T00:00:00.000Z');
        expect(result.basis).toContain('conservatively moved');
        expect(result.human_review_required).toBe(true);
    });

    it('returns paused_clarification while clarification is unresolved', () => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            clarification_requested_at: '2024-01-18T00:00:00.000Z',
            evaluationAt: '2024-03-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe('paused_clarification');
        expect(result.deadline_at).toBeNull();
        expect(result.human_review_required).toBe(true);
    });

    it('uses the latest applicable resolved pause date', () => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            identity_requested_at: '2024-01-12T00:00:00.000Z',
            identity_verified_at: '2024-01-20T00:00:00.000Z',
            clarification_requested_at: '2024-01-22T00:00:00.000Z',
            clarification_resolved_at: '2024-01-31T00:00:00.000Z',
            evaluationAt: '2024-02-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe('known');
        expect(result.deadline_at).toBe('2024-02-29T00:00:00.000Z');
        expect(result.human_review_required).toBe(true);
    });

    it('uses an extension only when notice and deadline are both recorded', () => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            extension_notified_at: '2024-02-01T00:00:00.000Z',
            extension_deadline_at: '2024-04-10T00:00:00.000Z',
            evaluationAt: '2024-03-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe('extended');
        expect(result.deadline_at).toBe('2024-04-10T00:00:00.000Z');
        expect(result.human_review_required).toBe(false);
    });

    it.each([
        [{ extension_notified_at: '2024-02-01T00:00:00.000Z' }],
        [{ extension_deadline_at: '2024-04-10T00:00:00.000Z' }],
    ])('retains the ordinary deadline for incomplete extension evidence %#', extension => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            evaluationAt: '2024-02-01T00:00:00.000Z',
            ...extension,
        });

        expect(result.deadline_state).toBe('known');
        expect(result.deadline_at).toBe('2024-02-10T00:00:00.000Z');
        expect(result.uncertainties.join(' ')).toContain('Extension evidence is incomplete');
        expect(result.human_review_required).toBe(true);
    });

    it('returns unknown when neither receipt nor sent evidence exists', () => {
        const result = screenRequestDeadline({ evaluationAt });

        expect(result.deadline_state).toBe('unknown');
        expect(result.deadline_at).toBeNull();
        expect(result.human_review_required).toBe(true);
    });

    it('uses sent_at only as an estimated base when receipt is missing', () => {
        const result = screenRequestDeadline({
            sent_at: '2024-01-31T00:00:00.000Z',
            evaluationAt: '2024-02-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe('estimated');
        expect(result.deadline_at).toBe('2024-02-29T00:00:00.000Z');
        expect(result.uncertainties.join(' ')).toContain('Controller receipt date is unknown');
        expect(result.human_review_required).toBe(true);
    });

    it('does not treat local completion as evidence of response timeliness', () => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            completed_at: '2024-01-25T00:00:00.000Z',
            evaluationAt: '2024-02-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe('known');
        expect(result.uncertainties.join(' ')).toContain('local completion does not establish timeliness');
        expect(result.human_review_required).toBe(true);
    });

    it.each([
        ['completed_on_time', '2024-02-10T00:00:00.000Z'],
        ['completed_late', '2024-02-10T00:00:00.001Z'],
    ] as const)('compares response_received_at and yields %s', (state, responseAt) => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            response_received_at: responseAt,
            completed_at: '2024-02-01T00:00:00.000Z',
            evaluationAt: '2025-01-01T00:00:00.000Z',
        });

        expect(result.deadline_state).toBe(state);
        expect(result.basis).toContain('response_received_at');
    });

    it('surfaces disputed dates and forces human review', () => {
        const result = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            response_received_at: '2024-02-01T00:00:00.000Z',
            evaluationAt,
            disputedFields: ['controller_received_at', 'response_received_at'],
        });

        expect(result.deadline_state).toBe('completed_on_time');
        expect(result.uncertainties).toEqual(expect.arrayContaining([
            'Disputed date: controller_received_at.',
            'Disputed date: response_received_at.',
        ]));
        expect(result.human_review_required).toBe(true);
    });

    it('uses explicit evaluationAt deterministically for open deadlines', () => {
        const before = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            evaluationAt: '2024-02-10T00:00:00.000Z',
        });
        const after = screenRequestDeadline({
            controller_received_at: '2024-01-10T00:00:00.000Z',
            evaluationAt: '2024-02-10T00:00:00.001Z',
        });

        expect(before.deadline_state).toBe('known');
        expect(after.deadline_state).toBe('overdue');
        expect(before.input_dates.evaluation_at).toBe('2024-02-10T00:00:00.000Z');
        expect(after.input_dates.evaluation_at).toBe('2024-02-10T00:00:00.001Z');
    });
});
