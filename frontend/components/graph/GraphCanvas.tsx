'use client';

/**
 * GraphCanvas Component - Enhanced Version
 * 
 * Interactive force-directed graph visualization using react-force-graph.
 * Supports 2D/3D rendering, ONSIT/GDPR layer filtering, community visualization,
 * and dashed edge styling for inferred relationships.
 * 
 * Architecture inspired by:
 * - Flowsint: OSINT investigation graph patterns
 * - AI-KG: Community detection and visualization
 * - Photon: Entity type categorization
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { Loader2, Box, Square, AlertTriangle, RefreshCw, Database, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SkeletonGraph } from '@/components/ui/skeleton';
import { GraphToolbar, GraphFilters, defaultGraphFilters } from './GraphToolbar';
import { GraphLegend, generateLegendItems, nodeColors, nodeSizes } from './GraphLegend';

// Dynamically import force graphs to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });
const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), { ssr: false });

// =============================================================================
// Types
// =============================================================================

export interface GraphNode {
    id: string;
    label: string;
    type: string;
    properties: Record<string, unknown>;
    source?: 'onsit' | 'gdpr' | 'inference';
    riskLevel?: 'low' | 'medium' | 'high' | 'critical';
    confidence?: number;
    discoveredAt?: string;
    communityId?: string;
    x?: number;
    y?: number;
    z?: number;
}

export interface GraphLink {
    source: string | GraphNode;
    target: string | GraphNode;
    type: string;
    isInferred?: boolean;
    confidence?: number;
}

export interface GraphData {
    nodes: GraphNode[];
    links: GraphLink[];
}

export interface GraphCanvasProps {
    onNodeClick: (node: GraphNode) => void;
    selectedNodeId?: string | null;
}

// =============================================================================
// Node Type Category Mapping
// =============================================================================

const nodeTypeCategories: Record<string, 'core' | 'gdpr' | 'onsit' | 'inference'> = {
    // Core types
    User: 'core',
    Persona: 'core',
    Email: 'core',

    // GDPR types
    Company: 'gdpr',
    Account: 'gdpr',
    Attribute: 'gdpr',
    DataPoint: 'gdpr',

    // ONSIT types
    ONSITFinding: 'onsit',
    SocialProfile: 'onsit',
    BreachRecord: 'onsit',
    PublicDocument: 'onsit',
    CryptoWallet: 'onsit',
    Credential: 'onsit',
    Domain: 'onsit',
    IP: 'onsit',
    Username: 'onsit',
    Phone: 'onsit',

    // Inference
    Inference: 'inference',
};

// Community colors for Louvain visualization (from AI-KG)
const communityColors = [
    '#9333ea', '#3b82f6', '#22c55e', '#f97316', '#06b6d4',
    '#ec4899', '#eab308', '#ef4444', '#8b5cf6', '#14b8a6',
];

// =============================================================================
// Component
// =============================================================================

export function GraphCanvas({ onNodeClick, selectedNodeId }: GraphCanvasProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const graphRef = useRef<any>(null);

    // State
    const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [dbStatus, setDbStatus] = useState<string>('unknown');
    const [pagination, setPagination] = useState<{ hasMore: boolean; nextCursor: string | null; total: number }>(
        { hasMore: false, nextCursor: null, total: 0 }
    );
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const [is3D, setIs3D] = useState(false);
    const [filters, setFilters] = useState<GraphFilters>({ ...defaultGraphFilters, selectedTypes: [] });
    const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
    const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

    // Fetch graph data with pagination
    const fetchGraphData = useCallback(async (cursor?: string) => {
        const isLoadingMore = !!cursor;
        if (isLoadingMore) {
            setLoadingMore(true);
        } else {
            setLoading(true);
        }

        try {
            const params = new URLSearchParams();
            params.set('limit', '100');
            if (cursor) {
                params.set('skip', cursor);
            }
            if (!filters.showONSIT || !filters.showGDPR) {
                params.set('layer', filters.showONSIT ? 'onsit' : filters.showGDPR ? 'gdpr' : 'all');
            }
            if (!filters.showInferences) {
                params.set('showInferences', 'false');
            }

            const res = await fetch(`/api/graph?${params.toString()}`);
            if (res.ok) {
                const data = await res.json();

                if (isLoadingMore) {
                    // Append new nodes and links
                    setGraphData(prev => ({
                        nodes: [...prev.nodes, ...data.nodes],
                        links: [...prev.links, ...data.links],
                    }));
                } else {
                    setGraphData(data);
                    // Initialize selectedTypes with all available types if empty
                    if (filters.selectedTypes.length === 0) {
                        const types = [...new Set(data.nodes.map((n: GraphNode) => n.type))];
                        setFilters(prev => ({ ...prev, selectedTypes: types as string[] }));
                    }
                }

                if (data.pagination) {
                    setPagination(data.pagination);
                }

                // Capture database status from API response
                if (data.dbStatus) {
                    setDbStatus(data.dbStatus);
                } else if (data.error) {
                    setDbStatus('error');
                    setError(data.error);
                } else {
                    setDbStatus('connected');
                }
            }
        } catch (e) {
            console.error('Failed to load graph data', e);
            setError(e instanceof Error ? e.message : 'Failed to load graph data');
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }, [filters.showONSIT, filters.showGDPR, filters.showInferences, filters.selectedTypes.length]);

    // Initial fetch
    useEffect(() => {
        fetchGraphData();
    }, []);

    // Handle container resize
    useEffect(() => {
        function handleResize() {
            if (containerRef.current) {
                // Get the actual bounding rect for accurate dimensions
                const rect = containerRef.current.getBoundingClientRect();
                // Account for toolbar height (approx 52px)
                const toolbarHeight = 52;
                const newWidth = Math.max(rect.width, 400);
                const newHeight = Math.max(rect.height - toolbarHeight, 400);

                setDimensions({
                    width: newWidth,
                    height: newHeight,
                });
            }
        }

        // Initial measurement with delay for DOM to settle
        const initialTimer = setTimeout(handleResize, 100);
        // Second measurement after layout stabilizes
        const stabilizeTimer = setTimeout(handleResize, 500);

        window.addEventListener('resize', handleResize);

        // Also use ResizeObserver for more accurate container tracking
        const resizeObserver = new ResizeObserver(handleResize);
        if (containerRef.current) {
            resizeObserver.observe(containerRef.current);
        }

        return () => {
            clearTimeout(initialTimer);
            clearTimeout(stabilizeTimer);
            window.removeEventListener('resize', handleResize);
            resizeObserver.disconnect();
        };
    }, []);

    // Get unique node types
    const availableTypes = useMemo(() =>
        [...new Set(graphData.nodes.map(n => n.type))],
        [graphData.nodes]
    );

    // Filter graph data based on all filters
    const filteredData = useMemo(() => {
        let nodes = graphData.nodes;
        let links = graphData.links;

        // Filter by layer visibility
        nodes = nodes.filter(n => {
            const category = nodeTypeCategories[n.type] || 'core';
            if (category === 'onsit' && !filters.showONSIT) return false;
            if (category === 'gdpr' && !filters.showGDPR) return false;
            if (category === 'inference' && !filters.showInferences) return false;
            return true;
        });

        // Filter by selected types
        if (filters.selectedTypes.length > 0 && filters.selectedTypes.length < availableTypes.length) {
            nodes = nodes.filter(n => filters.selectedTypes.includes(n.type));
        }

        // Filter by risk level
        if (filters.riskLevel !== 'all') {
            nodes = nodes.filter(n => n.riskLevel === filters.riskLevel);
        }

        // Filter links to only include nodes that are visible
        const visibleNodeIds = new Set(nodes.map(n => n.id));
        links = links.filter(l => {
            const sourceId = typeof l.source === 'string' ? l.source : l.source.id;
            const targetId = typeof l.target === 'string' ? l.target : l.target.id;

            // Also filter out inferred links if inferences are hidden
            if (l.isInferred && !filters.showInferences) return false;

            return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId);
        });

        return { nodes, links };
    }, [graphData, filters, availableTypes]);

    // Generate legend items
    const legendItems = useMemo(() =>
        generateLegendItems(filteredData.nodes, filters.selectedTypes),
        [filteredData.nodes, filters.selectedTypes]
    );

    // Node rendering for 2D with enhanced styling
    // Using 'any' type for react-force-graph compatibility
    const paintNode = useCallback(
        (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const typedNode = node as GraphNode;
            const label = typedNode.label || typedNode.id;
            const fontSize = Math.max(10, 14 / globalScale);
            const size = nodeSizes[typedNode.type] || 10;
            const color = nodeColors[typedNode.type] || '#888888';
            const isSelected = selectedNodeId === typedNode.id;
            const isHovered = hoveredNode?.id === typedNode.id;

            // Community color override if present
            const fillColor = typedNode.communityId
                ? communityColors[parseInt(typedNode.communityId) % communityColors.length]
                : color;

            // Outer glow for selected/User/high-risk
            if (isSelected || typedNode.type === 'User' || typedNode.riskLevel === 'critical') {
                ctx.beginPath();
                ctx.arc(typedNode.x!, typedNode.y!, size + 6, 0, 2 * Math.PI);
                ctx.fillStyle = isSelected
                    ? 'rgba(59, 130, 246, 0.3)'
                    : typedNode.riskLevel === 'critical'
                        ? 'rgba(239, 68, 68, 0.4)'
                        : 'rgba(147, 51, 234, 0.3)';
                ctx.fill();
            }

            // Main node circle
            ctx.beginPath();
            ctx.arc(typedNode.x!, typedNode.y!, size, 0, 2 * Math.PI);
            ctx.fillStyle = fillColor;
            ctx.fill();

            // Border
            ctx.strokeStyle = isSelected
                ? '#3b82f6'
                : isHovered
                    ? '#60a5fa'
                    : 'rgba(255, 255, 255, 0.8)';
            ctx.lineWidth = isSelected || isHovered ? 3 : 2;
            ctx.stroke();

            // Risk indicator for high-risk nodes
            if (typedNode.riskLevel === 'high' || typedNode.riskLevel === 'critical') {
                ctx.beginPath();
                ctx.arc(typedNode.x! + size * 0.7, typedNode.y! - size * 0.7, 4, 0, 2 * Math.PI);
                ctx.fillStyle = typedNode.riskLevel === 'critical' ? '#dc2626' : '#f97316';
                ctx.fill();
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1;
                ctx.stroke();
            }

            // Label
            if (globalScale > 0.8 || isSelected || isHovered) {
                ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillStyle = '#374151';

                // Background for readability
                const textWidth = ctx.measureText(label).width;
                ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
                ctx.fillRect(
                    typedNode.x! - textWidth / 2 - 2,
                    typedNode.y! + size + 2,
                    textWidth + 4,
                    fontSize + 2
                );

                ctx.fillStyle = '#374151';
                ctx.fillText(label, typedNode.x!, typedNode.y! + size + 4);
            }
        },
        [selectedNodeId, hoveredNode]
    );

    // Link rendering with dashed lines for inferences
    // Using 'any' type for react-force-graph compatibility
    const paintLink = useCallback(
        (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const typedLink = link as GraphLink;
            const source = typedLink.source as GraphNode;
            const target = typedLink.target as GraphNode;

            if (!source.x || !source.y || !target.x || !target.y) return;

            ctx.beginPath();
            ctx.moveTo(source.x, source.y);

            // Dashed line for inferred relationships
            if (typedLink.isInferred) {
                ctx.setLineDash([5, 5]);
                ctx.strokeStyle = 'rgba(239, 68, 68, 0.5)'; // Red for inferred
            } else {
                ctx.setLineDash([]);
                ctx.strokeStyle = 'rgba(156, 163, 175, 0.4)';
            }

            ctx.lineTo(target.x, target.y);
            ctx.lineWidth = typedLink.isInferred ? 1.5 : 1;
            ctx.stroke();
            ctx.setLineDash([]);
        },
        []
    );

    // Event handlers - using any for react-force-graph compatibility
    const handleNodeClick = useCallback((node: any) => {
        const typedNode = node as GraphNode;
        onNodeClick(typedNode);
        if (graphRef.current) {
            graphRef.current.centerAt(typedNode.x, typedNode.y, 500);
            graphRef.current.zoom(2, 500);
        }
    }, [onNodeClick]);

    const handleNodeHover = useCallback((node: any) => {
        const typedNode = node ? (node as GraphNode) : null;
        setHoveredNode(typedNode);
    }, []);

    const zoomToFit = useCallback(() => {
        if (graphRef.current) {
            graphRef.current.zoomToFit(400, 50);
        }
    }, []);

    const resetFilters = useCallback(() => {
        setFilters({
            ...defaultGraphFilters,
            selectedTypes: availableTypes,
        });
    }, [availableTypes]);

    const handleTypeClick = useCallback((type: string) => {
        setFilters(prev => {
            const isSelected = prev.selectedTypes.includes(type);
            return {
                ...prev,
                selectedTypes: isSelected
                    ? prev.selectedTypes.filter(t => t !== type)
                    : [...prev.selectedTypes, type],
            };
        });
    }, []);

    // Loading state
    if (loading) {
        return (
            <div className="h-full w-full p-4 bg-zinc-50 dark:bg-zinc-950">
                <SkeletonGraph />
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="h-full w-full flex flex-col items-center justify-center bg-zinc-50 dark:bg-zinc-950 gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
                    <AlertTriangle className="h-6 w-6 text-destructive" />
                </div>
                <div className="text-center">
                    <p className="font-medium">Failed to load graph</p>
                    <p className="text-sm text-muted-foreground">{error}</p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.location.reload()}
                    className="gap-2"
                >
                    <RefreshCw className="h-4 w-4" />
                    Reload
                </Button>
            </div>
        );
    }

    const GraphComponent = is3D ? ForceGraph3D : ForceGraph2D;

    return (
        <div ref={containerRef} className="h-full w-full min-h-0 bg-zinc-50 dark:bg-zinc-950 relative flex flex-col overflow-hidden">
            {/* Toolbar */}
            <div className="border-b bg-white dark:bg-zinc-900 px-4 py-2">
                <div className="flex items-center gap-3">
                    {/* 2D/3D Toggle */}
                    <Button
                        variant={is3D ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setIs3D(!is3D)}
                        className="gap-1 h-9"
                        aria-label={is3D ? 'Switch to 2D view' : 'Switch to 3D view'}
                    >
                        {is3D ? <Box className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                        {is3D ? '3D' : '2D'}
                    </Button>

                    {/* Main Toolbar */}
                    <GraphToolbar
                        filters={filters}
                        onFiltersChange={setFilters}
                        availableTypes={availableTypes}
                        onZoomToFit={zoomToFit}
                        onReset={resetFilters}
                        nodeCount={filteredData.nodes.length}
                        linkCount={filteredData.links.length}
                    />
                </div>
            </div>

            {/* Graph Container */}
            <div className="flex-1 relative">
                {/* Legend */}
                <div className="absolute bottom-4 left-4 z-20 max-w-[280px]">
                    <GraphLegend
                        items={legendItems}
                        selectedTypes={filters.selectedTypes}
                        onTypeClick={handleTypeClick}
                        showInferences={filters.showInferences}
                    />
                </div>

                {/* Hover Tooltip */}
                {hoveredNode && (
                    <div
                        className="fixed z-50 p-3 bg-popover border rounded-lg shadow-lg text-sm max-w-xs pointer-events-none"
                        style={{
                            left: Number.isFinite(tooltipPos.x) ? tooltipPos.x + 15 : 0,
                            top: Number.isFinite(tooltipPos.y) ? tooltipPos.y + 15 : 0,
                        }}
                    >
                        <div className="flex items-center gap-2 mb-2">
                            <span
                                className="w-3 h-3 rounded-full border border-white/30"
                                style={{ backgroundColor: nodeColors[hoveredNode.type] || '#888888' }}
                            />
                            <span className="font-semibold">{hoveredNode.label}</span>
                        </div>
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded">
                                {hoveredNode.type}
                            </span>
                            {hoveredNode.riskLevel && hoveredNode.riskLevel !== 'low' && (
                                <span className={`text-xs px-2 py-0.5 rounded ${hoveredNode.riskLevel === 'critical' ? 'bg-red-100 text-red-700' :
                                    hoveredNode.riskLevel === 'high' ? 'bg-orange-100 text-orange-700' :
                                        'bg-yellow-100 text-yellow-700'
                                    }`}>
                                    {hoveredNode.riskLevel}
                                </span>
                            )}
                            {hoveredNode.source && (
                                <span className="text-xs text-muted-foreground">
                                    {hoveredNode.source.toUpperCase()}
                                </span>
                            )}
                        </div>
                        {Object.keys(hoveredNode.properties).length > 0 && (
                            <div className="space-y-1 text-xs text-muted-foreground border-t pt-2 mt-2">
                                {Object.entries(hoveredNode.properties).slice(0, 4).map(([key, value]) => (
                                    <div key={key} className="flex justify-between gap-4">
                                        <span className="font-medium">{key}:</span>
                                        <span className="truncate max-w-[150px]">{String(value)}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Empty State — contextual messaging */}
                {filteredData.nodes.length === 0 && !loading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
                        {dbStatus === 'disconnected' || dbStatus === 'error' ? (
                            // Case 1: Neo4j connection issue
                            <>
                                <div className="flex items-center justify-center w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30">
                                    <AlertTriangle className="h-8 w-8 text-red-500" />
                                </div>
                                <p className="text-sm font-medium text-red-600 dark:text-red-400">
                                    Database Connection Error
                                </p>
                                <p className="text-xs text-muted-foreground max-w-sm">
                                    {error || 'Could not connect to Neo4j. Please ensure the database is running.'}
                                </p>
                                <Button variant="outline" size="sm" onClick={() => fetchGraphData()} className="gap-1.5">
                                    <RefreshCw className="h-3.5 w-3.5" />
                                    Retry Connection
                                </Button>
                            </>
                        ) : graphData.nodes.length === 0 ? (
                            // Case 2: Database connected but empty — no documents processed yet
                            <>
                                <div className="flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900/30">
                                    <Database className="h-8 w-8 text-indigo-500" />
                                </div>
                                <p className="text-sm font-medium">
                                    No data in knowledge graph yet
                                </p>
                                <p className="text-xs text-muted-foreground max-w-sm">
                                    Upload GDPR data exports and process them with AI to populate the knowledge graph with entities and relationships.
                                </p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => window.location.href = '/dashboard/import'}
                                    className="gap-1.5"
                                >
                                    <Upload className="h-3.5 w-3.5" />
                                    Go to Data Import
                                </Button>
                            </>
                        ) : (
                            // Case 3: Data exists but filters hide everything
                            <>
                                <p className="text-muted-foreground mb-2">No nodes match your current filters</p>
                                <Button variant="outline" size="sm" onClick={resetFilters}>
                                    Reset Filters
                                </Button>
                            </>
                        )}
                    </div>
                )}

                {/* Graph */}
                {filteredData.nodes.length > 0 && (
                    <GraphComponent
                        ref={graphRef}
                        graphData={filteredData}
                        width={dimensions.width}
                        height={dimensions.height}
                        nodeCanvasObject={!is3D ? paintNode : undefined}
                        linkCanvasObject={!is3D ? paintLink : undefined}
                        nodeColor={(node: any) => nodeColors[(node as GraphNode).type] || '#888888'}
                        nodeLabel={(node: any) => (node as GraphNode).label}
                        nodeVal={(node: any) => nodeSizes[(node as GraphNode).type] || 10}
                        onNodeClick={handleNodeClick}
                        onNodeHover={handleNodeHover}
                        nodeId="id"
                        linkSource="source"
                        linkTarget="target"
                        linkColor={(link: any) =>
                            (link as GraphLink).isInferred ? 'rgba(239, 68, 68, 0.5)' : 'rgba(156, 163, 175, 0.4)'
                        }
                        linkLineDash={(link: any) => (link as GraphLink).isInferred ? [5, 5] : []}
                        cooldownTicks={100}
                        d3AlphaDecay={0.02}
                        d3VelocityDecay={0.3}
                        enableNodeDrag={true}
                        enableZoomInteraction={true}
                        enablePanInteraction={true}
                        backgroundColor="transparent"
                    />
                )}

                {/* Pagination Status Bar */}
                {(pagination.total > 0 || pagination.hasMore) && (
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-3 bg-white/90 dark:bg-zinc-900/90 backdrop-blur-sm rounded-full px-4 py-2 shadow-lg border">
                        <span className="text-sm text-muted-foreground">
                            {graphData.nodes.length} of {pagination.total} nodes
                        </span>
                        {pagination.hasMore && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => fetchGraphData(pagination.nextCursor || undefined)}
                                disabled={loadingMore}
                                className="h-7 rounded-full"
                            >
                                {loadingMore ? (
                                    <>
                                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                        Loading...
                                    </>
                                ) : (
                                    'Load More'
                                )}
                            </Button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

