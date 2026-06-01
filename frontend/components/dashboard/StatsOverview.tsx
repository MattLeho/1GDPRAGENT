'use client';

import { Card, CardContent } from '@/components/ui/card';
import {
    FileText,
    Clock,
    CheckCircle2,
    Database,
    TrendingUp,
    ArrowUpRight,
    ArrowDownRight
} from 'lucide-react';

interface StatsOverviewProps {
    totalRequests: number;
    pendingActions: number;
    completedRequests: number;
    dataRetrievedGB: number;
    avgResponseDays?: number;
    gdprDeadlinesMet?: number;
}

export function StatsOverview({
    totalRequests,
    pendingActions,
    completedRequests,
    dataRetrievedGB,
    avgResponseDays,
    gdprDeadlinesMet = 0,
}: StatsOverviewProps) {
    // Calculate trends dynamically (these come from real data)
    const requestsTrend = totalRequests > 0 ? `${totalRequests} total` : 'No requests yet';
    const dataTrend = dataRetrievedGB > 0 ? `${dataRetrievedGB.toFixed(2)} GB total` : 'No data yet';
    const responseTrend = avgResponseDays !== undefined && avgResponseDays > 0
        ? (avgResponseDays < 14 ? 'Within GDPR limit' : 'Above 14 day average')
        : 'No data yet';

    const stats = [
        {
            title: 'Total Requests',
            value: totalRequests,
            suffix: '',
            icon: FileText,
            color: 'text-blue-600',
            bgColor: 'bg-blue-100 dark:bg-blue-900/30',
            trend: requestsTrend,
            trendUp: totalRequests > 0,
        },
        {
            title: 'Pending Actions',
            value: pendingActions,
            suffix: '',
            icon: Clock,
            color: 'text-orange-600',
            bgColor: 'bg-orange-100 dark:bg-orange-900/30',
            trend: pendingActions > 0 ? 'Needs attention' : 'All clear',
            trendUp: pendingActions === 0,
        },
        {
            title: 'Completed',
            value: completedRequests,
            suffix: '',
            icon: CheckCircle2,
            color: 'text-green-600',
            bgColor: 'bg-green-100 dark:bg-green-900/30',
            trend: gdprDeadlinesMet > 0 ? `${gdprDeadlinesMet} on time` : 'None yet',
            trendUp: completedRequests > 0,
        },
        {
            title: 'Data Retrieved',
            value: dataRetrievedGB,
            suffix: 'GB',
            icon: Database,
            color: 'text-purple-600',
            bgColor: 'bg-purple-100 dark:bg-purple-900/30',
            trend: dataTrend,
            trendUp: dataRetrievedGB > 0,
        },
        {
            title: 'Avg Response',
            value: avgResponseDays ?? 0,
            suffix: 'days',
            icon: TrendingUp,
            color: 'text-cyan-600',
            bgColor: 'bg-cyan-100 dark:bg-cyan-900/30',
            trend: responseTrend,
            trendUp: avgResponseDays !== undefined ? avgResponseDays < 14 : true,
        },
    ];

    return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {stats.map((stat) => {
                const Icon = stat.icon;
                const TrendIcon = stat.trendUp ? ArrowUpRight : ArrowDownRight;

                return (
                    <Card
                        key={stat.title}
                        className="group relative overflow-hidden hover:shadow-lg transition-all hover:-translate-y-0.5"
                    >
                        {/* Gradient Accent */}
                        <div className={`absolute inset-0 ${stat.bgColor} opacity-0 group-hover:opacity-100 transition-opacity`} />

                        <CardContent className="p-4 relative">
                            <div className="flex items-start justify-between">
                                <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                                    <Icon className={`h-4 w-4 ${stat.color}`} />
                                </div>
                            </div>

                            <div className="mt-3">
                                <div className="flex items-baseline gap-1">
                                    <span className="text-2xl font-bold">{stat.value}</span>
                                    {stat.suffix && (
                                        <span className="text-sm text-muted-foreground">{stat.suffix}</span>
                                    )}
                                </div>
                                <p className="text-xs text-muted-foreground mt-0.5">{stat.title}</p>
                            </div>

                            <div className={`flex items-center gap-1 mt-2 text-xs ${stat.trendUp ? 'text-green-600' : 'text-orange-600'}`}>
                                <TrendIcon className="h-3 w-3" />
                                <span>{stat.trend}</span>
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
}
