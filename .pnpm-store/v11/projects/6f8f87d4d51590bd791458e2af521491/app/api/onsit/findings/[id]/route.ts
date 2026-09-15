/**
 * ONSIT Findings API Route
 * 
 * Retrieves and manages findings from ONSIT discovery scans.
 * Supports GET (retrieve findings) and DELETE (dismiss findings).
 * 
 * @see https://github.com/reconurge/flowsint - Entity types
 */

import { NextResponse, NextRequest } from 'next/server';
import { createHash } from 'node:crypto';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const INTELLIGENCE_URL = process.env.INTELLIGENCE_SERVICE_URL || 'http://localhost:8000';

/**
 * Intelligence service finding format
 */
interface IntelligenceFinding {
    id?: string;
    type?: string;
    value?: string;
    label?: string;
    source?: string | null;
    enricher?: string;
    confidence?: number;
    risk_level?: 'low' | 'medium' | 'high' | 'critical';
    metadata?: Record<string, unknown>;
    discovered_at?: string;
    data?: Record<string, unknown>;
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
    sourcePlatform: string;
    sourceUrl?: string;
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
        social_profile: () => `Social media profile discovered`,
        breach_record: () => `Found in data breach`,
        domain: (v) => `Domain ${v} analyzed`,
        ip: (v) => `IP address ${v} associated`,
        phone: (v) => `Phone number ${v} found`,
        website: (v) => `Website ${v} crawled`,
        credential: () => `Credential exposure detected`,
        document: () => `Public document found`,
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

function normalizeFindingType(type: string): string {
    const aliases: Record<string, string> = {
        SocialAccount: 'SocialProfile',
        social_profile: 'SocialProfile',
        Breach: 'BreachRecord',
        Leak: 'BreachRecord',
        breach_record: 'BreachRecord',
        File: 'PublicDocument',
        Document: 'PublicDocument',
        document: 'PublicDocument',
        Wallet: 'CryptoWallet',
        Finding: 'Generic',
    };
    const normalized = aliases[type] || type;
    const supported = new Set([
        'SocialProfile', 'BreachRecord', 'PublicDocument', 'CryptoWallet',
        'Credential', 'Domain', 'IP', 'Username', 'Email', 'Generic',
    ]);
    return supported.has(normalized) ? normalized : 'Generic';
}

/**
 * Transform intelligence finding to frontend format
 */
function transformFinding(finding: IntelligenceFinding): Finding {
    const data = finding.data || {};
    const rawType = String(data.finding_type || finding.type || 'Generic');
    const type = normalizeFindingType(rawType);
    const value = String(data.value || finding.value || finding.label || 'Untitled finding');
    const sourcePlatform = String(finding.source || finding.enricher || data.source || 'Unknown provider');
    const confidenceValue = Number(data.confidence ?? finding.confidence ?? 0);
    const confidence = Number.isFinite(confidenceValue)
        ? Math.min(1, Math.max(0, confidenceValue))
        : 0;
    const discoveredAt = String(data.discovered_at || finding.discovered_at || new Date().toISOString());
    const risk = String(data.risk_level || finding.risk_level || '').toLowerCase();
    const riskLevel = ['low', 'medium', 'high', 'critical'].includes(risk)
        ? risk as Finding['riskLevel']
        : inferRiskLevel(rawType, sourcePlatform.toLowerCase());
    const sourceUrl = typeof data.url === 'string'
        ? data.url
        : finding.evidence?.find(item => item.url)?.url;
    const id = finding.id || `onsit-${createHash('sha256')
        .update(`${rawType}\0${value}\0${sourcePlatform}\0${discoveredAt}`)
        .digest('hex')
        .slice(0, 24)}`;

    return {
        id,
        type,
        title: finding.label || value,
        description: getEntityDescription(rawType, value),
        sourcePlatform,
        sourceUrl,
        riskLevel,
        confidence,
        metadata: { ...data, ...(finding.metadata || {}) },
        discoveredAt,
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
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { id } = await params;

        if (!id) {
            return NextResponse.json(
                { error: 'ID is required' },
                { status: 400 }
            );
        }

        // Try fetching as scan ID first (get all findings for scan)
        const target = `${INTELLIGENCE_URL}/onsit/discover/${id}/findings`;
        const response = await fetch(
            target,
            {
                method: 'GET',
                headers: intelligenceAuthorityHeaders(authority.profileId, target, 'GET'),
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
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { id } = await params;

        if (!id) {
            return NextResponse.json(
                { error: 'ID is required' },
                { status: 400 }
            );
        }

        // Try to cancel/dismiss via intelligence service
        const target = `${INTELLIGENCE_URL}/onsit/discover/${id}`;
        const response = await fetch(
            target,
            { method: 'DELETE', headers: intelligenceAuthorityHeaders(authority.profileId, target, 'DELETE') }
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
