"use client";
import { useEffect, useState, type ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  approvePlan,
  createControllerCandidate,
  createControllerDraft,
  createDeletionPlan,
  createPolicy,
  executeItem,
  fetchRetention,
  reviewDecision,
  reviewPlan,
  stageItem,
  type RetentionOverview,
} from "@/lib/retention/client";
import type { DeletionPlanItem } from "@/lib/retention/types";
import { toast } from "sonner";
import { shouldSuppressProtectedRequestError } from "@/lib/api-client";
import { reportProtectedConsumerError } from "@/lib/protected-consumer-feedback";

export function RetentionSettingsSection() {
  const [data, setData] = useState<RetentionOverview | null>(null),
    [busy, setBusy] = useState(false),
    [name, setName] = useState("Low-value email review"),
    [action, setAction] = useState("review_only"),
    [days, setDays] = useState("180"),
    [confirmation, setConfirmation] = useState("");
  const refresh = async () => setData(await fetchRetention());
  useEffect(() => {
    refresh().catch((error) => {
      reportProtectedConsumerError(error, () => {
        toast.error(error instanceof Error ? error.message : String(error));
      });
    });
  }, []);
  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await fn();
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
  const addPolicy = () =>
    run(
      () =>
        createPolicy({
          name,
          action,
          minimum_age_seconds: Number(days) * 86400,
          eligibility_threshold: 0.8,
          grace_period_seconds: 30 * 86400,
          connector_keys: ["email.imap"],
          data_classes: ["email.message"],
        }),
      "Retention policy saved",
    );
  return (
    <div className="space-y-4">
      <Alert>
        <AlertTitle>Review-first retention</AlertTitle>
        <AlertDescription>
          Retention is independent of interests. Important and uncertain items
          stay protected. Every plan starts as a dry run, followed by review,
          quarantine and a grace period.
        </AlertDescription>
      </Alert>
      <Card>
        <CardHeader>
          <CardTitle>Create retention policy</CardTitle>
          <CardDescription>
            Policies classify candidates; they do not delete anything when
            saved.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Field label="Policy name">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label="Minimum age (days)">
            <Input
              type="number"
              min="0"
              value={days}
              onChange={(event) => setDays(event.target.value)}
            />
          </Field>
          <div className="space-y-1">
            <Label>Reviewed action</Label>
            <Select value={action} onValueChange={setAction}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="review_only">Review only</SelectItem>
                <SelectItem value="local_purge">Purge local copy</SelectItem>
                <SelectItem value="source_delete">
                  Move source to Trash
                </SelectItem>
                <SelectItem value="controller_erasure_candidate">
                  Draft controller erasure
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button disabled={busy} onClick={addPolicy}>
              Save policy
            </Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Decision review queue</CardTitle>
          <CardDescription>
            Only LOW_VALUE_BULK or SPAM can become eligible. UNSURE always
            remains review-only.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!data?.decisions.length && (
            <p className="text-sm text-muted-foreground">
              No retention decisions yet. Run a connector and policy evaluation
              first.
            </p>
          )}
          {data?.decisions.map((decision) => (
            <div
              key={decision.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded border p-3"
            >
              <div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      decision.classification === "UNSURE"
                        ? "outline"
                        : decision.classification.startsWith("KEEP_")
                          ? "secondary"
                          : "default"
                    }
                  >
                    {decision.classification.replaceAll("_", " ")}
                  </Badge>
                  <span className="text-sm">
                    {Math.round(decision.confidence * 100)}% confidence
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Artifact {decision.source_artifact_id}
                </p>
              </div>
              {decision.review_status === "pending" ? (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      run(
                        () => reviewDecision(decision.id, false),
                        "Decision rejected and protected",
                      )
                    }
                  >
                    Keep / reject
                  </Button>
                  {["LOW_VALUE_BULK", "SPAM"].includes(
                    decision.classification,
                  ) && (
                    <Button
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        run(
                          () => reviewDecision(decision.id, true),
                          "Low-value decision approved for planning",
                        )
                      }
                    >
                      Approve for plan
                    </Button>
                  )}
                </div>
              ) : (
                <Badge variant="outline">{decision.review_status}</Badge>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Deletion plans</CardTitle>
          <CardDescription>
            Review the eligible, protected and uncertain groups before approving
            destructive actions.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {data?.policies.map((policy) => {
            const decisions = data.decisions.filter(
              (item) =>
                item.policy_id === policy.id &&
                item.policy_version === policy.policy_version &&
                item.review_status === "approved",
            );
            return (
              <div
                key={`${policy.id}-${policy.policy_version}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded border p-3"
              >
                <div>
                  <p className="font-medium">{policy.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {policy.action.replaceAll("_", " ")} · minimum{" "}
                    {Math.round(policy.minimum_age_seconds / 86400)} days
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || !decisions.length}
                  onClick={() =>
                    run(
                      () =>
                        createDeletionPlan({
                          policy_id: policy.id,
                          policy_version: policy.policy_version,
                          analysis_run_id: decisions[0].analysis_run_id,
                          decision_ids: decisions
                            .filter(
                              (item) =>
                                item.analysis_run_id ===
                                decisions[0].analysis_run_id,
                            )
                            .map((item) => item.id),
                        }),
                      "Dry-run plan created",
                    )
                  }
                >
                  Create dry run ({decisions.length})
                </Button>
              </div>
            );
          })}
          {data?.plans.map((plan) => (
            <div key={plan.id} className="rounded-lg border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-semibold">Plan {plan.id.slice(0, 8)}</p>
                  <p className="text-sm text-muted-foreground">
                    {plan.items.filter((i) => i.group === "eligible").length}{" "}
                    eligible ·{" "}
                    {plan.items.filter((i) => i.group === "protected").length}{" "}
                    protected ·{" "}
                    {plan.items.filter((i) => i.group === "uncertain").length}{" "}
                    uncertain
                  </p>
                </div>
                <div className="flex gap-2">
                  <Badge variant={plan.dry_run ? "outline" : "destructive"}>
                    {plan.dry_run ? "Dry run" : plan.status}
                  </Badge>
                  {plan.status === "draft" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() =>
                        run(() => reviewPlan(plan.id), "Plan marked reviewed")
                      }
                    >
                      Review plan
                    </Button>
                  )}
                </div>
              </div>
              <div className="mt-3 space-y-2">
                {plan.items.map((item) => (
                  <PlanItem key={item.id} item={item} busy={busy} run={run} />
                ))}
              </div>
              {plan.status === "reviewed" && (
                <div className="mt-4 flex flex-wrap items-end gap-2">
                  <Field label="Type APPROVE DESTRUCTIVE ACTIONS">
                    <Input
                      value={confirmation}
                      onChange={(event) => setConfirmation(event.target.value)}
                      className="w-full min-w-0 sm:min-w-72"
                    />
                  </Field>
                  <Button
                    variant="destructive"
                    disabled={
                      busy || confirmation !== "APPROVE DESTRUCTIVE ACTIONS"
                    }
                    onClick={() =>
                      run(
                        () => approvePlan(plan.id, confirmation),
                        "Plan approved; quarantine is now available",
                      )
                    }
                  >
                    Approve reviewed plan
                  </Button>
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
function PlanItem({
  item,
  busy,
  run,
}: {
  item: DeletionPlanItem;
  busy: boolean;
  run: (fn: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const action = async () => {
    if (item.stage === "candidate")
      return run(
        () => stageItem(item.id, "review", "MARK FOR REVIEW"),
        "Item moved to review",
      );
    if (item.stage === "review")
      return run(
        () => stageItem(item.id, "quarantine", "START QUARANTINE"),
        "Grace period started",
      );
    if (item.stage === "quarantine")
      return run(
        () =>
          stageItem(item.id, "eligible_for_delete", "CONFIRM GRACE EXPIRED"),
        "Grace period verified",
      );
    if (item.stage === "eligible_for_delete") {
      if (item.action === "controller_erasure_candidate") {
        const controller = window.prompt("Controller domain or key");
        if (!controller) return;
        return run(async () => {
          const candidate = await createControllerCandidate(
            item.id,
            controller,
          );
          await createControllerDraft(candidate.id, controller);
        }, "Draft erasure request created; nothing sent");
      }
      return run(
        () => executeItem(item.id, "EXECUTE REVIEWED ACTION"),
        "Reviewed action executed",
      );
    }
  };
  const label =
    item.stage === "candidate"
      ? "Mark for review"
      : item.stage === "review"
        ? "Start quarantine"
        : item.stage === "quarantine"
          ? "Confirm grace expired"
          : item.stage === "eligible_for_delete"
            ? item.action === "controller_erasure_candidate"
              ? "Create request draft"
              : "Execute reviewed action"
            : item.stage;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded bg-muted/40 p-3 text-sm">
      <div>
        <span className="font-medium">{item.group}</span> ·{" "}
        {item.action.replaceAll("_", " ")}
        <p className="text-xs text-muted-foreground">
          {item.reasons.join(" · ")}
        </p>
      </div>
      {item.group === "eligible" &&
      !["executed", "cancelled"].includes(item.stage) ? (
        <Button
          size="sm"
          variant={
            item.stage === "eligible_for_delete" ? "destructive" : "outline"
          }
          disabled={busy}
          onClick={action}
        >
          {label}
        </Button>
      ) : (
        <Badge variant="outline">{item.stage}</Badge>
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
