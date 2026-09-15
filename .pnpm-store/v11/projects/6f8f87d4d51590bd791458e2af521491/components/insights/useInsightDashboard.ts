'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
    fetchInsightModule, type InsightModule, type InsightModuleResponseMap,
} from '@/lib/insights/client';
import {
    parseInsightSelection, selectionsEqual, serializeInsightSelection,
    type InsightTemporalSelection,
} from '@/lib/insights/query';

const MODULES: InsightModule[] = ['overview', 'interests', 'search', 'ai-conversations', 'places', 'changes', 'context'];

export type InsightDashboardData = Partial<{
    [K in InsightModule]: InsightModuleResponseMap[K]
}>;

export function useInsightDashboard(initialNow: string) {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const searchParamsKey = searchParams.toString();
    const subjectId = searchParams.get('subject_id') || undefined;
    // Defaults include the current instant. Keep that instant stable until the
    // URL changes, otherwise every completed request produces a new key and
    // immediately starts another seven-module refresh.
    const selection = useMemo(
        () => parseInsightSelection(new URLSearchParams(searchParamsKey), new Date(initialNow)),
        [initialNow, searchParamsKey],
    );
    const selectionKey = serializeInsightSelection(selection, subjectId).toString();
    const [data, setData] = useState<InsightDashboardData>({});
    const [errors, setErrors] = useState<Partial<Record<InsightModule, string>>>({});
    const [loadedKey, setLoadedKey] = useState<string | null>(null);
    const [reloadKey, setReloadKey] = useState(0);
    const requestKey = `${selectionKey}:${reloadKey}`;

    useEffect(() => {
        const controller = new AbortController();
        const tasks = MODULES.map(async module => {
            try {
                const moduleData = await fetchInsightModule(module, selection, subjectId, controller.signal);
                if (controller.signal.aborted) return;
                setData(current => ({ ...current, [module]: moduleData }));
                setErrors(current => {
                    if (!(module in current)) return current;
                    const next = { ...current };
                    delete next[module];
                    return next;
                });
            } catch (error) {
                if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return;
                setErrors(current => ({
                    ...current,
                    [module]: error instanceof Error ? error.message : 'Module unavailable',
                }));
            }
        });
        Promise.allSettled(tasks).then(() => {
            if (!controller.signal.aborted) setLoadedKey(requestKey);
        });
        return () => controller.abort();
        // selectionKey is the canonical serialization of the whole selection.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [requestKey]);

    const setSelection = useCallback((next: InsightTemporalSelection) => {
        if (selectionsEqual(selection, next)) return;
        const query = serializeInsightSelection(next, subjectId);
        router.replace(`${pathname}?${query.toString()}`, { scroll: false });
    }, [pathname, router, selection, subjectId]);

    return {
        selection, setSelection, subjectId, data, errors, loading: loadedKey !== requestKey,
        retry: useCallback(() => setReloadKey(value => value + 1), []),
    };
}
