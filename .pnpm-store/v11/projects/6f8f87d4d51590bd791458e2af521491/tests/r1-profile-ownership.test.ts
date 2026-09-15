import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
    authority: { userId: 'user-a', profileId: 'profile-a' },
    poolQuery: vi.fn(),
    connect: vi.fn(),
    mkdir: vi.fn(),
    writeFile: vi.fn(),
    unlink: vi.fn(),
    compare: vi.fn(),
    hash: vi.fn(),
}));

vi.mock('@/lib/api-session', () => ({
    requireApiSession: vi.fn(async () => mocks.authority),
}));
vi.mock('@/lib/db', () => ({
    pool: { query: mocks.poolQuery, connect: mocks.connect },
}));
vi.mock('fs/promises', () => ({
    mkdir: mocks.mkdir,
    writeFile: mocks.writeFile,
    unlink: mocks.unlink,
}));
vi.mock('bcryptjs', () => ({
    default: { compare: mocks.compare, hash: mocks.hash },
}));

import { GET, PUT } from '@/app/api/settings/profile/route';
import { POST as changePassword } from '@/app/api/settings/profile/password/route';

function requestWithForm(entries: Array<[string, string | File]>) {
    const form = new FormData();
    for (const [key, value] of entries) form.set(key, value);
    return { formData: vi.fn(async () => form) } as never;
}

function requestWithJson(value: unknown) {
    return { json: vi.fn(async () => value) } as never;
}

