'use client';

import { useState, useCallback } from 'react';
import { protectedFetch as fetch, shouldSuppressProtectedRequestError } from '@/lib/api-client';
import { GraphCanvas } from '@/components/graph/GraphCanvas';
import { InspectorPanel } from '@/components/graph/InspectorPanel';
import { ShadowProfileChat } from '@/components/graph/ShadowProfileChat';
import { PrivacyGraphControls } from '@/components/graph/PrivacyGraphControls';
import { PrivacyModePanel } from '@/components/graph/PrivacyModePanel';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import type { PrivacyGraphFilters, PrivacyGraphMode } from '@/lib/privacy/types';
import { toast } from 'sonner';

interface GraphNode {
    id: string;
    label: string;
    type: string;
    properties: Record<string, unknown>;
}

export default function GraphPage() {
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const [graphRefreshKey, setGraphRefreshKey] = useState(0);
    const [mode,setMode]=useState<PrivacyGraphMode>('now');
    const [privacyFilters,setPrivacyFilters]=useState<PrivacyGraphFilters>({});

    const handleNodeClick = useCallback((node: GraphNode) => {
        setSelectedNode(node);
    }, []);

    const handleCloseInspector = useCallback(() => {
        setSelectedNode(null);
    }, []);

    const handleDeleteNode = useCallback(async (nodeId: string) => {
        if (!window.confirm('Delete this graph node and its relationships?')) {
            return;
        }

        try {
            const response = await fetch(`/api/graph/nodes?id=${encodeURIComponent(nodeId)}`, {
                method: 'DELETE',
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                toast.error('Failed to delete node', {
                    description: data.error || `Node ${nodeId} was not deleted.`,
                });
                return;
            }

            toast.success('Node deleted', {
                description: data.label || `Node ${nodeId} removed from graph.`,
            });
            setSelectedNode(null);
            setGraphRefreshKey(key => key + 1);
        } catch (error) {
            if (!shouldSuppressProtectedRequestError(error)) {
                toast.error('Failed to delete node');
            }
        }
    }, []);

    const handleMergeNode = useCallback(async (nodeId: string) => {
        const targetId = window.prompt('Enter the target node ID to merge into:');
        if (!targetId) {
            return;
        }

        try {
            const response = await fetch('/api/graph/nodes/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sourceId: nodeId, targetId }),
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                toast.error('Failed to merge nodes', {
                    description: data.error || `Node ${nodeId} was not merged.`,
                });
                return;
            }

            toast.success('Nodes merged', {
                description: `${data.relationshipsRewired} relationships rewired.`,
            });
            setSelectedNode(null);
            setGraphRefreshKey(key => key + 1);
        } catch (error) {
            if (!shouldSuppressProtectedRequestError(error)) {
                toast.error('Failed to merge nodes');
            }
        }
    }, []);

    const handleFlagNode = useCallback((nodeId: string) => {
        toast.success('Node flagged for review', {
            description: `MAKGED agents will verify node ${nodeId}.`,
        });
    }, []);

    return (
        <div className="-m-3 flex h-[calc(100dvh-3.5rem)] min-h-0 flex-col sm:-m-5 lg:-m-6 lg:h-[calc(100dvh-4rem)] xl:-m-8">
            {/* Header */}
            <div className="flex shrink-0 items-center justify-between border-b bg-white px-4 py-3 dark:bg-zinc-900 sm:px-5 sm:py-4 lg:px-6">
                <div>
                    <h1 className="text-xl font-bold">Data Graph</h1>
                    <p className="text-sm text-muted-foreground">
                        Your digital footprint visualized
                    </p>
                </div>
            </div>
            <PrivacyGraphControls mode={mode} filters={privacyFilters} onMode={next=>{
                setMode(next);
                setPrivacyFilters(current=>({ ...current,
                    profileLayer: next==='controller_profile'?'controller_profile':current.profileLayer,
                    capabilityStatus: next==='capabilities'?(current.capabilityStatus||'evidenced_from_export'):undefined,
                    purpose: next==='purpose'?(current.purpose||undefined):undefined,
                    compareTo: next==='compare'?current.compareTo:undefined,
                }));
            }} onFilters={setPrivacyFilters}/>

            {/* Main Content */}
            <div className="flex flex-1 min-h-0 overflow-hidden">
                {/* Graph Canvas - Zone A */}
                <div className="flex-1 min-h-0 min-w-0 relative">
                    <GraphCanvas
                        onNodeClick={handleNodeClick}
                        selectedNodeId={selectedNode?.id}
                        refreshKey={graphRefreshKey}
                        privacyFilters={privacyFilters}
                    />
                </div>

                {/* Inspector Panel - Zone B */}
                <div className="hidden w-80 shrink-0 overflow-y-auto border-l bg-white dark:bg-zinc-900 xl:block">
                    <PrivacyModePanel mode={mode} filters={privacyFilters}/>
                    <InspectorPanel
                        selectedNode={selectedNode}
                        onClose={handleCloseInspector}
                        onDelete={handleDeleteNode}
                        onMerge={handleMergeNode}
                        onFlag={handleFlagNode}
                    />
                </div>
            </div>

            <Sheet open={selectedNode !== null} onOpenChange={open => { if (!open) handleCloseInspector(); }}>
                <SheetContent side="right" className="w-full overflow-y-auto p-0 sm:max-w-md xl:hidden">
                    <SheetHeader className="border-b p-4 text-left">
                        <SheetTitle>Graph inspector</SheetTitle>
                    </SheetHeader>
                    <PrivacyModePanel mode={mode} filters={privacyFilters}/>
                    <InspectorPanel
                        selectedNode={selectedNode}
                        onClose={handleCloseInspector}
                        onDelete={handleDeleteNode}
                        onMerge={handleMergeNode}
                        onFlag={handleFlagNode}
                    />
                </SheetContent>
            </Sheet>

            {/* Shadow Profile Chat - Zone C */}
            <ShadowProfileChat />
        </div>
    );
}
