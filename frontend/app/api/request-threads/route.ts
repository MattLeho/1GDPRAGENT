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
import { Pool } from 'pg';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

// Initialize request_threads table
async function initTable() {
    const client = await pool.connect();
    try {
        await client.query(`
            CREATE TABLE IF NOT EXISTS request_threads (
                id SERIAL PRIMARY KEY,
                company VARCHAR(255) NOT NULL,
                domain VARCHAR(255),
                thread_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
                
                -- Policy Analysis
                policy_url TEXT,
                policy_markdown TEXT,
                policy_summary TEXT,
                dpo_email VARCHAR(255),
                compliance_score INTEGER,
                
                -- Request Draft
                request_type VARCHAR(50),
                draft_subject TEXT,
                draft_body TEXT,
                drafted_at TIMESTAMP,
                
                -- Email Sending
                sent_at TIMESTAMP,
                sent_via VARCHAR(50) DEFAULT 'n8n',
                email_status VARCHAR(50),
                
                -- Response Tracking
                response_received_at TIMESTAMP,
                response_content TEXT,
                response_summary TEXT,
                
                -- Follow-up
                follow_up_needed BOOLEAN DEFAULT false,
                follow_up_reason TEXT,
                follow_up_sent_at TIMESTAMP,
                
                -- Metadata
                status VARCHAR(50) DEFAULT 'initialized',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                
                -- AI Context
                conversation_history JSONB DEFAULT '[]'::jsonb,
                
                UNIQUE(company, domain)
            );
            
            CREATE INDEX IF NOT EXISTS idx_threads_company ON request_threads(company);
            CREATE INDEX IF NOT EXISTS idx_threads_thread_id ON request_threads(thread_id);
            CREATE INDEX IF NOT EXISTS idx_threads_status ON request_threads(status);
        `);
    } finally {
        client.release();
    }
}

// GET: Fetch thread for a company
export async function GET(request: NextRequest) {
    try {
        await initTable();

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
                    'SELECT * FROM request_threads WHERE thread_id = $1',
                    [threadId]
                );
            } else {
                result = await client.query(
                    'SELECT * FROM request_threads WHERE LOWER(company) = LOWER($1) ORDER BY created_at DESC LIMIT 1',
                    [company]
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
    try {
        await initTable();

        const body = await request.json();
        const { company, domain, action, data } = body;

        if (!company) {
            return NextResponse.json(
                { success: false, error: 'Company is required' },
                { status: 400 }
            );
        }

        const client = await pool.connect();
        try {
            // Check if thread exists
            const existing = await client.query(
                'SELECT * FROM request_threads WHERE LOWER(company) = LOWER($1) AND domain = $2',
                [company, domain || '']
            );

            let threadId;

            if (existing.rows.length === 0) {
                // Create new thread
                const result = await client.query(
                    `INSERT INTO request_threads (company, domain, status, conversation_history)
                     VALUES ($1, $2, $3, $4)
                     RETURNING thread_id, id`,
                    [company, domain || null, 'initialized', JSON.stringify([])]
                );
                threadId = result.rows[0].thread_id;
            } else {
                threadId = existing.rows[0].thread_id;
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
                'SELECT * FROM request_threads WHERE thread_id = $1',
                [threadId]
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
