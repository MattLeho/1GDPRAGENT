import { NextRequest, NextResponse } from 'next/server';
import { pool } from '@/lib/db';
import bcrypt from 'bcryptjs';
import { cookies } from 'next/headers';
import {
    createSessionToken,
    SESSION_COOKIE_NAME,
    SESSION_TTL_MS,
    sessionCookieOptions,
} from '@/lib/auth-session';
import { enforceSameOriginMutation } from '@/lib/api-session';

export async function POST(request: NextRequest) {
    try {
        const csrfFailure = enforceSameOriginMutation(request);
        if (csrfFailure) return csrfFailure;
        const { username, password } = await request.json();

        if (!username || !password) {
            return NextResponse.json(
                { success: false, error: 'Username and password required' },
                { status: 400 }
            );
        }

        // Check if user exists
        const result = await pool.query(
            `SELECT up.id, up.username, up.password_hash, up.default_profile_id
               FROM user_profiles up
               INNER JOIN profiles p ON p.id = up.default_profile_id
              WHERE up.username = $1`,
            [username]
        );

        if (result.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Invalid credentials' },
                { status: 401 }
            );
        }

        const user = result.rows[0];

        // Verify password
        const isValid = await bcrypt.compare(password, user.password_hash);

        if (!isValid) {
            return NextResponse.json(
                { success: false, error: 'Invalid credentials' },
                { status: 401 }
            );
        }

        // Create session token
        const issuedAt = Date.now();
        const expiresAt = issuedAt + SESSION_TTL_MS;
        const token = createSessionToken(String(user.id), String(user.default_profile_id), issuedAt, expiresAt);

        // Set HTTP-only cookie - await cookies() for Next.js 16+
        const cookieStore = await cookies();
        cookieStore.set(SESSION_COOKIE_NAME, token, sessionCookieOptions(expiresAt, issuedAt));

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('[Login] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Login failed' },
            { status: 500 }
        );
    }
}
