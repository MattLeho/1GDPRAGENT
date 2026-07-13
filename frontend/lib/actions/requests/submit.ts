"use server";

import { revalidatePath } from "next/cache";
import { db } from "@/lib/db";
import { draftRequest, sendEmail } from "@/lib/n8n-client";
import { completeWorkflowLog, failWorkflowLog, startWorkflowLog } from "@/lib/workflow-logs";
import { getWorkflowPreference } from '@/lib/workflows/registry';
import { monitorInboxBuiltIn, sendBuiltInEmail } from '@/lib/connectors/email';

interface AnalysisData {
    dpo_email?: string;
    address?: string;
    data_collected?: string[];
    retention_period?: string;
    third_party_sharing?: string[];
    summary?: string;
}

interface RequestPayload {
    company: string;
    identity: unknown;
    scope: string; // "access", "deletion", or "access+deletion"
    dateRange: { from?: Date; to?: Date } | null;
    notes: string;
    analysis: AnalysisData | null;
}

interface DraftEmail {
    subject: string;
    body: string;
}

interface RequestAccountDetail {
    fieldKey: string;
    encryptedValue: string;
}

function extractIdentityField(identity: unknown, fieldNames: string[]): string | null {
    if (!identity || typeof identity !== 'object') {
        return null;
    }

    const identityRecord = identity as Record<string, unknown>;
    for (const fieldName of fieldNames) {
        const value = identityRecord[fieldName];
        if (typeof value === 'string' && value.trim()) {
            return value.trim();
        }
    }

    for (const value of Object.values(identityRecord)) {
        if (typeof value === 'string') {
            continue;
        }
        if (value && typeof value === 'object') {
            const nested = extractIdentityField(value, fieldNames);
            if (nested) {
                return nested;
            }
        }
    }

    return null;
}

function extractRequestAccountDetails(identity: unknown): RequestAccountDetail[] {
    if (!identity || typeof identity !== 'object') {
        return [];
    }

    const requestDetails = (identity as Record<string, unknown>).requestDetails;
    if (!Array.isArray(requestDetails)) {
        return [];
    }

    return requestDetails.flatMap((detail) => {
        if (!detail || typeof detail !== 'object') {
            return [];
        }

        const detailRecord = detail as Record<string, unknown>;
        const fieldKey = detailRecord.fieldKey;
        const encryptedValue = detailRecord.encryptedValue;

        if (typeof fieldKey !== 'string' || typeof encryptedValue !== 'string') {
            return [];
        }

        const normalizedKey = fieldKey.trim();
        const normalizedValue = encryptedValue.trim();

        if (!normalizedKey || !normalizedValue) {
            return [];
        }

        return [{ fieldKey: normalizedKey, encryptedValue: normalizedValue }];
    });
}

