import { NextResponse, NextRequest } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import { pool } from '@/lib/db';

const UPLOAD_DIR = path.join(process.cwd(), 'uploads', 'profiles');

// Ensure upload directory exists
async function ensureUploadDir() {
    if (!existsSync(UPLOAD_DIR)) {
        await mkdir(UPLOAD_DIR, { recursive: true });
    }
}

/**
 * GET /api/settings/profile - Get user profile
 */
export async function GET() {
    try {
        // Since we only have one user (local app), just get the first profile
        const result = await pool.query(
            `SELECT id, username, email, profile_picture_url, created_at, updated_at 
             FROM user_profiles 
             LIMIT 1`
        );

        if (result.rows.length === 0) {
            return NextResponse.json({ profile: null });
        }

        return NextResponse.json({
            success: true,
            profile: {
                id: result.rows[0].id,
                username: result.rows[0].username,
                email: result.rows[0].email,
                profilePictureUrl: result.rows[0].profile_picture_url,
                createdAt: result.rows[0].created_at,
                updatedAt: result.rows[0].updated_at,
            },
        });
    } catch (error) {
        console.error('Failed to get profile:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to load profile' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/settings/profile - Create or update user profile
 */
export async function POST(request: NextRequest) {
    try {
        const formData = await request.formData();
        const username = formData.get('username') as string;
        const email = formData.get('email') as string;
        const profilePicture = formData.get('profilePicture') as File | null;

        if (!username || !email) {
            return NextResponse.json(
                { success: false, error: 'Username and email are required' },
                { status: 400 }
            );
        }

        await ensureUploadDir();

        let profilePictureUrl: string | undefined;

        // Handle profile picture upload
        if (profilePicture) {
            const bytes = await profilePicture.arrayBuffer();
            const buffer = Buffer.from(bytes);

            // Generate safe filename
            const ext = path.extname(profilePicture.name);
            const filename = `profile_${Date.now()}${ext}`;
            const filepath = path.join(UPLOAD_DIR, filename);

            await writeFile(filepath, buffer);
            profilePictureUrl = `/uploads/profiles/${filename}`;
        }

        // Check if profile exists
        const existing = await pool.query('SELECT id FROM user_profiles LIMIT 1');

        let result;
        if (existing.rows.length === 0) {
            // Create new profile
            result = await pool.query(
                `INSERT INTO user_profiles (username, email, profile_picture_url)
                 VALUES ($1, $2, $3)
                 RETURNING id, username, email, profile_picture_url, created_at, updated_at`,
                [username, email, profilePictureUrl || null]
            );
        } else {
            // Update existing profile
            const updateFields = ['username = $1', 'email = $2', 'updated_at = NOW()'];
            const params: any[] = [username, email];

            if (profilePictureUrl) {
                updateFields.push(`profile_picture_url = $${params.length + 1}`);
                params.push(profilePictureUrl);
            }

            params.push(existing.rows[0].id);

            result = await pool.query(
                `UPDATE user_profiles 
                 SET ${updateFields.join(', ')}
                 WHERE id = $${params.length}
                 RETURNING id, username, email, profile_picture_url, created_at, updated_at`,
                params
            );
        }

        return NextResponse.json({
            success: true,
            profile: {
                id: result.rows[0].id,
                username: result.rows[0].username,
                email: result.rows[0].email,
                profilePictureUrl: result.rows[0].profile_picture_url,
                createdAt: result.rows[0].created_at,
                updatedAt: result.rows[0].updated_at,
            },
        });
    } catch (error) {
        console.error('Failed to save profile:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to save profile' },
            { status: 500 }
        );
    }
}
