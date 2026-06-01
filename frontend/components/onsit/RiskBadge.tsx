'use client';

/**
 * RiskBadge Component
 * 
 * Reusable risk level indicator badge with consistent styling.
 * Used throughout ONSIT findings, graph nodes, and inspector.
 */

import { AlertTriangle, Shield, AlertCircle, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical' | 'unknown';

interface RiskBadgeProps {
    level: RiskLevel;
    showIcon?: boolean;
    showLabel?: boolean;
    size?: 'sm' | 'md' | 'lg';
    className?: string;
}

const riskConfig: Record<RiskLevel, {
    label: string;
    icon: React.ElementType;
    bgColor: string;
    textColor: string;
    borderColor: string;
}> = {
    low: {
        label: 'Low',
        icon: Shield,
        bgColor: 'bg-green-100 dark:bg-green-900/30',
        textColor: 'text-green-700 dark:text-green-300',
        borderColor: 'border-green-200 dark:border-green-800',
    },
    medium: {
        label: 'Medium',
        icon: AlertCircle,
        bgColor: 'bg-yellow-100 dark:bg-yellow-900/30',
        textColor: 'text-yellow-700 dark:text-yellow-300',
        borderColor: 'border-yellow-200 dark:border-yellow-800',
    },
    high: {
        label: 'High',
        icon: AlertTriangle,
        bgColor: 'bg-orange-100 dark:bg-orange-900/30',
        textColor: 'text-orange-700 dark:text-orange-300',
        borderColor: 'border-orange-200 dark:border-orange-800',
    },
    critical: {
        label: 'Critical',
        icon: XCircle,
        bgColor: 'bg-red-100 dark:bg-red-900/30',
        textColor: 'text-red-700 dark:text-red-300',
        borderColor: 'border-red-200 dark:border-red-800',
    },
    unknown: {
        label: 'Unknown',
        icon: AlertCircle,
        bgColor: 'bg-zinc-100 dark:bg-zinc-800',
        textColor: 'text-zinc-600 dark:text-zinc-400',
        borderColor: 'border-zinc-200 dark:border-zinc-700',
    },
};

const sizeClasses = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-sm px-2 py-0.5',
    lg: 'text-base px-3 py-1',
};

const iconSizes = {
    sm: 'h-3 w-3',
    md: 'h-3.5 w-3.5',
    lg: 'h-4 w-4',
};

export function RiskBadge({
    level,
    showIcon = true,
    showLabel = true,
    size = 'md',
    className,
}: RiskBadgeProps) {
    const config = riskConfig[level] || riskConfig.unknown;
    const Icon = config.icon;

    return (
        <Badge
            variant="outline"
            className={cn(
                config.bgColor,
                config.textColor,
                config.borderColor,
                sizeClasses[size],
                'font-medium inline-flex items-center gap-1',
                className
            )}
            role="status"
            aria-label={`Risk level: ${config.label}`}
        >
            {showIcon && <Icon className={iconSizes[size]} />}
            {showLabel && <span>{config.label}</span>}
        </Badge>
    );
}

// Utility function to determine risk level from various inputs
export function determineRiskLevel(input: {
    breachCount?: number;
    credentialExposed?: boolean;
    publicDocuments?: number;
    dataCategories?: string[];
}): RiskLevel {
    // Critical: credentials exposed or in multiple breaches
    if (input.credentialExposed || (input.breachCount && input.breachCount >= 3)) {
        return 'critical';
    }

    // High: in breaches or sensitive categories
    if (input.breachCount && input.breachCount >= 1) {
        return 'high';
    }

    const sensitiveCategories = ['health', 'financial', 'biometric', 'location'];
    if (input.dataCategories?.some(cat => sensitiveCategories.includes(cat.toLowerCase()))) {
        return 'high';
    }

    // Medium: public documents or moderate exposure
    if (input.publicDocuments && input.publicDocuments >= 2) {
        return 'medium';
    }

    return 'low';
}
