"use client";

import { Link2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CorrelationStatus, TemporalCorrelationCandidate } from "@/lib/insights/types";

interface ContextCorrelationsProps { data: TemporalCorrelationCandidate[]; onInspect: (insightId: string) => void }
const WORDING: Record<CorrelationStatus, string> = {
  coincidence_candidate: "Coincidence candidate — timing alone does not establish a relationship.",
  possible_relation: "Possible relation — supporting evidence is limited.",
  evidence_supported_relation: "Evidence-supported relation — this is not a causal claim.",
  user_confirmed: "User-confirmed relation — based on a direct user statement; causation is not inferred.",
  rejected: "Rejected relation — retained for audit.",
};

export function ContextCorrelations({ data, onInspect }: ContextCorrelationsProps) {
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Link2 className="size-5" />Contextual correlations</CardTitle><CardDescription>External events are searched only after a local change is detected. The system never automatically claims causation.</CardDescription></CardHeader><CardContent className="space-y-3">{data.map(item => <div key={item.insight_id} className="rounded-lg border p-4"><div className="flex flex-wrap items-center justify-between gap-2"><Badge variant={item.status === "rejected" ? "outline" : "secondary"}>{item.status.replaceAll("_", " ")}</Badge><span className="text-xs text-muted-foreground">Detector {item.detector_id} v{item.detector_version}</span></div><p className="mt-3 font-medium">{WORDING[item.status]}</p><div className="mt-3 grid gap-3 md:grid-cols-2"><div className="rounded-lg border p-3"><p className="text-xs font-medium uppercase text-muted-foreground">Detected local change</p><p className="mt-1 font-medium">{item.local_change.state_key || item.local_change_id}</p><p className="text-xs text-muted-foreground">{item.local_change.change_type?.replaceAll("_", " ")}{item.local_change.detected_at ? ` · ${new Date(item.local_change.detected_at).toLocaleString()}` : ""}</p></div><div className="rounded-lg border p-3"><p className="text-xs font-medium uppercase text-muted-foreground">External context event</p><p className="mt-1 font-medium">{item.external_event.title || item.external_event_id}</p><p className="text-xs text-muted-foreground">{item.external_event.event_type?.replaceAll("_", " ")}{item.external_event.occurred_at ? ` · ${new Date(item.external_event.occurred_at).toLocaleString()}` : ""}</p></div></div><div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4"><div className="rounded bg-muted p-2">Temporal proximity <b>{(item.temporal_proximity * 100).toFixed(0)}%</b></div><div className="rounded bg-muted p-2">Semantic relevance <b>{(item.semantic_relevance * 100).toFixed(0)}%</b></div><div className="rounded bg-muted p-2">Exposure evidence <b>{item.user_exposure_evidence.length}</b></div><div className="rounded bg-muted p-2">Competing explanations <b>{item.competing_explanations_count}</b></div></div><ul className="mt-3 list-disc pl-5 text-xs text-muted-foreground"><li>{item.preceding_related_activity ? "Related user activity preceded the change." : "No preceding related user activity was established."}</li><li>{item.direct_user_statement ? "A direct user statement is recorded." : "No direct user statement is recorded."}</li><li>Causal claim: never generated automatically.</li></ul><Button className="mt-3" size="sm" variant="outline" onClick={() => onInspect(item.insight_id)}>Inspect evidence</Button></div>)}{data.length === 0 && <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">No contextual correlation candidates in this period.</p>}</CardContent></Card>;
}
