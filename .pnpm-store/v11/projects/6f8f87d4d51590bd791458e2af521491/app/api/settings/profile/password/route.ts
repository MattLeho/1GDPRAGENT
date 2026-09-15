import bcrypt from 'bcryptjs';
import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db';

/** POST /api/settings/profile/password - change only the authenticated account's password. */
export async function POST(request: NextRequest) {
    try {
        const authority = await requireApiSession(request);
        if (authority instanceof NextResponse) return authority;

        const body = await request.json();
        const currentPassword = typeof body.currentPassword === 'string' ? body.currentPassword : '';
        const newPassword = typeof body.newPassword === 'string' ? body.newPassword : '';
        if (!currentPassword || !newPassword) {
            return NextResponse.json({ success: false, error: 'Both passwords are required' }, { status: 400 });
        }
        if (newPassword.length < 8) {
            return NextResponse.json({ success: false, error: 'New password must be at least 8 characters' }, { status: 400 });
        }

        const account = await pool.query<{ id: string; password_hash: string }>(
            `SELECT up.id, up.password_hash
             FROM user_profiles up
             JOIN profiles p ON p.id = up.default_profile_id
             WHERE up.id = $1 AND p.id = $2`,
            [authority.userId, authority.profileId],
        );
        // Do not reveal whether an object from another profile exists.
        if (account.rowCount !== 1) {
            return NextResponse.json({ success: false, error: 'Profile not found' }, { status: 404 });
        }
        if (!await bcrypt.compare(currentPassword, account.rows[0].password_hash)) {
            return NextResponse.json({ success: false, error: 'Current password is incorrect' }, { status: 401 });
        }

        const newHash = await bcrypt.hash(newPassword, 12);
        const result = await pool.query(
            `UPDATE user_profiles
             SET password_hash = $1, updated_at = NOW()
             WHERE id = $2 AND default_profile_id = $3`,
            [newHash, authority.userId, authority.profileId],
        );
        if (result.rowCount !== 1) {
            return NextResponse.json({ success: false, error: 'Profile not found' }, { status: 404 });
        }
        return NextResponse.json({ success: true, message: 'Password changed successfully' });
    } catch (error) {
        console.error('Failed to change password:', error);
        return NextResponse.json({ success: false, error: 'Failed to change password' }, { status: 500 });
    }
}
