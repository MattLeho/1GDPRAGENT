import { NextResponse } from 'next/server';
import { pool } from '@/lib/db';

/**
 * GET /api/auth/check-setup - Check if user profile exists (first-time setup)
 */
export async function GET() {
    try {
        const result = await pool.query('SELECT id FROM user_profiles LIMIT 1');

        return NextResponse.json({
            success: true,
            hasProfile: result.rows.length > 0,
        });
    } catch (error) {
        console.error('Failed to check setup:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to check setup status' },
            { status: 500 }
        );
    }
}
