import { NextResponse } from 'next/server';
import { pool } from '@/lib/db';

/**
 * GET /api/auth/check-setup - Check if user profile exists (first-time setup)
 */
export async function GET() {
    try {
        const result = await pool.query('SELECT EXISTS(SELECT 1 FROM user_profiles) AS has_profile');

        return NextResponse.json({
            success: true,
            hasProfile: Boolean(result.rows[0]?.has_profile),
        });
    } catch (error) {
        console.error('Failed to check setup:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to check setup status' },
            { status: 500 }
        );
    }
}
