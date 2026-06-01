/**
 * Bulk GDPR Email Sender API Route
 * 
 * Sends GDPR requests to multiple vendors at once via N8N workflow.
 * Checks database to avoid sending duplicate emails to already-contacted vendors.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getWebhookUrl } from '@/lib/n8n-webhooks';
import { Pool } from 'pg';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { vendors, requestType = 'access', userDetails } = body;

        if (!Array.isArray(vendors) || vendors.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Vendors array is required' },
                { status: 400 }
            );
        }

        if (!userDetails || !userDetails.email || !userDetails.name) {
            return NextResponse.json(
                { success: false, error: 'User details are required' },
                { status: 400 }
            );
        }

        // Check which vendors have already been contacted
        const alreadyContacted = await checkContactedVendors(vendors);

        // Filter out already contacted vendors
        const vendorsToContact = vendors.filter(
            v => !alreadyContacted.includes(v.vendor.toLowerCase())
        );

        if (vendorsToContact.length === 0) {
            return NextResponse.json({
                success: true,
                message: 'All vendors have already been contacted',
                skipped: vendors.length,
                sent: 0,
            });
        }

        // Get N8N webhook URL
        const webhookUrl = await getWebhookUrl('gdpr_email_sender');

        if (!webhookUrl) {
            return NextResponse.json(
                { success: false, error: 'N8N webhook not configured' },
                { status: 500 }
            );
        }

        // Send bulk email request to N8N
        const results = await Promise.all(
            vendorsToContact.map(async (vendorData) => {
                try {
                    const response = await fetch(webhookUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            to: vendorData.dpoEmail,
                            company: vendorData.vendor,
                            requestType,
                            userName: userDetails.name,
                            userEmail: userDetails.email,
                        }),
                    });

                    if (response.ok) {
                        // Record in database
                        await recordSentEmail(
                            vendorData.vendor,
                            vendorData.dpoEmail,
                            requestType,
                            userDetails.email
                        );
                        return { vendor: vendorData.vendor, status: 'sent' };
                    } else {
                        return { vendor: vendorData.vendor, status: 'failed' };
                    }
                } catch (error) {
                    console.error(`Failed to send email to ${vendorData.vendor}:`, error);
                    return { vendor: vendorData.vendor, status: 'error' };
                }
            })
        );

        const sent = results.filter(r => r.status === 'sent').length;
        const failed = results.filter(r => r.status !== 'sent').length;

        return NextResponse.json({
            success: true,
            sent,
            failed,
            skipped: alreadyContacted.length,
            results,
        });

    } catch (error) {
        console.error('[Bulk Email Sender] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to send bulk emails' },
            { status: 500 }
        );
    }
}

/**
 * Check which vendors have already been contacted
 */
async function checkContactedVendors(vendors: any[]): Promise<string[]> {
    const client = await pool.connect();
    try {
        const vendorNames = vendors.map(v => v.vendor.toLowerCase());

        const result = await client.query(
            `SELECT DISTINCT LOWER(company_name) as company 
             FROM requests 
             WHERE LOWER(company_name) = ANY($1::text[])
             AND status IN ('sent', 'pending')`,
            [vendorNames]
        );

        return result.rows.map(row => row.company);
    } catch (error) {
        console.error('[Bulk Email] Error checking contacted vendors:', error);
        return [];
    } finally {
        client.release();
    }
}

/**
 * Record sent email in database
 */
async function recordSentEmail(
    company: string,
    dpoEmail: string,
    requestType: string,
    userEmail: string
) {
    const client = await pool.connect();
    try {
        await client.query(
            `INSERT INTO requests (company_name, domain, status, request_type, notes, created_at)
             VALUES ($1, $2, $3, $4, $5, NOW())`,
            [
                company,
                dpoEmail.split('@')[1] || '',
                'sent',
                requestType,
                `Bulk email sent via vendor discovery to ${dpoEmail}`,
            ]
        );
    } catch (error) {
        console.error(`[Bulk Email] Error recording email for ${company}:`, error);
    } finally {
        client.release();
    }
}
