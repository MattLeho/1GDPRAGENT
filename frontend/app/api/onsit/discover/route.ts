/**
 * ONSIT Discovery API Route
 * 
 * Proxies discovery requests to the Python intelligence service.
 * Implements the Flowsint orchestrator pattern for initiating OSINT scans.
 * 
 * @see https://github.com/reconurge/flowsint - Enricher architecture
 * @see https://github.com/s0md3v/Photon - Crawler patterns
 */

import { NextResponse } from 'next/server';

// Intelligence service URL - configurable for Docker vs local development
const INTELLIGENCE_URL = process.env.INTELLIGENCE_SERVICE_URL || 'http://localhost:8000';

/**
 * Request body interface matching the DiscoveryForm output
 */
interface DiscoverRequestBody {
    email?: string;
    usernames?: string[];
    phone?: string;
    domains?: string[];
    includeBreachCheck?: boolean;
    includeSocialScan?: boolean;
    depth?: 'quick' | 'standard' | 'deep';
    seeds?: string[];
    enrichers?: string[];
}

/**
 * Map scan depth to enricher configuration
 * Quick: Basic email/username only
 * Standard: Full platform + breach
 * Deep: All enrichers including domain intel
 */
function getEnrichersForDepth(depth: string, options: DiscoverRequestBody): string[] {
    const enrichers: string[] = [];

    // Always include email if provided
    if (options.email) enrichers.push('email');

    // Always include username for username searches
    if (options.usernames?.length) enrichers.push('username');

    // Breach check (configurable)
    if (options.includeBreachCheck !== false) {
        enrichers.push('breach');
    }

    // Social scan (configurable)
    if (options.includeSocialScan !== false && depth !== 'quick') {
        enrichers.push('social');
    }

    // Domain enrichers for standard+ depth
    if (depth !== 'quick') {
        if (options.domains?.length) {
            enrichers.push('domain', 'dns', 'whois');
        }
    }

    // Deep scan adds all available enrichers
    if (depth === 'deep') {
        enrichers.push('subdomain', 'technology', 'crawler');
    }

    return [...new Set(enrichers)]; // Deduplicate
}

/**
 * Build seed list from form data
 * Seeds are the initial entities to discover from
 */
function buildSeeds(data: DiscoverRequestBody): string[] {
    const seeds: string[] = [];

    if (data.email) seeds.push(data.email);
    if (data.usernames) seeds.push(...data.usernames);
    if (data.phone) seeds.push(data.phone);
    if (data.domains) seeds.push(...data.domains);
    if (data.seeds) seeds.push(...data.seeds);

    return seeds.filter(Boolean);
}

/**
 * POST /api/onsit/discover
 * 
 * Initiates an ONSIT discovery scan. The scan runs asynchronously
 * and the client should poll /api/onsit/status/[taskId] for updates.
 */
export async function POST(request: Request) {
    try {
        const body: DiscoverRequestBody = await request.json();

        // Build seeds from form data
        const seeds = buildSeeds(body);

        if (seeds.length === 0) {
            return NextResponse.json(
                { error: 'At least one identity (email, username, phone, or domain) is required' },
                { status: 400 }
            );
        }

        // Map depth to enrichers
        const enrichers = body.enrichers || getEnrichersForDepth(body.depth || 'standard', body);

        // Forward to intelligence service
        const response = await fetch(`${INTELLIGENCE_URL}/onsit/discover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                seeds,
                enrichers,
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('[ONSIT Discover] Intelligence service error:', errorText);
            return NextResponse.json(
                { error: 'Failed to start discovery', details: errorText },
                { status: response.status }
            );
        }

        const data = await response.json();

        // Transform response to match frontend expectations
        return NextResponse.json({
            taskId: data.scan_id,
            status: data.status,
            message: data.message || 'Discovery started',
        });

    } catch (error) {
        console.error('[ONSIT Discover] Error:', error);

        // Check if it's a connection error (service unavailable)
        if (error instanceof TypeError && error.message.includes('fetch')) {
            return NextResponse.json(
                { error: 'Intelligence service unavailable', details: 'Could not connect to the discovery service' },
                { status: 503 }
            );
        }

        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
