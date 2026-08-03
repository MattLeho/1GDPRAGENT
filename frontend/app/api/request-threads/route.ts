/**
 * Request Threads API Route
 * 
 * Manages per-company request threads that track the full GDPR request lifecycle:
 * 1. Privacy policy analysis
 * 2. Request draft (Python RLM agent)
 * 3. Email sending (via N8N with SMTP credentials from settings)
 * 4. Response monitoring
 * 5. Follow-up actions
 * 
 * Each company gets one thread containing all interactions for AI context.
 */

import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { Pool } from 'pg';
import { RequestService } from '@/lib/requests/service';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const requests=new RequestService();

// GET: Fetch thread for a company
export async function GET(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { searchParams } = new URL(request.url);
        const company = searchParams.get('company');
        const threadId = searchParams.get('threadId');

        if (!company && !threadId) {
            return NextResponse.json(
                { success: false, error: 'Company or threadId required' },
                { status: 400 }
            );
        }

        const client = await pool.connect();
        try {
            let result;
            if (threadId) {
                result = await client.query(
                    'SELECT * FROM request_threads WHERE thread_id = $1 AND profile_id = $2',
                    [threadId, authority.profileId]
                );
            } else {
                result = await client.query(
                    'SELECT * FROM request_threads WHERE LOWER(company) = LOWER($1) AND profile_id = $2 ORDER BY created_at DESC LIMIT 1',
                    [company, authority.profileId]
                );
            }

            if (result.rows.length === 0) {
                return NextResponse.json({
                    success: true,
                    thread: null,
                    exists: false,
                });
            }

            return NextResponse.json({
                success: true,
                thread: result.rows[0],
                exists: true,
            });
        } finally {
            client.release();
        }
    } catch (error) {
        console.error('[Request Threads] GET error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to fetch thread' },
            { status: 500 }
        );
    }
}

