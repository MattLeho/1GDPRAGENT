'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Bot, Clock, Activity, Play, RefreshCw, Calendar, Mail, Shield, Database, FileSearch, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface Agent {
    id: string;
    name: string;
    description: string;
    status: 'idle' | 'running' | 'error';
    lastRun?: Date;
    schedule?: string;
    apiEndpoint: string;
    prerequisites: () => Promise<{ enabled: boolean; reason?: string }>;
}

const SCHEDULE_OPTIONS = [
    { value: 'manual', label: 'Manual' },
    { value: '1h', label: 'Every hour' },
    { value: '6h', label: 'Every 6 hours' },
    { value: '12h', label: 'Every 12 hours' },
    { value: '24h', label: 'Daily' },
    { value: '168h', label: 'Weekly' },
];

// Check if email is connected
async function checkEmailConnected() {
    try {
        const res = await fetch('/api/settings/n8n-webhooks');
        const data = await res.json();
        const hasEmail = data.webhooks?.some((w: any) => w.description?.includes('email') || w.description?.includes('IMAP'));
        return { enabled: hasEmail, reason: hasEmail ? undefined : 'Email not configured in Settings' };
    } catch {
        return { enabled: false, reason: 'Failed to check email configuration' };
    }
}

// Always enabled
async function alwaysEnabled() {
    return { enabled: true };
}

