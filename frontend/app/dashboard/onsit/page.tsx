'use client';

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

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
            setActiveTaskId(result.taskId);
            toast.success('Discovery started', {
                description: 'Searching public sources for your digital footprint',
            });
        } catch (error) {
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
            if (res.ok) {
                const data = await res.json();
                setFindings(data.findings || []);
            }
        } catch (e) {
            console.error('Failed to fetch findings', e);
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

    // Dismiss a finding
    const handleDismiss = useCallback(async (finding: Finding) => {
        try {
            await fetch(`/api/onsit/findings/${finding.id}`, {
                method: 'DELETE',
            });
            setFindings(prev => prev.filter(f => f.id !== finding.id));
            toast.success('Finding dismissed');
        } catch (e) {
            toast.error('Failed to dismiss finding');
        }
    }, []);

    // Add finding to graph
    const handleAddToGraph = useCallback(async (finding: Finding) => {
        try {
            const res = await fetch('/api/graph/nodes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: finding.type,
                    label: finding.title,
                    properties: finding.metadata,
                    source: 'onsit',
                    riskLevel: finding.riskLevel,
                }),
            });

            if (res.ok) {
                setFindings(prev =>
                    prev.map(f => f.id === finding.id ? { ...f, addedToGraph: true } : f)
                );
                toast.success('Added to graph', {
                    description: 'View in the Data Graph page',
                    action: {
                        label: 'View',
                        onClick: () => router.push('/dashboard/graph'),
                    },
                });
            }
        } catch (e) {
            toast.error('Failed to add to graph');
        }
    }, [router]);

    // Bulk add to graph
    const handleBulkAddToGraph = useCallback(async (findingsToAdd: Finding[]) => {
        try {
            const res = await fetch('/api/graph/nodes/bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nodes: findingsToAdd.map(f => ({
                        type: f.type,
                        label: f.title,
                        properties: f.metadata,
                        source: 'onsit',
                        riskLevel: f.riskLevel,
                    })),
                }),
            });

            if (res.ok) {
                setFindings(prev =>
                    prev.map(f =>
                        findingsToAdd.some(fa => fa.id === f.id)
                            ? { ...f, addedToGraph: true }
                            : f
                    )
                );
                toast.success(`Added ${findingsToAdd.length} items to graph`);
            }
        } catch (e) {
            toast.error('Failed to add items to graph');
        }
    }, []);

    return (
        <div className="space-y-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-orange-100">
                            <Search className="h-6 w-6 text-orange-600" />
                        </div>
                        ONSIT Discovery
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Find your digital footprint across public sources
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
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div className="flex items-center gap-2">
                            <Globe className="h-4 w-4 text-orange-600" />
                            <span>500+ social platforms</span>
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
                        onAddToGraph={handleAddToGraph}
                        onBulkAddToGraph={handleBulkAddToGraph}
                    />
                </TabsContent>
            </Tabs>
        </div>
    );
}
