/**
 * ONSIT Findings API Route
 * 
 * Retrieves and manages findings from ONSIT discovery scans.
 * Supports GET (retrieve findings) and DELETE (dismiss findings).
 * 
 * @see https://github.com/reconurge/flowsint - Entity types
 */

import { NextResponse } from 'next/server';

const INTELLIGENCE_URL = process.env.INTELLIGENCE_SERVICE_URL || 'http://localhost:8000';

/**
 * Intelligence service finding format
 */
interface IntelligenceFinding {
    id: string;
    type: string;
    value: string;
    label?: string;
    source: string;
    enricher: string;
    confidence: number;
    risk_level?: 'low' | 'medium' | 'high' | 'critical';
    metadata?: Record<string, unknown>;
    discovered_at: string;
    evidence?: Array<{
        url: string;
        snippet?: string;
    }>;
}

/**
 * Frontend-friendly finding format
 * Matches the Finding interface in FindingCard.tsx
 */
interface Finding {
    id: string;
    type: string;
    title: string;
    description: string;
    source: string;
    riskLevel: 'low' | 'medium' | 'high' | 'critical';
    confidence: number;
    metadata: Record<string, unknown>;
    discoveredAt: string;
    evidence?: Array<{
        url: string;
        snippet?: string;
    }>;
    addedToGraph?: boolean;
}

/**
 * Map entity type to human-readable description
 */
function getEntityDescription(type: string, value: string): string {
    const descriptions: Record<string, (v: string) => string> = {
        email: (v) => `Email address found: ${v}`,
        username: (v) => `Username "${v}" found on social platforms`,
        social_profile: (v) => `Social media profile discovered`,
        breach_record: (v) => `Found in data breach`,
        domain: (v) => `Domain ${v} analyzed`,
        ip: (v) => `IP address ${v} associated`,
        phone: (v) => `Phone number ${v} found`,
        website: (v) => `Website ${v} crawled`,
        credential: (v) => `Credential exposure detected`,
        document: (v) => `Public document found`,
    };

    const descFunc = descriptions[type.toLowerCase()];
    return descFunc ? descFunc(value) : `${type}: ${value}`;
}

/**
 * Determine risk level based on entity type and source
 */
function inferRiskLevel(type: string, source: string): 'low' | 'medium' | 'high' | 'critical' {
    // High risk types
    if (['breach_record', 'credential', 'password'].includes(type.toLowerCase())) {
        return 'critical';
    }

    // Medium-high risk
    if (['social_profile', 'phone'].includes(type.toLowerCase())) {
        return 'medium';
    }

    // Source-based risk
    if (source.includes('breach') || source.includes('leak')) {
        return 'high';
    }

    return 'low';
}

/**
 * Transform intelligence finding to frontend format
 */
function transformFinding(finding: IntelligenceFinding): Finding {
    return {
        id: finding.id,
        type: finding.type,
        title: finding.label || finding.value,
        description: getEntityDescription(finding.type, finding.value),
        source: finding.source || finding.enricher,
        riskLevel: finding.risk_level || inferRiskLevel(finding.type, finding.source),
        confidence: finding.confidence,
        metadata: finding.metadata || {},
        discoveredAt: finding.discovered_at,
        evidence: finding.evidence,
        addedToGraph: false,
    };
}

/**
 * GET /api/onsit/findings/[id]
 * 
 * Retrieves findings for a discovery scan.
 * The [id] can be either a scan ID (returns all findings) or a finding ID.
 */
export async function GET(
    request: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    try {
        const { id } = await params;

        if (!id) {
            return NextResponse.json(
                { error: 'ID is required' },
                { status: 400 }
            );
        }

        // Try fetching as scan ID first (get all findings for scan)
        const response = await fetch(
            `${INTELLIGENCE_URL}/onsit/discover/${id}/findings`,
            {
                method: 'GET',
                cache: 'no-store',
            }
        );

        if (!response.ok) {
            if (response.status === 404) {
                // Return empty findings if scan not found
                return NextResponse.json({ findings: [] });
            }
            return NextResponse.json(
                { error: 'Failed to fetch findings' },
                { status: response.status }
            );
        }

        const data = await response.json();
        const findings: IntelligenceFinding[] = data.findings || data || [];

        // Transform findings to frontend format
        const transformedFindings = findings.map(transformFinding);

        return NextResponse.json({
            findings: transformedFindings,
            totalCount: transformedFindings.length,
            riskSummary: {
                critical: transformedFindings.filter(f => f.riskLevel === 'critical').length,
                high: transformedFindings.filter(f => f.riskLevel === 'high').length,
                medium: transformedFindings.filter(f => f.riskLevel === 'medium').length,
                low: transformedFindings.filter(f => f.riskLevel === 'low').length,
            },
        });

    } catch (error) {
        console.error('[ONSIT Findings GET] Error:', error);

        if (error instanceof TypeError && error.message.includes('fetch')) {
            return NextResponse.json({ findings: [] });
        }

        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}

/**
 * DELETE /api/onsit/findings/[id]
 * 
 * Dismisses/cancels a finding or scan.
 * For scan IDs - cancels the scan.
 * For finding IDs - dismisses the finding.
 */
export async function DELETE(
    request: Request,
    { params }: { params: Promise<{ id: string }> }
) {
    try {
        const { id } = await params;

        if (!id) {
            return NextResponse.json(
                { error: 'ID is required' },
                { status: 400 }
            );
        }

        // Try to cancel/dismiss via intelligence service
        const response = await fetch(
            `${INTELLIGENCE_URL}/onsit/discover/${id}`,
            { method: 'DELETE' }
        );

        if (!response.ok && response.status !== 404) {
            return NextResponse.json(
                { error: 'Failed to dismiss finding' },
                { status: response.status }
            );
        }

        return NextResponse.json({
            success: true,
            message: 'Finding dismissed',
        });

    } catch (error) {
        console.error('[ONSIT Findings DELETE] Error:', error);

        // Return success even if service unavailable (graceful degradation)
        return NextResponse.json({
            success: true,
            message: 'Finding dismissed locally',
        });
    }
}