export function AgentManager() {
    const [agents, setAgents] = useState<Agent[]>([
        {
            id: 'policy-analyzer',
            name: 'Policy Analyzer',
            description: 'Scans company privacy policies',
            status: 'idle',
            schedule: 'manual',
            apiEndpoint: '/api/gdpr-agent/analyze-policy',
            prerequisites: alwaysEnabled,
        },
        {
            id: 'inbox-monitor',
            name: 'Inbox Monitor',
            description: 'Monitors for GDPR responses',
            status: 'idle',
            schedule: '6h',
            apiEndpoint: '/api/n8n/test-imap',
            prerequisites: checkEmailConnected,
        },
        {
            id: 'kg-ingestor',
            name: 'Graph Enhancer',
            description: 'Updates knowledge graph',
            status: 'idle',
            schedule: 'manual',
            apiEndpoint: '/api/graph/stats',
            prerequisites: alwaysEnabled,
        },
        {
            id: 'databroker-scanner',
            name: 'Databroker Scanner',
            description: 'Scans data brokers',
            status: 'idle',
            schedule: '24h',
            apiEndpoint: '/api/onsit/discover',
            prerequisites: alwaysEnabled,
        },
        {
            id: 'report-generator',
            name: 'Report Generator',
            description: 'Creates privacy reports',
            status: 'idle',
            schedule: 'manual',
            apiEndpoint: '/api/upload',
            prerequisites: alwaysEnabled,
        },
    ]);

    const [pulseIndex, setPulseIndex] = useState(0);
    const [prerequisiteStatus, setPrerequisiteStatus] = useState<Record<string, { enabled: boolean; reason?: string }>>({});

    // Check prerequisites on mount
    useEffect(() => {
        async function checkPrereqs() {
            const statuses: Record<string, { enabled: boolean; reason?: string }> = {};
            for (const agent of agents) {
                statuses[agent.id] = await agent.prerequisites();
            }
            setPrerequisiteStatus(statuses);
        }
        checkPrereqs();
    }, []);

    useEffect(() => {
        const interval = setInterval(() => {
            setPulseIndex((prev) => (prev + 1) % agents.length);
        }, 2000);
        return () => clearInterval(interval);
    }, [agents.length]);

    const triggerAgent = async (agentId: string) => {
        const agent = agents.find(a => a.id === agentId);
        if (!agent) return;

        // Check prerequisites
        const prereq = await agent.prerequisites();
        if (!prereq.enabled) {
            toast.error(`Cannot run ${agent.name}`, {
                description: prereq.reason || 'Prerequisites not met'
            });
            return;
        }

        setAgents((prev) =>
            prev.map((a) =>
                a.id === agentId ? { ...a, status: 'running' as const } : a
            )
        );

        try {
            // Call the actual API endpoint
            const res = await fetch(agent.apiEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: 'agent_manager' }),
            });

            if (!res.ok) {
                throw new Error('Agent execution failed');
            }

            toast.success(`${agent.name} completed successfully`);
            setAgents((prev) =>
                prev.map((a) =>
                    a.id === agentId
                        ? { ...a, status: 'idle' as const, lastRun: new Date() }
                        : a
                )
            );
        } catch (error) {
            toast.error(`${agent.name} failed`, {
                description: error instanceof Error ? error.message : 'Unknown error'
            });
            setAgents((prev) =>
                prev.map((a) =>
                    a.id === agentId ? { ...a, status: 'error' as const } : a
                )
            );
        }
    };

    const setSchedule = (agentId: string, schedule: string) => {
        setAgents((prev) =>
            prev.map((a) => (a.id === agentId ? { ...a, schedule } : a))
        );
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'running': return 'bg-green-500';
            case 'error': return 'bg-red-500';
            default: return 'bg-zinc-400 dark:bg-zinc-600';
        }
    };

    const formatLastRun = (date?: Date) => {
        if (!date) return 'Never';
        const diff = Date.now() - date.getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'Just now';
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        if (hours < 24) return `${hours}h ago`;
        return date.toLocaleDateString();
    };

    const runningCount = agents.filter((a) => a.status === 'running').length;
    const getAgentIcon = (id: string) => {
        switch (id) {
            case 'policy-analyzer': return FileSearch;
            case 'inbox-monitor': return Mail;
            case 'kg-ingestor': return Database;
            case 'databroker-scanner': return Shield;
            case 'report-generator': return FileText;
            default: return Bot;
        }
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Bot className="h-4 w-4 text-indigo-500" />
                        Agent Manager
                    </CardTitle>
                    <Badge variant={runningCount > 0 ? 'default' : 'secondary'} className="text-xs">
                        {runningCount > 0 ? (
                            <>
                                <Activity className="h-3 w-3 mr-1 animate-pulse" />
                                {runningCount} Active
                            </>
                        ) : (
                            'All Idle'
                        )}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-2">
                {agents.map((agent, idx) => {
                    const AgentIcon = getAgentIcon(agent.id);
                    const isEnabled = prerequisiteStatus[agent.id]?.enabled !== false;

                    return (
                        <div
                            key={agent.id}
                            className={cn(
                                'flex items-center justify-between p-2 rounded-lg border transition-all duration-300',
                                agent.status === 'running'
                                    ? 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30 animate-pulse'
                                    : 'border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900',
                                !isEnabled && 'opacity-60'
                            )}
                        >
                            <div className="flex items-center gap-2 min-w-0">
                                <div className="relative">
                                    <AgentIcon className={cn(
                                        "h-4 w-4 transition-transform",
                                        agent.status === 'running' && "animate-bounce text-green-500"
                                    )} />
                                    <span
                                        className={cn(
                                            'absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full block',
                                            getStatusColor(agent.status),
                                            agent.status === 'running' && 'animate-pulse'
                                        )}
                                    />
                                    {idx === pulseIndex && agent.status === 'idle' && isEnabled && (
                                        <span className="absolute inset-0 h-4 w-4 rounded-full bg-indigo-400 animate-ping opacity-50" />
                                    )}
                                </div>
                                <div className="min-w-0">
                                    <p className="text-xs font-medium truncate">{agent.name}</p>
                                    <p className="text-[10px] text-muted-foreground flex items-center gap-1">
                                        <Clock className="h-2.5 w-2.5" />
                                        {formatLastRun(agent.lastRun)}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-1">
                                <Select
                                    value={agent.schedule}
                                    onValueChange={(v) => setSchedule(agent.id, v)}
                                >
                                    <SelectTrigger className="h-6 w-[70px] text-[10px] px-1">
                                        <Calendar className="h-2.5 w-2.5 mr-0.5" />
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {SCHEDULE_OPTIONS.map((opt) => (
                                            <SelectItem key={opt.value} value={opt.value} className="text-xs">
                                                {opt.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Button
                                    size="sm"
                                    variant={agent.status === 'running' ? 'secondary' : 'outline'}
                                    className={cn(
                                        "h-6 w-6 p-0",
                                        !isEnabled && "cursor-not-allowed opacity-50"
                                    )}
                                    onClick={() => triggerAgent(agent.id)}
                                    disabled={agent.status === 'running' || !isEnabled}
                                    title={!isEnabled ? prerequisiteStatus[agent.id]?.reason : undefined}
                                >
                                    {agent.status === 'running' ? (
                                        <RefreshCw className="h-3 w-3 animate-spin" />
                                    ) : (
                                        <Play className={cn("h-3 w-3", !isEnabled && "opacity-30")} />
                                    )}
                                </Button>
                            </div>
                        </div>
                    );
                })}
            </CardContent>
        </Card>
    );
}
