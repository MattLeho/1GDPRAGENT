'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
    FileText,
    Mail,
    Download,
    CheckCircle2,
    Bot,
    Building2
} from 'lucide-react';

interface ActivityItem {
    id: string;
    type: 'request_created' | 'response_received' | 'data_retrieved' | 'request_completed';
    message: string;
    timestamp: Date;
    companyName?: string;
}

interface ActivityFeedProps {
    items: ActivityItem[];
}

export function ActivityFeed({ items }: ActivityFeedProps) {
    const getTypeConfig = (type: ActivityItem['type']) => {
        switch (type) {
            case 'request_created':
                return {
                    icon: FileText,
                    color: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
                    label: 'Request',
                };
            case 'response_received':
                return {
                    icon: Mail,
                    color: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
                    label: 'Response',
                };
            case 'data_retrieved':
                return {
                    icon: Download,
                    color: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
                    label: 'Data',
                };
            case 'request_completed':
                return {
                    icon: CheckCircle2,
                    color: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
                    label: 'Complete',
                };
            default:
                return {
                    icon: Bot,
                    color: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
                    label: 'Update',
                };
        }
    };

    const formatTime = (date: Date | string) => {
        const d = new Date(date);
        const now = new Date();
        const diffMs = now.getTime() - d.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays === 1) return 'Yesterday';
        return `${diffDays}d ago`;
    };

    return (
        <Card className="h-full">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center justify-between">
                    Recent Activity
                    <Badge variant="outline" className="text-xs font-normal">
                        Live
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <ScrollArea className="h-[280px] px-6">
                    <div className="space-y-4 py-2">
                        {items.map((item, idx) => {
                            const config = getTypeConfig(item.type);
                            const Icon = config.icon;

                            return (
                                <div key={item.id} className="flex gap-3">
                                    {/* Timeline Line */}
                                    <div className="flex flex-col items-center">
                                        <div className={`p-2 rounded-lg ${config.color}`}>
                                            <Icon className="h-4 w-4" />
                                        </div>
                                        {idx < items.length - 1 && (
                                            <div className="w-px h-full bg-zinc-200 dark:bg-zinc-800 my-1" />
                                        )}
                                    </div>

                                    {/* Content */}
                                    <div className="flex-1 pb-4">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                {item.companyName && (
                                                    <span className="text-sm font-medium">{item.companyName}</span>
                                                )}
                                                <Badge variant="outline" className="text-[10px] uppercase">
                                                    {config.label}
                                                </Badge>
                                            </div>
                                            <span className="text-xs text-muted-foreground">
                                                {formatTime(item.timestamp)}
                                            </span>
                                        </div>
                                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                                            {item.message}
                                        </p>
                                    </div>
                                </div>
                            );
                        })}

                        {items.length === 0 && (
                            <div className="text-center py-12 text-muted-foreground text-sm">
                                <Bot className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                No recent activity
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </CardContent>
        </Card>
    );
}
