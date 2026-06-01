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

        // Get vendor details
        const result = await pool.query(
            'SELECT id, domain, company_name FROM vendor_lists WHERE id = ANY($1)',
            [vendorIds]
        );

        const vendors = result.rows;
        const updated = [];

        // Call Python intelligence service for DPO discovery
        const intelligenceUrl = process.env.INTELLIGENCE_SERVICE_URL || 'http://localhost:8000';

        for (const vendor of vendors) {
            try {
                const res = await fetch(`${intelligenceUrl}/vendor/find-dpo`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        domain: vendor.domain,
                        company_name: vendor.company_name,
                    }),
                });

                if (res.ok) {
                    const data = await res.json();
                    if (data.dpo_email) {
                        // Update database
                        await pool.query(
                            'UPDATE vendor_lists SET dpo_email = $1 WHERE id = $2',
                            [data.dpo_email, vendor.id]
                        );
                        updated.push({ id: vendor.id, dpo_email: data.dpo_email });
                    }
                }
            } catch (error) {
                console.error(`[DPO Discovery] Failed for vendor ${vendor.id}:`, error);
            }
        }

        return NextResponse.json({
            success: true,
            updated,
        });
    } catch (error) {
        console.error('[DPO Discovery] Error:', error);
        return NextResponse.json(
            { success: false, error: 'DPO discovery failed' },
            { status: 500 }
        );
    }
}
