"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import {
  protectedFetch as fetch,
  shouldSuppressProtectedRequestError,
} from "@/lib/api-client";
import { ENGINE_DEFINITIONS } from "@/lib/execution/registry";

interface Settings {
  processing_mode: "strict_local" | "local_first" | "controlled_cloud";
  external_fallback_enabled: boolean;
  approved_external_engines: string[];
}

interface AuditRecord {
  id: string;
  task_key: string;
  provider: string;
  model?: string | null;
  status: string;
  started_at: string;
}

const externalEngines = ENGINE_DEFINITIONS.filter(
  (engine) => engine.execution_location === "external",
);

async function settingsFromResponse(response: Response): Promise<Settings> {
  if (!response.ok) throw new Error("Could not load processing policy");
  return response.json();
}

export function PrivacySecuritySection() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [loadError, setLoadError] = useState("");
  const [auditError, setAuditError] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/settings/processing")
      .then(settingsFromResponse)
      .then((data) => {
        if (!active) return;
        setSettings(data);
        setDraft(data);
        setLoadError("");
      })
      .catch((error) => {
        if (!active || shouldSuppressProtectedRequestError(error)) return;
        setLoadError("Could not load processing policy");
        toast.error("Could not load processing policy");
      });
    fetch("/api/settings/execution-audit")
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load processing audit");
        return response.json() as Promise<{ records?: AuditRecord[] }>;
      })
      .then((data) => {
        if (!active) return;
        setRecords(data.records || []);
        setAuditError("");
      })
      .catch((error) => {
        if (!active || shouldSuppressProtectedRequestError(error)) return;
        setAuditError("Could not load processing audit");
        toast.error("Could not load processing audit");
      });
    return () => {
      active = false;
    };
  }, []);

  const retrySettings = async () => {
    setLoadError("");
    try {
      const data = await settingsFromResponse(await fetch("/api/settings/processing"));
      setSettings(data);
      setDraft(data);
      setStatus("Privacy settings loaded");
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        setLoadError("Could not load processing policy");
        setStatus("Privacy settings could not be loaded");
      }
    }
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    setStatus("Saving processing policy");
    try {
      const response = await fetch("/api/settings/processing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!response.ok) throw new Error("Could not save processing policy");
      const data = (await response.json()) as { settings: Settings };
      setSettings(data.settings);
      setDraft(data.settings);
      setStatus("Processing policy saved");
      toast.success("Processing policy saved");
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        setStatus("Changes not saved");
        toast.error("Could not save processing policy. Changes not saved.");
      }
    } finally {
      setSaving(false);
    }
  };

  if (!draft || !settings) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Processing privacy</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {loadError ? (
            <div role="alert" className="space-y-3">
              <p className="text-sm text-destructive">{loadError}</p>
              <Button className="min-h-11 sm:min-h-9" variant="outline" onClick={retrySettings}>
                Retry privacy settings
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Loading privacy settings…</p>
          )}
        </CardContent>
      </Card>
    );
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(settings);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Processing privacy</CardTitle>
          <CardDescription>
            Provider policy statements are documentation, not technical retention guarantees.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="processing-mode">Processing mode</Label>
            <Select
              value={draft.processing_mode}
              onValueChange={(value) =>
                setDraft({ ...draft, processing_mode: value as Settings["processing_mode"] })
              }
            >
              <SelectTrigger id="processing-mode" className="min-h-11 sm:min-h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="strict_local">Strict local</SelectItem>
                <SelectItem value="local_first">Local first</SelectItem>
                <SelectItem value="controlled_cloud">Controlled cloud</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-3 rounded border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <Label htmlFor="external-fallback">Explicit external fallback</Label>
              <p className="text-xs text-muted-foreground">
                Used only when a task route names that external fallback.
              </p>
            </div>
            <Switch
              id="external-fallback"
              checked={draft.external_fallback_enabled}
              onCheckedChange={(value) => setDraft({ ...draft, external_fallback_enabled: value })}
            />
          </div>
          {draft.processing_mode === "controlled_cloud" && (
            <fieldset className="space-y-3 rounded border p-3">
              <legend className="px-1 text-sm font-medium">Approved external engines</legend>
              <p className="text-xs text-muted-foreground">
                Only checked engines may process personal data in controlled-cloud mode.
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {externalEngines.map((engine) => {
                  const id = `approved-engine-${engine.engine_id}`;
                  const checked = draft.approved_external_engines.includes(engine.engine_id);
                  return (
                    <div key={engine.engine_id} className="flex min-w-0 items-start gap-2">
                      <Checkbox
                        id={id}
                        checked={checked}
                        onCheckedChange={(value) => {
                          const approved = new Set(draft.approved_external_engines);
                          if (value) approved.add(engine.engine_id);
                          else approved.delete(engine.engine_id);
                          setDraft({ ...draft, approved_external_engines: [...approved] });
                        }}
                      />
                      <Label htmlFor={id} className="min-w-0 text-sm font-normal">
                        <span className="block font-medium">{engine.display_name}</span>
                        <span className="break-all text-xs text-muted-foreground">
                          {engine.provider} · {engine.engine_id}
                        </span>
                      </Label>
                    </div>
                  );
                })}
              </div>
            </fieldset>
          )}
          <div className="rounded border p-3 text-sm">
            <p>Credential encryption: AES-256-GCM, server-side</p>
            <p className="text-muted-foreground">
              Local data paths: PostgreSQL evidence ledger and configured local artifact storage.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button
              className="min-h-11 sm:min-h-9"
              disabled={!dirty || saving}
              onClick={save}
            >
              {saving ? "Saving…" : "Save processing policy"}
            </Button>
            <p className="text-xs text-muted-foreground">
              {dirty ? "Changes not saved" : "Settings match the saved policy"}
            </p>
          </div>
          <p className="sr-only" aria-live="polite">{status}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>External processing audit</CardTitle>
          <CardDescription>Which external models processed personal data?</CardDescription>
        </CardHeader>
        <CardContent>
          {auditError ? (
            <p role="alert" className="text-sm text-destructive">{auditError}</p>
          ) : records.length === 0 ? (
            <p className="text-sm text-muted-foreground">No external processing records.</p>
          ) : (
            <div className="space-y-2">
              {records.slice(0, 25).map((record) => (
                <div key={record.id} className="break-words rounded border p-2 text-xs">
                  <b>{record.task_key}</b> · {record.provider} / {record.model || "default"} ·{" "}
                  {record.status} · {new Date(record.started_at).toLocaleString()}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
