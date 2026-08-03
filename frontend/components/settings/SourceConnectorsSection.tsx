"use client";
import { useEffect, useMemo, useState, type ReactNode } from "react";
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
  fetchConnectors,
  revokeBrowserPairing,
  syncConnector,
  updateConnectorPermissions,
  updateConnectorStatus,
  type BrowserPairing,
  type ConnectorOverview,
} from "@/lib/connectors/client";
import type { SourceConnectorDefinition } from "@/lib/connectors/types";
import { toast } from "sonner";
import { shouldSuppressProtectedRequestError } from "@/lib/api-client";

export function SourceConnectorsSection() {
  const [data, setData] = useState<ConnectorOverview | null>(null),
    [selected, setSelected] = useState(""),
    [name, setName] = useState(""),
    [account, setAccount] = useState("default"),
    [path, setPath] = useState(""),
    [host, setHost] = useState(""),
    [busy, setBusy] = useState(false);
  const refresh = async () => setData(await fetchConnectors());
  useEffect(() => {
    fetchConnectors()
      .then(setData)
      .catch((error) => {
        if (!shouldSuppressProtectedRequestError(error))
          toast.error(error.message);
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
      const configuration = configFor(definition, { path, host, account });
      await createConnector({
        definition_key: definition.key,
        definition_version: definition.version,
        display_name: name || definition.display_name,
        account_key: account,
        enabled_permissions: definition.permissions
          .filter((p) => p.required || p.enabled_by_default)
          .map((p) => p.key),
        configuration,
      });
      toast.success("Source connector added");
      setSelected("");
      setName("");
      await refresh();
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error))
        toast.error(error instanceof Error ? error.message : String(error));
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
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label>Source type</Label>
              <Select value={selected} onValueChange={setSelected}>
                <SelectTrigger>
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
            <Field label="Display name">
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={definition?.display_name || "My source"}
              />
            </Field>
            {definition?.key === "email.imap" && (
              <>
                <Field label="Email account">
                  <Input
                    value={account}
                    onChange={(event) => setAccount(event.target.value)}
                    placeholder="you@example.com"
                  />
                </Field>
                <Field label="IMAP host">
                  <Input
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
                <Field label="Allowed folder or export path">
                  <Input
                    value={path}
                    onChange={(event) => setPath(event.target.value)}
                    placeholder="C:\Users\You\Documents\Selected folder"
                  />
                </Field>
              )}
          </div>
          {definition && <PermissionPreview definition={definition} />}
          <Button disabled={busy || !definition} onClick={add}>
            Add source
          </Button>
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
function configFor(
  definition: SourceConnectorDefinition,
  input: { path: string; host: string; account: string },
) {
  if (definition.key === "email.imap")
    return {
      host: input.host,
      port: 993,
      username: input.account,
      scope: "headers_and_subject",
      mailboxes: ["INBOX"],
      trash_mailbox: "Trash",
    };
  if (definition.key === "ai.conversation.snapshot")
    return { paths: [input.path], service: "auto" };
  if (definition.key === "filesystem.scoped") return { roots: [input.path] };
  if (definition.key === "media.photo.folder")
    return { roots: [input.path], mode: "metadata_only" };
  return { page_content_capture: false, queue_limit: 1000 };
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
  const [busy, setBusy] = useState(false);
  const enabled = new Set(instance.enabled_permissions);
  const run = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await action();
      toast.success(message);
      await refresh();
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        toast.error(error instanceof Error ? error.message : String(error));
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
                    checked
                      ? next.add(permission.key)
                      : next.delete(permission.key);
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
            disabled={
              busy || !["connected", "degraded"].includes(instance.status)
            }
            onClick={() =>
              run(() => syncConnector(instance.id, false), "Sync scheduled")
            }
          >
            Sync now
          </Button>
          {definition?.supports_backfill && (
            <Button
              size="sm"
              variant="outline"
              disabled={
                busy || !["connected", "degraded"].includes(instance.status)
              }
              onClick={() =>
                run(
                  () => syncConnector(instance.id, true),
                  "Backfill scheduled",
                )
              }
            >
              Initial backfill
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
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
          <Field label="Local bridge URL">
            <Input readOnly value={bridgeUrl} />
          </Field>
          <Field label="Connector instance ID">
            <Input readOnly value={instanceId} />
          </Field>
          <Field label="One-time pairing token">
            <Input readOnly value={pairing.token} />
          </Field>
          <p className="text-xs font-medium text-amber-700 dark:text-amber-300">
            Copy these values into the extension options now. The token cannot
            be recovered after this panel is closed.
          </p>
          <Button
            size="sm"
            variant="destructive"
            disabled={busy}
            onClick={revoke}
          >
            Revoke this pairing
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <Field label="Browser profile label">
            <Input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="Chromium profile"
            />
          </Field>
          <Button
            size="sm"
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
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
