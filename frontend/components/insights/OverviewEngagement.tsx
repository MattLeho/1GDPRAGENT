'use client';

import { Eye, MessageSquare, MousePointerClick, Search, Wrench, PenLine } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import type { InsightEngagementProfile, PeriodOverview } from '@/lib/insights/types';

export interface OverviewEngagementProps {
    overview: PeriodOverview;
    onInspect: (id: string) => void;
}

const engagementRows: Array<{
    key: keyof Pick<InsightEngagementProfile, 'ambient_exposure' | 'passive_consumption' | 'active_investigation' | 'creation' | 'implementation' | 'communication'>;
    label: string;
    icon: typeof Eye;
}> = [
    { key: 'ambient_exposure', label: 'Ambient exposure', icon: Eye },
    { key: 'passive_consumption', label: 'Passive consumption', icon: MousePointerClick },
    { key: 'active_investigation', label: 'Active investigation', icon: Search },
    { key: 'creation', label: 'Creation', icon: PenLine },
    { key: 'implementation', label: 'Implementation', icon: Wrench },
    { key: 'communication', label: 'Communication', icon: MessageSquare },
];

function dateLabel(value?: string | null) {
    return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value)) : 'Not available';
}

function deltaLabel(value: number | undefined) {
    if (value === undefined) return null;
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} vs comparison`;
}

export function OverviewEngagement({ overview, onInspect }: OverviewEngagementProps) {
    const engagement = overview.engagement;
    const maximumEngagement = engagement
        ? Math.max(1, ...engagementRows.map(row => engagement[row.key]))
        : 1;

    return (
        <section aria-labelledby="overview-engagement-title" className="space-y-4">
            <div>
                <h2 id="overview-engagement-title" className="text-xl font-semibold">Period overview</h2>
                <p className="text-sm text-muted-foreground">
                    Calculated activity from {dateLabel(overview.period.from_at ?? overview.period.point_at)} to {dateLabel(overview.period.to_at ?? overview.period.point_at)}.
                </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {[
                    ['Events', overview.total_event_count],
                    ['Active topics', overview.active_topic_count],
                    ['Emerging', overview.emerging_topic_count],
                    ['Returning', overview.returning_topic_count],
                    ['Project episodes', overview.project_episode_count],
                ].map(([label, value]) => (
                    <Card key={String(label)} className="gap-2 py-4">
                        <CardContent className="px-4">
                            <p className="text-sm text-muted-foreground">{label}</p>
                            <p className="mt-1 text-2xl font-semibold tabular-nums">{Number(value).toLocaleString()}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div>
                <Card>
                    <CardHeader>
                        <CardTitle>Engagement profile</CardTitle>
                        <CardDescription>Exposure, consumption and behavioural evidence remain separate.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {engagement ? <>
                            {engagementRows.map(row => {
                                const Icon = row.icon;
                                const value = engagement[row.key];
                                const delta = engagement.comparison_delta[row.key];
                                return <div key={row.key} className="space-y-1.5">
                                    <div className="flex items-center justify-between gap-3 text-sm">
                                        <span className="flex items-center gap-2"><Icon className="size-4" aria-hidden="true" />{row.label}</span>
                                        <span className="text-right tabular-nums">
                                            {value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                            {deltaLabel(delta) && <span className="ml-2 text-xs text-muted-foreground">{deltaLabel(delta)}</span>}
                                        </span>
                                    </div>
                                    <Progress value={(value / maximumEngagement) * 100} aria-label={`${row.label}: ${value}`} />
                                </div>;
                            })}
                            <div className="flex items-center justify-between border-t pt-3 text-sm">
                                <span>Disengagement</span>
                                <span className="text-right tabular-nums">
                                    {engagement.disengagement.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                    {deltaLabel(engagement.comparison_delta.disengagement) && <span className="ml-2 text-xs text-muted-foreground">{deltaLabel(engagement.comparison_delta.disengagement)}</span>}
                                </span>
                            </div>
                            {engagement.evidence.length > 0 && <Button variant="outline" size="sm" onClick={() => onInspect(engagement.insight_id)}>
                                Why am I seeing this?
                            </Button>}
                        </> : <p className="text-sm text-muted-foreground">No calculated engagement profile for this period.</p>}
                    </CardContent>
                </Card>
            </div>
        </section>
    );
}
