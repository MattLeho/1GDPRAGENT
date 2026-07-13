"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Database, FileSearch } from "lucide-react";
import { fetchInsightTrace } from "@/lib/insights/client";
import type { InsightTrace } from "@/lib/insights/types";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

interface EvidenceInspectorProps {
  insightId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function Records({ title, rows }: { title: string; rows: Array<Record<string, unknown>> }) {
  return <section>
    <h3 className="mb-2 font-medium">{title} <Badge variant="outline">{rows.length}</Badge></h3>
    {rows.length === 0
      ? <p className="text-xs text-muted-foreground">None.</p>
      : <div className="space-y-2">{rows.map((row, index) => <pre key={String(row.id || index)} className="overflow-auto whitespace-pre-wrap rounded-md border bg-muted/50 p-2 text-xs">{JSON.stringify(row, null, 2)}</pre>)}</div>}
  </section>;
}

export function EvidenceInspector({ insightId, open, onOpenChange }: EvidenceInspectorProps) {
  const [result, setResult] = useState<{ id: string; trace: InsightTrace | null; error: string | null } | null>(null);
  useEffect(() => {
    if (!open || !insightId) return;
    const controller = new AbortController();
    fetchInsightTrace(insightId, controller.signal)
      .then(trace => { if (!controller.signal.aborted) setResult({ id: insightId, trace, error: null }); })
      .catch(value => { if (!controller.signal.aborted) setResult({ id: insightId, trace: null, error: value instanceof Error ? value.message : "Could not load evidence" }); });
    return () => controller.abort();
  }, [insightId, open]);
  const active = result?.id === insightId ? result : null;
  const loading = Boolean(open && insightId && !active);
  const trace = active?.trace;
  return <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent className="w-full sm:max-w-2xl">
      <SheetHeader>
        <SheetTitle className="flex items-center gap-2"><FileSearch className="size-5" />Evidence inspector</SheetTitle>
        <SheetDescription>Reproduce the insight from its detector values, source evidence, artefacts, and exact locators.</SheetDescription>
      </SheetHeader>
      <ScrollArea className="min-h-0 flex-1 px-4 pb-6">
        {loading && <p className="text-sm text-muted-foreground">Loading evidence...</p>}
        {active?.error && <div className="flex gap-2 rounded-md border border-destructive/40 p-3 text-sm text-destructive"><AlertTriangle className="size-4" />{active.error}</div>}
        {trace && <div className="space-y-5">
          <div className="rounded-lg border p-3">
            <p className="font-medium">Detector {trace.detector_id} v{trace.detector_version}</p>
            <p className="text-xs text-muted-foreground">Insight {trace.insight_id}</p>
            {trace.time_window && <p className="mt-1 text-xs">{new Date(trace.time_window[0]).toLocaleString()} – {new Date(trace.time_window[1]).toLocaleString()}</p>}
          </div>
          <section>
            <h3 className="mb-2 flex items-center gap-2 font-medium"><Database className="size-4" />Calculated features</h3>
            <pre className="overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">{JSON.stringify(trace.calculated_features, null, 2)}</pre>
          </section>
          <Records title="Activity events" rows={trace.activity_events} />
          <Records title="Accepted assertions" rows={trace.assertions} />
          <Records title="Temporal states" rows={trace.temporal_states} />
          <Records title="Temporal aggregates" rows={trace.temporal_aggregates} />
          <Records title="External context events" rows={trace.external_context_events} />
          <Records title="Source artefacts" rows={trace.source_artifacts} />
          <Records title="Exact evidence locators" rows={trace.evidence_locators} />
          {trace.model_explanation && <section className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-950">
            <h3 className="font-medium">Model explanation — not evidence</h3>
            <p className="mt-1 text-sm">{trace.model_explanation}</p>
          </section>}
          <section>
            <h3 className="font-medium">Source counts</h3>
            <pre className="mt-2 overflow-auto rounded-md border p-2 text-xs">{JSON.stringify(trace.source_counts, null, 2)}</pre>
          </section>
        </div>}
      </ScrollArea>
    </SheetContent>
  </Sheet>;
}
