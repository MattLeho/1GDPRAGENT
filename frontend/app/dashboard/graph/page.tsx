'use client';

import { useState, useCallback } from 'react';
import { GraphCanvas } from '@/components/graph/GraphCanvas';
import { InspectorPanel } from '@/components/graph/InspectorPanel';
import { ShadowProfileChat } from '@/components/graph/ShadowProfileChat';
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
    }, []);

    const handleMergeNode = useCallback(async (nodeId: string) => {
        const targetId = window.prompt('Enter the target node ID to merge into:');
        if (!targetId) {
            return;
        }

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
    }, []);

    const handleFlagNode = useCallback((nodeId: string) => {
        toast.success('Node flagged for review', {
            description: `MAKGED agents will verify node ${nodeId}.`,
        });
    }, []);

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] -m-4 md:-m-8 min-h-0">
            {/* Header */}
            <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b bg-white dark:bg-zinc-900">
                <div>
                    <h1 className="text-xl font-bold">Data Graph</h1>
                    <p className="text-sm text-muted-foreground">
                        Your digital footprint visualized
                    </p>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex flex-1 min-h-0 overflow-hidden">
                {/* Graph Canvas - Zone A */}
                <div className="flex-1 min-h-0 min-w-0 relative">
                    <GraphCanvas
                        onNodeClick={handleNodeClick}
                        selectedNodeId={selectedNode?.id}
                        refreshKey={graphRefreshKey}
                    />
                </div>

                {/* Inspector Panel - Zone B */}
                <div className="w-80 flex-shrink-0 border-l bg-white dark:bg-zinc-900 overflow-y-auto">
                    <InspectorPanel
                        selectedNode={selectedNode}
                        onClose={handleCloseInspector}
                        onDelete={handleDeleteNode}
                        onMerge={handleMergeNode}
                        onFlag={handleFlagNode}
                    />
                </div>
            </div>

            {/* Shadow Profile Chat - Zone C */}
            <ShadowProfileChat />
        </div>
    );
}
