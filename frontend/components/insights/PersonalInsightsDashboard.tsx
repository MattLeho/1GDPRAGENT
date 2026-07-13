'use client';

import { useState } from 'react';
import { ActivityDensityTimeline } from './ActivityDensityTimeline';
import { TemporalControl } from './TemporalControl';
import { useInsightDashboard } from './useInsightDashboard';
import { OverviewEngagement } from './OverviewEngagement';
import { InterestAtlas } from './InterestAtlas';
import { SearchAIInsights } from './SearchAIInsights';
import { PlacesMovement } from './PlacesMovement';
import { ChangesProjectsEras } from './ChangesProjectsEras';
import { ContextCorrelations } from './ContextCorrelations';
import { EvidenceInspector } from './EvidenceInspector';

export function PersonalInsightsDashboard() {
    const { selection, setSelection, data, errors, loading, retry } = useInsightDashboard();
    const [inspectedInsightId, setInspectedInsightId] = useState<string | null>(null);
    const onInspect = (insightId: string) => setInspectedInsightId(insightId);
    const changes = data.changes;
    const errorEntries = Object.entries(errors);

    return (
        <main className="mx-auto max-w-[1600px] space-y-6 p-4 sm:p-6 lg:p-8">
            <header className="flex flex-wrap items-end justify-between gap-4">
                <div><p className="text-sm font-medium text-indigo-600 dark:text-indigo-400">Evidence-backed reflection</p><h1 className="mt-1 text-3xl font-semibold tracking-tight text-foreground">Personal Insights</h1><p className="mt-2 max-w-3xl text-sm text-muted-foreground">How did observed activity, interests, routines, projects, places and engagement change through time?</p></div>
                {loading && <span role="status" className="rounded-full bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">Refreshing all modules…</span>}
            </header>

            <TemporalControl selection={selection} onChange={setSelection} disabled={loading} />

            {errorEntries.length > 0 && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"><span>{errorEntries.length} module{errorEntries.length === 1 ? '' : 's'} could not be loaded: {errorEntries.map(([module]) => module).join(', ')}.</span><button type="button" onClick={retry} className="rounded-lg bg-amber-900 px-3 py-2 font-medium text-white dark:bg-amber-200 dark:text-amber-950">Retry</button></div>}

            {!loading && !data.overview && errorEntries.length === 0 && <EmptyState />}

            {data.overview && <>
                <ActivityDensityTimeline bins={data.overview.density} />
                <OverviewEngagement overview={data.overview} onInspect={onInspect} />
            </>}
            {data.interests && <InterestAtlas interests={data.interests} onInspect={onInspect} />}
            {(data.search || data['ai-conversations']) && <SearchAIInsights search={data.search ?? null} aiConversations={data['ai-conversations'] ?? null} onInspect={onInspect} />}
            {data.places && <PlacesMovement data={data.places} onInspect={onInspect} />}
            {changes && <ChangesProjectsEras data={changes} onInspect={onInspect} />}
            {data.context && <ContextCorrelations data={data.context} onInspect={onInspect} />}

            <EvidenceInspector insightId={inspectedInsightId} open={inspectedInsightId !== null} onOpenChange={open => { if (!open) setInspectedInsightId(null); }} />
        </main>
    );
}

function EmptyState() {
    return <section className="rounded-2xl border border-dashed border-border bg-card px-6 py-14 text-center text-card-foreground"><h2 className="text-lg font-semibold text-foreground">No calculated insights for this selection</h2><p className="mt-2 text-sm text-muted-foreground">Choose another period after local activity has been imported and analysed.</p></section>;
}
