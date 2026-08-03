# Codex Execution Order and Subagent Protocol

## Individual goals

Use one Codex `/goal` per plan. A plan is not a prompt fragment; it is the complete scope, dependency and acceptance contract for one implementation stage.

## Branches and worktrees

Recommended branches:

```text
remediation/r0-baseline
remediation/r1-auth
remediation/r2-schema
remediation/r3-model-control
remediation/r4-connectors
remediation/r5-responsive
remediation/r6-temporal-graph
remediation/r7-hardening
remediation/r8-acceptance
```

Use separate worktrees for concurrent plans.

## Merge order

```text
R0 → R1 → R2 → R3 → R4 → R5 → integration → R6 → R7 → R8
```

`R3`–`R5` may run concurrently only after `R1` and `R2` are merged and shared interfaces are frozen.

## Parallel ownership boundaries

### R3 owns

```text
frontend/lib/execution/**
frontend/app/api/settings/task-routes/**
frontend/app/api/settings/engine-health/**
model discovery and recommendation
model setup jobs
product call-site migration to TaskRoute
processing/model settings components
```

### R4 owns

```text
intelligence/connectors/**
intelligence/api/connectors*
browser-extension/**
OAuth routes and callbacks
connector scheduler and workers
connector settings components
```

### R5 owns

```text
DashboardLayout and shell
sidebar and top header layout
shared responsive primitives
page containers
global status and error surfaces
graph responsive composition
```

R5 must not rewrite the semantic internals of R3 or R4 components. It should integrate their frozen interfaces.

## Shared files controlled by the integration lead

```text
frontend/app/dashboard/settings/page.tsx
frontend/package.json
docker-compose.yml
.env.example
database/migrations/
frontend/lib/api-client*
frontend/components/ui/**
README.md
IMPLEMENTATION_TRACKER.md
```

Resolve shared-file conflicts semantically. Never accept one branch wholesale without checking whether it deletes another plan’s contract.

## Bounded subagent assignment format

Every delegated task must state:

```text
Objective
Owned paths
Read-only dependencies
Non-goals
Required tests
Deliverables
Stop conditions
```

A subagent must not:

- edit outside owned paths without approval;
- create a competing schema, router, credential store or graph writer;
- modify migrations independently of the lead;
- weaken authentication or provenance to make tests pass;
- mark the overall plan complete;
- act as the sole final auditor of its own implementation.

## Lead-agent responsibilities

Retain centrally:

- cross-cutting architecture;
- schema and migrations;
- security and authority;
- shared types;
- destructive operations;
- cross-service wiring;
- conflict resolution;
- final definition-of-done judgement.

## Plan start protocol

1. Record branch and commit SHA.
2. Read the plan.
3. Re-run predecessor tests.
4. Audit predecessor definitions of done.
5. Record current failures and blockers.
6. Freeze shared interfaces.
7. Create a delegation map.
8. Start implementation.

## Plan completion protocol

1. Re-read every requirement.
2. Map each requirement to code, migration, test and runtime evidence.
3. Run clean install.
4. Run the relevant legacy upgrade.
5. Run type-check, lint, Python suite and production build.
6. Run authenticated browser journeys.
7. Inject failures and missing configuration.
8. Delegate an independent audit.
9. Repair findings.
10. Re-run acceptance and update documentation.

## Completion language

Permitted:

```text
Implemented and verified in the environments listed below. Remaining environment-dependent limitations are explicit.
```

Not permitted before R8:

```text
Everything is complete.
No incomplete requirements.
Production ready.
```
