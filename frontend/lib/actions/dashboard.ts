'use server';

import { safeQuery } from '@/lib/db';
import { runCypher } from '@/lib/graph';

export interface DashboardStats {
    totalRequests: number;
    pendingActions: number;
    completedRequests: number;
    dataRetrievedGB: number;
    volumeByCompany: { name: string; value: number; color: string }[];
}

export interface EnhancedDashboardStats extends DashboardStats {
    // Privacy Score (0-100)
    privacyScore: number;
    privacyScoreBreakdown: {
        dataMinimization: number;
        companyCompliance: number;
        requestSuccess: number;
    };

    // Timeline data (requests over time)
    requestsTimeline: { date: string; requests: number; completed: number }[];

    // Request type distribution
    requestTypeDistribution: { type: string; count: number; color: string }[];

    // Companies with most data
    topDataHolders: { name: string; dataPoints: number; riskLevel: 'low' | 'medium' | 'high' }[];

    // Response time stats
    avgResponseDays: number;
    fastestResponseDays: number;

    // Recent activity
    recentActivity: {
        id: string;
        type: 'request_created' | 'response_received' | 'data_retrieved' | 'request_completed';
        message: string;
        timestamp: Date;
        companyName?: string;
    }[];

    // Compliance stats
    gdprDeadlinesMet: number;
    gdprDeadlinesMissed: number;

    // Graph stats
    graphNodes: number;
    graphConnections: number;

    // Database status
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

export async function getEnhancedDashboardStats(): Promise<EnhancedDashboardStats> {
    // Basic counts
    const countRes = await safeQuery<{
        total: string;
        pending: string;
        completed: string;
        access_count: string;
        deletion_count: string;
    }>(`
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status IN ('action_required', 'processing') THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN request_type LIKE '%access%' THEN 1 END) as access_count,
            COUNT(CASE WHEN request_type LIKE '%deletion%' THEN 1 END) as deletion_count
        FROM requests
    `);

    const isDbAvailable = !countRes.error;
    const counts = countRes.rows[0] || { total: '0', pending: '0', completed: '0', access_count: '0', deletion_count: '0' };

    // Volume by company (linked to requests)
    const volumeRes = await safeQuery<{ company_name: string; total_mb: string }>(`
        SELECT r.company_name, COALESCE(SUM(rd.file_size_mb), 0) as total_mb
        FROM requests r
        LEFT JOIN received_data rd ON r.id = rd.request_id
        GROUP BY r.company_name
        ORDER BY total_mb DESC
        LIMIT 5
    `);

    const volumeData = volumeRes.rows.map((row, idx) => ({
        name: row.company_name,
        value: parseFloat(row.total_mb) / 1024 || 0,
        color: Object.values(COLORS)[idx % Object.keys(COLORS).length],
    }));

    // Total data (ALL uploaded data, including unlinked)
    const totalDataRes = await safeQuery<{ total_mb: string }>(`
        SELECT COALESCE(SUM(file_size_mb), 0) as total_mb
        FROM received_data
    `);

    const totalGB = parseFloat(totalDataRes.rows[0]?.total_mb || '0') / 1024;

    // Timeline data (last 7 days)
    const timelineRes = await safeQuery<{ date: Date; requests: string; completed: string }>(`
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as requests,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
        FROM requests
        WHERE created_at >= NOW() - INTERVAL '7 days'
        GROUP BY DATE(created_at)
        ORDER BY date ASC
    `);

    // Fill in missing days
    const timeline: { date: string; requests: number; completed: number }[] = [];
    for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const dateStr = date.toISOString().split('T')[0];
        const existing = timelineRes.rows.find((r) =>
            r.date?.toISOString?.()?.split('T')[0] === dateStr
        );
        timeline.push({
            date: date.toLocaleDateString('en-US', { weekday: 'short' }),
            requests: existing ? parseInt(existing.requests) : 0,
            completed: existing ? parseInt(existing.completed) : 0,
        });
    }

    // Top data holders
    const holdersRes = await safeQuery<{ company_name: string; data_points: string }>(`
        SELECT company_name, COUNT(*) as data_points
        FROM requests
        GROUP BY company_name
        ORDER BY data_points DESC
        LIMIT 5
    `);

    const topDataHolders = holdersRes.rows.map((row) => ({
        name: row.company_name,
        dataPoints: parseInt(row.data_points),
        riskLevel: (parseInt(row.data_points) > 3 ? 'high' : parseInt(row.data_points) > 1 ? 'medium' : 'low') as 'low' | 'medium' | 'high',
    }));

    // Recent activity (from messages table)
    const activityRes = await safeQuery<{
        id: string;
        sender: string;
        content: string;
        timestamp: Date;
        company_name: string;
    }>(`
        SELECT m.id, m.sender, m.content, m.timestamp, r.company_name
        FROM messages m
        JOIN requests r ON m.request_id = r.id
        ORDER BY m.timestamp DESC
        LIMIT 5
    `);

