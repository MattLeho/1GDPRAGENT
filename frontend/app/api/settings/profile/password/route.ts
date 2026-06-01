import { NextResponse, NextRequest } from 'next/server';
import { pool } from '@/lib/db';
import bcrypt from 'bcryptjs';

/**
 * POST /api/settings/profile/password - Change user password
 */
export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { currentPassword, newPassword } = body;

        if (!currentPassword || !newPassword) {
            return NextResponse.json(
                { success: false, error: 'Both passwords are required' },
                { status: 400 }
            );
        }

        if (newPassword.length < 8) {
            return NextResponse.json(
                { success: false, error: 'New password must be at least 8 characters' },
                { status: 400 }
            );
        }

        // Get current profile
        const profile = await pool.query('SELECT id, password_hash FROM user_profiles LIMIT 1');

        if (profile.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Profile not found. Please create a profile first.' },
                { status: 404 }
            );
        }

        const passwordHash = profile.rows[0].password_hash;

        // If password is not set yet (first time setup), allow without checking current
        if (passwordHash) {
            // Verify current password
            const isValid = await bcrypt.compare(currentPassword, passwordHash);
            if (!isValid) {
                return NextResponse.json(
                    { success: false, error: 'Current password is incorrect' },
                    { status: 401 }
                );
            }
        }

        // Hash new password
        const newHash = await bcrypt.hash(newPassword, 10);

        // Update password
        await pool.query(
            'UPDATE user_profiles SET password_hash = $1, updated_at = NOW() WHERE id = $2',
            [newHash, profile.rows[0].id]
        );

        return NextResponse.json({
            success: true,
            message: 'Password changed successfully',
        });
    } catch (error) {
        console.error('Failed to change password:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to change password' },
            { status: 500 }
        );
    }
}
