'use server';

import { safeQuery } from '@/lib/db';
import { revalidatePath } from 'next/cache';

export interface Message {
    id: string;
    request_id: string;
    sender: 'user' | 'agent' | 'company';
    content: string;
    timestamp: Date;
    read?: boolean;
}

/**
 * Fetches all messages for a specific request
 */
export async function getMessages(requestId: string): Promise<Message[]> {
    const result = await safeQuery<Message>(
        `SELECT * FROM messages 
         WHERE request_id = $1 
         ORDER BY timestamp ASC`,
        [requestId]
    );

    if (result.error) {
        console.error('Failed to fetch messages:', result.error);
    }

    return result.rows;
}

/**
 * Sends a new message (from user to agent)
 */
export async function sendMessage(
    requestId: string,
    content: string
): Promise<{ success: boolean; message?: Message }> {
    try {
        const { db } = await import('@/lib/db');
        const result = await db.query<Message>(
            `INSERT INTO messages (request_id, sender, content, timestamp)
             VALUES ($1, 'user', $2, NOW())
             RETURNING *`,
            [requestId, content]
        );

        revalidatePath('/dashboard/requests');
        revalidatePath(`/dashboard/requests/${requestId}`);

        return { success: true, message: result.rows[0] };
    } catch (error) {
        console.error('Failed to send message:', error);
        return { success: false };
    }
}

/**
 * Gets unread review items (messages and data needing attention)
 */
export async function getUnreadItems(): Promise<{
    type: 'email' | 'file' | 'action';
    id: string;
    title: string;
    description: string;
    date: string;
    requestId?: string;
    companyName?: string;
    data?: Record<string, unknown>;
}[]> {
    const items: {
        type: 'email' | 'file' | 'action';
        id: string;
        title: string;
        description: string;
        date: string;
        requestId?: string;
        companyName?: string;
        data?: Record<string, unknown>;
    }[] = [];

    // Get unread messages from companies
    const messagesResult = await safeQuery<{
        id: string;
        content: string;
        timestamp: Date;
        company_name: string;
        request_id: string;
    }>(`
        SELECT m.id, m.content, m.timestamp, r.company_name, r.id as request_id
        FROM messages m
        JOIN requests r ON m.request_id = r.id
        WHERE m.sender = 'company'
        ORDER BY m.timestamp DESC
        LIMIT 10
    `);

    // Get pending received data
    const dataResult = await safeQuery<{
        id: string;
        file_name: string;
        file_size_mb: number;
        date_received: Date;
        company_name: string;
        request_id: string;
    }>(`
        SELECT rd.id, rd.file_name, rd.file_size_mb, rd.date_received, r.company_name, r.id as request_id
        FROM received_data rd
        JOIN requests r ON rd.request_id = r.id
        ORDER BY rd.date_received DESC
        LIMIT 5
    `);

    // Map messages to review items
    messagesResult.rows.forEach((msg) => {
        items.push({
            type: 'email',
            id: msg.id,
            title: `Response from ${msg.company_name}`,
            description: msg.content.substring(0, 100) + (msg.content.length > 100 ? '...' : ''),
            date: formatTimeAgo(msg.timestamp),
            requestId: msg.request_id,
            companyName: msg.company_name,
            data: {
                content: msg.content,
                timestamp: msg.timestamp,
                requestId: msg.request_id,
            },
        });
    });

    // Map data files to review items
    dataResult.rows.forEach((data) => {
        items.push({
            type: 'file',
            id: data.id,
            title: `Data ready from ${data.company_name}`,
            description: `${data.file_name} (${data.file_size_mb} MB)`,
            date: formatTimeAgo(data.date_received),
            requestId: data.request_id,
            companyName: data.company_name,
            data: {
                fileName: data.file_name,
                fileSizeMb: data.file_size_mb,
                dateReceived: data.date_received,
                requestId: data.request_id,
            },
        });
    });

    return items;
}

function formatTimeAgo(date: Date | string): string {
    const now = new Date();
    const then = new Date(date);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    if (diffDays === 1) return 'Yesterday';
    return `${diffDays} days ago`;
}
