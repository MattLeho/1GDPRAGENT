# R7 — Security, Operational Hardening and Semantic Integrity

## Goal

Harden the local-first deployment, unify secret handling, prevent unsafe server-side acquisition, prove backup/recovery and remove unsupported semantic claims.


## Programme rules

- Current code and runtime behaviour outrank previous completion reports.
- Preserve user data, provenance and migration history.
- PostgreSQL remains canonical; Neo4j remains a rebuildable projection.
- Model output cannot silently become graph truth.
- Every model call must use the canonical Task Router and create an execution record.
- Every protected operation must be scoped to the authenticated canonical profile.
- Distinguish unknown, unconfigured, unavailable, blocked and failed.
- Do not introduce hardcoded Google execution, synthetic graph data or invented compliance metrics.
- Implementation agents cannot be the sole final auditors of their own work.


## Dependencies

- R0–R6 accepted.
- Major runtime journeys exist and can be hardened end to end.

## Lead-agent ownership

The lead agent owns the threat model, secret architecture, network/SSRF boundary, production runtime, backup policy, semantic-claims policy, risk acceptance and final security gate.

## Subagent delegation

### A — SSRF-safe acquisition

Build a hardened external document acquisition service and migrate policy scanning.

### B — Secret consolidation

Unify AI, connector, OAuth and optional infrastructure secrets under one authenticated versioned AES-GCM service.

### C — Container/network hardening

Bind services locally, pin versions and build production images.

### D — Service-to-service security

Apply internal authority and least privilege.

### E — Backup/recovery

Automate and rehearse backup/restore for persistent stores.

### F — Semantic integrity

Audit every compliance, risk, deletion, causation and certainty claim.

### G — Supply-chain security

Add dependency, container and secret scanning.

### H — Independent threat testing

Run adversarial tests without implementing controls.

## Threat model

Cover:

- malicious webpage;
- local unprivileged process;
- compromised connector token;
- malicious archive;
- malicious policy URL;
- compromised provider response;
- exposed port;
- stale session;
- tampered internal request;
- accidental deletion;
- corrupted migration;
- backup theft;
- prompt injection in imported content.

## SSRF-safe acquisition

Requirements:

- `http`/`https` only;
- parse and normalise URL;
- block loopback, link-local, private, multicast, reserved and metadata ranges;
- DNS resolution before every request;
- redirect destination revalidation;
- redirect, response, decompression and time limits;
- content-type allowlist;
- rate limiting;
- no ambient credentials;
- no container-hostname access;
- acquisition audit record;
- immutable bytes and hash.

Test:

```text
localhost
127.0.0.1
::1
10/8
172.16/12
192.168/16
169.254.169.254
redirect to private IP
DNS rebinding fixture
oversized body
compression bomb
unsupported scheme
```

## Unified secrets

Use versioned AES-256-GCM and record:

```text
purpose
provider
account
profile
ciphertext
encryption version
rotation version
created/updated/rotated
needs_reentry
audit history
```

Remove active AES-CBC, hardcoded development keys, shared session/internal/encryption keys and unauthenticated writes. Support rotation without returning plaintext.

## Container/network hardening

Bind host ports to `127.0.0.1` by default. Remove default passwords. Pin images/digests. Use production Next.js and Uvicorn/Gunicorn; do not install dependencies at every start. Use read-only mounts, non-root users and resource limits where practical. Health checks must verify function, not merely an open port.

## Service security

- signed Next.js→Python authority;
- least-privilege database users where feasible;
- Qdrant key/local binding;
- strong n8n credentials and optional disablement;
- Neo4j application roles;
- only projection service writes graph state.

## Backup/restore

Back up:

- PostgreSQL;
- immutable content store;
- Parquet/event lake;
- connector configuration/secrets;
- app configuration/audit logs;
- Qdrant if not rebuildable;
- Neo4j or proof of rebuild from PostgreSQL.

Requirements:

- encrypted backup;
- integrity hashes;
- documented restore order;
- version compatibility;
- clean-volume rehearsal;
- measured recovery point/time;
- credentials remain usable after restore.

## Semantic integrity

Audit phrases such as:

```text
compliant
non-compliant
risk
safe
deleted
erased
known
proved
caused
guaranteed
deadline met
deadline missed
```

Requirements:

- expose basis and uncertainty;
- separate observed/inferred/controller-assigned/hypothetical;
- no completion-as-compliance;
- no absence-as-deletion;
- no correlation-as-causation;
- no fabricated privacy score;
- real evidence for data-holder counts;
- R2 deadline engine as the only deadline source.

## Prompt injection

Imported content is untrusted:

- separate instructions from source content;
- structured output validation;
- allowlisted tools;
- no source-directed arbitrary tools/network;
- mechanical citation resolution;
- model cannot manufacture locators;
- invalid output is logged/rejected.

## Required tests

### Security

- SSRF suite;
- secret rotation/wrong key/missing key;
- internal-authority tampering;
- cross-origin mutation;
- exposed-port/default-password scan;
- prompt-injection fixtures;
- archive traversal/expansion limits.

### Operational

- production image build/cold start;
- service restart;
- Celery retry;
- database outage/recovery;
- Neo4j rebuild;
- clean-volume restore;
- restored connector credentials;
- corrupted backup rejection.

### Semantic

- no unsupported score;
- no completion-as-compliance;
- no absence-as-deletion;
- no correlation-as-causation;
- every evidence-bearing claim has provenance;
- unknown is preserved.

## Definition of done

- Policy acquisition cannot reach local/private infrastructure.
- One authenticated AES-GCM service owns active secrets.
- Services bind safely and use production runtimes.
- Default passwords/runtime installs are removed.
- Clean-volume backup restore succeeds.
- Failure recovery does not silently lose data.
- User-facing claims are evidence-grounded.
- Prompt-injection boundaries are tested.
- Independent penetration, cryptography, recovery and semantics audits pass.

## Paste-ready `/goal`

```text
Execute R7 — Security, Operational Hardening and Semantic Integrity.

Audit R0–R6 first. Build SSRF-safe external policy acquisition, consolidate active secrets under authenticated versioned AES-256-GCM, separate session/internal/encryption keys, harden Docker networking and production runtimes, and prove clean-volume backup/restore.

Audit every compliance, risk, deletion, causation and certainty claim. Remove unsupported scores and use canonical evidence/deadlines. Treat imported content as untrusted and test prompt-injection boundaries.

Delegate SSRF, secrets, containers, service authority, recovery, semantics and supply-chain work to bounded subagents. Keep the threat model, cryptographic contract, destructive decisions, risk acceptance and final security gate under the lead agent.

Before completion, run adversarial security, exposed-port, production image, failure recovery, backup restore, prompt-injection and semantic-invariant tests. Commission independent penetration, cryptography, recovery and semantics audits.
```
