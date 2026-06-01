'use client';

/**
 * FindingsList Component
 * 
 * Grid display of ONSIT findings with filtering, sorting, and bulk actions.
 * Supports grid/list view toggle.
 */

import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    LayoutGrid,
    List,
    Search,
    Filter,
    GitGraph,
    AlertTriangle,
    TrendingUp,
    Inbox,
} from 'lucide-react';
import { FindingCard, Finding, FindingType } from './FindingCard';
import { RiskLevel } from './RiskBadge';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

type SortOption = 'date' | 'risk' | 'type' | 'confidence';
type ViewMode = 'grid' | 'list';

interface FindingsListProps {
    findings: Finding[];
    onViewInGraph: (finding: Finding) => void;
    onDismiss: (finding: Finding) => void;
    onAddToGraph?: (finding: Finding) => void;
    onBulkAddToGraph?: (findings: Finding[]) => void;
    isLoading?: boolean;
}

// =============================================================================
// Risk Level Priority for Sorting
// =============================================================================

const riskPriority: Record<RiskLevel, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
    unknown: 0,
};

// =============================================================================
// Component
// =============================================================================

export function FindingsList({
    findings,
    onViewInGraph,
    onDismiss,
    onAddToGraph,
    onBulkAddToGraph,
    isLoading = false,
}: FindingsListProps) {
    const [viewMode, setViewMode] = useState<ViewMode>('grid');
    const [sortBy, setSortBy] = useState<SortOption>('risk');
    const [filterRisk, setFilterRisk] = useState<RiskLevel | 'all'>('all');
    const [filterType, setFilterType] = useState<FindingType | 'all'>('all');
    const [searchQuery, setSearchQuery] = useState('');

    // Get unique types from findings
    const availableTypes = useMemo(() => {
        const types = new Set(findings.map(f => f.type));
        return Array.from(types);
    }, [findings]);

    // Filter and sort findings
    const processedFindings = useMemo(() => {
        let result = [...findings];

        // Search filter
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            result = result.filter(f =>
                f.title.toLowerCase().includes(query) ||
                f.description.toLowerCase().includes(query) ||
                f.sourcePlatform.toLowerCase().includes(query)
            );
        }

        // Risk filter
        if (filterRisk !== 'all') {
            result = result.filter(f => f.riskLevel === filterRisk);
        }

        // Type filter
        if (filterType !== 'all') {
            result = result.filter(f => f.type === filterType);
        }

        // Sort
        result.sort((a, b) => {
            switch (sortBy) {
                case 'date':
                    return new Date(b.discoveredAt).getTime() - new Date(a.discoveredAt).getTime();
                case 'risk':
                    return riskPriority[b.riskLevel] - riskPriority[a.riskLevel];
                case 'type':
                    return a.type.localeCompare(b.type);
                case 'confidence':
                    return b.confidence - a.confidence;
                default:
                    return 0;
            }
        });

        return result;
    }, [findings, searchQuery, filterRisk, filterType, sortBy]);

    // Stats
    const stats = useMemo(() => ({
        total: findings.length,
        critical: findings.filter(f => f.riskLevel === 'critical').length,
        high: findings.filter(f => f.riskLevel === 'high').length,
        notInGraph: findings.filter(f => !f.addedToGraph).length,
    }), [findings]);

    // Get findings not yet in graph
    const findingsNotInGraph = findings.filter(f => !f.addedToGraph);

    return (
        <Card>
            <CardHeader className="pb-4">
                <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-3">
                        <CardTitle className="text-lg">Findings</CardTitle>
                        <Badge variant="secondary">{stats.total}</Badge>
                        {stats.critical > 0 && (
                            <Badge variant="destructive" className="gap-1">
                                <AlertTriangle className="h-3 w-3" />
                                {stats.critical} Critical
                            </Badge>
                        )}
                    </div>

                    {/* Bulk Actions */}
                    {onBulkAddToGraph && stats.notInGraph > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="gap-1.5"
                            onClick={() => onBulkAddToGraph(findingsNotInGraph)}
                        >
                            <GitGraph className="h-4 w-4" />
                            Add All to Graph ({stats.notInGraph})
                        </Button>
                    )}
                </div>

                {/* Filters Row */}
                <div className="flex items-center gap-3 flex-wrap mt-4">
                    {/* Search */}
                    <div className="relative flex-1 min-w-[200px]">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search findings..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-9"
                        />
                    </div>

                    {/* Risk Filter */}
                    <Select value={filterRisk} onValueChange={(v) => setFilterRisk(v as RiskLevel | 'all')}>
                        <SelectTrigger className="w-[130px]">
                            <Filter className="h-3.5 w-3.5 mr-1.5 opacity-50" />
                            <SelectValue placeholder="Risk" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Risks</SelectItem>
                            <SelectItem value="critical">
                                <span className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-red-500" />
                                    Critical
                                </span>
                            </SelectItem>
                            <SelectItem value="high">
                                <span className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-orange-500" />
                                    High
                                </span>
                            </SelectItem>
                            <SelectItem value="medium">
                                <span className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-yellow-500" />
                                    Medium
                                </span>
                            </SelectItem>
                            <SelectItem value="low">
                                <span className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-green-500" />
                                    Low
                                </span>
                            </SelectItem>
                        </SelectContent>
                    </Select>

                    {/* Type Filter */}
                    <Select value={filterType} onValueChange={(v) => setFilterType(v as FindingType | 'all')}>
                        <SelectTrigger className="w-[150px]">
                            <SelectValue placeholder="Type" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Types</SelectItem>
                            {availableTypes.map(type => (
                                <SelectItem key={type} value={type}>
                                    {type.replace(/([A-Z])/g, ' $1').trim()}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Sort */}
                    <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
                        <SelectTrigger className="w-[140px]">
                            <TrendingUp className="h-3.5 w-3.5 mr-1.5 opacity-50" />
                            <SelectValue placeholder="Sort" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="risk">Risk Level</SelectItem>
                            <SelectItem value="date">Date</SelectItem>
                            <SelectItem value="type">Type</SelectItem>
                            <SelectItem value="confidence">Confidence</SelectItem>
                        </SelectContent>
                    </Select>

                    {/* View Toggle */}
                    <div className="flex border rounded-lg overflow-hidden">
                        <Button
                            variant={viewMode === 'grid' ? 'default' : 'ghost'}
                            size="sm"
                            className="rounded-none px-3"
                            onClick={() => setViewMode('grid')}
                            aria-label="Grid view"
                        >
                            <LayoutGrid className="h-4 w-4" />
                        </Button>
                        <Button
                            variant={viewMode === 'list' ? 'default' : 'ghost'}
                            size="sm"
                            className="rounded-none px-3"
                            onClick={() => setViewMode('list')}
                            aria-label="List view"
                        >
                            <List className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </CardHeader>

            <CardContent>
                {/* Loading State */}
                {isLoading && (
                    <div className="flex items-center justify-center py-12">
                        <p className="text-muted-foreground">Loading findings...</p>
                    </div>
                )}

                {/* Empty State */}
                {!isLoading && processedFindings.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <Inbox className="h-12 w-12 text-muted-foreground mb-4" />
                        {findings.length === 0 ? (
                            <>
                                <p className="font-medium">No findings yet</p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Start a discovery to find your digital footprint
                                </p>
                            </>
                        ) : (
                            <>
                                <p className="font-medium">No matching findings</p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Try adjusting your filters
                                </p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="mt-4"
                                    onClick={() => {
                                        setSearchQuery('');
                                        setFilterRisk('all');
                                        setFilterType('all');
                                    }}
                                >
                                    Clear Filters
                                </Button>
                            </>
                        )}
                    </div>
                )}

                {/* Findings Grid/List */}
                {!isLoading && processedFindings.length > 0 && (
                    <div className={cn(
                        viewMode === 'grid'
                            ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
                            : "space-y-2"
                    )}>
                        {processedFindings.map(finding => (
                            <FindingCard
                                key={finding.id}
                                finding={finding}
                                onViewInGraph={onViewInGraph}
                                onDismiss={onDismiss}
                                onAddToGraph={onAddToGraph}
                                compact={viewMode === 'list'}
                            />
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
