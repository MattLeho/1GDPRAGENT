'use client';

import { protectedFetch as fetch, shouldSuppressProtectedRequestError } from '@/lib/api-client';

/**
 * ProgressTracker Component
 * 
 * Real-time progress display for ONSIT discovery jobs.
 * Uses polling mechanism to fetch status updates from the intelligence API.
 * 
 * Following Flowsint orchestrator patterns for job status display.
 */

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
    CheckCircle2,
    Circle,
    Loader2,
    XCircle,
    Clock,
    AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export interface DiscoveryStep {
    id: string;
    name: string;
    description: string;
    status: StepStatus;
    startedAt?: string;
    completedAt?: string;
    error?: string;
    findingsCount?: number;
}

export interface DiscoveryProgress {
    taskId: string;
    status: 'queued' | 'processing' | 'completed' | 'failed';
    progress: number;
    currentStep: string;
    steps: DiscoveryStep[];
    startedAt: string;
    estimatedTimeRemaining?: number;
    error?: string;
}

interface ProgressTrackerProps {
    taskId: string | null;
    onComplete?: (taskId: string) => void;
    onError?: (error: string) => void;
}

// =============================================================================
// Step Status Icons
// =============================================================================

const statusConfig: Record<StepStatus, {
    icon: React.ElementType;
    color: string;
    bgColor: string;
}> = {
    pending: {
        icon: Circle,
        color: 'text-zinc-400',
        bgColor: 'bg-zinc-100',
    },
    running: {
        icon: Loader2,
        color: 'text-blue-600',
        bgColor: 'bg-blue-100',
    },
    completed: {
        icon: CheckCircle2,
        color: 'text-green-600',
        bgColor: 'bg-green-100',
    },
    failed: {
        icon: XCircle,
        color: 'text-red-600',
        bgColor: 'bg-red-100',
    },
    skipped: {
        icon: Circle,
        color: 'text-zinc-300',
        bgColor: 'bg-zinc-50',
    },
};

// =============================================================================
// Component
// =============================================================================

export function ProgressTracker({
    taskId,
    onComplete,
    onError,
}: ProgressTrackerProps) {
    const [progress, setProgress] = useState<DiscoveryProgress | null>(null);
    const [elapsedTime, setElapsedTime] = useState(0);

    // Polling effect
    useEffect(() => {
        if (!taskId) {
            return;
        }
        const activeTaskId = taskId;

        let consecutiveFailures = 0;
        // Assigned after fetchStatus is defined so stopPolling can close over both handles.
        // eslint-disable-next-line prefer-const
        let intervalId: ReturnType<typeof setInterval>;
        // eslint-disable-next-line prefer-const
        let timerIntervalId: ReturnType<typeof setInterval>;

        const stopPolling = () => {
            clearInterval(intervalId);
            clearInterval(timerIntervalId);
        };

        async function fetchStatus() {
            try {
                const res = await fetch(`/api/onsit/status/${activeTaskId}`);
                if (!res.ok) {
                    const body = await res.json().catch(() => null) as { error?: string } | null;
                    throw new Error(body?.error || `Status service returned ${res.status}`);
                }
                consecutiveFailures = 0;
                const data: DiscoveryProgress = await res.json();
                setProgress(data);

                if (data.status === 'completed') {
                    stopPolling();
                    onComplete?.(activeTaskId);
                } else if (data.status === 'failed') {
                    stopPolling();
                    onError?.(data.error || 'Discovery failed');
                }
            } catch (e) {
                consecutiveFailures++;
                if (shouldSuppressProtectedRequestError(e)) {
                    stopPolling();
                    return;
                }
                console.error('Failed to fetch discovery status', e);
                if (consecutiveFailures >= 3) {
                    const error = 'Discovery status is unavailable after three attempts. Retry the discovery when the service is available.';
                    setProgress({
                        taskId: activeTaskId, status: 'failed', progress: 0, currentStep: 'Status unavailable',
                        steps: [], startedAt: new Date().toISOString(), error,
                    });
                    stopPolling();
                    onError?.(error);
                }
            }
        }

        // Poll every 3 seconds
        intervalId = setInterval(fetchStatus, 3000);

        // Timer for elapsed time
        const startTime = Date.now();
        timerIntervalId = setInterval(() => {
            setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
        }, 1000);

        // Initial fetch
        fetchStatus();

        return () => {
            clearInterval(intervalId);
            clearInterval(timerIntervalId);
        };
    }, [taskId, onComplete, onError]);

    // Format elapsed time
    const formatTime = (seconds: number): string => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // No task state
    if (!taskId) {
        return (
            <Card className="border-dashed">
                <CardContent className="py-8 text-center">
                    <p className="text-muted-foreground">
                        Start a discovery to track progress
                    </p>
                </CardContent>
            </Card>
        );
    }

    const current = progress?.taskId === taskId ? progress : null;
    const steps = current?.steps || [];
    const currentProgress = current?.progress ?? 0;
    const status = current?.status || 'queued';

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <CardTitle className="text-base">Discovery Progress</CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">
                            {current?.currentStep || 'Initializing...'}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge
                            variant={status === 'completed' ? 'default' : 'secondary'}
                            className={cn(
                                status === 'processing' && 'bg-blue-100 text-blue-700',
                                status === 'failed' && 'bg-red-100 text-red-700',
                                status === 'completed' && 'bg-green-100 text-green-700'
                            )}
                        >
                            {status === 'processing' && (
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            )}
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                        </Badge>
                        <span className="text-sm text-muted-foreground flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTime(elapsedTime)}
                        </span>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Progress Bar */}
                {steps.length > 0 ? <div className="space-y-2">
                    <Progress value={currentProgress} className="h-2" />
                    <p className="text-xs text-muted-foreground text-right">
                        {currentProgress}% complete
                    </p>
                </div> : (
                    <p className="text-sm text-muted-foreground">
                        Detailed provider steps are not available for this discovery. The status above comes directly from the discovery service.
                    </p>
                )}

                {/* Steps */}
                <div className="space-y-2">
                    {steps.map((step) => {
                        const config = statusConfig[step.status];
                        const Icon = config.icon;
                        const isRunning = step.status === 'running';

                        return (
                            <div
                                key={step.id}
                                className={cn(
                                    "flex items-center gap-3 p-2 rounded-lg transition-colors",
                                    isRunning && "bg-blue-50 dark:bg-blue-900/20",
                                    step.status === 'completed' && "opacity-75"
                                )}
                            >
                                <div className={cn(
                                    "p-1.5 rounded-full",
                                    config.bgColor
                                )}>
                                    <Icon
                                        className={cn(
                                            "h-4 w-4",
                                            config.color,
                                            isRunning && "animate-spin"
                                        )}
                                    />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium">{step.name}</p>
                                    <p className="text-xs text-muted-foreground truncate">
                                        {step.status === 'failed' ? (
                                            <span className="text-red-600">{step.error}</span>
                                        ) : (
                                            step.description
                                        )}
                                    </p>
                                </div>
                                {step.findingsCount !== undefined && step.findingsCount > 0 && (
                                    <Badge variant="secondary" className="text-xs">
                                        +{step.findingsCount}
                                    </Badge>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Error Display */}
                {status === 'failed' && current?.error && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                        <div className="flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5" />
                            <div>
                                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                                    Discovery Failed
                                </p>
                                <p className="text-xs text-red-600 dark:text-red-300 mt-1">
                                    {current.error}
                                </p>
                            </div>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
