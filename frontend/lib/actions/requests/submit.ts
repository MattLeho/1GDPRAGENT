"use server";

import { revalidatePath } from "next/cache";
import { db } from "@/lib/db";
import { draftRequest, sendEmail } from "@/lib/n8n-client";
import { completeWorkflowLog, failWorkflowLog, startWorkflowLog } from "@/lib/workflow-logs";
import { getWorkflowPreference } from '@/lib/workflows/registry';
import { monitorInboxBuiltIn, sendBuiltInEmail } from '@/lib/connectors/email';
import { requireServerSessionAuthority } from '@/lib/api-session';
import { executeTask } from '@/lib/execution/router';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

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
        const {profileId,userId}=await requireServerSessionAuthority();
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

        // Creation is operational. No controller-receipt date or legal deadline
        // exists until explicit evidence is recorded.
        const createdRequest = await requests.create(profileId, {
            company_name: companyName, company_url: companyUrl, domain,
            status: 'draft', request_type: payload.scope, notes: payload.notes,
            next_action_at: new Date(),
        });
        const newRequestId = createdRequest.id;
        await requests.appendEvent(profileId,{request_id:newRequestId,event_type:'created',
            description:'Request created for drafting',occurred_at:new Date(),
            actor:`user:${userId}`,reason:'User submitted request details'});
        const userName = extractIdentityField(payload.identity, ['contactName', 'name', 'fullName', 'full_name', 'displayName']) || 'GDPR requester';
        const userEmail = extractIdentityField(payload.identity, ['contactEmail', 'email', 'emailAddress', 'email_address']) || 'not-provided@example.local';
        console.log("Inserted Request ID:", newRequestId);

        const requestDetails = extractRequestAccountDetails(payload.identity);
        if (requestDetails.length > 0) {
            try {
                await Promise.all(requestDetails.map(detail =>
                    requests.addRequestDetail(profileId,newRequestId,detail.fieldKey,detail.encryptedValue)
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
            await requests.appendMessage(profileId,newRequestId,'agent',`Request initiated for ${companyName}. Analyzing privacy policy and preparing GDPR request.`);
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
                    profileId,
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
                    const typeLabels: Record<string, { label: string; article: number }> = {
                        access: { label: 'Subject Access Request', article: 15 },
                        deletion: { label: 'Erasure Request', article: 17 },
                        erasure: { label: 'Erasure Request', article: 17 },
                        rectification: { label: 'Rectification Request', article: 16 },
                        portability: { label: 'Data Portability Request', article: 20 },
                        objection: { label: 'Objection to Processing', article: 21 },
                    };
                    const kind = typeLabels[payload.scope] || { label: 'GDPR Request', article: 15 };
                    const input = `Controller: ${companyName}\nPolicy URL: ${companyUrl || 'not supplied'}\nData subject: ${userName} <${userEmail}>\nRequest type: ${kind.label} (UK GDPR Article ${kind.article})\nUser instructions: ${payload.notes || `Prepare a ${payload.scope} GDPR request.`}`;
                    const routed = await executeTask({
                        taskKey: 'request.drafting',
                        workflowKey: 'request.drafting',
                        input: { text: input },
                        configuration: { systemPrompt: 'Draft a formal UK GDPR request letter using only the supplied facts. Cite the relevant right and Article 12(3) response period, offer proportionate identity verification, and mention the right to complain to the ICO. Do not invent account identifiers. Return only the complete letter body.' },
                        profileId,
                    });
                    if (!routed.ok) throw new Error(routed.error.message);
                    const draftBody = (routed.output as { text?: unknown }).text;
                    if (typeof draftBody !== 'string' || !draftBody.trim()) throw new Error('Built-in draft engine returned no text');

                    builtInDraft = {
                        subject: `${kind.label} – ${userName}`,
                        body: draftBody,
                    };
                    draftCreated = true;
                    draftBackend = 'built_in';
                    await completeWorkflowLog(profileId, builtInLogId, {
                        subject: builtInDraft.subject,
                        emailTransport: sendingPreference.execution_mode,
                    });

                    await requests.appendMessage(profileId,newRequestId,'agent',`Built-in workflow drafted a GDPR request for ${dpoEmail}.\n\nSubject: ${builtInDraft.subject}\n\n${builtInDraft.body}`);
                    await requests.updateProgress(profileId,newRequestId,15);
                    await requests.transition(profileId,{request_id:newRequestId,next_state:'ready_for_review',
                        actor:'workflow:request.drafting',reason:'Draft produced for human review',
                        evidence_reference:`workflow_log:${builtInLogId}`,transitioned_at:new Date()});
                } catch (builtInError) {
                    console.error("Built-in workflow failed:", builtInError);
                    await failWorkflowLog(profileId, builtInLogId, builtInError, {
                        workflowKey: 'request.drafting',
                        stage: 'draft',
                    });

                    if (!allowN8NDraft) {
                        await requests.appendMessage(profileId,newRequestId,'agent',`Built-in workflow failed. Please check model provider settings and retry. Error: ${builtInError instanceof Error ? builtInError.message : 'Unknown error'}`);
                    }
                }
            }

            let emailDraft: DraftEmail | null = builtInDraft;
            if (allowN8NDraft && !emailDraft) {
                    const n8nDraftLogId = await startWorkflowLog({
                        profileId,
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
                        await completeWorkflowLog(profileId, n8nDraftLogId, {
                            subject: emailDraft.subject,
                        });
                        await requests.updateProgress(profileId,newRequestId,15);
                        await requests.transition(profileId,{request_id:newRequestId,next_state:'ready_for_review',
                            actor:'workflow:request.drafting',reason:'N8N draft produced for human review',
                            evidence_reference:`workflow_log:${n8nDraftLogId}`,transitioned_at:new Date()});
                    } catch (n8nDraftError) {
                        console.error("N8N draft workflow failed:", n8nDraftError);
                        await failWorkflowLog(profileId, n8nDraftLogId, n8nDraftError, {
                            workflowKey: 'request.drafting',
                            stage: 'draft',
                        });

                        if (!builtInDraft) {
                            await requests.appendMessage(profileId,newRequestId,'agent',`N8N request drafter failed. Error: ${n8nDraftError instanceof Error ? n8nDraftError.message : 'Unknown error'}`);
                        }
                    }
            }

            if (emailDraft && sendingPreference.enabled && sendingPreference.execution_mode !== 'disabled') {
                const requireReview = sendingPreference.configuration.require_review === true;
                if (!requireReview && (sendingPreference.execution_mode === 'built_in' || sendingPreference.execution_mode === 'hybrid')) {
                    const builtInEmailLogId = await startWorkflowLog({profileId,requestId:newRequestId,workflowName:'Built-in SMTP Email Sender',workflowType:'built_in',details:{workflowKey:'email.sending',to:dpoEmail}});
                    try {
                        const sent=await sendBuiltInEmail(profileId,{requestId:newRequestId,to:dpoEmail,subject:emailDraft.subject,body:emailDraft.body});
                        emailSent=true; await completeWorkflowLog(profileId,builtInEmailLogId,{messageId:sent.messageId,transport:sent.transport});
                        await requests.appendMessage(profileId,newRequestId,'agent',`Built-in SMTP transport sent the GDPR request to ${dpoEmail}.`);
                        const sentAt=new Date();
                        await requests.transition(profileId,{request_id:newRequestId,next_state:'sent',actor:'workflow:email.sending',
                            reason:'SMTP transport recorded successful send',evidence_reference:`workflow_log:${builtInEmailLogId}`,
                            transitioned_at:sentAt,sent_at:sentAt});
                        await requests.transition(profileId,{request_id:newRequestId,next_state:'awaiting_response',actor:'workflow:email.sending',
                            reason:'Sent request is awaiting controller response',evidence_reference:`workflow_log:${builtInEmailLogId}`,
                            transitioned_at:sentAt,next_action_at:sentAt});
                        await requests.updateProgress(profileId,newRequestId,20);
                        // Prime the built-in monitor; a failed initial check does not undo a successful send.
                        monitorInboxBuiltIn().catch(error=>console.warn('Initial inbox monitor check failed:',error));
                    } catch (error) { await failWorkflowLog(profileId,builtInEmailLogId,error,{workflowKey:'email.sending',stage:'smtp_send'}); }
                }

                const useN8NTransport = !requireReview && !emailSent && (sendingPreference.execution_mode === 'n8n' || sendingPreference.execution_mode === 'hybrid');
                if (useN8NTransport) {
                    const n8nEmailLogId = await startWorkflowLog({
                        profileId,
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
                        await completeWorkflowLog(profileId, n8nEmailLogId, {
                            messageId: sendResult.data?.messageId || null,
                        });

                        await requests.appendMessage(profileId,newRequestId,'agent',`N8N email transport sent the GDPR request email to ${dpoEmail}`);
                        const sentAt=new Date();
                        await requests.transition(profileId,{request_id:newRequestId,next_state:'sent',actor:'workflow:email.sending',
                            reason:'N8N transport recorded successful send',evidence_reference:`workflow_log:${n8nEmailLogId}`,
                            transitioned_at:sentAt,sent_at:sentAt});
                        await requests.transition(profileId,{request_id:newRequestId,next_state:'awaiting_response',actor:'workflow:email.sending',
                            reason:'Sent request is awaiting controller response',evidence_reference:`workflow_log:${n8nEmailLogId}`,
                            transitioned_at:sentAt,next_action_at:sentAt});
                        await requests.updateProgress(profileId,newRequestId,20);
                    } catch (n8nEmailError) {
                        console.error("N8N email workflow failed:", n8nEmailError);
                        await failWorkflowLog(profileId, n8nEmailLogId, n8nEmailError, {
                            workflowKey: 'email.sending',
                            stage: 'email_send',
                        });

                        await requests.appendMessage(profileId,newRequestId,'agent',`N8N email transport failed. Draft is available for review. Error: ${n8nEmailError instanceof Error ? n8nEmailError.message : 'Unknown error'}`);
                    }
                }
                if (requireReview) await requests.appendMessage(profileId,newRequestId,'agent','Draft is awaiting human review before email delivery.');
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
