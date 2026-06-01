'use client';

/**
 * InspectorPanel Component - Enhanced Version
 * 
 * Detailed node inspector with evidence display, confidence scores,
 * ONSIT discovery path visualization, and comprehensive actions.
 * 
 * Features:
 * - Properties display with type-aware formatting
 * - Evidence section with source links (LangExtract grounding pattern)
 * - Confidence gauge visualization
 * - Discovery path for ONSIT findings
 * - Action buttons: Delete, Merge, Flag, Re-validate
 * - Full accessibility with ARIA labels
 */

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import {
    User,
    Building2,
    AtSign,
    Shield,
    AlertTriangle,
    Trash2,
    GitMerge,
    Flag,
    X,
    Loader2,
    ExternalLink,
    FileText,
    Globe,
    Mail,
    Key,
    Wallet,
    Server,
    RefreshCw,
    Eye,
    CheckCircle2,
    Clock,
    Link as LinkIcon,
} from 'lucide-react';
import { nodeColors } from './GraphLegend';

// =============================================================================
// Types
// =============================================================================

interface GraphNode {
    id: string;
    label: string;
    type: string;
    properties: Record<string, unknown>;
    source?: 'onsit' | 'gdpr' | 'inference';
    riskLevel?: 'low' | 'medium' | 'high' | 'critical';
    confidence?: number;
    discoveredAt?: string;
    evidenceLinks?: EvidenceLink[];
    discoveryPath?: DiscoveryStep[];
}

interface EvidenceLink {
    url: string;
    title: string;
    snippet?: string;
    confidence: number;
}

interface DiscoveryStep {
    step: number;
    action: string;
    result: string;
    timestamp: string;
}

interface GraphStats {
    totalNodes: number;
    totalRelationships: number;
    nodesByType: Record<string, number>;
    highRiskConnections: number;
    lastUpdated: string;
    onsitFindings?: number;
    gdprEntities?: number;
    inferences?: number;
}

interface InspectorPanelProps {
    selectedNode: GraphNode | null;
    onClose: () => void;
    onDelete: (nodeId: string) => void;
    onMerge: (nodeId: string) => void;
    onFlag: (nodeId: string) => void;
    onRevalidate?: (nodeId: string) => void;
}

// =============================================================================
// Node Type Configuration
// =============================================================================

const nodeTypeConfig: Record<string, {
    icon: React.ElementType;
    color: string;
    bgColor: string;
    description: string;
}> = {
    // Core types
    User: {
        icon: User,
        color: 'text-purple-600',
        bgColor: 'bg-purple-100',
        description: 'Your primary identity'
    },
    Persona: {
        icon: Shield,
        color: 'text-blue-600',
        bgColor: 'bg-blue-100',
        description: 'Alternative persona or alias'
    },
    Email: {
        icon: Mail,
        color: 'text-pink-600',
        bgColor: 'bg-pink-100',
        description: 'Email address'
    },

    // GDPR types
    Company: {
        icon: Building2,
        color: 'text-green-600',
        bgColor: 'bg-green-100',
        description: 'Data controller or processor'
    },
    Account: {
        icon: User,
        color: 'text-orange-600',
        bgColor: 'bg-orange-100',
        description: 'Account with a service'
    },
    Attribute: {
        icon: AtSign,
        color: 'text-cyan-600',
        bgColor: 'bg-cyan-100',
        description: 'Data attribute'
    },
    DataPoint: {
        icon: FileText,
        color: 'text-yellow-600',
        bgColor: 'bg-yellow-100',
        description: 'Individual data point'
    },

    // ONSIT types
    ONSITFinding: {
        icon: Globe,
        color: 'text-orange-600',
        bgColor: 'bg-orange-100',
        description: 'Discovered via ONSIT scan'
    },
    SocialProfile: {
        icon: User,
        color: 'text-pink-600',
        bgColor: 'bg-pink-100',
        description: 'Social media profile'
    },
    BreachRecord: {
        icon: AlertTriangle,
        color: 'text-red-600',
        bgColor: 'bg-red-100',
        description: 'Found in data breach'
    },
    PublicDocument: {
        icon: FileText,
        color: 'text-purple-600',
        bgColor: 'bg-purple-100',
        description: 'Publicly accessible document'
    },
    CryptoWallet: {
        icon: Wallet,
        color: 'text-indigo-600',
        bgColor: 'bg-indigo-100',
        description: 'Cryptocurrency wallet'
    },
    Credential: {
        icon: Key,
        color: 'text-red-700',
        bgColor: 'bg-red-200',
        description: 'Exposed credential'
    },
    Domain: {
        icon: Globe,
        color: 'text-sky-600',
        bgColor: 'bg-sky-100',
        description: 'Domain name'
    },
    IP: {
        icon: Server,
        color: 'text-teal-600',
        bgColor: 'bg-teal-100',
        description: 'IP address'
    },

    // Inference
    Inference: {
        icon: AlertTriangle,
        color: 'text-red-600',
        bgColor: 'bg-red-100',
        description: 'AI-inferred relationship'
    },
};

