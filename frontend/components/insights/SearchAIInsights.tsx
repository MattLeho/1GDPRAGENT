'use client';

import { Bot, Search } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { AIConversationInsight, SearchInsight } from '@/lib/insights/types';

export interface SearchAIInsightsProps {
    search?: SearchInsight | null;
    aiConversations?: AIConversationInsight | null;
    onInspect: (id: string) => void;
}

function safeAggregateLabel(value: Record<string, unknown>, fallback: string) {
    for (const key of ['display_label', 'cluster_label', 'topic', 'label', 'name']) {
        if (typeof value[key] === 'string' && value[key]) return String(value[key]);
    }
    return fallback;
}

function Metric({ label, value }: { label: string; value: number }) {
    return <div className="rounded-lg border p-3"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-xl font-semibold tabular-nums">{value.toLocaleString()}</dd></div>;
}

export function SearchAIInsights({ search, aiConversations, onInspect }: SearchAIInsightsProps) {
    return (
        <section aria-labelledby="search-ai-title" className="space-y-4">
            <div>
                <h2 id="search-ai-title" className="text-xl font-semibold">Search and AI conversations</h2>
                <p className="text-sm text-muted-foreground">Calculated patterns only. Raw sensitive queries and conversation text are not displayed.</p>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Search aria-hidden="true" /> Search and investigation</CardTitle>
                        <CardDescription>Repeated patterns are kept distinct from one-off curiosity.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-5">
                        {search ? <>
                            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                <Metric label="Recurring patterns" value={search.recurring_queries.length} />
                                <Metric label="Emerging clusters" value={search.emerging_clusters.length} />
                                <Metric label="Refinement chains" value={search.refinement_chains.length} />
                                <Metric label="Abandoned one-offs" value={search.abandoned_one_offs} />
                            </dl>
                            <div className="grid gap-3 sm:grid-cols-3">
                                <div><h3 className="text-sm font-medium">Recurring searches</h3>{search.recurring_queries.map((item, index) => <p key={String(item.query_fingerprint || index)} className="mt-1 text-xs text-muted-foreground">Pattern {String(item.query_fingerprint || index + 1)} · {Number(item.count || 0)} searches · {Number(item.revisit_count || 0)} revisits</p>)}</div>
                                <div><h3 className="text-sm font-medium">Question clusters</h3>{search.emerging_clusters.map((item, index) => <p key={`${safeAggregateLabel(item, 'Cluster')}-${index}`} className="mt-1 text-xs text-muted-foreground">{safeAggregateLabel(item, `Cluster ${index + 1}`)} · {Number(item.event_count || 0)} events</p>)}</div>
                                <div><h3 className="text-sm font-medium">Refinement chains</h3>{search.refinement_chains.map((item, index) => <p key={String(index)} className="mt-1 text-xs text-muted-foreground">Chain {index + 1} · depth {Number(item.depth || 0)}</p>)}</div>
                            </div>
                            {search.episodes.length > 0 && <div className="space-y-2">
                                <h3 className="text-sm font-medium">Investigation episodes</h3>
                                {search.episodes.map((episode, index) => <div key={episode.insight_id} className="rounded-lg border p-3 text-sm">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <span className="font-medium">{episode.topic_labels.join(' · ') || `Investigation episode ${index + 1}`}</span>
                                        <Badge variant="outline">{episode.status}</Badge>
                                    </div>
                                    {episode.project_transition && <Badge className="mt-2" variant="secondary">Transitioned toward project activity</Badge>}
                                    <p className="mt-2 text-xs text-muted-foreground">
                                        {episode.query_count} query events · {episode.domain_diversity} domains · refinement depth {episode.refinement_depth} · {episode.cross_source_count} sources
                                    </p>
                                    <Button className="mt-3" variant="outline" size="sm" onClick={() => onInspect(episode.insight_id)}>Why am I seeing this?</Button>
                                </div>)}
                            </div>}
                            {search.evidence.length > 0 && <Button variant="outline" size="sm" onClick={() => onInspect(search.insight_id)}>Why am I seeing this?</Button>}
                        </> : <p className="text-sm text-muted-foreground">No calculated search insight for this period.</p>}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Bot aria-hidden="true" /> AI conversations</CardTitle>
                        <CardDescription>User-authored turns are behavioural evidence; assistant output is not treated as user interest.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-5">
                        {aiConversations ? <>
                            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                                <Metric label="Sessions" value={aiConversations.session_count} />
                                <Metric label="User turns" value={aiConversations.user_turn_count} />
                                <Metric label="Assistant turns" value={aiConversations.assistant_turn_count} />
                                <Metric label="Max follow-up depth" value={aiConversations.maximum_follow_up_depth} />
                                <Metric label="Recurrent questions" value={aiConversations.recurrent_questions.length} />
                            </dl>
                            <div className="space-y-3">
                                <div><h3 className="text-sm font-medium">User-originated topic aggregates</h3><div className="mt-2 flex flex-wrap gap-2">{aiConversations.user_originated_topics.map((item, index) => <Badge key={`${safeAggregateLabel(item, 'Topic aggregate')}-${index}`} variant="secondary">{safeAggregateLabel(item, `Topic aggregate ${index + 1}`)}</Badge>)}</div></div>
                                <div><h3 className="text-sm font-medium">Sustained clusters</h3><div className="mt-2 flex flex-wrap gap-2">{aiConversations.sustained_clusters.map((item, index) => <Badge key={`${safeAggregateLabel(item, 'Sustained cluster')}-${index}`} variant="outline">{safeAggregateLabel(item, `Sustained cluster ${index + 1}`)}</Badge>)}</div></div>
                                <div><h3 className="text-sm font-medium">Question refinement chains</h3><div className="mt-2 space-y-2">{aiConversations.refinement_chains.map((item, index) => <p key={String(item.session_id || index)} className="rounded border p-2 text-xs">{Array.isArray(item.stage_sequence) ? item.stage_sequence.join(' → ') : 'No staged refinement'}</p>)}{aiConversations.refinement_chains.length === 0 && <p className="text-xs text-muted-foreground">No user-authored refinement chain in this period.</p>}</div></div>
                                <p className="text-sm text-muted-foreground">Services: {aiConversations.services.length ? aiConversations.services.join(', ') : 'None recorded'} · Project-linked sessions: {aiConversations.project_linked_session_ids.length}</p>
                            </div>
                            {aiConversations.evidence.length > 0 && <Button variant="outline" size="sm" onClick={() => onInspect(aiConversations.insight_id)}>Why am I seeing this?</Button>}
                        </> : <p className="text-sm text-muted-foreground">No calculated AI-conversation insight for this period.</p>}
                    </CardContent>
                </Card>
            </div>
        </section>
    );
}
