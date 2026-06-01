'use client';

/**
 * FindingCard Component
 * 
 * Individual finding card displaying discovered information with
 * risk level, source, and actions.
 * 
 * Following Flowsint entity display patterns.
 */

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    User,
    Globe,
    AlertTriangle,
    ExternalLink,
    GitGraph,
    Trash2,
    Mail,
    Key,
    Wallet,
    FileText,
    Server,
    Hash,
} from 'lucide-react';
import { RiskBadge, RiskLevel } from './RiskBadge';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

export type FindingType =
    | 'SocialProfile'
    | 'BreachRecord'
    | 'PublicDocument'
    | 'CryptoWallet'
    | 'Credential'
    | 'Domain'
    | 'IP'
    | 'Username'
    | 'Email'
    | 'Generic';

export interface Finding {
    id: string;
    type: FindingType;
    title: string;
    description: string;
    sourceUrl?: string;
    sourcePlatform: string;
    riskLevel: RiskLevel;
    confidence: number;
    discoveredAt: string;
    metadata: Record<string, unknown>;
    addedToGraph?: boolean;
}

interface FindingCardProps {
    finding: Finding;
    onViewInGraph: (finding: Finding) => void;
    onDismiss: (finding: Finding) => void;
    onAddToGraph?: (finding: Finding) => void;
    compact?: boolean;
}

// =============================================================================
// Type Configuration
// =============================================================================

const typeConfig: Record<FindingType, {
    icon: React.ElementType;
    color: string;
    bgColor: string;
    label: string;
}> = {
    SocialProfile: {
        icon: User,
        color: 'text-pink-600',
        bgColor: 'bg-pink-100',
        label: 'Social Profile',
    },
    BreachRecord: {
        icon: AlertTriangle,
        color: 'text-red-600',
        bgColor: 'bg-red-100',
        label: 'Data Breach',
    },
    PublicDocument: {
        icon: FileText,
        color: 'text-purple-600',
        bgColor: 'bg-purple-100',
        label: 'Public Document',
    },
    CryptoWallet: {
        icon: Wallet,
        color: 'text-indigo-600',
        bgColor: 'bg-indigo-100',
        label: 'Crypto Wallet',
    },
    Credential: {
        icon: Key,
        color: 'text-red-700',
        bgColor: 'bg-red-200',
        label: 'Credential',
    },
    Domain: {
        icon: Globe,
        color: 'text-sky-600',
        bgColor: 'bg-sky-100',
        label: 'Domain',
    },
    IP: {
        icon: Server,
        color: 'text-teal-600',
        bgColor: 'bg-teal-100',
        label: 'IP Address',
    },
    Username: {
        icon: Hash,
        color: 'text-violet-600',
        bgColor: 'bg-violet-100',
        label: 'Username',
    },
    Email: {
        icon: Mail,
        color: 'text-pink-600',
        bgColor: 'bg-pink-100',
        label: 'Email',
    },
    Generic: {
        icon: Globe,
        color: 'text-orange-600',
        bgColor: 'bg-orange-100',
        label: 'Finding',
    },
};

// =============================================================================
// Component
// =============================================================================

export function FindingCard({
    finding,
    onViewInGraph,
    onDismiss,
    onAddToGraph,
    compact = false,
}: FindingCardProps) {
    const config = typeConfig[finding.type] || typeConfig.Generic;
    const Icon = config.icon;

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    if (compact) {
        return (
            <div className={cn(
                "flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors",
                finding.riskLevel === 'critical' && "border-red-200 bg-red-50/50 dark:bg-red-900/10",
                finding.riskLevel === 'high' && "border-orange-200 bg-orange-50/50 dark:bg-orange-900/10",
            )}>
                <div className={cn("p-2 rounded-lg", config.bgColor)}>
                    <Icon className={cn("h-4 w-4", config.color)} />
                </div>
                <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{finding.title}</p>
                    <p className="text-xs text-muted-foreground truncate">
                        {finding.sourcePlatform}
                    </p>
                </div>
                <RiskBadge level={finding.riskLevel} showLabel={false} size="sm" />
            </div>
        );
    }

    return (
        <Card className={cn(
            "overflow-hidden transition-shadow hover:shadow-md",
            finding.riskLevel === 'critical' && "border-red-200 dark:border-red-800",
            finding.riskLevel === 'high' && "border-orange-200 dark:border-orange-800",
        )}>
            <CardContent className="p-4 space-y-4">
                {/* Header */}
                <div className="flex items-start gap-3">
                    <div className={cn("p-2.5 rounded-lg", config.bgColor)}>
                        <Icon className={cn("h-5 w-5", config.color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-semibold text-sm truncate">
                                {finding.title}
                            </h3>
                            <RiskBadge level={finding.riskLevel} size="sm" />
                        </div>
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                            {finding.description}
                        </p>
                    </div>
                </div>

                {/* Metadata */}
                <div className="flex items-center gap-3 flex-wrap text-xs text-muted-foreground">
                    <Badge variant="outline" className="gap-1">
                        {config.label}
                    </Badge>
                    <span className="flex items-center gap-1">
                        <Globe className="h-3 w-3" />
                        {finding.sourcePlatform}
                    </span>
                    <span>•</span>
                    <span>{formatDate(finding.discoveredAt)}</span>
                    <span>•</span>
                    <span>{Math.round(finding.confidence * 100)}% confidence</span>
                </div>

                {/* Key Metadata Values */}
                {Object.keys(finding.metadata).length > 0 && (
                    <div className="bg-zinc-50 dark:bg-zinc-900 rounded-lg p-3 space-y-1.5">
                        {Object.entries(finding.metadata).slice(0, 4).map(([key, value]) => (
                            <div key={key} className="flex justify-between text-xs gap-2">
                                <span className="text-muted-foreground capitalize">
                                    {key.replace(/_/g, ' ')}
                                </span>
                                <span className="font-medium truncate max-w-[200px]">
                                    {String(value)}
                                </span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2 pt-2">
                    {finding.addedToGraph ? (
                        <Button
                            variant="default"
                            size="sm"
                            className="gap-1.5"
                            onClick={() => onViewInGraph(finding)}
                        >
                            <GitGraph className="h-4 w-4" />
                            View in Graph
                        </Button>
                    ) : onAddToGraph && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="gap-1.5"
                            onClick={() => onAddToGraph(finding)}
                        >
                            <GitGraph className="h-4 w-4" />
                            Add to Graph
                        </Button>
                    )}
                    {finding.sourceUrl && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="gap-1.5"
                            asChild
                        >
                            <a href={finding.sourceUrl} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="h-4 w-4" />
                                View Source
                            </a>
                        </Button>
                    )}
                    <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1.5 ml-auto text-muted-foreground hover:text-red-600"
                        onClick={() => onDismiss(finding)}
                    >
                        <Trash2 className="h-4 w-4" />
                        Dismiss
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
