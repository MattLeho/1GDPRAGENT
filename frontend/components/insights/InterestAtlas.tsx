'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import type { ObservedInterestState } from '@/lib/insights/types';

export interface InterestAtlasProps {
    interests: ObservedInterestState[];
    onInspect: (id: string) => void;
}

const dimensions: Array<{ key: keyof Pick<ObservedInterestState, 'intensity' | 'persistence' | 'recurrence' | 'breadth' | 'novelty' | 'context_dispersion'>; label: string }> = [
    { key: 'intensity', label: 'Intensity' },
    { key: 'persistence', label: 'Persistence' },
    { key: 'recurrence', label: 'Recurrence' },
    { key: 'breadth', label: 'Breadth' },
    { key: 'novelty', label: 'Novelty' },
    { key: 'context_dispersion', label: 'Context dispersion' },
];

function shortDate(value: string) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
}

export function InterestAtlas({ interests, onInspect }: InterestAtlasProps) {
    const groups = interests.reduce<Map<string, ObservedInterestState[]>>((result, interest) => {
        const root = interest.topic_path[0] || 'Other';
        result.set(root, [...(result.get(root) || []), interest]);
        return result;
    }, new Map());

    return (
        <section aria-labelledby="interest-atlas-title" className="space-y-4">
            <div>
                <h2 id="interest-atlas-title" className="text-xl font-semibold">Interest Atlas</h2>
                <p className="text-sm text-muted-foreground">Versioned behavioural views grouped by their calculated topic hierarchy.</p>
            </div>
            {interests.length === 0 ? (
                <Card><CardContent className="py-2 text-sm text-muted-foreground">No observed interests were calculated for this period.</CardContent></Card>
            ) : (
                <div className="space-y-6">
                    {[...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([root, group]) => (
                        <div key={root} className="space-y-3">
                            <h3 className="border-b pb-2 text-base font-semibold">{root}</h3>
                            <div className="grid gap-4 lg:grid-cols-2">
                                {group.sort((a, b) => b.intensity - a.intensity).map(interest => {
                                    const maxDimension = Math.max(1, ...dimensions.map(item => interest[item.key]));
                                    return <Card key={interest.insight_id}>
                                        <CardHeader>
                                            <div className="flex flex-wrap items-start justify-between gap-2">
                                                <div>
                                                    <CardTitle>{interest.topic_path.at(-1) || interest.topic_id}</CardTitle>
                                                    <CardDescription className="mt-1">{interest.topic_path.join(' / ')}</CardDescription>
                                                </div>
                                                <Badge variant="outline">{interest.change.replace('_', ' ')}</Badge>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <dl className="grid grid-cols-2 gap-3 text-sm">
                                                <div><dt className="text-muted-foreground">Period</dt><dd>{shortDate(interest.window_start)} – {shortDate(interest.window_end)}</dd></div>
                                                <div><dt className="text-muted-foreground">First observed</dt><dd>{shortDate(interest.first_observed_at)}</dd></div>
                                                <div><dt className="text-muted-foreground">Latest observed</dt><dd>{shortDate(interest.latest_observed_at)}</dd></div>
                                                <div><dt className="text-muted-foreground">Peak investigation</dt><dd>{interest.peak_at ? shortDate(interest.peak_at) : 'No peak calculated'}</dd></div>
                                                <div><dt className="text-muted-foreground">Sources</dt><dd>{interest.source_domains.length ? interest.source_domains.join(', ') : 'No source domain label'}</dd></div>
                                            </dl>
                                            <div className="grid gap-3 sm:grid-cols-2">
                                                {dimensions.map(item => {
                                                    const value = interest[item.key];
                                                    return <div key={item.key} className="space-y-1">
                                                        <div className="flex justify-between gap-2 text-xs"><span>{item.label}</span><span className="tabular-nums">{value.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span></div>
                                                        {interest.previous_period_dimensions[item.key] !== undefined && <p className="text-[11px] text-muted-foreground">Previous {interest.previous_period_dimensions[item.key].toLocaleString(undefined, { maximumFractionDigits: 2 })} · Δ {interest.comparison_delta[item.key].toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>}
                                                        <Progress value={(value / maxDimension) * 100} aria-label={`${item.label}: ${value}`} />
                                                    </div>;
                                                })}
                                            </div>
                                            {interest.controller_profile_comparison.length > 0 && <p className="rounded-md border p-2 text-xs text-muted-foreground">Compared separately with {interest.controller_profile_comparison.length} controller-profile state{interest.controller_profile_comparison.length === 1 ? '' : 's'}; these are not treated as personal behaviour.</p>}
                                            <Button variant="outline" size="sm" onClick={() => onInspect(interest.insight_id)}>
                                                Why am I seeing this?
                                            </Button>
                                        </CardContent>
                                    </Card>;
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}
