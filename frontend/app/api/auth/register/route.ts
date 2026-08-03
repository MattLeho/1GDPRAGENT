import { NextResponse, NextRequest } from 'next/server';
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

/**
 * POST /api/auth/register - Register first-time user
 */
export async function POST(request: NextRequest) {
    try {
        const csrfFailure = enforceSameOriginMutation(request);
        if (csrfFailure) return csrfFailure;
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
        const client=await pool.connect();
        let createdUser:{id:string;username:string;default_profile_id:string}|null=null;
        try{
            await client.query('BEGIN');
            // Public registration is bootstrap-only. The transaction-scoped lock
            // makes the empty-install check safe when two setup requests race.
            await client.query("SELECT pg_advisory_xact_lock(hashtext('gdpr-agent-initial-registration'))");
            const existingUsers = await client.query('SELECT 1 FROM user_profiles LIMIT 1');
            if (existingUsers.rowCount) {
                await client.query('ROLLBACK');
                return NextResponse.json(
                    { success: false, error: 'Account setup is already complete' },
                    { status: 409 },
                );
            }
            const profile=await client.query('INSERT INTO profiles(identity_name) VALUES($1) RETURNING id',[username]);
            const userResult=await client.query(
                `INSERT INTO user_profiles (username, email, password_hash, default_profile_id)
                 VALUES ($1, $2, $3, $4)
                 RETURNING id, username, default_profile_id`,
                [username, `${username}@local`, passwordHash, profile.rows[0].id]
            );
            createdUser=userResult.rows[0] as {id:string;username:string;default_profile_id:string};
            await client.query('COMMIT');
        }catch(error){await client.query('ROLLBACK');throw error}finally{client.release()}

        if(!createdUser) throw new Error('user transaction returned no row');
        const userId = createdUser.id;

        // Create session token
        const issuedAt = Date.now();
        const expiresAt = issuedAt + SESSION_TTL_MS;
        const token = createSessionToken(
            String(userId),
            String(createdUser.default_profile_id),
            issuedAt,
            expiresAt,
        );

        // Set session cookie - await cookies() for Next.js 16+
        const cookieStore = await cookies();
        cookieStore.set(SESSION_COOKIE_NAME, token, sessionCookieOptions(expiresAt, issuedAt));

        return NextResponse.json({
            success: true,
            user: {
                id: userId,
                username: createdUser.username,
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
