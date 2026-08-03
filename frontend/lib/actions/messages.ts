'use server';

import { revalidatePath } from 'next/cache';
import { requireServerSessionAuthority } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';

const requests=new RequestService();

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
    const {profileId}=await requireServerSessionAuthority();
    return requests.messages(profileId,requestId) as Promise<Message[]>;
}

/**
 * Sends a new message (from user to agent)
 */
export async function sendMessage(
    requestId: string,
    content: string
): Promise<{ success: boolean; message?: Message }> {
    try {
        const {profileId}=await requireServerSessionAuthority();
        const created=await requests.appendMessage(profileId,requestId,'user',content);
        if(!created)return {success:false};

        revalidatePath('/dashboard/requests');
        revalidatePath(`/dashboard/requests/${requestId}`);

        return { success: true, message: created as Message };
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
    const {profileId}=await requireServerSessionAuthority();
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
    const review=await requests.reviewItems(profileId);
    const messageRows=review.messages as unknown as Array<{id:string;content:string;timestamp:Date;company_name:string;request_id:string}>;
    const dataRows=review.files as unknown as Array<{id:string;file_name:string;file_size_mb:number;date_received:Date;company_name:string;request_id:string}>;

    // Map messages to review items
    messageRows.forEach((msg) => {
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
    dataRows.forEach((data) => {
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