describe('R1 authenticated profile ownership', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mocks.unlink.mockResolvedValue(undefined);
        mocks.mkdir.mockResolvedValue(undefined);
        mocks.writeFile.mockResolvedValue(undefined);
    });

    it('GET resolves the exact authority user and canonical profile without a first-row shortcut', async () => {
        mocks.poolQuery.mockResolvedValue({
            rowCount: 1,
            rows: [{
                id: 'user-a', username: 'Alice', email: 'alice@example.test', profile_picture_url: null,
                created_at: new Date('2026-01-01'), updated_at: new Date('2026-01-02'),
            }],
        });

        const response = await GET({} as never);

        expect(response.status).toBe(200);
        expect(mocks.poolQuery).toHaveBeenCalledWith(
            expect.stringMatching(/WHERE up\.id = \$1 AND p\.id = \$2/),
            ['user-a', 'profile-a'],
        );
        expect(String(mocks.poolQuery.mock.calls[0][0])).not.toMatch(/LIMIT\s+1/i);
    });

    it('PUT changes identity fields while retaining password and ownership columns', async () => {
        const clientQuery = vi.fn()
            .mockResolvedValueOnce({}) // BEGIN
            .mockResolvedValueOnce({ rowCount: 1, rows: [{ profile_picture_url: null }] })
            .mockResolvedValueOnce({ rowCount: 1 }) // canonical profile display name
            .mockResolvedValueOnce({
                rowCount: 1,
                rows: [{
                    id: 'user-a', username: 'Alice Updated', email: 'new@example.test', profile_picture_url: null,
                    created_at: new Date('2026-01-01'), updated_at: new Date('2026-01-03'),
                }],
            })
            .mockResolvedValueOnce({}); // COMMIT
        mocks.connect.mockResolvedValue({ query: clientQuery, release: vi.fn() });

        const response = await PUT(requestWithForm([
            ['username', 'Alice Updated'],
            ['email', 'new@example.test'],
        ]));

        expect(response.status).toBe(200);
        const accountUpdate = String(clientQuery.mock.calls[3][0]);
        const updateClause = accountUpdate.split(/\bWHERE\b/i)[0];
        expect(accountUpdate).toMatch(/WHERE id = \$3 AND default_profile_id = \$4/);
        expect(updateClause).not.toMatch(/password_hash\s*=/);
        expect(updateClause).not.toMatch(/default_profile_id\s*=/);
        expect(clientQuery.mock.calls[3][1]).toEqual(['Alice Updated', 'new@example.test', 'user-a', 'profile-a']);
    });

    it('removes the new avatar after a failed transaction and keeps the old avatar', async () => {
        const clientQuery = vi.fn()
            .mockResolvedValueOnce({})
            .mockResolvedValueOnce({ rowCount: 1, rows: [{ profile_picture_url: '/uploads/profiles/old.png' }] })
            .mockResolvedValueOnce({ rowCount: 1 })
            .mockRejectedValueOnce(new Error('database failed'))
            .mockResolvedValue({});
        mocks.connect.mockResolvedValue({ query: clientQuery, release: vi.fn() });
        const avatar = new File([new Uint8Array([1, 2, 3])], 'ignored.exe', { type: 'image/png' });

        const response = await PUT(requestWithForm([
            ['username', 'Alice'],
            ['email', 'alice@example.test'],
            ['profilePicture', avatar],
        ]));

        expect(response.status).toBe(500);
        const removed = mocks.unlink.mock.calls.map(call => String(call[0]));
        expect(removed.some(value => value.endsWith('old.png'))).toBe(false);
        expect(removed.some(value => value.includes('profile_user-a_'))).toBe(true);
    });

    it('deletes the superseded managed avatar only after commit', async () => {
        const order: string[] = [];
        mocks.unlink.mockImplementation(async () => { order.push('unlink'); });
        const clientQuery = vi.fn(async (sql: string) => {
            if (sql === 'COMMIT') order.push('commit');
            if (sql.includes('SELECT up.profile_picture_url')) return { rowCount: 1, rows: [{ profile_picture_url: '/uploads/profiles/old.png' }] };
            if (sql.includes('UPDATE user_profiles')) return {
                rowCount: 1,
                rows: [{
                    id: 'user-a', username: 'Alice', email: 'alice@example.test', profile_picture_url: '/uploads/profiles/new.png',
                    created_at: new Date(), updated_at: new Date(),
                }],
            };
            return { rowCount: 1 };
        });
        mocks.connect.mockResolvedValue({ query: clientQuery, release: vi.fn() });
        const avatar = new File([new Uint8Array([1])], 'new.png', { type: 'image/png' });

        const response = await PUT(requestWithForm([
            ['username', 'Alice'], ['email', 'alice@example.test'], ['profilePicture', avatar],
        ]));

        expect(response.status).toBe(200);
        expect(order).toEqual(['commit', 'unlink']);
    });

    it('password change verifies and updates only the authority-bound account', async () => {
        mocks.poolQuery
            .mockResolvedValueOnce({ rowCount: 1, rows: [{ id: 'user-a', password_hash: 'old-hash' }] })
            .mockResolvedValueOnce({ rowCount: 1 });
        mocks.compare.mockResolvedValue(true);
        mocks.hash.mockResolvedValue('new-hash');

        const response = await changePassword(requestWithJson({ currentPassword: 'old-password', newPassword: 'new-password' }));

        expect(response.status).toBe(200);
        expect(mocks.compare).toHaveBeenCalledWith('old-password', 'old-hash');
        expect(mocks.poolQuery.mock.calls[0][1]).toEqual(['user-a', 'profile-a']);
        expect(mocks.poolQuery.mock.calls[1][1]).toEqual(['new-hash', 'user-a', 'profile-a']);
        expect(String(mocks.poolQuery.mock.calls[1][0])).toMatch(/WHERE id = \$2 AND default_profile_id = \$3/);
    });

    it('returns the same not-found response when the authority binding is absent', async () => {
        mocks.poolQuery.mockResolvedValue({ rowCount: 0, rows: [] });

        const response = await changePassword(requestWithJson({ currentPassword: 'old-password', newPassword: 'new-password' }));

        expect(response.status).toBe(404);
        expect(await response.json()).toEqual({ success: false, error: 'Profile not found' });
    });
});
