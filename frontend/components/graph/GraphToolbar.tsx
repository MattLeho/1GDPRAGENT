'use client';

/**
 * GraphToolbar Component
 * 
 * Provides comprehensive filtering and control for the Data Graph visualization.
 * Features layer toggles, node type filtering, date range, and view controls.
 * 
 * Following Flowsint UI patterns for OSINT investigation workflows.
 */

import { useState } from 'react';
import {
    Eye,
    EyeOff,
    Filter,
    Layers,
    ZoomIn,
    Calendar,
    AlertTriangle,
    ChevronDown,
    Search,
    Globe,
    FileText,
    RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

export interface GraphFilters {
    showONSIT: boolean;
    showGDPR: boolean;
    showInferences: boolean;
    selectedTypes: string[];
    riskLevel: 'all' | 'low' | 'medium' | 'high' | 'critical';
    dateFrom?: Date;
    dateTo?: Date;
}

export interface GraphToolbarProps {
    filters: GraphFilters;
    onFiltersChange: (filters: GraphFilters) => void;
    availableTypes: string[];
    onZoomToFit: () => void;
    onReset: () => void;
    nodeCount: number;
    linkCount: number;
}

// =============================================================================
// Node Type Configuration (matching GraphCanvas)
// =============================================================================

const nodeTypeConfig: Record<string, { label: string; category: 'onsit' | 'gdpr' | 'core' }> = {
    // Core types
    User: { label: 'User', category: 'core' },
    Persona: { label: 'Persona', category: 'core' },

    // GDPR types
    Company: { label: 'Company', category: 'gdpr' },
    Account: { label: 'Account', category: 'gdpr' },
    Attribute: { label: 'Attribute', category: 'gdpr' },
    DataPoint: { label: 'Data Point', category: 'gdpr' },

    // ONSIT types
    ONSITFinding: { label: 'ONSIT Finding', category: 'onsit' },
    SocialProfile: { label: 'Social Profile', category: 'onsit' },
    BreachRecord: { label: 'Breach Record', category: 'onsit' },
    PublicDocument: { label: 'Public Document', category: 'onsit' },
    CryptoWallet: { label: 'Crypto Wallet', category: 'onsit' },
    Credential: { label: 'Credential', category: 'onsit' },
    Domain: { label: 'Domain', category: 'onsit' },
    IP: { label: 'IP Address', category: 'onsit' },

    // Inference
    Inference: { label: 'Inference', category: 'core' },
    Email: { label: 'Email', category: 'core' },
};

// =============================================================================
// Component
// =============================================================================

export function GraphToolbar({
    filters,
    onFiltersChange,
    availableTypes,
    onZoomToFit,
    onReset,
    nodeCount,
    linkCount,
}: GraphToolbarProps) {
    const [layerPopoverOpen, setLayerPopoverOpen] = useState(false);
    const [typePopoverOpen, setTypePopoverOpen] = useState(false);

    // Count active filters
    const activeFilterCount = [
        !filters.showONSIT || !filters.showGDPR || !filters.showInferences ? 1 : 0,
        filters.selectedTypes.length < availableTypes.length ? 1 : 0,
        filters.riskLevel !== 'all' ? 1 : 0,
        filters.dateFrom || filters.dateTo ? 1 : 0,
    ].reduce((a, b) => a + b, 0);

    const updateFilter = <K extends keyof GraphFilters>(key: K, value: GraphFilters[K]) => {
        onFiltersChange({ ...filters, [key]: value });
    };

    const toggleType = (type: string) => {
        const newTypes = filters.selectedTypes.includes(type)
            ? filters.selectedTypes.filter(t => t !== type)
            : [...filters.selectedTypes, type];
        updateFilter('selectedTypes', newTypes);
    };

    const selectAllTypes = () => {
        updateFilter('selectedTypes', [...availableTypes]);
    };

    const clearAllTypes = () => {
        updateFilter('selectedTypes', []);
    };

    return (
        <div className="flex items-center gap-2 flex-wrap" role="toolbar" aria-label="Graph controls">
            {/* Layer Toggles */}
            <Popover open={layerPopoverOpen} onOpenChange={setLayerPopoverOpen}>
                <PopoverTrigger asChild>
                    <Button
                        variant="outline"
                        size="sm"
                        className="gap-2 h-9"
                        aria-label="Layer visibility controls"
                    >
                        <Layers className="h-4 w-4" />
                        Layers
                        <ChevronDown className="h-3 w-3 opacity-50" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent className="w-72" align="start">
                    <div className="space-y-4">
                        <h4 className="font-medium text-sm">Data Layers</h4>
                        <p className="text-xs text-muted-foreground">
                            Toggle visibility of different data sources
                        </p>

                        <Separator />

                        {/* ONSIT Layer */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-orange-100">
                                    <Search className="h-4 w-4 text-orange-600" />
                                </div>
                                <div>
                                    <Label htmlFor="onsit-toggle" className="font-medium">
                                        ONSIT Discoveries
                                    </Label>
                                    <p className="text-xs text-muted-foreground">
                                        Public web findings
                                    </p>
                                </div>
                            </div>
                            <Switch
                                id="onsit-toggle"
                                checked={filters.showONSIT}
                                onCheckedChange={(checked) => updateFilter('showONSIT', checked)}
                                aria-label="Show ONSIT discoveries"
                            />
                        </div>

                        {/* GDPR Layer */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-green-100">
                                    <FileText className="h-4 w-4 text-green-600" />
                                </div>
                                <div>
                                    <Label htmlFor="gdpr-toggle" className="font-medium">
                                        GDPR Data
                                    </Label>
                                    <p className="text-xs text-muted-foreground">
                                        From SAR responses
                                    </p>
                                </div>
                            </div>
                            <Switch
                                id="gdpr-toggle"
                                checked={filters.showGDPR}
                                onCheckedChange={(checked) => updateFilter('showGDPR', checked)}
                                aria-label="Show GDPR data"
                            />
                        </div>

                        {/* Inferences Layer */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-purple-100">
                                    <Globe className="h-4 w-4 text-purple-600" />
                                </div>
                                <div>
                                    <Label htmlFor="inference-toggle" className="font-medium">
                                        AI Inferences
                                    </Label>
                                    <p className="text-xs text-muted-foreground">
                                        Relationship predictions
                                    </p>
                                </div>
                            </div>
                            <Switch
                                id="inference-toggle"
                                checked={filters.showInferences}
                                onCheckedChange={(checked) => updateFilter('showInferences', checked)}
                                aria-label="Show AI inferences"
                            />
                        </div>
                    </div>
                </PopoverContent>
            </Popover>

            {/* Node Type Filter */}
            <Popover open={typePopoverOpen} onOpenChange={setTypePopoverOpen}>
                <PopoverTrigger asChild>
                    <Button
                        variant="outline"
                        size="sm"
                        className="gap-2 h-9"
                        aria-label="Filter by node type"
                    >
                        <Filter className="h-4 w-4" />
                        Types
                        {filters.selectedTypes.length < availableTypes.length && (
                            <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                                {filters.selectedTypes.length}
                            </Badge>
                        )}
                        <ChevronDown className="h-3 w-3 opacity-50" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80" align="start">
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h4 className="font-medium text-sm">Node Types</h4>
                            <div className="flex gap-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2 text-xs"
                                    onClick={selectAllTypes}
                                >
                                    All
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2 text-xs"
                                    onClick={clearAllTypes}
                                >
                                    None
                                </Button>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto">
                            {availableTypes.map(type => {
                                const config = nodeTypeConfig[type];
                                const isSelected = filters.selectedTypes.includes(type);
                                return (
                                    <button
                                        key={type}
                                        onClick={() => toggleType(type)}
                                        className={cn(
                                            "flex items-center gap-2 p-2 rounded-md text-left text-sm transition-colors",
                                            isSelected
                                                ? "bg-primary/10 border border-primary/30"
                                                : "bg-zinc-50 dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                                        )}
                                        aria-pressed={isSelected}
                                    >
                                        <div className={cn(
                                            "w-3 h-3 rounded-full border-2",
                                            isSelected ? "bg-primary border-primary" : "border-zinc-300"
                                        )} />
                                        <span className="truncate">
                                            {config?.label || type}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </PopoverContent>
            </Popover>

            {/* Risk Level Filter */}
            <Select
                value={filters.riskLevel}
                onValueChange={(value) => updateFilter('riskLevel', value as GraphFilters['riskLevel'])}
            >
                <SelectTrigger className="w-[130px] h-9" aria-label="Filter by risk level">
                    <AlertTriangle className="h-3.5 w-3.5 mr-1.5 opacity-50" />
                    <SelectValue placeholder="Risk" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Risks</SelectItem>
                    <SelectItem value="low">
                        <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500" />
                            Low
                        </span>
                    </SelectItem>
                    <SelectItem value="medium">
                        <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-yellow-500" />
                            Medium
                        </span>
                    </SelectItem>
                    <SelectItem value="high">
                        <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-orange-500" />
                            High
                        </span>
                    </SelectItem>
                    <SelectItem value="critical">
                        <span className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-red-500" />
                            Critical
                        </span>
                    </SelectItem>
                </SelectContent>
            </Select>

            <Separator orientation="vertical" className="h-6" />

            {/* View Controls */}
            <Button
                variant="outline"
                size="sm"
                onClick={onZoomToFit}
                className="gap-2 h-9"
                aria-label="Zoom to fit all nodes"
            >
                <ZoomIn className="h-4 w-4" />
                Fit
            </Button>

            <Button
                variant="ghost"
                size="sm"
                onClick={onReset}
                className="gap-2 h-9"
                aria-label="Reset all filters"
            >
                <RotateCcw className="h-4 w-4" />
                Reset
            </Button>

            {/* Stats Badge */}
            <div className="ml-auto flex items-center gap-2">
                {activeFilterCount > 0 && (
                    <Badge variant="secondary" className="text-xs">
                        {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''} active
                    </Badge>
                )}
                <Badge variant="outline" className="text-xs font-normal">
                    {nodeCount} nodes • {linkCount} links
                </Badge>
            </div>
        </div>
    );
}

// =============================================================================
// Default Filters Export
// =============================================================================

export const defaultGraphFilters: GraphFilters = {
    showONSIT: true,
    showGDPR: true,
    showInferences: true,
    selectedTypes: [],
    riskLevel: 'all',
};
