import { randomUUID } from 'crypto';
import { mkdir, unlink, writeFile } from 'fs/promises';
import path from 'path';
import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db';

const UPLOAD_DIR = path.join(process.cwd(), 'uploads', 'profiles');
const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
const AVATAR_EXTENSIONS = new Map([
    ['image/jpeg', '.jpg'],
    ['image/png', '.png'],
    ['image/webp', '.webp'],
    ['image/gif', '.gif'],
]);

interface ProfileRow {
    id: string;
    username: string;
    email: string | null;
    profile_picture_url: string | null;
    created_at: Date;
    updated_at: Date;
}

function publicProfile(row: ProfileRow) {
    return {
        id: row.id,
        username: row.username,
        email: row.email,
        profilePictureUrl: row.profile_picture_url,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
    };
}

function managedAvatarPath(url: string | null): string | null {
    const prefix = '/uploads/profiles/';
    if (!url?.startsWith(prefix)) return null;
    const filename = url.slice(prefix.length);
    if (!filename || path.basename(filename) !== filename) return null;
    return path.join(UPLOAD_DIR, filename);
}

async function removeManagedAvatar(url: string | null): Promise<void> {
    const filepath = managedAvatarPath(url);
    if (!filepath) return;
    try {
        await unlink(filepath);
    } catch (error) {
        const code = (error as NodeJS.ErrnoException).code;
        if (code !== 'ENOENT') console.warn('Failed to remove superseded profile image:', error);
    }
}

/** GET /api/settings/profile - get the authenticated account and its canonical profile. */
export async function GET(request: NextRequest) {
    try {
        const authority = await requireApiSession(request);
        if (authority instanceof NextResponse) return authority;

        const result = await pool.query<ProfileRow>(
            `SELECT up.id, up.username, up.email, up.profile_picture_url, up.created_at, up.updated_at
             FROM user_profiles up
             JOIN profiles p ON p.id = up.default_profile_id
             WHERE up.id = $1 AND p.id = $2`,
            [authority.userId, authority.profileId],
        );
        if (result.rowCount !== 1) {
            return NextResponse.json({ success: false, error: 'Profile not found' }, { status: 404 });
        }
        return NextResponse.json({ success: true, profile: publicProfile(result.rows[0]) });
    } catch (error) {
        console.error('Failed to get profile:', error);
        return NextResponse.json({ success: false, error: 'Failed to load profile' }, { status: 500 });
    }
}

async function updateProfile(request: NextRequest) {
    let newAvatarUrl: string | null = null;
    try {
        const authority = await requireApiSession(request);
        if (authority instanceof NextResponse) return authority;

        const formData = await request.formData();
        const usernameValue = formData.get('username');
        const emailValue = formData.get('email');
        const username = typeof usernameValue === 'string' ? usernameValue.trim() : '';
        const email = typeof emailValue === 'string' ? emailValue.trim() : '';
        const avatarValue = formData.get('profilePicture');
        const avatar = avatarValue instanceof File && avatarValue.size > 0 ? avatarValue : null;

        if (!username || !email) {
            return NextResponse.json({ success: false, error: 'Username and email are required' }, { status: 400 });
        }

        if (avatar) {
            const extension = AVATAR_EXTENSIONS.get(avatar.type);
            if (!extension || avatar.size > MAX_AVATAR_BYTES) {
                return NextResponse.json(
                    { success: false, error: 'Profile image must be JPEG, PNG, WebP or GIF and no larger than 5 MB' },
                    { status: 400 },
                );
            }
            await mkdir(UPLOAD_DIR, { recursive: true });
            const filename = `profile_${authority.userId}_${randomUUID()}${extension}`;
            await writeFile(path.join(UPLOAD_DIR, filename), Buffer.from(await avatar.arrayBuffer()), { flag: 'wx' });
            newAvatarUrl = `/uploads/profiles/${filename}`;
        }

        const client = await pool.connect();
        let oldAvatarUrl: string | null = null;
        try {
            await client.query('BEGIN');
            const current = await client.query<{ profile_picture_url: string | null }>(
                `SELECT up.profile_picture_url
                 FROM user_profiles up
                 JOIN profiles p ON p.id = up.default_profile_id
                 WHERE up.id = $1 AND p.id = $2
                 FOR UPDATE OF up`,
                [authority.userId, authority.profileId],
            );
            if (current.rowCount !== 1) {
                await client.query('ROLLBACK');
                await removeManagedAvatar(newAvatarUrl);
                return NextResponse.json({ success: false, error: 'Profile not found' }, { status: 404 });
            }
            oldAvatarUrl = current.rows[0].profile_picture_url;

            await client.query(
                `UPDATE profiles SET identity_name = $1 WHERE id = $2`,
                [username, authority.profileId],
            );
            const params: Array<string> = [username, email];
            const avatarSql = newAvatarUrl ? `, profile_picture_url = $${params.push(newAvatarUrl)}` : '';
            params.push(authority.userId, authority.profileId);
            const result = await client.query<ProfileRow>(
                `UPDATE user_profiles
                 SET username = $1, email = $2${avatarSql}, updated_at = NOW()
                 WHERE id = $${params.length - 1} AND default_profile_id = $${params.length}
                 RETURNING id, username, email, profile_picture_url, created_at, updated_at`,
                params,
            );
            if (result.rowCount !== 1) throw new Error('Authenticated profile binding changed during update');
            await client.query('COMMIT');

            if (newAvatarUrl && oldAvatarUrl !== newAvatarUrl) await removeManagedAvatar(oldAvatarUrl);
            return NextResponse.json({ success: true, profile: publicProfile(result.rows[0]) });
        } catch (error) {
            try { await client.query('ROLLBACK'); } catch { /* preserve the original failure */ }
            await removeManagedAvatar(newAvatarUrl);
            throw error;
        } finally {
            client.release();
        }
    } catch (error) {
        console.error('Failed to save profile:', error);
        await removeManagedAvatar(newAvatarUrl);
        return NextResponse.json({ success: false, error: 'Failed to save profile' }, { status: 500 });
    }
}

/** PUT is canonical; POST remains as a compatibility alias for the current settings form. */
export const PUT = updateProfile;
export const POST = updateProfile;
