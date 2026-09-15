'use client';

/**
 * GraphLegend Component
 * 
 * Interactive legend displaying node type colors and edge styles.
 * Supports click-to-filter functionality for rapid exploration.
 * 
 * Following AI-KG visualization patterns with color-coded communities
 * and Flowsint entity type conventions.
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp, Circle, Minus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

export interface LegendItem {
    type: string;
    label: string;
    color: string;
    count: number;
    category: 'core' | 'gdpr' | 'onsit' | 'inference';
}

export interface GraphLegendProps {
    items: LegendItem[];
    selectedTypes: string[];
    onTypeClick: (type: string) => void;
    showInferences: boolean;
    collapsed?: boolean;
}

// =============================================================================
// Node Color Configuration
// Complete mapping from ONSIT_Graph_Implementation_Plan.md Section 7.3
// =============================================================================

export const nodeColors: Record<string, string> = {
    // Core types (Purple/Blue spectrum)
    User: '#9333ea',          // Purple - The user's identity
    Persona: '#3b82f6',       // Blue - Alternative personas
    Email: '#ec4899',         // Pink - Email addresses

    // GDPR types (Green/Yellow/Cyan spectrum)
    Company: '#22c55e',       // Green - Data controllers
    Account: '#f97316',       // Orange - User accounts  
    Attribute: '#06b6d4',     // Cyan - Data attributes
    DataPoint: '#eab308',     // Yellow - Individual data points

    // ONSIT Discovery types (Orange/Red spectrum - high visibility)
    ONSITFinding: '#fb923c',   // Orange - General findings
    SocialProfile: '#f472b6',  // Pink - Social media profiles
    BreachRecord: '#dc2626',   // Red - Data breach records (HIGH RISK)
    PublicDocument: '#a855f7', // Purple - Publicly accessible documents
    CryptoWallet: '#6366f1',   // Indigo - Cryptocurrency wallets
    Credential: '#b91c1c',     // Dark Red - Exposed credentials (CRITICAL)
    Domain: '#0ea5e9',         // Sky Blue - Domains
    IP: '#14b8a6',             // Teal - IP addresses
    Username: '#8b5cf6',       // Violet - Usernames across platforms
    Phone: '#10b981',          // Emerald - Phone numbers

    // Inference types (Red spectrum - AI-generated)
    Inference: '#ef4444',      // Red - AI inferred relationships
};

// Node size configuration for visual hierarchy
export const nodeSizes: Record<string, number> = {
    User: 24,           // Largest - center of the graph
    Persona: 18,
    Company: 20,        // Large - major data controllers
    Account: 14,
    Attribute: 10,
    DataPoint: 8,
    Email: 12,
    ONSITFinding: 14,
    SocialProfile: 12,
    BreachRecord: 16,   // Larger - important risk indicator
    PublicDocument: 12,
    CryptoWallet: 12,
    Credential: 16,     // Larger - critical risk
    Domain: 12,
    IP: 10,
    Username: 10,
    Phone: 10,
    Inference: 10,
};

// Category labels for grouping
const categoryLabels: Record<string, string> = {
    core: 'Identity',
    gdpr: 'GDPR Data',
    onsit: 'ONSIT Discoveries',
    inference: 'AI Inferences',
};

const categoryColors: Record<string, string> = {
    core: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
    gdpr: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
    onsit: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
    inference: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
};

// =============================================================================
// Component
// =============================================================================

export function GraphLegend({
    items,
    selectedTypes,
    onTypeClick,
    showInferences,
    collapsed: initialCollapsed = false,
}: GraphLegendProps) {
    const [isCollapsed, setIsCollapsed] = useState(initialCollapsed);

    // Group items by category
    const groupedItems = items.reduce((acc, item) => {
        const category = item.category;
        if (!acc[category]) acc[category] = [];
        acc[category].push(item);
        return acc;
    }, {} as Record<string, LegendItem[]>);

    // Sort categories for consistent display
    const categoryOrder = ['core', 'gdpr', 'onsit', 'inference'];
    const sortedCategories = categoryOrder.filter(cat => groupedItems[cat]?.length > 0);

    const totalNodes = items.reduce((sum, item) => sum + item.count, 0);
    const selectedCount = items
        .filter(item => selectedTypes.length === 0 || selectedTypes.includes(item.type))
        .reduce((sum, item) => sum + item.count, 0);

    return (
        <div
            className="bg-white dark:bg-zinc-900 rounded-lg border shadow-sm overflow-hidden"
            role="region"
            aria-label="Graph legend"
        >
            {/* Header */}
            <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className="w-full flex items-center justify-between p-3 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                aria-expanded={!isCollapsed}
            >
                <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">Legend</span>
                    <Badge variant="secondary" className="text-xs">
                        {selectedTypes.length === 0 ? totalNodes : selectedCount} nodes
                    </Badge>
                </div>
                {isCollapsed ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                )}
            </button>

            {/* Content */}
            {!isCollapsed && (
                <div className="p-3 pt-0 space-y-4">
                    {/* Node Types by Category */}
                    {sortedCategories.map(category => (
                        <div key={category} className="space-y-2">
                            <div className="flex items-center gap-2">
                                <Badge
                                    variant="outline"
                                    className={cn("text-xs", categoryColors[category])}
                                >
                                    {categoryLabels[category]}
                                </Badge>
                            </div>
                            <div className="grid grid-cols-2 gap-1">
                                {groupedItems[category].map(item => {
                                    const isSelected = selectedTypes.length === 0 ||
                                        selectedTypes.includes(item.type);
                                    const isHidden = category === 'inference' && !showInferences;

                                    return (
                                        <button
                                            key={item.type}
                                            onClick={() => onTypeClick(item.type)}
                                            disabled={isHidden}
                                            className={cn(
                                                "flex items-center gap-2 px-2 py-1.5 rounded text-left text-xs transition-all",
                                                isSelected && !isHidden
                                                    ? "bg-zinc-100 dark:bg-zinc-800"
                                                    : "opacity-50 hover:opacity-75",
                                                isHidden && "opacity-30 cursor-not-allowed"
                                            )}
                                            aria-pressed={isSelected}
                                            title={`${item.label}: ${item.count} nodes. Click to toggle filter.`}
                                        >
                                            <span
                                                className="w-3 h-3 rounded-full flex-shrink-0 border border-white/20"
                                                style={{ backgroundColor: item.color }}
                                            />
                                            <span className="truncate flex-1">{item.label}</span>
                                            <span className="text-muted-foreground">
                                                {item.count}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    ))}

                    {/* Edge Types Legend */}
                    <div className="pt-2 border-t space-y-2">
                        <span className="text-xs font-medium text-muted-foreground">
                            Relationships
                        </span>
                        <div className="flex flex-col gap-1.5">
                            <div className="flex items-center gap-2 text-xs">
                                <div className="w-8 h-0.5 bg-zinc-400" />
                                <span>Original (from data)</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                <div
                                    className="w-8 h-0.5 border-t-2 border-dashed border-red-400"
                                    style={{ borderStyle: 'dashed' }}
                                />
                                <span className={cn(!showInferences && "opacity-50")}>
                                    Inferred (AI predicted)
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Help Text */}
                    <p className="text-xs text-muted-foreground pt-2 border-t">
                        Click types to filter • Larger nodes are more connected
                    </p>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Utility: Generate legend items from graph data
// =============================================================================

export function generateLegendItems(
    nodes: { type: string }[],
    selectedTypes: string[] = []
): LegendItem[] {
    // Count nodes by type
    const typeCounts = nodes.reduce((acc, node) => {
        acc[node.type] = (acc[node.type] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    // Generate legend items
    return Object.entries(typeCounts).map(([type, count]) => {
        // Determine category
        let category: LegendItem['category'] = 'core';
        const onsitTypes = ['ONSITFinding', 'SocialProfile', 'BreachRecord', 'PublicDocument',
            'CryptoWallet', 'Credential', 'Domain', 'IP', 'Username', 'Phone'];
        const gdprTypes = ['Company', 'Account', 'Attribute', 'DataPoint'];
        const inferenceTypes = ['Inference'];

        if (onsitTypes.includes(type)) category = 'onsit';
        else if (gdprTypes.includes(type)) category = 'gdpr';
        else if (inferenceTypes.includes(type)) category = 'inference';

        // Get label (convert CamelCase to words)
        const label = type.replace(/([A-Z])/g, ' $1').trim();

        return {
            type,
            label,
            color: nodeColors[type] || '#888888',
            count,
            category,
        };
    }).sort((a, b) => b.count - a.count);
}