export async function submitRequest(payload: RequestPayload) {
    console.log("Submitting Request Payload:", payload);

    try {
        // payload.company IS the target URL in our current flow
        const companyUrl = payload.company;
        let domain: string | null = null;
        let companyName = payload.company;

        try {
            if (companyUrl.startsWith('http')) {
                const urlObj = new URL(companyUrl);
                domain = urlObj.hostname;
                companyName = domain.replace('www.', '').replace('.com', '').replace('.', ' ');
                // Capitalize first letter
                companyName = companyName.charAt(0).toUpperCase() + companyName.slice(1);
            }
        } catch {
            console.warn("Could not parse company URL:", companyUrl);
        }

        // Calculate deadline (30 days from now per GDPR Article 12)
        const deadline = new Date();
        deadline.setDate(deadline.getDate() + 30);

        // Insert the main request
        const requestQuery = `
            INSERT INTO requests (
                company_name, 
                company_url, 
                domain, 
                status, 
                request_type, 
                deadline_date, 
                notes,
                data_period_start,
                data_period_end,
                next_action_date
            ) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            RETURNING id
        `;

        const requestValues = [
            companyName,
            companyUrl,
            domain,
            'processing',
            // Handle multi-select: "access", "deletion", or "access+deletion"
            payload.scope,
            deadline,
            payload.notes,
            payload.dateRange?.from || null,
            payload.dateRange?.to || null
        ];

        const res = await db.query<{ id: string }>(requestQuery, requestValues);

        if (!res.rows || res.rows.length === 0) {
            throw new Error("Failed to create request in database");
        }

        const newRequestId = res.rows[0].id;
        const userName = extractIdentityField(payload.identity, ['contactName', 'name', 'fullName', 'full_name', 'displayName']) || 'GDPR requester';
        const userEmail = extractIdentityField(payload.identity, ['contactEmail', 'email', 'emailAddress', 'email_address']) || 'not-provided@example.local';
        console.log("Inserted Request ID:", newRequestId);

        const requestDetails = extractRequestAccountDetails(payload.identity);
        if (requestDetails.length > 0) {
            try {
                await Promise.all(requestDetails.map(detail =>
                    db.query(
                        `INSERT INTO request_details (request_id, field_key, field_value_encrypted)
                         VALUES ($1, $2, $3)`,
                        [newRequestId, detail.fieldKey, detail.encryptedValue]
                    )
                ));
                console.log(`Saved ${requestDetails.length} request detail fields for request:`, newRequestId);
            } catch (detailsError) {
                console.error("Failed to save request details:", detailsError);
            }
        }

        // Save policy analysis if provided
        if (payload.analysis) {
            try {
                await db.query(
                    `INSERT INTO policy_analyses (
                        url, domain, dpo_email, data_collected, summary, created_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (url) DO NOTHING`,
                    [
                        companyUrl,
                        domain || companyUrl,
                        payload.analysis.dpo_email || null,
                        JSON.stringify(payload.analysis.data_collected || []),
                        payload.analysis.summary || "Analysis from request"
                    ]
                );
                console.log("Saved policy analysis for request:", newRequestId);
            } catch (analysisError) {
                console.error("Failed to save policy analysis:", analysisError);
            }
        }

        // Create initial agent message
        try {
            await db.query(
                `INSERT INTO messages (request_id, sender, content) VALUES ($1, 'agent', $2)`,
                [newRequestId, `Request initiated for ${companyName}. Analyzing privacy policy and preparing GDPR request.`]
            );
        } catch (msgError) {
            console.error("Failed to create initial message:", msgError);
        }

        const draftingPreference = await getWorkflowPreference('request.drafting');
        const sendingPreference = await getWorkflowPreference('email.sending');

        // Drafting and transport are independently routed workflows.
        let emailSent = false;
        let draftCreated = false;
        let draftBackend: 'built_in' | 'n8n' | null = null;
        let builtInDraft: DraftEmail | null = null;
        if (payload.analysis?.dpo_email) {
            const dpoEmail = payload.analysis.dpo_email;
            const useBuiltInDraft = draftingPreference.enabled && (draftingPreference.execution_mode === 'built_in' || draftingPreference.execution_mode === 'hybrid');
            const allowN8NDraft = draftingPreference.enabled && (draftingPreference.execution_mode === 'n8n' || draftingPreference.execution_mode === 'hybrid');

            if (useBuiltInDraft) {
                const builtInLogId = await startWorkflowLog({
                    requestId: newRequestId,
                    workflowName: 'Built-in GDPR Request Drafter',
                    workflowType: 'built_in',
                    details: {
                        workflowKey: 'request.drafting',
                        companyName,
                        dpoEmail,
                        requestType: payload.scope,
                    },
                });

                try {
                    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';
                    const response = await fetch(`${baseUrl}/api/gdpr-agent/draft`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            requestType: payload.scope,
                            company: companyName,
                            userQuery: payload.notes || `Prepare a ${payload.scope} GDPR request.`,
                            userName,
                            userEmail,
                            policyUrl: companyUrl,
                        }),
                    });

                    if (!response.ok) {
                        throw new Error(`Built-in draft route returned ${response.status}`);
                    }

                    const builtInResult = await response.json() as {
                        success?: boolean;
                        error?: string;
                        draft?: {
                            subject?: string;
                            body?: string;
                        };
                    };

                    if (!builtInResult.success || !builtInResult.draft?.subject || !builtInResult.draft.body) {
                        throw new Error(builtInResult.error || 'Built-in draft failed');
                    }

                    builtInDraft = {
                        subject: builtInResult.draft.subject,
                        body: builtInResult.draft.body,
                    };
                    draftCreated = true;
                    draftBackend = 'built_in';
                    await completeWorkflowLog(builtInLogId, {
                        subject: builtInDraft.subject,
                        emailTransport: sendingPreference.execution_mode,
                    });

                    await db.query(
                        `INSERT INTO messages (request_id, sender, content) VALUES ($1, 'agent', $2)`,
                        [newRequestId, `Built-in workflow drafted a GDPR request for ${dpoEmail}.\n\nSubject: ${builtInDraft.subject}\n\n${builtInDraft.body}`]
                    );
                    await db.query(
                        `UPDATE requests SET progress = 15, status = 'action_required' WHERE id = $1`,
                        [newRequestId]
                    );
                } catch (builtInError) {
                    console.error("Built-in workflow failed:", builtInError);
                    await failWorkflowLog(builtInLogId, builtInError, {
                        workflowKey: 'request.drafting',
                        stage: 'draft',
                    });

                    if (!allowN8NDraft) {
                        await db.query(
                            `INSERT INTO messages (request_id, sender, content) VALUES ($1, 'agent', $2)`,
                            [newRequestId, `Built-in workflow failed. Please check model provider settings and retry. Error: ${builtInError instanceof Error ? builtInError.message : 'Unknown error'}`]
                        );
                    }
                }
            }

            let emailDraft: DraftEmail | null = builtInDraft;
            if (allowN8NDraft && !emailDraft) {
                    const n8nDraftLogId = await startWorkflowLog({
                        requestId: newRequestId,
                        workflowName: 'N8N Request Drafter',
                        workflowType: 'n8n',
                        details: {
                            workflowKey: 'request.drafting',
                            companyName,
                            dpoEmail,
                            requestType: payload.scope,
                        },
                    });

                    try {
                        const draftResult = await draftRequest({
                            companyName,
                            companyUrl,
                            requestType: payload.scope,
                            identity: payload.identity as Record<string, unknown>,
                            notes: payload.notes,
                            datePeriod: payload.dateRange ? {
                                from: payload.dateRange.from?.toISOString(),
                                to: payload.dateRange.to?.toISOString(),
                            } : undefined,
                        });

                        if (!draftResult.success || !draftResult.data?.subject || !draftResult.data.body) {
                            throw new Error(draftResult.error || 'N8N draft workflow failed');
                        }

                        emailDraft = {
                            subject: draftResult.data.subject,
                            body: draftResult.data.body,
                        };
                        draftCreated = true;
                        draftBackend = 'n8n';
                        await completeWorkflowLog(n8nDraftLogId, {
                            subject: emailDraft.subject,
                        });
                    } catch (n8nDraftError) {
                        console.error("N8N draft workflow failed:", n8nDraftError);
                        await failWorkflowLog(n8nDraftLogId, n8nDraftError, {
                            workflowKey: 'request.drafting',
                            stage: 'draft',
                        });

                        if (!builtInDraft) {
                            await db.query(
                                `INSERT INTO messages (request_id, sender, content) VALUES ($1, 'agent', $2)`,
                                [newRequestId, `N8N request drafter failed. Error: ${n8nDraftError instanceof Error ? n8nDraftError.message : 'Unknown error'}`]
                            );
                        }
                    }
            }

            if (emailDraft && sendingPreference.enabled && sendingPreference.execution_mode !== 'disabled') {
                const requireReview = sendingPreference.configuration.require_review === true;
                if (!requireReview && (sendingPreference.execution_mode === 'built_in' || sendingPreference.execution_mode === 'hybrid')) {
                    const builtInEmailLogId = await startWorkflowLog({requestId:newRequestId,workflowName:'Built-in SMTP Email Sender',workflowType:'built_in',details:{workflowKey:'email.sending',to:dpoEmail}});
                    try {
                        const sent=await sendBuiltInEmail({requestId:newRequestId,to:dpoEmail,subject:emailDraft.subject,body:emailDraft.body});
                        emailSent=true; await completeWorkflowLog(builtInEmailLogId,{messageId:sent.messageId,transport:sent.transport});
                        await db.query(`INSERT INTO messages (request_id,sender,content) VALUES($1,'agent',$2)`,[newRequestId,`Built-in SMTP transport sent the GDPR request to ${dpoEmail}.`]);
                        await db.query(`UPDATE requests SET progress=20,status='processing' WHERE id=$1`,[newRequestId]);
                        // Prime the built-in monitor; a failed initial check does not undo a successful send.
                        monitorInboxBuiltIn().catch(error=>console.warn('Initial inbox monitor check failed:',error));
                    } catch (error) { await failWorkflowLog(builtInEmailLogId,error,{workflowKey:'email.sending',stage:'smtp_send'}); }
                }

                const useN8NTransport = !requireReview && !emailSent && (sendingPreference.execution_mode === 'n8n' || sendingPreference.execution_mode === 'hybrid');
                if (useN8NTransport) {
                    const n8nEmailLogId = await startWorkflowLog({
                        requestId: newRequestId,
                        workflowName: 'N8N Email Sender',
                        workflowType: 'n8n',
                        details: {
                            workflowKey: 'email.sending',
                            to: dpoEmail,
                            draftSource: emailDraft === builtInDraft ? 'built_in' : 'n8n',
                        },
                    });

                    try {
                        const sendResult = await sendEmail({
                            to: dpoEmail,
                            subject: emailDraft.subject,
                            body: emailDraft.body,
                        });

                        if (!sendResult.success) {
                            throw new Error(sendResult.error || 'N8N email workflow failed');
                        }

                        emailSent = true;
                        await completeWorkflowLog(n8nEmailLogId, {
                            messageId: sendResult.data?.messageId || null,
                        });

                        await db.query(
                            `INSERT INTO messages (request_id, sender, content) VALUES ($1, 'agent', $2)`,
                            [newRequestId, `N8N email transport sent the GDPR request email to ${dpoEmail}`]
                        );
                        await db.query(
                            `UPDATE requests SET progress = 20, status = 'processing' WHERE id = $1`,
                            [newRequestId]
                        );
                    } catch (n8nEmailError) {
                        console.error("N8N email workflow failed:", n8nEmailError);
                        await failWorkflowLog(n8nEmailLogId, n8nEmailError, {
                            workflowKey: 'email.sending',
                            stage: 'email_send',
                        });

                        await db.query(
                            `INSERT INTO messages (request_id, sender, content) VALUES ($1, 'agent', $2)`,
                            [newRequestId, `N8N email transport failed. Draft is available for review. Error: ${n8nEmailError instanceof Error ? n8nEmailError.message : 'Unknown error'}`]
                        );
                    }
                }
                if (requireReview) await db.query(`INSERT INTO messages(request_id,sender,content) VALUES($1,'agent',$2)`,[newRequestId,'Draft is awaiting human review before email delivery.']);
            }
        }

        revalidatePath('/dashboard/requests');
        revalidatePath('/dashboard/home');

        return {
            success: true,
            message: emailSent
                ? "Request sent and GDPR email delivered!"
                : draftCreated
                    ? `Request created and ${draftBackend === 'n8n' ? 'N8N' : 'built-in'} workflow drafted an email for review`
                    : "Request queued for processing",
            requestId: newRequestId,
            emailSent,
            draftCreated,
        };

    } catch (error: unknown) {
        console.error("Failed to submit request:", error);
        const message = error instanceof Error ? error.message : "Failed to submit request";
        return { success: false, message };
    }
}
