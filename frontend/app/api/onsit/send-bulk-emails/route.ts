/**
 * Bulk GDPR Email Sender API Route
 * 
 * Sends GDPR requests to multiple vendors at once via N8N workflow.
 * Checks database to avoid sending duplicate emails to already-contacted vendors.
 */

import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { getWebhookUrl } from '@/lib/n8n-webhooks';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
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
        const alreadyContacted = await checkContactedVendors(vendors, authority.profileId);

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
                            userDetails.email,
                            authority.profileId,
                            authority.userId,
                        );
                        return { vendor: vendorData.vendor, status: 'sent' };
                    } else {
                        return { vendor: vendorData.vendor, status: 'failed' };
                    }
                } catch (error) {
                    console.error(`Failed to send email to ${vendorData.vendor}:`, error);
                    return { vendor: vendorData.vendor, status: 'error', error: 'Delivery or audit persistence failed' };
                }
            })
        );

        const sent = results.filter(r => r.status === 'sent').length;
        const failed = results.filter(r => r.status !== 'sent').length;

        return NextResponse.json({
            success: failed === 0,
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
async function checkContactedVendors(vendors: any[], profileId: string): Promise<string[]> {
    return requests.contactedCompanyNames(profileId,vendors.map(v=>String(v.vendor)));
}

/**
 * Record sent email in database
 */
async function recordSentEmail(
    company: string,
    dpoEmail: string,
    requestType: string,
    userEmail: string,
    profileId: string,
    userId: string,
) {
    void userEmail;
    const sentAt=new Date();
    const created=await requests.create(profileId,{company_name:company,domain:dpoEmail.split('@')[1]||'',
        status:'ready_for_review',request_type:requestType,notes:`Bulk email sent via vendor discovery to ${dpoEmail}`});
    await requests.transition(profileId,{request_id:created.id,next_state:'sent',actor:`user:${userId}`,
        reason:'Vendor-discovery transport recorded successful send',evidence_reference:`recipient:${dpoEmail}`,
        transitioned_at:sentAt,sent_at:sentAt});
}
