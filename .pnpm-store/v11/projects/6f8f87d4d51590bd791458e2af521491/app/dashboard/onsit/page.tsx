'use client';

import { protectedFetch as fetch, shouldSuppressProtectedRequestError } from '@/lib/api-client';

/**
 * ONSIT Discovery Page
 * 
 * Main page for initiating and viewing ONSIT (Open Source Network Intelligence Toolkit)
 * discoveries. Allows users to search for their digital footprint across public sources.
 * 
 * Features:
 * - Discovery form for initiating searches
 * - Real-time progress tracking
 * - Findings display with risk assessment
 * - Add findings to graph
 */

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
    Search,
    History,
    GitGraph,
    AlertTriangle,
    ShieldCheck,
    Globe,
    FileText,
    Zap,
} from 'lucide-react';
import { DiscoveryForm, DiscoveryFormData } from '@/components/onsit/DiscoveryForm';
import { ProgressTracker } from '@/components/onsit/ProgressTracker';
import { FindingsList } from '@/components/onsit/FindingsList';
import { Finding } from '@/components/onsit/FindingCard';

// =============================================================================
// Page Component
// =============================================================================

export default function ONSITPage() {
    const router = useRouter();
    const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
    const [findings, setFindings] = useState<Finding[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        const taskId = new URLSearchParams(window.location.search).get('task');
        let active = true;
        if (taskId && /^[a-zA-Z0-9-]{1,100}$/.test(taskId)) {
            queueMicrotask(() => { if (active) setActiveTaskId(taskId); });
        }
        return () => { active = false; };
    }, []);

    // Handle discovery form submission
    const handleDiscoverySubmit = async (data: DiscoveryFormData) => {
        setIsSubmitting(true);
        try {
            const res = await fetch('/api/onsit/discover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (!res.ok) {
                throw new Error('Failed to start discovery');
            }

            const result = await res.json();
            if (typeof result.taskId !== 'string' || !result.taskId) throw new Error('Discovery service returned no task ID');
            setActiveTaskId(result.taskId);
            router.replace(`/dashboard/onsit?task=${encodeURIComponent(result.taskId)}`, { scroll: false });
            toast.success('Discovery started', {
                description: 'Searching public sources for your digital footprint',
            });
        } catch (error) {
            if (shouldSuppressProtectedRequestError(error)) return;
            console.error('Discovery error:', error);
            toast.error('Failed to start discovery', {
                description: 'Please try again later',
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    // Handle discovery completion
    const handleDiscoveryComplete = useCallback(async (taskId: string) => {
        toast.success('Discovery complete', {
            description: 'View your findings below',
        });

        // Fetch findings
        try {
            const res = await fetch(`/api/onsit/findings/${taskId}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Findings could not be loaded');
            setFindings(data.findings || []);
        } catch (e) {
            if (shouldSuppressProtectedRequestError(e)) return;
            console.error('Failed to fetch findings', e);
            toast.error('Discovery finished, but findings could not be loaded');
        }
    }, []);

    // Handle discovery error
    const handleDiscoveryError = useCallback((error: string) => {
        toast.error('Discovery failed', { description: error });
    }, []);

    // Navigate to graph with finding focused
    const handleViewInGraph = useCallback((finding: Finding) => {
        router.push(`/dashboard/graph?focus=${finding.id}`);
    }, [router]);

    // The current Intelligence service keeps findings in scan memory and has no
    // finding-level dismissal endpoint. Keep this action explicitly view-local.
    const handleDismiss = useCallback((finding: Finding) => {
        setFindings(prev => prev.filter(f => f.id !== finding.id));
        toast.success('Finding hidden from this view', {
            description: 'This does not delete the source finding.',
        });
    }, []);

    return (
        <div className="space-y-6 p-4 sm:p-6">
            {/* Header */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                    <h1 className="flex items-center gap-3 text-2xl font-bold tracking-tight sm:text-3xl">
                        <div className="p-2 rounded-lg bg-orange-100">
                            <Search className="h-6 w-6 text-orange-600" />
                        </div>
                        ONSIT Discovery
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Find your digital footprint across public sources
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                        The task link can resume this view while the local Intelligence service remains running; scan history is not yet durable across service restarts.
                    </p>
                </div>
                <Button
                    variant="outline"
                    className="gap-2"
                    onClick={() => router.push('/dashboard/graph')}
                >
                    <GitGraph className="h-4 w-4" />
                    View Graph
                </Button>
            </div>

            {/* Capabilities Banner */}
            <Card className="bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-900/20 dark:to-amber-900/20 border-orange-200 dark:border-orange-800">
                <CardContent className="py-4">
                    <div className="flex items-center gap-3 mb-3">
                        <Zap className="h-5 w-5 text-orange-600" />
                        <span className="font-semibold text-orange-800 dark:text-orange-200">
                            What ONSIT Can Find
                        </span>
                    </div>
                    <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
                        <div className="flex items-center gap-2">
                            <Globe className="h-4 w-4 text-orange-600" />
                            <span>Enabled public profile providers</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 text-orange-600" />
                            <span>Data breach records</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-orange-600" />
                            <span>Public documents</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <ShieldCheck className="h-4 w-4 text-orange-600" />
                            <span>Domain intelligence</span>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Main Content Tabs */}
            <Tabs defaultValue="discover" className="space-y-6">
                <TabsList>
                    <TabsTrigger value="discover" className="gap-2">
                        <Search className="h-4 w-4" />
                        New Discovery
                    </TabsTrigger>
                    <TabsTrigger value="findings" className="gap-2">
                        <History className="h-4 w-4" />
                        Findings
                        {findings.length > 0 && (
                            <Badge variant="secondary" className="ml-1">
                                {findings.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                </TabsList>

                {/* Discover Tab */}
                <TabsContent value="discover" className="space-y-6">
                    <div className="grid gap-6 lg:grid-cols-2">
                        {/* Form */}
                        <DiscoveryForm
                            onSubmit={handleDiscoverySubmit}
                            isSubmitting={isSubmitting}
                        />

                        {/* Progress Tracker */}
                        <ProgressTracker
                            taskId={activeTaskId}
                            onComplete={handleDiscoveryComplete}
                            onError={handleDiscoveryError}
                        />
                    </div>
                </TabsContent>

                {/* Findings Tab */}
                <TabsContent value="findings">
                    <FindingsList
                        findings={findings}
                        onViewInGraph={handleViewInGraph}
                        onDismiss={handleDismiss}
                    />
                </TabsContent>
            </Tabs>
        </div>
    );
}
