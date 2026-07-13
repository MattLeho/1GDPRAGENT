import type { PeriodGranularity, TemporalMode } from './types';

export interface InsightTemporalSelection {
    mode: TemporalMode;
    granularity: PeriodGranularity;
    from?: string;
    to?: string;
    point?: string;
    compareFrom?: string;
    compareTo?: string;
}

function iso(value: string | null): string | undefined {
    if (!value) return undefined;
    const parsed = new Date(value);
    return Number.isNaN(parsed.valueOf()) ? undefined : parsed.toISOString();
}

export function defaultInsightSelection(now = new Date()): InsightTemporalSelection {
    const to = new Date(now);
    const from = new Date(now);
    from.setUTCFullYear(from.getUTCFullYear() - 1);
    return { mode: 'period', granularity: 'month', from: from.toISOString(), to: to.toISOString() };
}

export function parseInsightSelection(params: URLSearchParams, now = new Date()): InsightTemporalSelection {
    const fallback = defaultInsightSelection(now);
    const rawMode = params.get('mode');
    const mode: TemporalMode = rawMode === 'point_in_time' || rawMode === 'compare' ? rawMode : 'period';
    const rawGranularity = params.get('granularity');
    const allowed = new Set<PeriodGranularity>(['day', 'week', 'month', 'quarter', 'year', 'custom']);
    const granularity = allowed.has(rawGranularity as PeriodGranularity) ? rawGranularity as PeriodGranularity : fallback.granularity;
    if (mode === 'point_in_time') {
        return { mode, granularity, point: iso(params.get('point')) || now.toISOString() };
    }
    const from = iso(params.get('from')) || fallback.from;
    const to = iso(params.get('to')) || fallback.to;
    if (mode === 'compare') {
        const duration = new Date(to!).valueOf() - new Date(from!).valueOf();
        const defaultCompareTo = new Date(new Date(from!).valueOf()).toISOString();
        const defaultCompareFrom = new Date(new Date(from!).valueOf() - duration).toISOString();
        return {
            mode, granularity, from, to,
            compareFrom: iso(params.get('compareFrom')) || defaultCompareFrom,
            compareTo: iso(params.get('compareTo')) || defaultCompareTo,
        };
    }
    return { mode, granularity, from, to };
}

export function serializeInsightSelection(selection: InsightTemporalSelection, subjectId?: string): URLSearchParams {
    const params = new URLSearchParams({ mode: selection.mode, granularity: selection.granularity });
    if (subjectId) params.set('subject_id', subjectId);
    if (selection.from) params.set('from', selection.from);
    if (selection.to) params.set('to', selection.to);
    if (selection.point) params.set('point', selection.point);
    if (selection.compareFrom) params.set('compareFrom', selection.compareFrom);
    if (selection.compareTo) params.set('compareTo', selection.compareTo);
    return params;
}

export function selectionsEqual(left: InsightTemporalSelection, right: InsightTemporalSelection): boolean {
    return serializeInsightSelection(left).toString() === serializeInsightSelection(right).toString();
}
