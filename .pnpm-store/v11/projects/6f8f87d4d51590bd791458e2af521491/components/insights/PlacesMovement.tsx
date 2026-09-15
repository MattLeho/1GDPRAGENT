"use client";

import { useMemo, useState } from "react";
import Map, { Marker, NavigationControl } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapPin, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { LocationEvidenceClass, MediaLocationCandidate, PlaceInsight } from "@/lib/insights/types";

interface PlacesMovementProps { data: PlaceInsight; onInspect: (insightId: string) => void }
type Filter = "all" | LocationEvidenceClass;

const LABELS: Record<LocationEvidenceClass, string> = {
  strong_observation: "Strong observation",
  user_confirmed: "User confirmed",
  candidate: "Candidate — review required",
  rejected: "Rejected",
};
const COLOURS: Record<LocationEvidenceClass, string> = {
  strong_observation: "#0f766e", user_confirmed: "#2563eb", candidate: "#d97706", rejected: "#64748b",
};
const BLANK_STYLE = { version: 8 as const, sources: {}, layers: [{ id: "background", type: "background" as const, paint: { "background-color": "#f1f5f9" } }] };

function CandidateRow({ item, onInspect }: { item: MediaLocationCandidate; onInspect: (id: string) => void }) {
  return <div className="rounded-lg border p-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><p className="font-medium">{item.place_label || "Unlabelled location"}</p><p className="text-xs text-muted-foreground">{item.basis.replaceAll("_", " ")} · {item.media_origin.replaceAll("_", " ")}</p></div>
      <Badge variant={item.evidence_class === "rejected" ? "outline" : "secondary"}>{LABELS[item.evidence_class]}</Badge>
    </div>
    <p className="mt-2 text-xs text-muted-foreground">Confidence {(item.confidence * 100).toFixed(0)}%{item.occurred_at ? ` · ${new Date(item.occurred_at).toLocaleString()}` : ""}</p>
    {item.evidence_class === "candidate" && <p className="mt-2 text-xs text-amber-700">This may identify a place, but it does not establish physical presence.</p>}
    <Button className="mt-3" size="sm" variant="outline" onClick={() => onInspect(item.insight_id)}>Inspect evidence</Button>
  </div>;
}

export function PlacesMovement({ data, onInspect }: PlacesMovementProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const visible = useMemo(() => data.candidates.filter(item => filter === "all" || item.evidence_class === filter), [data.candidates, filter]);
  const mapped = visible.filter(item => item.lat != null && item.lon != null);
  const centre = mapped.length ? { latitude: mapped.reduce((n, item) => n + Number(item.lat), 0) / mapped.length, longitude: mapped.reduce((n, item) => n + Number(item.lon), 0) / mapped.length } : { latitude: 20, longitude: 0 };
  return <Card>
    <CardHeader><CardTitle className="flex items-center gap-2"><MapPin className="size-5" />Places and movement</CardTitle><CardDescription>Location evidence remains separated by strength. Screenshots, downloads, and visual landmarks are never shown as proof of presence.</CardDescription></CardHeader>
    <CardContent className="space-y-4">
      <div className="flex flex-wrap gap-2">{(["all", "strong_observation", "user_confirmed", "candidate", "rejected"] as Filter[]).map(value => <Button key={value} size="sm" variant={filter === value ? "default" : "outline"} onClick={() => setFilter(value)}>{value === "all" ? "All" : LABELS[value]}</Button>)}</div>
      {mapped.length > 0 && <div className="h-72 overflow-hidden rounded-lg border" aria-label="Interactive location evidence map">
        <Map initialViewState={{ ...centre, zoom: mapped.length === 1 ? 8 : 2 }} mapStyle={BLANK_STYLE} attributionControl={false} reuseMaps>
          <NavigationControl position="top-right" />
          {mapped.map(item => <Marker key={item.insight_id} latitude={Number(item.lat)} longitude={Number(item.lon)} anchor="bottom" onClick={event => { event.originalEvent.stopPropagation(); onInspect(item.insight_id); }}><MapPin className="size-6 drop-shadow" style={{ color: COLOURS[item.evidence_class], fill: COLOURS[item.evidence_class] }} aria-label={LABELS[item.evidence_class]} /></Marker>)}
        </Map>
      </div>}
      <div className="grid gap-3 md:grid-cols-2">{visible.map(item => <CandidateRow key={item.insight_id} item={item} onInspect={onInspect} />)}</div>
      {visible.length === 0 && <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">No location evidence in this filter and period.</p>}
      <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-lg bg-muted p-3"><b>{data.recurrent_places.length}</b><p>Recurrent places</p></div><div className="rounded-lg bg-muted p-3"><b>{data.new_places.length}</b><p>New places</p></div><div className="rounded-lg bg-muted p-3"><b>{data.activity_centre_changes.length}</b><p>Activity-centre changes</p></div><div className="rounded-lg bg-muted p-3"><b>{data.travel_periods.length}</b><p>Travel-period candidates</p></div><div className="rounded-lg bg-muted p-3"><b>{data.place_linked_project_episodes.length}</b><p>Place-linked projects</p></div>
      </div>
      {data.media_content_candidates.length > 0 && <div className="space-y-2"><h3 className="font-medium">Screenshot and visible-content candidates</h3>{data.media_content_candidates.map(item => <div key={item.insight_id} className="rounded-lg border p-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><span>{item.media_origin.replaceAll("_", " ")} · {item.ocr_word_count} OCR words</span><Badge variant="outline">Content only — not presence</Badge></div><p className="mt-2 text-xs text-muted-foreground">Applications: {item.application_candidates.join(", ") || "none"} · Interfaces: {item.interface_candidates.join(", ") || "none"} · Webpages: {item.webpage_candidates.join(", ") || "none"}</p><Button className="mt-3" size="sm" variant="outline" onClick={() => onInspect(item.insight_id)}>Inspect evidence</Button></div>)}</div>}
      {data.evidence.length > 0 && <Button size="sm" variant="outline" onClick={() => onInspect(data.insight_id)}>Why am I seeing these place aggregates?</Button>}
      <p className="flex items-center gap-2 text-xs text-muted-foreground"><ShieldCheck className="size-4" />Map uses a local blank style and makes no external tile request.</p>
    </CardContent>
  </Card>;
}