// =============================================================================
// Helper Components
// =============================================================================

function ConfidenceGauge({ confidence }: { confidence: number }) {
    const percentage = Math.round(confidence * 100);
    const color = confidence >= 0.8 ? 'bg-green-500' :
        confidence >= 0.5 ? 'bg-yellow-500' : 'bg-red-500';

    return (
        <div className="space-y-1" role="meter" aria-valuenow={percentage} aria-valuemin={0} aria-valuemax={100}>
            <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Confidence</span>
                <span className="font-medium">{percentage}%</span>
            </div>
            <div className="h-2 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
                <div
                    className={`h-full ${color} transition-all duration-500`}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    );
}

function RiskBadge({ level }: { level: string }) {
    const config = {
        low: { color: 'bg-green-100 text-green-700 border-green-200', label: 'Low Risk' },
        medium: { color: 'bg-yellow-100 text-yellow-700 border-yellow-200', label: 'Medium Risk' },
        high: { color: 'bg-orange-100 text-orange-700 border-orange-200', label: 'High Risk' },
        critical: { color: 'bg-red-100 text-red-700 border-red-200', label: 'Critical Risk' },
    };
    const c = config[level as keyof typeof config] || config.low;

    return (
        <Badge variant="outline" className={c.color}>
            <AlertTriangle className="h-3 w-3 mr-1" />
            {c.label}
        </Badge>
    );
}