// POST: Create or update thread
export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json();
        const { company, domain, action, data, requestId } = body;

        if (!company) {
            return NextResponse.json(
                { success: false, error: 'Company is required' },
                { status: 400 }
            );
        }

        const client = await pool.connect();
        try {
            if(requestId&&!await requests.get(authority.profileId,String(requestId))){
                return NextResponse.json({success:false,error:'Request not found'},{status:404});
            }
            // Check if thread exists
            const existing = await client.query(
                'SELECT * FROM request_threads WHERE LOWER(company) = LOWER($1) AND domain = $2 AND profile_id = $3',
                [company, domain || '', authority.profileId]
            );

            let threadId;

            if (existing.rows.length === 0) {
                // Create new thread
                const result = await client.query(
                    `INSERT INTO request_threads (company, domain, status, conversation_history, profile_id,request_id)
                     VALUES ($1, $2, $3, $4, $5,$6)
                     RETURNING thread_id, id,request_id`,
                    [company, domain || null, 'initialized', JSON.stringify([]), authority.profileId,requestId||null]
                );
                threadId = result.rows[0].thread_id;
            } else {
                threadId = existing.rows[0].thread_id;
            }

            const linked=await client.query('SELECT request_id FROM request_threads WHERE thread_id=$1 AND profile_id=$2',[threadId,authority.profileId]);
            const canonicalRequestId=linked.rows[0]?.request_id?String(linked.rows[0].request_id):null;
            if(['request_drafted','email_sent','response_received'].includes(action)&&!canonicalRequestId){
                return NextResponse.json({success:false,error:'Lifecycle actions require a canonical request link'},{status:409});
            }

            // Update thread based on action
            switch (action) {
                case 'policy_analyzed':
                    await client.query(
                        `UPDATE request_threads 
                         SET policy_url = $1, policy_markdown = $2, policy_summary = $3,
                             dpo_email = $4, compliance_score = $5, status = 'policy_analyzed',
                             updated_at = NOW(),
                             conversation_history = conversation_history || $6::jsonb
                         WHERE thread_id = $7`,
                        [
                            data.policyUrl,
                            data.markdownContent,
                            data.summary,
                            data.dpoEmail,
                            data.complianceScore,
                            JSON.stringify([{
                                timestamp: new Date().toISOString(),
                                action: 'policy_analyzed',
                                data: {
                                    url: data.policyUrl,
                                    score: data.complianceScore,
                                    dpo: data.dpoEmail,
                                }
                            }]),
                            threadId
                        ]
                    );
                    break;

                case 'request_drafted':
                    await client.query(
                        `UPDATE request_threads 
                         SET request_type = $1, draft_subject = $2, draft_body = $3,
                             drafted_at = NOW(), status = 'drafted',
                             updated_at = NOW(),
                             conversation_history = conversation_history || $4::jsonb
                         WHERE thread_id = $5`,
                        [
                            data.requestType,
                            data.subject,
                            data.body,
                            JSON.stringify([{
                                timestamp: new Date().toISOString(),
                                action: 'request_drafted',
                                data: {
                                    type: data.requestType,
                                    subject: data.subject,
                                }
                            }]),
                            threadId
                        ]
                    );
                    await requests.transition(authority.profileId,{request_id:canonicalRequestId!,next_state:'ready_for_review',
                        actor:`user:${authority.userId}`,reason:'Request thread draft recorded',
                        evidence_reference:`request_thread:${threadId}`,transitioned_at:new Date()});
                    break;

                case 'email_sent':
                    await client.query(
                        `UPDATE request_threads 
                         SET sent_at = NOW(), sent_via = $1, email_status = 'sent',
                             status = 'sent', updated_at = NOW(),
                             conversation_history = conversation_history || $2::jsonb
                         WHERE thread_id = $3`,
                        [
                            data.sentVia || 'n8n',
                            JSON.stringify([{
                                timestamp: new Date().toISOString(),
                                action: 'email_sent',
                                data: {
                                    to: data.to,
                                    via: data.sentVia || 'n8n',
                                }
                            }]),
                            threadId
                        ]
                    );
                    const sentAt=new Date();
                    await requests.transition(authority.profileId,{request_id:canonicalRequestId!,next_state:'sent',
                        actor:`user:${authority.userId}`,reason:'Request thread recorded successful send',
                        evidence_reference:`request_thread:${threadId}`,transitioned_at:sentAt,sent_at:sentAt});
                    break;

                case 'response_received':
                    await client.query(
                        `UPDATE request_threads 
                         SET response_received_at = NOW(), response_content = $1,
                             response_summary = $2, status = 'response_received',
                             updated_at = NOW(),
                             conversation_history = conversation_history || $3::jsonb
                         WHERE thread_id = $4`,
                        [
                            data.content,
                            data.summary,
                            JSON.stringify([{
                                timestamp: new Date().toISOString(),
                                action: 'response_received',
                                data: {
                                    summary: data.summary,
                                }
                            }]),
                            threadId
                        ]
                    );
                    const responseAt=new Date();
                    await requests.transition(authority.profileId,{request_id:canonicalRequestId!,next_state:'response_received',
                        actor:`user:${authority.userId}`,reason:'Controller response recorded in request thread',
                        evidence_reference:`request_thread:${threadId}`,transitioned_at:responseAt,response_received_at:responseAt});
                    break;

                case 'follow_up':
                    await client.query(
                        `UPDATE request_threads 
                         SET follow_up_needed = $1, follow_up_reason = $2,
                             follow_up_sent_at = $3, status = $4,
                             updated_at = NOW(),
                             conversation_history = conversation_history || $5::jsonb
                         WHERE thread_id = $6`,
                        [
                            data.needed !== false,
                            data.reason,
                            data.sent ? new Date() : null,
                            data.sent ? 'follow_up_sent' : 'follow_up_needed',
                            JSON.stringify([{
                                timestamp: new Date().toISOString(),
                                action: 'follow_up',
                                data: {
                                    needed: data.needed,
                                    reason: data.reason,
                                    sent: data.sent || false,
                                }
                            }]),
                            threadId
                        ]
                    );
                    break;

                default:
                    return NextResponse.json(
                        { success: false, error: `Unknown action: ${action}` },
                        { status: 400 }
                    );
            }

            // Fetch updated thread
            const updated = await client.query(
                'SELECT * FROM request_threads WHERE thread_id = $1 AND profile_id = $2',
                [threadId, authority.profileId]
            );

            return NextResponse.json({
                success: true,
                thread: updated.rows[0],
                threadId,
            });

        } finally {
            client.release();
        }
    } catch (error) {
        console.error('[Request Threads] POST error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to update thread' },
            { status: 500 }
        );
    }
}
