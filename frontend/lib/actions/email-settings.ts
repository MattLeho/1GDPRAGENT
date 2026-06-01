'use server';

import { db, safeQuery } from '@/lib/db';
import { revalidatePath } from 'next/cache';

export interface EmailSettings {
    id: string;
    email: string;
    imap_host: string;
    imap_port: number;
    connection_verified: boolean;
    created_at: Date;
    updated_at: Date;
}

/**
 * Saves email credentials (encrypted password should be handled client-side before calling)
 */
export async function saveEmailCredentials(settings: {
    email: string;
    password_encrypted: string;
    imap_host: string;
    imap_port: number;
}): Promise<{ success: boolean; message: string }> {
    try {
        // Check if settings already exist
        const existing = await safeQuery<{ id: string }>(`SELECT id FROM email_settings LIMIT 1`);

        if (existing.rows.length > 0) {
            // Update existing
            await db.query(
                `UPDATE email_settings 
                 SET email = $1, password_encrypted = $2, imap_host = $3, imap_port = $4, updated_at = NOW()
                 WHERE id = $5`,
                [settings.email, settings.password_encrypted, settings.imap_host, settings.imap_port, existing.rows[0].id]
            );
        } else {
            // Insert new
            await db.query(
                `INSERT INTO email_settings (email, password_encrypted, imap_host, imap_port, connection_verified)
                 VALUES ($1, $2, $3, $4, false)`,
                [settings.email, settings.password_encrypted, settings.imap_host, settings.imap_port]
            );
        }

        revalidatePath('/dashboard/settings');
        return { success: true, message: 'Settings saved successfully' };
    } catch (error) {
        console.error('Failed to save email settings:', error);
        return { success: false, message: 'Failed to save settings. Database may be unavailable.' };
    }
}

/**
 * Gets current email settings (without password)
 */
export async function getEmailSettings(): Promise<EmailSettings | null> {
    const result = await safeQuery<EmailSettings>(
        `SELECT id, email, imap_host, imap_port, connection_verified, created_at, updated_at
         FROM email_settings LIMIT 1`
    );

    if (result.error) {
        console.error('Failed to fetch email settings:', result.error);
        return null;
    }

    return result.rows[0] || null;
}

/**
 * Gets email settings with encrypted password (for internal use)
 */
export async function getEmailSettingsWithPassword(): Promise<(EmailSettings & { password_encrypted: string }) | null> {
    const result = await safeQuery<EmailSettings & { password_encrypted: string }>(
        `SELECT * FROM email_settings LIMIT 1`
    );

    if (result.error) {
        console.error('Failed to fetch email settings:', result.error);
        return null;
    }

    return result.rows[0] || null;
}

/**
 * Tests IMAP connection via N8N Inbox Monitor agent
 */
export async function testImapConnection(): Promise<{ success: boolean; message: string }> {
    const settings = await getEmailSettingsWithPassword();

    if (!settings) {
        return { success: false, message: 'No email settings configured' };
    }

    try {
        // Call the N8N test-imap API route
        const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
        const response = await fetch(`${baseUrl}/api/n8n/test-imap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: settings.email,
                host: settings.imap_host,
                port: settings.imap_port,
                password: settings.password_encrypted, // In production, this should be decrypted
            }),
        });

        const result = await response.json();

        if (result.success) {
            // Update connection verified status
            await updateConnectionStatus(true);
        }

        return {
            success: result.success,
            message: result.message || (result.success ? 'Connection verified!' : 'Connection failed'),
        };
    } catch (error) {
        console.error('IMAP test failed:', error);
        return {
            success: false,
            message: 'Failed to test connection. Check if N8N is running.',
        };
    }
}

/**
 * Updates connection verified status
 */
export async function updateConnectionStatus(verified: boolean): Promise<void> {
    try {
        await db.query(
            `UPDATE email_settings SET connection_verified = $1, updated_at = NOW()`,
            [verified]
        );
        revalidatePath('/dashboard/settings');
    } catch (error) {
        console.error('Failed to update connection status:', error);
    }
}
