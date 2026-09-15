"use client";

import { Activity, Layers3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ChangeInsight, PersonalEraView, ProjectEpisodeView } from "@/lib/insights/types";

interface ChangesProjectsErasProps {
  data: { changes: ChangeInsight[]; project_episodes: ProjectEpisodeView[]; personal_eras: PersonalEraView[] };
  onInspect: (insightId: string) => void;
}
const date = (value: string) => new Date(value).toLocaleDateString();

function Labels({ machine, human }: { machine?: string | null; human?: string | null }) {
  return <div className="mt-3 grid gap-2 sm:grid-cols-2">
    <div className="rounded-md bg-muted p-2"><p className="text-xs font-medium uppercase text-muted-foreground">Machine label</p><p className="text-sm">{machine || "No machine label"}</p></div>
    <div className="rounded-md border p-2"><p className="text-xs font-medium uppercase text-muted-foreground">Human label</p><p className="text-sm">{human || "Not labelled by a person"}</p></div>
  </div>;
}

function InspectButton({ item, onInspect }: { item: ChangeInsight | ProjectEpisodeView | PersonalEraView; onInspect: (id: string) => void }) {
  if (item.evidence.length === 0) return null;
  return <Button className="mt-3" size="sm" variant="outline" onClick={() => onInspect(item.insight_id)}>Inspect evidence</Button>;
}

export function ChangesProjectsEras({ data, onInspect }: ChangesProjectsErasProps) {
  return <div className="space-y-4">
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Activity className="size-5" />Changes and regime shifts</CardTitle><CardDescription>Detector outputs are calculated changes, not explanations of why they happened.</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        {data.changes.map(item => <div key={item.insight_id} className="rounded-lg border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><div><Badge variant="outline">{item.change_type.replaceAll("_", " ")}</Badge><p className="mt-2 font-medium">{item.state_key}</p></div><p className="text-sm">Magnitude <b>{item.magnitude.toFixed(2)}</b></p></div>
          <p className="mt-2 text-xs text-muted-foreground">Detected {new Date(item.detected_at).toLocaleString()} · {item.detector_id} v{item.detector_version}</p>
          <div className="mt-2 rounded bg-muted p-2 text-xs"><b>Calculated detector values</b><pre className="mt-1 overflow-auto whitespace-pre-wrap">{JSON.stringify(item.calculated_features, null, 2)}</pre></div>
          <InspectButton item={item} onInspect={onInspect} />
        </div>)}
        {data.changes.length === 0 && <p className="text-sm text-muted-foreground">No calculated changes in this period.</p>}
      </CardContent>
    </Card>
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Project episodes</CardTitle><CardDescription>Evidence-linked candidates derived from activity patterns.</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          {data.project_episodes.map(item => <div key={item.insight_id} className="rounded-lg border p-3"><p className="font-medium">{date(item.start_at)} – {date(item.end_at)}</p><p className="mt-1 text-xs text-muted-foreground">{item.topic_ids.join(" · ") || "No topic label"}</p>{item.topic_co_emergence.length > 1 && <p className="mt-2 text-xs text-muted-foreground">Co-emerging topics: {item.topic_co_emergence.join(" · ")}</p>}<div className="mt-2 flex flex-wrap gap-2">{item.progressed_to_creation && <Badge>Progressed to creation</Badge>}{item.progressed_to_implementation && <Badge variant="secondary">Progressed to implementation</Badge>}</div>{item.peak_investigation_at && <p className="mt-2 text-xs text-muted-foreground">Peak investigation {new Date(item.peak_investigation_at).toLocaleString()}</p>}<Labels machine={item.machine_label} human={item.human_label} /><InspectButton item={item} onInspect={onInspect} /></div>)}
          {data.project_episodes.length === 0 && <p className="text-sm text-muted-foreground">No project episodes in this period.</p>}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Layers3 className="size-5" />Personal eras</CardTitle><CardDescription>Contiguous periods detected from changing activity features.</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          {data.personal_eras.map(item => <div key={item.insight_id} className="rounded-lg border p-3"><p className="font-medium">{date(item.start_at)} – {date(item.end_at)}</p><Labels machine={item.machine_label} human={item.human_label} /><InspectButton item={item} onInspect={onInspect} /></div>)}
          {data.personal_eras.length === 0 && <p className="text-sm text-muted-foreground">No personal-era candidates in this period.</p>}
        </CardContent>
      </Card>
    </div>
  </div>;
}
