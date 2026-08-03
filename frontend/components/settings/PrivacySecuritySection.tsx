"use client";
import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
interface Settings {
  processing_mode: "strict_local" | "local_first" | "controlled_cloud";
  external_fallback_enabled: boolean;
  approved_external_engines: string[];
}
export function PrivacySecuritySection() {
  const [settings, setSettings] = useState<Settings | null>(null),
    [records, setRecords] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => {
    fetch("/api/settings/processing")
      .then((r) => r.json())
      .then(setSettings)
      .catch((error) => {
        if (!shouldSuppressProtectedRequestError(error)) {
          toast.error("Could not load processing policy");
        }
      });
    fetch("/api/settings/execution-audit")
      .then((r) => r.json())
      .then((d) => setRecords(d.records || []))
      .catch((error) => {
        if (!shouldSuppressProtectedRequestError(error)) {
          toast.error("Could not load processing audit");
        }
      });
  }, []);
  if (!settings) return <p>Loading privacy settings…</p>;
  const save = async (next: Settings) => {
    setSettings(next);
    try {
      const response = await fetch("/api/settings/processing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      if (!response.ok) toast.error("Could not save processing policy");
      else toast.success("Processing policy saved");
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        toast.error("Could not save processing policy");
      }
    }
  };
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Processing privacy</CardTitle>
          <CardDescription>
            Provider policy statements are documentation, not technical
            retention guarantees.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium">Processing mode</p>
            <Select
              value={settings.processing_mode}
              onValueChange={(value) =>
                save({
                  ...settings,
                  processing_mode: value as Settings["processing_mode"],
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="strict_local">Strict local</SelectItem>
                <SelectItem value="local_first">Local first</SelectItem>
                <SelectItem value="controlled_cloud">
                  Controlled cloud
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between rounded border p-3">
            <div>
              <p className="text-sm font-medium">Explicit external fallback</p>
              <p className="text-xs text-muted-foreground">
                Used only when a task route names that external fallback.
              </p>
            </div>
            <Switch
              checked={settings.external_fallback_enabled}
              onCheckedChange={(value) =>
                save({ ...settings, external_fallback_enabled: value })
              }
            />
          </div>
          <div className="rounded border p-3 text-sm">
            <p>Credential encryption: AES-256-GCM, server-side</p>
            <p className="text-muted-foreground">
              Local data paths: PostgreSQL evidence ledger and configured local
              artifact storage.
            </p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>External processing audit</CardTitle>
          <CardDescription>
            Which external models processed personal data?
          </CardDescription>
        </CardHeader>
        <CardContent>
          {records.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No external processing records.
            </p>
          ) : (
            <div className="space-y-2">
              {records.slice(0, 25).map((record) => (
                <div
                  key={String(record.id)}
                  className="rounded border p-2 text-xs"
                >
                  <b>{String(record.task_key)}</b> · {String(record.provider)} /{" "}
                  {String(record.model || "default")} · {String(record.status)}{" "}
                  · {new Date(String(record.started_at)).toLocaleString()}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
