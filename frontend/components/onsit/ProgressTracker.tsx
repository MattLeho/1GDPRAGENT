'use client';

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
// Default Steps
// =============================================================================

const defaultSteps: DiscoveryStep[] = [
    { id: 'init', name: 'Initialize', description: 'Setting up discovery job', status: 'pending' },
    { id: 'email', name: 'Email Check', description: 'Checking email addresses', status: 'pending' },
    { id: 'username', name: 'Username Search', description: 'Searching 500+ platforms', status: 'pending' },
    { id: 'breach', name: 'Breach Lookup', description: 'Checking data breaches', status: 'pending' },
    { id: 'social', name: 'Social Scan', description: 'Finding social profiles', status: 'pending' },
    { id: 'domain', name: 'Domain Intel', description: 'Analyzing domains', status: 'pending' },
    { id: 'compile', name: 'Compile Results', description: 'Building graph', status: 'pending' },
];

// =============================================================================
// Component
// =============================================================================

export function ProgressTracker({
    taskId,
    onComplete,
    onError,
}: ProgressTrackerProps) {
    const [progress, setProgress] = useState<DiscoveryProgress | null>(null);
    const [polling, setPolling] = useState(false);
    const [elapsedTime, setElapsedTime] = useState(0);

    // Polling effect
    useEffect(() => {
        if (!taskId) {
            setProgress(null);
            return;
        }

        setPolling(true);

        async function fetchStatus() {
            try {
                const res = await fetch(`/api/onsit/status/${taskId}`);
                if (res.ok) {
                    const data: DiscoveryProgress = await res.json();
                    setProgress(data);

                    if (data.status === 'completed') {
                        setPolling(false);
                        clearInterval(intervalId);
                        clearInterval(timerIntervalId);
                        onComplete?.(taskId!);
                    } else if (data.status === 'failed') {
                        setPolling(false);
                        clearInterval(intervalId);
                        clearInterval(timerIntervalId);
                        onError?.(data.error || 'Discovery failed');
                    }
                }
            } catch (e) {
                console.error('Failed to fetch discovery status', e);
            }
        }

        // Poll every 3 seconds
        const intervalId = setInterval(fetchStatus, 3000);

        // Timer for elapsed time
        const startTime = Date.now();
        const timerIntervalId = setInterval(() => {
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

    // Use default steps if no progress yet
    const steps = progress?.steps || defaultSteps;
    const currentProgress = progress?.progress || 0;
    const status = progress?.status || 'queued';

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-base">Discovery Progress</CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">
                            {progress?.currentStep || 'Initializing...'}
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
                <div className="space-y-2">
                    <Progress value={currentProgress} className="h-2" />
                    <p className="text-xs text-muted-foreground text-right">
                        {currentProgress}% complete
                    </p>
                </div>

                {/* Steps */}
                <div className="space-y-2">
                    {steps.map((step, idx) => {
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
                {status === 'failed' && progress?.error && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                        <div className="flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5" />
                            <div>
                                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                                    Discovery Failed
                                </p>
                                <p className="text-xs text-red-600 dark:text-red-300 mt-1">
                                    {progress.error}
                                </p>
                            </div>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
