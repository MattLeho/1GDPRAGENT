import { NextResponse, NextRequest } from 'next/server';
import { pool } from '@/lib/db';
import bcrypt from 'bcryptjs';
import { cookies } from 'next/headers';

/**
 * POST /api/auth/register - Register first-time user
 */
export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { username, password } = body;

        if (!username || !password) {
            return NextResponse.json(
                { success: false, error: 'Username and password are required' },
                { status: 400 }
            );
        }

        // Hash password
        const passwordHash = await bcrypt.hash(password, 10);

        // Create profile (allow multiple users now)
        const result = await pool.query(
            `INSERT INTO user_profiles (username, email, password_hash)
             VALUES ($1, $2, $3)
             RETURNING id, username`,
            [username, `${username}@local`, passwordHash]
        );

        const userId = result.rows[0].id;

        // Create session token
        const token = Buffer.from(`${userId}:${Date.now()}`).toString('base64');

        // Set session cookie - await cookies() for Next.js 16+
        const cookieStore = await cookies();
        cookieStore.set('gdpr-session', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            maxAge: 60 * 60 * 24 * 30, // 30 days
        });

        return NextResponse.json({
            success: true,
            token,
            user: {
                id: userId,
                username: result.rows[0].username,
            },
        });
    } catch (error: any) {
        console.error('Registration failed:', error);

        // Handle duplicate username error
        if (error.code === '23505') {
            return NextResponse.json(
                { success: false, error: 'Username already exists' },
                { status: 400 }
            );
        }

        return NextResponse.json(
            { success: false, error: 'Failed to create account' },
            { status: 500 }
        );
    }
}
