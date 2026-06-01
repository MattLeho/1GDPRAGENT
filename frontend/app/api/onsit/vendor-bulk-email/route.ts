import { NextResponse } from 'next/server';
import { pool } from '@/lib/db';

export async function POST(request: Request) {
    try {
        const { vendorIds } = await request.json();

        if (!vendorIds || !Array.isArray(vendorIds)) {
            return NextResponse.json(
                { success: false, error: 'Vendor IDs required' },
                { status: 400 }
            );
        }

        // Get vendors with DPO emails
        const result = await pool.query(
            `SELECT id, domain, company_name, dpo_email 
             FROM vendor_lists 
             WHERE id = ANY($1) AND dpo_email IS NOT NULL`,
            [vendorIds]
        );

        const vendors = result.rows;

        if (vendors.length === 0) {
            return NextResponse.json(
                { success: false, error: 'No vendors with DPO emails found' },
                { status: 400 }
            );
        }

        let emailsSent = 0;
        const n8nDrafterUrl = process.env.N8N_WEBHOOK_REQUEST_DRAFTER;

        // Send GDPR requests via N8N Request Drafter workflow
        for (const vendor of vendors) {
            try {
                const res = await fetch(n8nDrafterUrl!, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        company_name: vendor.company_name || vendor.domain,
                        dpo_email: vendor.dpo_email,
                        request_type: 'access',
                        auto_send: true,
                    }),
                });

                if (res.ok) {
                    // Mark as sent in database
                    await pool.query(
                        `UPDATE vendor_lists 
                         SET gdpr_email_sent = true, gdpr_email_sent_at = NOW()
                         WHERE id = $1`,
                        [vendor.id]
                    );
                    emailsSent++;
                }
            } catch (error) {
                console.error(`[Bulk Email] Failed for vendor ${vendor.id}:`, error);
            }
        }

        return NextResponse.json({
            success: true,
            emailsSent,
            total: vendors.length,
        });
    } catch (error) {
        console.error('[Bulk Email] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Bulk email sending failed' },
            { status: 500 }
        );
    }
}
