import { NextResponse, NextRequest } from 'next/server';
import { pool } from '@/lib/db';
import bcrypt from 'bcryptjs';
import { cookies } from 'next/headers';
import { createSessionToken } from '@/lib/auth-session';

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
        const client=await pool.connect();
        let createdUser:{id:string;username:string;default_profile_id:string}|null=null;
        try{
            await client.query('BEGIN');
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
        const token = createSessionToken(String(userId),String(createdUser.default_profile_id));

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
