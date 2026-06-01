"use server";

import { revalidatePath } from "next/cache";
import { db } from "@/lib/db";
import { draftRequest, sendEmail } from "@/lib/n8n-client";

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
        } catch (e) {
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
        console.log("Inserted Request ID:", newRequestId);

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

        // Trigger N8N to draft and send the request email
        let emailSent = false;
        if (payload.analysis?.dpo_email) {
            try {
                // Draft the email via N8N
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

                if (draftResult.success && draftResult.data) {
                    // Send the email via N8N
                    const sendResult = await sendEmail({
                        to: payload.analysis.dpo_email,
                        subject: draftResult.data.subject,
                        body: draftResult.data.body,
                    });

                    if (sendResult.success) {
                        emailSent = true;
                        // Log that email was sent
                        await db.query(
                            `INSERT INTO messages (request_id, sender, content) VALUES ($1, 'agent', $2)`,
                            [newRequestId, `GDPR request email sent to ${payload.analysis.dpo_email}`]
                        );
                        // Update request status
                        await db.query(
                            `UPDATE requests SET progress = 20, status = 'processing' WHERE id = $1`,
                            [newRequestId]
                        );
                    }
                }
            } catch (n8nError) {
                console.error("N8N email workflow failed:", n8nError);
                // Request is still created, just not sent automatically
            }
        }

        revalidatePath('/dashboard/requests');
        revalidatePath('/dashboard/home');

        return {
            success: true,
            message: emailSent
                ? "Request sent and GDPR email delivered!"
                : "Request queued for processing",
            requestId: newRequestId,
            emailSent,
        };

    } catch (error: unknown) {
        console.error("Failed to submit request:", error);
        const message = error instanceof Error ? error.message : "Failed to submit request";
        return { success: false, message };
    }
}
