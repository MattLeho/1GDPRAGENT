'use client';

import { Card, CardContent } from '@/components/ui/card';
import { AlertCircle, CheckCircle2, Clock, FileArchive, FileText, Inbox } from 'lucide-react';

interface StatsOverviewProps {
    totalRequests: number;
    pendingActions: number;
    completedRequests: number;
    responsesReceived: number;
    receivedArtefactCount: number;
    failedWorkflows: number;
}

export function StatsOverview(props: StatsOverviewProps) {
    const stats = [
        { title: 'Requests', value: props.totalRequests, detail: 'Profile-scoped records', icon: FileText, color: 'text-blue-600', background: 'bg-blue-100 dark:bg-blue-900/30' },
        { title: 'Local actions', value: props.pendingActions, detail: 'Action or review states', icon: Clock, color: 'text-orange-600', background: 'bg-orange-100 dark:bg-orange-900/30' },
        { title: 'Locally completed', value: props.completedRequests, detail: 'Workflow state only', icon: CheckCircle2, color: 'text-green-600', background: 'bg-green-100 dark:bg-green-900/30' },
        { title: 'Responses recorded', value: props.responsesReceived, detail: 'Has response_received_at', icon: Inbox, color: 'text-cyan-600', background: 'bg-cyan-100 dark:bg-cyan-900/30' },
        { title: 'Received artefacts', value: props.receivedArtefactCount, detail: 'Stored received_data rows', icon: FileArchive, color: 'text-purple-600', background: 'bg-purple-100 dark:bg-purple-900/30' },
        { title: 'Failed workflows', value: props.failedWorkflows, detail: 'Recorded workflow failures', icon: AlertCircle, color: 'text-red-600', background: 'bg-red-100 dark:bg-red-900/30' },
    ];

    return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {stats.map((stat) => {
                const Icon = stat.icon;
                return (
                    <Card key={stat.title} className="group relative overflow-hidden hover:shadow-lg transition-all hover:-translate-y-0.5">
                        <div className={`absolute inset-0 ${stat.background} opacity-0 group-hover:opacity-100 transition-opacity`} />
                        <CardContent className="p-4 relative">
                            <div className={`inline-flex p-2 rounded-lg ${stat.background}`}>
                                <Icon className={`h-4 w-4 ${stat.color}`} aria-hidden="true" />
                            </div>
                            <p className="mt-3 text-2xl font-bold">{stat.value}</p>
                            <p className="text-xs font-medium text-muted-foreground">{stat.title}</p>
                            <p className="mt-2 text-xs text-muted-foreground">{stat.detail}</p>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
}
