import type { ActivityDensityBin } from '@/lib/insights/types';

export function ActivityDensityTimeline({ bins }: { bins: ActivityDensityBin[] }) {
    if (!bins.length) return <div className="rounded-xl border border-dashed border-border bg-card px-4 py-8 text-center text-sm text-muted-foreground shadow-sm">No activity was observed in this period.</div>;
    const maximum = Math.max(...bins.map(bin => bin.event_count), 1);
    return (
        <section aria-labelledby="activity-density-title" className="rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-sm">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2"><h2 id="activity-density-title" className="text-base font-semibold text-foreground">Activity density</h2><span className="text-xs text-muted-foreground">Observed events by selected interval</span></div>
            <div className="flex h-40 items-end gap-1 rounded-xl border-b border-border bg-muted/40 px-2 pt-2" role="img" aria-label={`Activity histogram with ${bins.length} time bins`}>
                {bins.map(bin => {
                    const height = bin.event_count ? Math.max(4, (bin.event_count / maximum) * 100) : 1;
                    return <div key={`${bin.start_at}-${bin.end_at}`} className="group relative min-w-0 flex-1 rounded-t bg-indigo-500/80 transition-colors hover:bg-indigo-600 dark:bg-indigo-400/80 dark:hover:bg-indigo-300" style={{ height: `${height}%` }} title={`${formatDate(bin.start_at)}: ${bin.event_count} events`}><span className="sr-only">{formatDate(bin.start_at)}: {bin.event_count} events</span></div>;
                })}
            </div>
            <div className="mt-2 flex justify-between text-xs text-muted-foreground"><span>{formatDate(bins[0].start_at)}</span><span>{formatDate(bins[bins.length - 1].end_at)}</span></div>
        </section>
    );
}

function formatDate(value: string) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
}
