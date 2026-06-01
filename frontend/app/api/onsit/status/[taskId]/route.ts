/**
 * ONSIT Discovery Status API Route
 * 
 * Polls the intelligence service for discovery scan status.
 * Returns progress updates including step-by-step status.
 * 
 * @see https://github.com/reconurge/flowsint - Orchestrator patterns
 */

import { NextResponse } from 'next/server';

const INTELLIGENCE_URL = process.env.INTELLIGENCE_SERVICE_URL || 'http://localhost:8000';

/**
 * Intelligence service status response
 */
interface IntelligenceStatusResponse {
    scan_id: string;
    status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
    progress?: number;
    current_step?: string;
    steps?: Array<{
        id: string;
        name: string;
        status: string;
        started_at?: string;
        completed_at?: string;
        error?: string;
        findings_count?: number;
    }>;
    started_at?: string;
    completed_at?: string;
    error?: string;
    findings_count?: number;
}

/**
 * Frontend-friendly status response
 */
interface DiscoveryProgressResponse {
    taskId: string;
    status: 'queued' | 'processing' | 'completed' | 'failed';
    progress: number;
    currentStep: string;
    steps: Array<{
        id: string;
        name: string;
        description: string;
        status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
        startedAt?: string;
        completedAt?: string;
        error?: string;
        findingsCount?: number;
    }>;
    startedAt: string;
    estimatedTimeRemaining?: number;
    error?: string;
}

/**
 * Map intelligence service status to frontend status
 */
function mapStatus(status: string): 'queued' | 'processing' | 'completed' | 'failed' {
    switch (status) {
        case 'queued':
            return 'queued';
        case 'running':
            return 'processing';
        case 'completed':
            return 'completed';
        case 'failed':
        case 'cancelled':
            return 'failed';
        default:
            return 'processing';
    }
}

/**
 * Map step status to frontend step status
 */
function mapStepStatus(status: string): 'pending' | 'running' | 'completed' | 'failed' | 'skipped' {
    switch (status.toLowerCase()) {
        case 'pending':
        case 'queued':
            return 'pending';
        case 'running':
        case 'in_progress':
            return 'running';
        case 'completed':
        case 'done':
        case 'success':
            return 'completed';
        case 'failed':
        case 'error':
            return 'failed';
        case 'skipped':
            return 'skipped';
        default:
            return 'pending';
    }
}

/**
 * Step descriptions for UI display
 */
const stepDescriptions: Record<string, string> = {
    init: 'Setting up discovery job',
    email: 'Checking email addresses',
    username: 'Searching 500+ platforms',
    breach: 'Checking data breaches',
    social: 'Finding social profiles',
    domain: 'Analyzing domains',
    dns: 'Resolving DNS records',
    whois: 'Looking up domain registration',
    subdomain: 'Enumerating subdomains',
    technology: 'Detecting technologies',
    crawler: 'Crawling web pages',
    compile: 'Building graph',
};

/**
 * GET /api/onsit/status/[taskId]
 * 
 * Returns the current status of a discovery scan.
 */
export async function GET(
    request: Request,
    { params }: { params: Promise<{ taskId: string }> }
) {
    try {
        const { taskId } = await params;

        if (!taskId) {
            return NextResponse.json(
                { error: 'Task ID is required' },
                { status: 400 }
            );
        }

        const response = await fetch(
            `${INTELLIGENCE_URL}/onsit/discover/${taskId}`,
            {
                method: 'GET',
                // Prevent caching for real-time updates
                cache: 'no-store',
            }
        );

        if (!response.ok) {
            if (response.status === 404) {
                return NextResponse.json(
                    { error: 'Scan not found' },
                    { status: 404 }
                );
            }
            return NextResponse.json(
                { error: 'Failed to fetch scan status' },
                { status: response.status }
            );
        }

        const data: IntelligenceStatusResponse = await response.json();

        // Transform to frontend format
        const progressResponse: DiscoveryProgressResponse = {
            taskId: data.scan_id,
            status: mapStatus(data.status),
            progress: data.progress || 0,
            currentStep: data.current_step || 'Initializing...',
            steps: (data.steps || []).map(step => ({
                id: step.id,
                name: step.name,
                description: stepDescriptions[step.id] || step.name,
                status: mapStepStatus(step.status),
                startedAt: step.started_at,
                completedAt: step.completed_at,
                error: step.error,
                findingsCount: step.findings_count,
            })),
            startedAt: data.started_at || new Date().toISOString(),
            error: data.error,
        };

        return NextResponse.json(progressResponse);

    } catch (error) {
        console.error('[ONSIT Status] Error:', error);

        if (error instanceof TypeError && error.message.includes('fetch')) {
            return NextResponse.json(
                { error: 'Intelligence service unavailable' },
                { status: 503 }
            );
        }

        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
