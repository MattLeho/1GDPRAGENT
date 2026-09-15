"use client";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createBrowserPairing,
  createConnector,
  fetchConnectorHealth,
  fetchConnectors,
  revokeBrowserPairing,
  syncConnector,
  updateConnectorPermissions,
  updateConnectorStatus,
  type BrowserPairing,
  type ConnectorOverview,
} from "@/lib/connectors/client";
import type { ConnectorHealth, SourceConnectorDefinition } from "@/lib/connectors/types";
import { validateConnectorDraft } from "@/lib/connectors/configuration";
import { toast } from "sonner";
import { shouldSuppressProtectedRequestError } from "@/lib/api-client";

export function SourceConnectorsSection() {
  const [data, setData] = useState<ConnectorOverview | null>(null),
    [selected, setSelected] = useState(""),
    [name, setName] = useState(""),
    [account, setAccount] = useState(""),
    [path, setPath] = useState(""),
    [host, setHost] = useState(""),
    [busy, setBusy] = useState(false),
    [loadError, setLoadError] = useState(""),
    [operationStatus, setOperationStatus] = useState("");
  const refresh = useCallback(async () => {
    const next = await fetchConnectors();
    setData(next);
    setLoadError("");
  }, []);
  useEffect(() => {
    fetchConnectors()
      .then((next) => {
        setData(next);
        setLoadError("");
      })
      .catch((error) => {
        if (!shouldSuppressProtectedRequestError(error)) {
          const message = error instanceof Error ? error.message : String(error);
          setLoadError(message);
          toast.error(message);
        }
      });
  }, []);
  const definition = useMemo(
    () => data?.definitions.find((item) => item.key === selected),
    [data, selected],
  );
  const add = async () => {
    if (!definition) return;
    setBusy(true);
    try {
      const configuration = validateConnectorDraft(definition.key, { path, host, account });
      await createConnector({
        definition_key: definition.key,
        definition_version: definition.version,
        display_name: name || definition.display_name,
        account_key: account.trim() || "default",
        enabled_permissions: definition.permissions
          .filter((p) => p.required || p.enabled_by_default)
          .map((p) => p.key),
        configuration,
      });
      setOperationStatus("Source connector added");
      toast.success("Source connector added");
      setSelected("");
      setName("");
      setAccount("");
      setPath("");
      setHost("");
      await refresh();
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        const message = error instanceof Error ? error.message : String(error);
        setOperationStatus(message);
        toast.error(message);
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Source connectors</CardTitle>
          <CardDescription>
            Sources collect evidence through the shared ingestion pipeline. They
            cannot create interests or graph facts directly.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadError && (
            <div role="alert" className="flex flex-col gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm">Source connectors could not be loaded. {loadError}</p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="min-h-11 shrink-0 sm:min-h-9"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await refresh();
                    setOperationStatus("Source connectors loaded");
                  } catch (error) {
                    if (!shouldSuppressProtectedRequestError(error)) {
                      const message = error instanceof Error ? error.message : String(error);
                      setLoadError(message);
                      setOperationStatus(message);
                    }
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Retry source connectors
              </Button>
            </div>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="source-connector-type">Source type</Label>
              <Select value={selected} onValueChange={setSelected}>
                <SelectTrigger id="source-connector-type" className="min-h-11 sm:min-h-9">
                  <SelectValue placeholder="Choose a source" />
                </SelectTrigger>
                <SelectContent>
                  {data?.definitions.map((item) => (
                    <SelectItem key={item.key} value={item.key}>
                      {item.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Field id="source-connector-name" label="Display name">
              <Input
                id="source-connector-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={definition?.display_name || "My source"}
              />
            </Field>
            {definition?.key === "email.imap" && (
              <>
                <Field id="source-connector-account" label="Email account">
                  <Input
                    id="source-connector-account"
                    value={account}
                    onChange={(event) => setAccount(event.target.value)}
                    placeholder="you@example.com"
                  />
                </Field>
                <Field id="source-connector-host" label="IMAP host">
                  <Input
                    id="source-connector-host"
                    value={host}
                    onChange={(event) => setHost(event.target.value)}
                    placeholder="imap.example.com"
                  />
                </Field>
              </>
            )}
            {definition &&
              [
                "ai.conversation.snapshot",
                "filesystem.scoped",
                "media.photo.folder",
              ].includes(definition.key) && (
                <Field id="source-connector-path" label="Intelligence-visible folder or export path">
                  <Input
                    id="source-connector-path"
                    value={path}
                    onChange={(event) => setPath(event.target.value)}
                    placeholder="/source-uploads/selected-folder"
                  />
                  <p className="text-xs text-muted-foreground">
                    Enter an absolute path visible inside the Intelligence runtime. A host path works only when it is mounted into the container.
                  </p>
                </Field>
              )}
          </div>
          {definition && <PermissionPreview definition={definition} />}
          <Button className="min-h-11 sm:min-h-9" disabled={busy || !definition} onClick={add}>
            Add source
          </Button>
          <p className="sr-only" aria-live="polite">{operationStatus}</p>
        </CardContent>
      </Card>
      {data?.instances.map((instance) => {
        const def = data.definitions.find(
          (item) => item.key === instance.definition_key,
        );
        return (
          <ConnectorCard
            key={instance.id}
            instance={instance}
            definition={def}
            refresh={refresh}
          />
        );
      })}
    </div>
  );
}
function PermissionPreview({
  definition,
}: {
  definition: SourceConnectorDefinition;
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="font-medium">Permission inspector</p>
        {definition.supports_source_delete ? (
          <Badge variant="destructive">
            Reviewed source deletion supported
          </Badge>
        ) : (
          <Badge variant="outline">No source deletion</Badge>
        )}
      </div>
      <div className="space-y-2">
        {definition.permissions.map((permission) => (
          <div key={permission.key} className="text-sm">
            <span className="font-medium">
              {permission.access === "not_read"
                ? "Not collected"
                : permission.data_class}
            </span>
            <span className="text-muted-foreground">
              {" "}
              — {permission.description}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
function ConnectorCard({
  instance,
  definition,
  refresh,
}: {
  instance: ConnectorOverview["instances"][number];
  definition?: SourceConnectorDefinition;
  refresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [health, setHealth] = useState<ConnectorHealth | null>(null),
    [queuedTaskId, setQueuedTaskId] = useState<string | null>(null),
    [operationStatus, setOperationStatus] = useState("");
  const enabled = new Set(instance.enabled_permissions);
  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await fetchConnectorHealth(instance.id));
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) setHealth(null);
    }
  }, [instance.id]);
  useEffect(() => {
    let active = true;
    fetchConnectorHealth(instance.id)
      .then((nextHealth) => {
        if (active) setHealth(nextHealth);
      })
      .catch((error) => {
        if (active && !shouldSuppressProtectedRequestError(error)) setHealth(null);
      });
    return () => {
      active = false;
    };
  }, [instance.id, instance.status, instance.last_sync_at, instance.next_sync_at]);
  const run = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await action();
      setOperationStatus(message);
      toast.success(message);
      await refresh();
      await refreshHealth();
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        toast.error(error instanceof Error ? error.message : String(error));
      }
    } finally {
      setBusy(false);
    }
  };
  const queueSync = async (backfill: boolean) => {
    setBusy(true);
    try {
      const result = await syncConnector(instance.id, backfill);
      if (!result.queued || !result.task_id) throw new Error("Connector service returned no task ID");
      setQueuedTaskId(result.task_id);
      const message = backfill ? "Backfill queued" : "Sync queued";
      setOperationStatus(`${message}. Task ${result.task_id}`);
      toast.success(message, { description: `Task ${result.task_id}` });
      await refreshHealth();
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        const message = error instanceof Error ? error.message : String(error);
        setOperationStatus(message);
        toast.error(message);
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle>{instance.display_name}</CardTitle>
            <CardDescription>
              {definition?.provider || instance.definition_key} ·{" "}
              {instance.status.replaceAll("_", " ")}
            </CardDescription>
          </div>
          <Badge
            variant={instance.status === "connected" ? "default" : "outline"}
          >
            {instance.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {definition && <PermissionPreview definition={definition} />}
        <div className="grid gap-2 rounded-md border bg-muted/20 p-3 text-xs sm:grid-cols-2">
          <p><span className="text-muted-foreground">Health:</span> {health ? (health.healthy ? "Healthy" : health.status.replaceAll("_", " ")) : "Unavailable"}</p>
          <p><span className="text-muted-foreground">Last sync:</span> {health?.last_sync_at ? new Date(health.last_sync_at).toLocaleString() : "Never"}</p>
          <p><span className="text-muted-foreground">Next sync:</span> {health?.next_sync_at ? new Date(health.next_sync_at).toLocaleString() : "Not scheduled"}</p>
          <p><span className="text-muted-foreground">Consecutive failures:</span> {health?.consecutive_failures ?? "Unknown"}</p>
          {health?.detail && <p className="sm:col-span-2 text-amber-700 dark:text-amber-300">{health.detail}</p>}
          {queuedTaskId && <p className="break-all sm:col-span-2"><span className="text-muted-foreground">Queued task:</span> {queuedTaskId}</p>}
        </div>
        <div className="space-y-2">
          {definition?.permissions
            .filter((p) => p.access !== "not_read")
            .map((permission) => (
              <label
                key={permission.key}
                className="flex items-start gap-2 text-sm"
              >
                <Checkbox
                  checked={enabled.has(permission.key)}
                  disabled={permission.required || busy}
                  onCheckedChange={(checked) => {
                    const next = new Set(enabled);
                    if (checked) next.add(permission.key);
                    else next.delete(permission.key);
                    run(
                      () => updateConnectorPermissions(instance.id, [...next]),
                      "Permissions updated",
                    );
                  }}
                />
                <span>
                  {permission.description}
                  {permission.required && (
                    <span className="text-muted-foreground"> (required)</span>
                  )}
                </span>
              </label>
            ))}
        </div>
        {definition?.key === "browser.chromium.history" && (
          <BrowserPairingPanel
            instanceId={instance.id}
            disabled={busy || instance.status === "disconnected"}
          />
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            className="min-h-11 sm:min-h-9"
            disabled={
              busy || !["connected", "degraded"].includes(instance.status)
            }
            onClick={() => queueSync(false)}
          >
            Sync now
          </Button>
          {definition?.supports_backfill && (
            <Button
              size="sm"
              variant="outline"
              className="min-h-11 sm:min-h-9"
              disabled={
                busy || !["connected", "degraded"].includes(instance.status)
              }
              onClick={() => queueSync(true)}
            >
              Initial backfill
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            className="min-h-11 sm:min-h-9"
            disabled={
              busy || !["connected", "paused"].includes(instance.status)
            }
            onClick={() =>
              run(
                () =>
                  updateConnectorStatus(
                    instance.id,
                    instance.status === "paused" ? "connected" : "paused",
                  ),
                instance.status === "paused"
                  ? "Connector resumed"
                  : "Connector paused",
              )
            }
          >
            {instance.status === "paused" ? "Resume" : "Pause"}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            className="min-h-11 sm:min-h-9"
            disabled={busy || instance.status === "disconnected"}
            onClick={() =>
              run(
                () => updateConnectorStatus(instance.id, "disconnected"),
                "Connector disconnected; existing evidence retained",
              )
            }
          >
            Disconnect
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Disconnecting does not erase previously ingested evidence. Page
          content remains disabled for browser history.
        </p>
        <p className="sr-only" aria-live="polite">{operationStatus}</p>
      </CardContent>
    </Card>
  );
}
function BrowserPairingPanel({
  instanceId,
  disabled,
}: {
  instanceId: string;
  disabled: boolean;
}) {
  const [label, setLabel] = useState("Chromium profile"),
    [pairing, setPairing] = useState<BrowserPairing | null>(null),
    [busy, setBusy] = useState(false);
  const bridgeUrl = "http://127.0.0.1:8001/connectors/browser/sync";
  const create = async () => {
    setBusy(true);
    try {
      setPairing(await createBrowserPairing(instanceId, label));
      toast.success("One-time browser pairing created");
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        toast.error(error instanceof Error ? error.message : String(error));
      }
    } finally {
      setBusy(false);
    }
  };
  const revoke = async () => {
    if (!pairing) return;
    setBusy(true);
    try {
      await revokeBrowserPairing(pairing.pairing_id);
      setPairing(null);
      toast.success("Browser pairing revoked");
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        toast.error(error instanceof Error ? error.message : String(error));
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-3 rounded-md border p-3">
      <div>
        <p className="font-medium">Local browser extension pairing</p>
        <p className="text-xs text-muted-foreground">
          The token is shown once. It is stored only as a hash by GDPR Agent and
          never enables page-content capture.
        </p>
      </div>
      {pairing ? (
        <div className="space-y-2">
          <Field id={`browser-bridge-${instanceId}`} label="Local bridge URL">
            <Input id={`browser-bridge-${instanceId}`} readOnly value={bridgeUrl} />
          </Field>
          <Field id={`browser-instance-${instanceId}`} label="Connector instance ID">
            <Input id={`browser-instance-${instanceId}`} readOnly value={instanceId} />
          </Field>
          <Field id={`browser-token-${instanceId}`} label="One-time pairing token">
            <Input id={`browser-token-${instanceId}`} readOnly value={pairing.token} />
          </Field>
          <p className="text-xs font-medium text-amber-700 dark:text-amber-300">
            Copy these values into the extension options now. The token cannot
            be recovered after this panel is closed.
          </p>
          <Button
            size="sm"
            variant="destructive"
            className="min-h-11 sm:min-h-9"
            disabled={busy}
            onClick={revoke}
          >
            Revoke this pairing
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <Field id={`browser-label-${instanceId}`} label="Browser profile label">
            <Input
              id={`browser-label-${instanceId}`}
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="Chromium profile"
            />
          </Field>
          <Button
            size="sm"
            className="min-h-11 sm:min-h-9"
            disabled={disabled || busy || !label.trim()}
            onClick={create}
          >
            Create one-time pairing
          </Button>
        </div>
      )}
    </div>
  );
}
function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}