    const recentActivity = activityRes.rows.map((row) => ({
        id: row.id,
        type: (row.sender === 'agent' ? 'request_created' :
            row.sender === 'company' ? 'response_received' : 'data_retrieved') as 'request_created' | 'response_received' | 'data_retrieved' | 'request_completed',
        message: row.content?.substring(0, 80) + (row.content?.length > 80 ? '...' : ''),
        timestamp: row.timestamp,
        companyName: row.company_name,
    }));

    // Calculate privacy score
    const total = parseInt(counts.total) || 1;
    const completed = parseInt(counts.completed);
    const successRate = (completed / total) * 100;
    const dataMinimization = Math.min(100, Math.max(0, 100 - (topDataHolders.length * 10)));
    const companyCompliance = successRate;
    const privacyScore = Math.round((dataMinimization * 0.3 + companyCompliance * 0.4 + successRate * 0.3));

    // Calculate actual response times from completed requests
    const responseTimeRes = await safeQuery<{
        avg_days: string;
        min_days: string;
        missed_deadlines: string;
    }>(`
        SELECT 
            COALESCE(AVG(
                EXTRACT(DAY FROM (
                    CASE WHEN status = 'completed' THEN updated_at ELSE NULL END - created_at
                ))
            ), 0) as avg_days,
            COALESCE(MIN(
                EXTRACT(DAY FROM (
                    CASE WHEN status = 'completed' THEN updated_at ELSE NULL END - created_at
                ))
            ), 0) as min_days,
            COUNT(
                CASE WHEN status = 'completed' 
                     AND EXTRACT(DAY FROM (updated_at - created_at)) > 30 
                     THEN 1 END
            ) as missed_deadlines
        FROM requests
        WHERE status = 'completed'
    `);

    const responseStats = responseTimeRes.rows[0] || { avg_days: '0', min_days: '0', missed_deadlines: '0' };
    const avgResponseDays = Math.round(parseFloat(responseStats.avg_days) || 0);
    const fastestResponseDays = Math.round(parseFloat(responseStats.min_days) || 0);
    const gdprDeadlinesMissed = parseInt(responseStats.missed_deadlines) || 0;

    return {
        totalRequests: parseInt(counts.total),
        pendingActions: parseInt(counts.pending),
        completedRequests: parseInt(counts.completed),
        dataRetrievedGB: parseFloat(totalGB.toFixed(2)),
        volumeByCompany: volumeData,

        privacyScore: Math.min(100, Math.max(0, privacyScore || 0)),
        privacyScoreBreakdown: {
            dataMinimization,
            companyCompliance,
            requestSuccess: successRate,
        },

        requestsTimeline: timeline,

        requestTypeDistribution: [
            { type: 'Access', count: parseInt(counts.access_count), color: COLORS.primary },
            { type: 'Deletion', count: parseInt(counts.deletion_count), color: COLORS.danger },
        ],

        topDataHolders,

        // Real calculated values - NO hardcoded data
        avgResponseDays,
        fastestResponseDays,

        recentActivity,

        gdprDeadlinesMet: completed,
        gdprDeadlinesMissed,

        // Fetch real graph stats from Neo4j
        graphNodes: await getGraphNodeCount(),
        graphConnections: await getGraphLinkCount(),

        isDbAvailable,
    };
}

// Keep the old function for backwards compatibility
export async function getDashboardStats(): Promise<DashboardStats> {
    const enhanced = await getEnhancedDashboardStats();
    return {
        totalRequests: enhanced.totalRequests,
        pendingActions: enhanced.pendingActions,
        completedRequests: enhanced.completedRequests,
        dataRetrievedGB: enhanced.dataRetrievedGB,
        volumeByCompany: enhanced.volumeByCompany,
    };
}

// Get real graph node count from Neo4j
async function getGraphNodeCount(): Promise<number> {
    try {
        const result = await runCypher('MATCH (n) RETURN count(n) as count');
        const record = result[0] as { get: (key: string) => { low?: number } | number };
        const count = record?.get?.('count');
        if (typeof count === 'object' && count?.low !== undefined) {
            return count.low;
        }
        return typeof count === 'number' ? count : 0;
    } catch {
        return 0;
    }
}

// Get real graph relationship count from Neo4j 
async function getGraphLinkCount(): Promise<number> {
    try {
        const result = await runCypher('MATCH ()-[r]->() RETURN count(r) as count');
        const record = result[0] as { get: (key: string) => { low?: number } | number };
        const count = record?.get?.('count');
        if (typeof count === 'object' && count?.low !== undefined) {
            return count.low;
        }
        return typeof count === 'number' ? count : 0;
    } catch {
        return 0;
    }
}