function SourceBadge({ source }: { source: string }) {
    const config = {
        onsit: { color: 'bg-orange-100 text-orange-700', icon: Globe, label: 'ONSIT' },
        gdpr: { color: 'bg-green-100 text-green-700', icon: FileText, label: 'GDPR' },
        inference: { color: 'bg-purple-100 text-purple-700', icon: LinkIcon, label: 'Inferred' },
    };
    const c = config[source as keyof typeof config] || config.gdpr;
    const Icon = c.icon;

    return (
        <Badge variant="outline" className={c.color}>
            <Icon className="h-3 w-3 mr-1" />
            {c.label}
        </Badge>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export function InspectorPanel({
    selectedNode,
    onClose,
    onDelete,
    onMerge,
    onFlag,
    onRevalidate,
}: InspectorPanelProps) {
    const [stats, setStats] = useState<GraphStats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchStats() {
            try {
                const res = await fetch('/api/graph/stats');
                if (res.ok) {
                    const data = await res.json();
                    setStats(data);
                }
            } catch (e) {
                console.error('Failed to load graph stats', e);
            } finally {
                setLoading(false);
            }
        }
        fetchStats();
    }, []);

    const config = selectedNode
        ? nodeTypeConfig[selectedNode.type] || nodeTypeConfig.User
        : null;
    const Icon = config?.icon || User;

    // ==========================================================================
    // Default View: Enhanced Stats
    // ==========================================================================

    if (!selectedNode) {
        return (
            <Card className="h-full flex flex-col border-l rounded-none" role="region" aria-label="Graph statistics">
                <CardHeader className="pb-4">
                    <CardTitle className="text-lg">Graph Overview</CardTitle>
                    <p className="text-sm text-muted-foreground">
                        Your digital footprint summary
                    </p>
                </CardHeader>
                <CardContent className="flex-1">
                    {loading ? (
                        <div className="flex items-center justify-center h-32">
                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : stats ? (
                        <div className="space-y-6">
                            {/* Summary Stats */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-zinc-50 dark:bg-zinc-900 rounded-lg p-4 text-center">
                                    <p className="text-3xl font-bold text-zinc-800 dark:text-zinc-100">
                                        {stats.totalNodes}
                                    </p>
                                    <p className="text-xs text-muted-foreground">Total Entities</p>
                                </div>
                                <div className="bg-zinc-50 dark:bg-zinc-900 rounded-lg p-4 text-center">
                                    <p className="text-3xl font-bold text-zinc-800 dark:text-zinc-100">
                                        {stats.totalRelationships}
                                    </p>
                                    <p className="text-xs text-muted-foreground">Connections</p>
                                </div>
                            </div>

                            {/* Data Sources */}
                            <div className="grid grid-cols-3 gap-2">
                                <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3 text-center">
                                    <Globe className="h-5 w-5 mx-auto text-orange-600 mb-1" />
                                    <p className="text-lg font-semibold">{stats.onsitFindings || 0}</p>
                                    <p className="text-xs text-muted-foreground">ONSIT</p>
                                </div>
                                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-center">
                                    <FileText className="h-5 w-5 mx-auto text-green-600 mb-1" />
                                    <p className="text-lg font-semibold">{stats.gdprEntities || 0}</p>
                                    <p className="text-xs text-muted-foreground">GDPR</p>
                                </div>
                                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3 text-center">
                                    <LinkIcon className="h-5 w-5 mx-auto text-purple-600 mb-1" />
                                    <p className="text-lg font-semibold">{stats.inferences || 0}</p>
                                    <p className="text-xs text-muted-foreground">Inferred</p>
                                </div>
                            </div>

                            {/* Risk Alert */}
                            {stats.highRiskConnections > 0 && (
                                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                                    <div className="flex items-center gap-2">
                                        <AlertTriangle className="h-5 w-5 text-red-600" />
                                        <span className="font-medium text-red-800 dark:text-red-200">
                                            {stats.highRiskConnections} High-Risk Items
                                        </span>
                                    </div>
                                    <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                                        Review breach records and exposed credentials
                                    </p>
                                </div>
                            )}

                            <Separator />

                            {/* Nodes by Type */}
                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground mb-3">
                                    Entities by Type
                                </h4>
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {Object.entries(stats.nodesByType)
                                        .sort((a, b) => b[1] - a[1])
                                        .map(([type, count]) => {
                                            const typeConfig = nodeTypeConfig[type] || nodeTypeConfig.User;
                                            const TypeIcon = typeConfig.icon;
                                            const color = nodeColors[type] || '#888888';
                                            return (
                                                <div
                                                    key={type}
                                                    className="flex items-center justify-between py-2 px-3 rounded-md bg-zinc-50 dark:bg-zinc-900"
                                                >
                                                    <div className="flex items-center gap-2">
                                                        <span
                                                            className="w-3 h-3 rounded-full"
                                                            style={{ backgroundColor: color }}
                                                        />
                                                        <span className="text-sm font-medium">{type}</span>
                                                    </div>
                                                    <Badge variant="secondary">{count}</Badge>
                                                </div>
                                            );
                                        })}
                                </div>
                            </div>

                            {/* Capabilities Info */}
                            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                                <h4 className="font-medium text-blue-800 dark:text-blue-200 mb-2 flex items-center gap-2">
                                    <Eye className="h-4 w-4" />
                                    What Can This System Do?
                                </h4>
                                <ul className="text-xs text-blue-700 dark:text-blue-300 space-y-1">
                                    <li>• <strong>ONSIT Discovery:</strong> Find your public digital footprint</li>
                                    <li>• <strong>Breach Detection:</strong> Check if your data was exposed</li>
                                    <li>• <strong>GDPR Analysis:</strong> Extract entities from SAR responses</li>
                                    <li>• <strong>AI Inference:</strong> Discover hidden connections</li>
                                    <li>• <strong>Risk Assessment:</strong> Identify privacy threats</li>
                                </ul>
                            </div>

                            {/* Last Updated */}
                            <p className="text-xs text-muted-foreground text-center flex items-center justify-center gap-1">
                                <Clock className="h-3 w-3" />
                                Updated: {new Date(stats.lastUpdated).toLocaleString()}
                            </p>
                        </div>
                    ) : (
                        <div className="text-center py-8">
                            <p className="text-muted-foreground">Click a node to inspect</p>
                        </div>
                    )}
                </CardContent>
            </Card>
        );
    }

    // ==========================================================================
    // Selected Node View
    // ==========================================================================

    return (
        <Card className="h-full flex flex-col border-l rounded-none" role="region" aria-label={`Details for ${selectedNode.label}`}>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div
                            className={`p-2 rounded-lg`}
                            style={{ backgroundColor: `${nodeColors[selectedNode.type]}20` }}
                        >
                            <Icon
                                className="h-5 w-5"
                                style={{ color: nodeColors[selectedNode.type] }}
                            />
                        </div>
                        <div>
                            <CardTitle className="text-lg">{selectedNode.label}</CardTitle>
                            <div className="flex items-center gap-2 mt-1">
                                <Badge variant="outline" className="text-xs">
                                    {selectedNode.type}
                                </Badge>
                                {selectedNode.source && (
                                    <SourceBadge source={selectedNode.source} />
                                )}
                            </div>
                        </div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close inspector">
                        <X className="h-4 w-4" />
                    </Button>
                </div>
            </CardHeader>

            <ScrollArea className="flex-1">
                <CardContent className="space-y-5">
                    {/* Risk Level & Confidence */}
                    {(selectedNode.riskLevel || selectedNode.confidence !== undefined) && (
                        <div className="space-y-3">
                            {selectedNode.riskLevel && selectedNode.riskLevel !== 'low' && (
                                <RiskBadge level={selectedNode.riskLevel} />
                            )}
                            {selectedNode.confidence !== undefined && (
                                <ConfidenceGauge confidence={selectedNode.confidence} />
                            )}
                        </div>
                    )}

                    {/* Type Description */}
                    {config?.description && (
                        <p className="text-sm text-muted-foreground italic">
                            {config.description}
                        </p>
                    )}

                    <Separator />

                    {/* Properties */}
                    <div>
                        <h4 className="text-sm font-medium text-muted-foreground mb-3">Properties</h4>
                        <div className="space-y-2 bg-zinc-50 dark:bg-zinc-900 rounded-lg p-3">
                            {Object.entries(selectedNode.properties).map(([key, value]) => (
                                <div key={key} className="flex justify-between text-sm gap-2">
                                    <span className="text-muted-foreground capitalize">
                                        {key.replace(/_/g, ' ')}
                                    </span>
                                    <span className="font-medium truncate max-w-[180px] text-right">
                                        {typeof value === 'boolean' ? (
                                            value ? <CheckCircle2 className="h-4 w-4 text-green-500" /> : '—'
                                        ) : (
                                            String(value)
                                        )}
                                    </span>
                                </div>
                            ))}
                            {Object.keys(selectedNode.properties).length === 0 && (
                                <p className="text-sm text-muted-foreground">No properties available</p>
                            )}
                        </div>
                    </div>

                    <Separator />

                    {/* Evidence Section (LangExtract grounding pattern) */}
                    <div>
                        <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                            <FileText className="h-4 w-4" />
                            Evidence
                        </h4>
                        {selectedNode.evidenceLinks && selectedNode.evidenceLinks.length > 0 ? (
                            <div className="space-y-2">
                                {selectedNode.evidenceLinks.map((evidence, idx) => (
                                    <a
                                        key={idx}
                                        href={evidence.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="block p-3 bg-zinc-50 dark:bg-zinc-900 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors group"
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate group-hover:text-primary">
                                                    {evidence.title}
                                                </p>
                                                {evidence.snippet && (
                                                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                                        "{evidence.snippet}"
                                                    </p>
                                                )}
                                            </div>
                                            <ExternalLink className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                                        </div>
                                        <div className="flex items-center gap-2 mt-2">
                                            <Progress value={evidence.confidence * 100} className="h-1 flex-1" />
                                            <span className="text-xs text-muted-foreground">
                                                {Math.round(evidence.confidence * 100)}%
                                            </span>
                                        </div>
                                    </a>
                                ))}
                            </div>
                        ) : (
                            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
                                <p className="text-sm text-amber-700 dark:text-amber-300">
                                    {selectedNode.source === 'onsit'
                                        ? 'Evidence collected during ONSIT scan'
                                        : selectedNode.source === 'inference'
                                            ? 'AI-inferred relationship (no direct evidence)'
                                            : 'Upload GDPR PDFs to link evidence'
                                    }
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Discovery Path (for ONSIT nodes) */}
                    {selectedNode.discoveryPath && selectedNode.discoveryPath.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                                    <Globe className="h-4 w-4" />
                                    Discovery Path
                                </h4>
                                <div className="space-y-2">
                                    {selectedNode.discoveryPath.map((step, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-start gap-3 text-sm"
                                        >
                                            <div className="flex flex-col items-center">
                                                <div className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-medium">
                                                    {step.step}
                                                </div>
                                                {idx < selectedNode.discoveryPath!.length - 1 && (
                                                    <div className="w-0.5 h-4 bg-zinc-200 dark:bg-zinc-700 mt-1" />
                                                )}
                                            </div>
                                            <div className="flex-1 pb-2">
                                                <p className="font-medium">{step.action}</p>
                                                <p className="text-xs text-muted-foreground">{step.result}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}

                    <Separator />

                    {/* Actions */}
                    <div className="space-y-2">
                        <h4 className="text-sm font-medium text-muted-foreground mb-3">Actions</h4>

                        <TooltipProvider>
                            <div className="grid grid-cols-2 gap-2">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full justify-start gap-2"
                                            onClick={() => onMerge(selectedNode.id)}
                                        >
                                            <GitMerge className="h-4 w-4" />
                                            Merge
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Merge with another similar node</p>
                                    </TooltipContent>
                                </Tooltip>

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full justify-start gap-2"
                                            onClick={() => onFlag(selectedNode.id)}
                                        >
                                            <Flag className="h-4 w-4" />
                                            Flag
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Flag as potentially incorrect</p>
                                    </TooltipContent>
                                </Tooltip>

                                {onRevalidate && selectedNode.source === 'inference' && (
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="w-full justify-start gap-2"
                                                onClick={() => onRevalidate(selectedNode.id)}
                                            >
                                                <RefreshCw className="h-4 w-4" />
                                                Re-validate
                                            </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                            <p>Run MAKGED validation again</p>
                                        </TooltipContent>
                                    </Tooltip>
                                )}

                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full justify-start gap-2 text-red-600 hover:text-red-700 hover:bg-red-50"
                                            onClick={() => onDelete(selectedNode.id)}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                            Delete
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Remove this node from the graph</p>
                                    </TooltipContent>
                                </Tooltip>
                            </div>
                        </TooltipProvider>
                    </div>

                    {/* Discovery Timestamp */}
                    {selectedNode.discoveredAt && (
                        <p className="text-xs text-muted-foreground text-center flex items-center justify-center gap-1 pt-2">
                            <Clock className="h-3 w-3" />
                            Discovered: {new Date(selectedNode.discoveredAt).toLocaleString()}
                        </p>
                    )}
                </CardContent>
            </ScrollArea>
        </Card>
    );
}
