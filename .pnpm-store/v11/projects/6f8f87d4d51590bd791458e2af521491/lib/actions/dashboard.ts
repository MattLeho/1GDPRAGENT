'use server';

import { requireServerSessionAuthority } from '@/lib/api-session';
import { runCypher } from '@/lib/graph';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

export interface DashboardStats {
    totalRequests: number;
    pendingActions: number;
    completedRequests: number;
    receivedArtefactCount: number;
    receivedArtefactVolumeGB: number;
    volumeByCompany: { name: string; value: number; color: string }[];
}

export interface EnhancedDashboardStats extends DashboardStats {
    responsesReceived: number;
    knownUpcomingDeadlines: number;
    unknownDeadlines: number;
    failedWorkflows: number;
    requestsByState: { state: string; count: number }[];
    requestsTimeline: { date: string; requests: number; completed: number }[];
    requestTypeDistribution: { type: string; count: number; color: string }[];
    receivedArtefactsByCompany: { name: string; artefactCount: number; volumeGB: number }[];
    responseDurationScreening: {
        sampleCount: number;
        averageDays: number | null;
        fastestDays: number | null;
    };
    graphNodes: number;
    graphConnections: number;
    isDbAvailable: boolean;
}

const COLORS = {
    primary: '#6366f1',
    success: '#22c55e',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#06b6d4',
    purple: '#8b5cf6',
    pink: '#ec4899',
    orange: '#f97316',
};

function integer(value: string | undefined): number {
    return Number.parseInt(value ?? '0', 10) || 0;
}

export async function getEnhancedDashboardStats(): Promise<EnhancedDashboardStats> {
    const { profileId } = await requireServerSessionAuthority();
    const projection = await requests.dashboard(profileId);
    const counts = projection.counts;
    const artefactCount = integer(projection.artefacts[0]?.overall_artefact_count);
    const totalArtefactMb = Number.parseFloat(projection.artefacts[0]?.overall_total_mb ?? '0') || 0;
    const receivedArtefactsByCompany = projection.artefacts.map((row) => ({
        name: row.company_name,
        artefactCount: integer(row.artefact_count),
        volumeGB: Number(((Number.parseFloat(row.total_mb) || 0) / 1024).toFixed(2)),
    }));
    const duration = projection.duration;
    const sampleCount = integer(duration?.sample_count);

    return {
        totalRequests: integer(counts?.total),
        pendingActions: integer(counts?.pending),
        completedRequests: integer(counts?.completed),
        responsesReceived: integer(counts?.responses_received),
        knownUpcomingDeadlines: integer(counts?.known_upcoming_deadlines),
        unknownDeadlines: integer(counts?.unknown_deadlines),
        failedWorkflows: integer(projection.failedWorkflows),
        receivedArtefactCount: artefactCount,
        receivedArtefactVolumeGB: Number((totalArtefactMb / 1024).toFixed(2)),
        volumeByCompany: receivedArtefactsByCompany.map((row, index) => ({
            name: row.name,
            value: row.volumeGB,
            color: Object.values(COLORS)[index % Object.keys(COLORS).length],
        })),
        receivedArtefactsByCompany,
        requestsByState: projection.states.map((row) => ({ state: row.state, count: integer(row.count) })),
        requestsTimeline: projection.timeline.map((row) => ({
            date: new Date(row.date).toLocaleDateString('en-US', { weekday: 'short' }),
            requests: integer(row.requests),
            completed: integer(row.completed),
        })),
        requestTypeDistribution: [
            { type: 'Access', count: integer(counts?.access_count), color: COLORS.primary },
            { type: 'Deletion', count: integer(counts?.deletion_count), color: COLORS.danger },
        ],
        responseDurationScreening: {
            sampleCount,
            averageDays: sampleCount > 0 && duration?.average_days !== null
                ? Number(Number.parseFloat(duration?.average_days ?? '0').toFixed(1))
                : null,
            fastestDays: sampleCount > 0 && duration?.fastest_days !== null
                ? Number(Number.parseFloat(duration?.fastest_days ?? '0').toFixed(1))
                : null,
        },
        graphNodes: await getGraphNodeCount(profileId),
        graphConnections: await getGraphLinkCount(profileId),
        isDbAvailable: true,
    };
}

export async function getDashboardStats(): Promise<DashboardStats> {
    const enhanced = await getEnhancedDashboardStats();
    return {
        totalRequests: enhanced.totalRequests,
        pendingActions: enhanced.pendingActions,
        completedRequests: enhanced.completedRequests,
        receivedArtefactCount: enhanced.receivedArtefactCount,
        receivedArtefactVolumeGB: enhanced.receivedArtefactVolumeGB,
        volumeByCompany: enhanced.volumeByCompany,
    };
}

async function getGraphNodeCount(profileId: string): Promise<number> {
    try {
        const result = await runCypher(`
            MATCH (n:GraphNode)-[owned]-(:GraphNode)
            WHERE owned.profile_id = $profileId
              AND coalesce(owned.profile_retired, false) = false
            RETURN count(DISTINCT n) as count
        `, { profileId });
        const record = result[0] as { get: (key: string) => { low?: number } | number };
        const count = record?.get?.('count');
        return typeof count === 'object' && count?.low !== undefined
            ? count.low
            : typeof count === 'number' ? count : 0;
    } catch {
        return 0;
    }
}

async function getGraphLinkCount(profileId: string): Promise<number> {
    try {
        const result = await runCypher(`
            MATCH (:GraphNode)-[r]->(:GraphNode)
            WHERE r.profile_id = $profileId
              AND coalesce(r.profile_retired, false) = false
              AND coalesce(r.epistemic_basis, '') <> 'model_hypothesis'
              AND (r.inferred IS NULL OR r.inferred = false)
            RETURN count(r) as count
        `, { profileId });
        const record = result[0] as { get: (key: string) => { low?: number } | number };
        const count = record?.get?.('count');
        return typeof count === 'object' && count?.low !== undefined
            ? count.low
            : typeof count === 'number' ? count : 0;
    } catch {
        return 0;
    }
}
