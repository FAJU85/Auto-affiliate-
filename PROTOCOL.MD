# PROTOCOL.md — UNIVERSAL MULTI-AGENT EXECUTION ENGINE
> **Document Version:** 1.2.0 | **Scope:** All standard (non-override) execution cycles

---

## 1. CORE OPERATIONAL PRINCIPLE

> **Build the smallest operationally valid system before introducing abstraction.**

The primary systemic risk in autonomous agent systems is **uncontrolled architectural expansion (scope drift)**. This protocol enforces **operational convergence**: every file mutation, routing decision, and validation step must directly drive the system toward a working, verified, and deployable state.

---

## 2. TRIAD NODE DEFINITIONS & ARCHITECTURE

The system operates via an immutable Minimum Viable Agent Team (MVAT) Triad. Three agents. No more are required for a standard cycle. Agents do not communicate conversationally — they execute via machine-readable JSON payloads.

```
       [ 1. ORCHESTRATOR ]
               │
               ▼  (Inbound Contract JSON)
         [ 2. BUILDER ]
               │
               ▼  (Outbound Diff JSON)
        [ 3. VALIDATOR ]
               │
               ▼  (Validation Report JSON)
       [ 1. ORCHESTRATOR ]  ◄── feedback loop
```

### 2.1 The Orchestrator (`orchestrator`)

One agent. Two internal phases. All lifecycle and planning responsibilities are unified here — there is no separate `sdlc-orchestrator` or `ai-orchestrator`.

**Phase 1 — Pre-Build Research (mandatory, non-delegable):**
Before producing any execution graph, the Orchestrator must read WIKI.md to resolve system dependencies, file locations, and structural data models. This is an internal step, not a delegated agent call. The former `layer1-research` agent was a named wrapper around this step — the wrapper is eliminated, the step remains.

**Phase 2 — Execution Planning:**
- **If no active canvas exists and no Autonomous Session is running:** parse the user's natural language brief into canvas fields (CANVAS.md §1–§7), present the Scope Summary, and await `CANVAS_APPROVED` before producing any execution graph.
- **If an Autonomous Session is active (CANVAS.md §8.7):** fill the canvas from context, auto-approve it within the declared session boundaries, log `CANVAS_AUTO_APPROVED`, and proceed immediately. Do not interrupt the user.
- **If session criticality ceiling would be exceeded:** pause the session, notify the user, and await `SESSION_RESUME` or explicit HITL resolution before proceeding.
- Once a canvas is approved (interactively or via session): parse objectives into deterministic execution graphs, define an explicit `approvedFileSet`, lock it, convert §1 Strict Exclusions into machine-detectable `forbiddenActions` patterns, and issue `iac_inbound.json` to the Builder.

**Phase 3 — Lifecycle Control:**
- Acquire the Execution Lock before any Builder mutation begins. This is the only agent authorised to hold or release the lock.
- Emit a heartbeat every 60 seconds while the lock is held (see §2.4).
- After receiving a `PASS` Validation Report: invoke `documentation-agent`, trigger WIKI re-indexing, post to the Cumulative Scope Ledger, then release the lock.

**Concurrency Capability (not a separate agent):**
When a Playbook step declares `"concurrency": true`, the Orchestrator manages parallel worker dispatch internally. There is no `parallel-dispatcher` agent. Concurrency is a scheduling mode of the Orchestrator, not an independent entity with its own IAC contract.

**Forbidden Actions:**
- Do not plan speculative architecture or refactor unrelated systems.
- Do not modify infrastructure or add packages without an explicit `dependencyOverride` object with written justification.

  > **Definition — Speculative Architecture:** Any of the following constitutes speculative architecture and is forbidden: (a) abstraction layers with zero current call sites; (b) configuration systems for features not present in the current `approvedFileSet`; (c) plugin or extension points with no registered handlers; (d) generic base classes with fewer than 3 existing, verified subclasses; (e) event or message bus systems with no current subscribers; (f) feature flags for features not yet approved in the active canvas; (g) database schema fields not read by any current code path. If an agent cannot point to a concrete, existing call site that requires the proposed abstraction, it is speculative.

### 2.2 The Builder (`layer3-development`)

- **Objective:** Ingest the Orchestrator's blueprint and generate high-fidelity, explicit code mutations.
- **Mandatory Actions:**
  - Mutate files *only* within the defined `approvedFileSet`.
  - Enforce absolute static typing, explicit error-handling wrappers, and line-level inline documentation.
  - Run `detect-secrets scan` on all mutated files before submitting — any finding is a hard stop.
  - Self-correct localized compilation or syntax failures.
- **Forbidden Actions:**
  - Do not leave placeholder comments, markers, or partial code blocks (e.g., `// TODO`).
  - Do not use dynamic/loose typing parameters or circumvent compilers.

### 2.3 The Validator (`layer4-testing`)

- **Objective:** Programmatically audit mutations against the original task contract, all quality gates, and architectural constraints. Issue the `ValidatorToOrchestratorReport`.
- **Mandatory Actions:**
  - Enforce all gates in §3.2–§3.8: complexity, function length, dead code, error handling, coverage, dependency audit, secrets, CI/CD pipeline gates.
  - Verify mutations do not leak outside the locked `approvedFileSet`.
  - After every WIKI re-indexing cycle: run schema integrity checks against live codebase imports (absorbs the former `schema-debugger` function — schema validation is a quality gate, not a separate agent role).
- **Definitive Fail Conditions:**
  - Any injection of unapproved third-party dependencies.
  - Introduction of speculative architecture (see §2.1 definition).

### 2.4 Execution Lock Management & Deadlock Prevention

The Execution Lock is a system-wide mutex owned exclusively by the `orchestrator`. The following rules are non-negotiable:

| Rule | Value | Enforcement |
|---|---|---|
| **Lock TTL** | 30 minutes from acquisition | `orchestrator` must emit a heartbeat every 60 seconds. Lock auto-expires if no heartbeat is received within the TTL window. |
| **Watchdog** | `internal-auditor` | Polls lock state every 5 minutes. If a lock has exceeded TTL with no heartbeat, `internal-auditor` forces release and triggers HITL. |
| **Orphaned Lock Recovery** | Automated | `internal-auditor` captures the last known `taskId` and `diffHash`, initiates `git reset --hard` to the pre-lock commit state on all `filesMutated`, and broadcasts a `LOCK_TIMEOUT` error payload. |
| **Nested Lock Prohibition** | Zero tolerance | No agent may attempt to acquire a second Execution Lock while one is active. Nested lock attempts trigger immediate HITL. |

> **Heartbeat Payload:** The `orchestrator` heartbeat must include `taskId`, `lockAcquiredAt` (ISO 8601), and `currentStep` so that `internal-auditor` can reconstruct execution state if recovery is needed.

---

## 3. DETERMINISTIC ARCHITECTURAL CONSTRAINTS

### 3.1 The Anti-Abstraction Rule

Agents are strictly **FORBIDDEN** from creating base classes, wrapper modules, interfaces, or generic type factories unless the proposed implementation directly consolidates **3 or more existing, verified call sites** in the active repository.

**Duplication Policy (Two-Strike Rule):**

| Duplication Count | Required Action |
|---|---|
| First occurrence of a duplicated pattern | Duplication is **permitted**. Log the pattern ID in the task's `mutationDirectives`. |
| Second occurrence of the same pattern | Duplication is **forbidden**. The Builder **must** submit a refactor proposal to the Orchestrator before proceeding. The Orchestrator evaluates scope and either approves consolidation or grants a one-time override with written justification. |
| Pattern present in 3+ verified call sites | Abstraction is **mandated**. Proceed with consolidation. |

> **Rationale:** Forcing immediate abstraction below a natural threshold produces premature generalization. Forcing unlimited duplication accumulates silent maintenance debt. The two-strike rule bounds both failure modes.

### 3.2 Systemic Simplicity Metric

The Validator must evaluate the Builder's diff using the following quantitative metrics. **All limits are enforced by automated tooling** — they are not advisory. A diff that fails any metric below must be rejected before human review is requested.

| Metric | Limit | Enforcement Tool | Notes |
|---|---|---|---|
| **Cyclomatic Complexity** | Max nesting depth of **3 levels** | `radon` / `flake8-cognitive-complexity` | Depth of 2 is the target; depth of 3 is the hard ceiling. A standard `try/except` inside a loop counts as depth 2. |
| **Function Length** | Max **50 lines** of logical code | `flake8 --max-function-length=50` | Comments and blank lines excluded from count. Functions exceeding this limit must be decomposed before the diff is re-submitted — no exceptions, no override flags. |
| **Dead Code** | Zero unreachable symbols | `vulture --min-confidence=80` | Any function, class, variable, or import flagged as unreachable is treated as a **security risk** (dead code is an attack surface for injection and confused-deputy vulnerabilities). The Builder must remove or justify every flagged symbol before the Validator passes the diff. |
| **Scope Drift** | Zero tolerance | File path diff vs `approvedFileSet` | Any file mutation not present in `approvedFileSet` trips a hard validation failure. |

> **Note on Nesting Depth:** The previous cap of 2 was incompatible with standard exception-handling patterns. The revised ceiling of 3 aligns with industry convention (PEP-8, Google Style Guide) while preserving the anti-complexity intent.

### 3.3 Error Handling Contract

The Builder is **FORBIDDEN** from submitting code that contains unguarded execution paths. The following rules are non-negotiable and enforced by the Validator's AST scan:

**Required Patterns:**

| Context | Required Pattern | Forbidden Anti-Pattern |
|---|---|---|
| Any I/O operation (file, network, DB) | Explicit `try/except` with typed exception classes | Bare `except:` or `except Exception:` with no logging |
| External API call | Typed exception + structured error payload returned upstream | Silent `return None` on failure |
| Agent-to-agent IAC payload receipt | `schemaVersion` check + `SchemaVersionError` on mismatch | Silent field coercion or default-value fallback |
| Background / async task | Explicit failure capture with audit log entry | Fire-and-forget with no error surface |

**Mandatory Error Payload Structure:**

Every caught exception must produce a structured error object. Agents may not log free-form strings as their only error output.

```json
{
  "errorCode":   "string  — machine-readable code, e.g. SCHEMA_VERSION_MISMATCH",
  "errorMessage":"string  — human-readable description",
  "sourceAgent": "string  — identifier of the agent that raised the error",
  "taskId":      "string  — execution cycle task ID",
  "timestamp":   "string  — ISO 8601 UTC",
  "recoverable": "boolean — whether layer6-self-healing may attempt remediation"
}
```

> **Enforcement:** The Validator runs `bandit -l` to detect bare excepts, swallowed exceptions, and unguarded subprocess calls. Any `bandit` finding at severity MEDIUM or above is a hard rejection.

### 3.4 Mandatory Test Coverage Gates

A diff is not valid unless it ships with tests. The Validator must confirm all three gates below before issuing a passing `BuilderToValidatorPayload`.

| Gate | Threshold | Tool | Notes |
|---|---|---|---|
| **Line Coverage** | ≥ 85% on mutated files | `pytest --cov` | Measured only over files in `filesMutated`. Global coverage is not a substitute. |
| **Branch Coverage** | ≥ 75% on mutated files | `pytest --cov-branch` | Every `if/else` and `try/except` branch must be exercised. |
| **Dead Test Detection** | Zero unused test functions | `vulture tests/` | A test that is never collected by the runner is dead code and must be removed. |

**Test Naming Convention (enforced by linter):**

```
test_<unit_under_test>__<scenario>__<expected_outcome>
# Example:
test_session_reader__missing_schema_version__raises_schema_version_error
```

Agents may not ship tests named `test_1`, `test_it`, or any name that does not encode the scenario and expected outcome. The Validator rejects diffs containing non-conforming test names.

### 3.5 Dependency Pinning Policy

Adding third-party packages is an open supply chain attack surface. The `dependencyOverride: true` flag in the IAC inbound contract permits package additions, but the following constraints apply unconditionally — they cannot be bypassed by `dependencyOverride`:

| Rule | Requirement | Forbidden |
|---|---|---|
| **Version Specifier** | Exact pinned version only (e.g., `requests==2.31.0`) | Range specifiers (`>=`, `~=`, `^`, `*`) |
| **Hash Verification** | SHA-256 hash must be declared alongside every pinned dependency | Unpinned or hash-less entries in `requirements.txt` / `pyproject.toml` |
| **Approved Registry** | Packages must be sourced from the internal approved registry or PyPI with hash verification | Private indexes without hash verification; Git URL dependencies |
| **Audit Log Entry** | Every new dependency addition must produce an audit log entry naming the package, version, hash, and the `taskId` that introduced it | Silent additions with no audit trail |

> **Enforcement:** The Validator runs `pip-audit` against any diff where `dependenciesAdded: true`. A `pip-audit` finding at any severity level is a hard rejection. The Builder must resolve or pin-and-document the finding before resubmission.

### 3.6 Cumulative Scope Ledger

Every execution cycle must write its results to the **Cumulative Scope Ledger** maintained in WIKI.md §7. This is the cross-cycle tracking mechanism that detects scope explosion over time — per-cycle gates alone cannot do this.

The Validator is responsible for posting the following fields to the ledger after every passing `BuilderToValidatorPayload`:

| Field | Source | Purpose |
|---|---|---|
| `cycleId` | `taskId` from IAC | Unique identifier for this cycle |
| `filesAddedCount` | `filesMutated` — new files only | Running total of files created |
| `filesMutatedCount` | `filesMutated` — modified files | Running total of files ever touched |
| `packagesAddedCount` | `dependencyOverride.packageCount` | Running total against canvas budget |
| `newSubsystemsRegistered` | WIKI §2.2 delta | Running total of subsystems |
| `timestamp` | ISO 8601 UTC | When this cycle completed |

**Scope Review Trigger:** A mandatory scope review is automatically triggered when ANY of the following thresholds are crossed. The `orchestrator` must halt new cycles and route to HITL until the review is completed and a human operator explicitly clears the flag:

| Trigger | Threshold | Rationale |
|---|---|---|
| Cycle count | Every 10 completed cycles | Forces periodic intent check |
| Cumulative files mutated | > 40 unique files | Signals potential scope explosion |
| Cumulative packages added | Exceeds canvas §6 dependency budget | Enforces budget declared at initialization |
| New subsystems in one cycle | > 2 | Adding 3+ subsystems in one cycle is a scope explosion signal |
| `filesMutated` files from > 3 repositories in one cycle | 3+ repos | Cross-repo sprawl indicator |

### 3.7 CI/CD Quality Gate Architecture

When a project includes a Web Frontend, a Telegram Bot backend, or both, the following four-gate pipeline is mandatory. It is implemented in `.github/workflows/autonomous_gate.yml` and mirrors the local validation sequence enforced during development. Gates are **strictly sequential** — a failure at any gate aborts all subsequent gates and blocks deployment.

```
Gate 1: UI Structure Lint  ──►  Gate 2: Web E2E + Visual  ──►  Gate 3: Telegram E2E  ──►  Gate 4: Deploy
```

---

**Gate 1 — UI Structure Linting (`test_ui_structures.py`)**

Purpose: Validate that `ui_config.py` — the single source of truth for all bot menus, inline keyboard schemas, and expected text outcomes — conforms to Telegram API structural constraints before any browser or bot tests run.

| Constraint | Rule | Enforcement |
|---|---|---|
| `callback_data` length | ≤ 64 bytes per button | pytest assertion loop over all keyboard configs |
| Inline keyboard row count | ≤ 8 rows per message | pytest structural check |
| Message text length | ≤ 4096 characters | pytest assertion on all text templates |
| Button text length | ≤ 40 characters | pytest assertion on all button labels |
| SSOT enforcement | All keyboard schemas must originate from `ui_config.py`. Hardcoded keyboard dicts in handler code are forbidden and will be flagged by AST scan. | `vulture` + custom AST check |

`validationType: UI_STRUCTURE_LINT`

---

**Gate 2 — Web E2E & Visual Regression**

Purpose: Verify that the web frontend's critical user journey produces correct DOM state AND that no unintended visual regressions have been introduced since the last approved baseline.

| Component | Tool | Config File | Assertion |
|---|---|---|---|
| Headless browser E2E | Playwright | `playwright.config.ts` + `web_journey.spec.ts` | DOM updates, navigation, form submissions pass |
| Visual regression | Percy or Applitools | CLI injected in CI step | Zero unreviewed visual diffs on critical pages |

Secrets required: `PERCY_TOKEN` **or** `APPLITOOLS_API_KEY` — sourced exclusively from GitHub Actions encrypted secrets. Never hardcoded.

`validationType: E2E_WEB`, `VISUAL_REGRESSION`

---

**Gate 3 — Headless Telegram Bot E2E (MTProto)**

Purpose: Simulate a real human user interacting with the staging bot to verify end-to-end bot response correctness — including keyboard rendering, callback routing, and message text.

| Rule | Requirement |
|---|---|
| Authentication | MTProto user session via `TG_SESSION_STRING` GitHub Secret. Never a bot token — a real user session is required to interact with inline keyboards. |
| Target | Staging bot username only. The production bot username must never appear in test scripts. |
| Test script | `telegram_e2e_test.py` using Telethon or Pyrogram. Sends `/start`, extracts inline keyboards, clicks target button, asserts response matches `ui_config.py` expected outcome. |
| Log sanitisation | `TG_SESSION_STRING`, `TG_API_ID`, `TG_API_HASH` must be masked in all CI logs. Any step that prints environment variables must explicitly exclude these. |
| Isolation | Tests run against isolated staging environment. No MTProto test may send messages to a production bot. |

`validationType: TELEGRAM_E2E`

---

**Gate 4 — Conditional Deployment & Production Telemetry**

Purpose: Deploy to production only when all previous gates pass AND the trigger branch matches the production branch. Attach a runtime telemetry hook immediately after deployment.

| Condition | Rule |
|---|---|
| Branch guard | Deployment step only runs on `main` or the declared production branch. All other branches run Gates 1–3 only. |
| Telemetry hook | After deployment, a shell command posts a release event to Sentry (`SENTRY_DSN`) or Datadog (`DATADOG_API_KEY`). Both sourced from GitHub Secrets. |
| Rollback | If the telemetry hook fails post-deploy, that is not a deployment failure — log and continue. If the deployment itself fails, execute `git reset --hard` to the pre-deploy commit and raise a 🔴 SESSION STOP (Autonomous Mode) or HITL (Supervised Mode). |

`validationType: DEPLOYMENT_GATE`

---

**Secrets Management for CI/CD Pipelines**

The following secrets must be declared in GitHub Actions encrypted secrets and referenced as `${{ secrets.NAME }}` in YAML and `os.environ["NAME"]` in Python. The Builder's mandatory `detect-secrets scan` (§2.2) will catch any hardcoded value at diff time — but the Builder must never produce a hardcoded value in the first place.

| Secret Name | Purpose | Used In |
|---|---|---|
| `TG_SESSION_STRING` | MTProto user session authentication | Gate 3 |
| `TG_API_ID` | Telegram API credential | Gate 3 |
| `TG_API_HASH` | Telegram API credential | Gate 3 |
| `PERCY_TOKEN` | Percy visual regression API key | Gate 2 |
| `APPLITOOLS_API_KEY` | Applitools visual regression API key | Gate 2 (alternative) |
| `SENTRY_DSN` | Sentry error tracking endpoint | Gate 4 |
| `DATADOG_API_KEY` | Datadog RUM telemetry key | Gate 4 (alternative) |

**`ui_config.py` SSOT Mandate:**
This file is the Single Source of Truth for all UI layouts. It must define every bot menu, inline keyboard schema, and expected text outcome. Handler code must import from `ui_config.py` — it must never define keyboard structures inline. The Validator enforces this via AST scan at every cycle. A keyboard definition found outside `ui_config.py` is treated as an out-of-scope mutation and triggers a diff rejection.

### 3.8 Mandatory Cleanup Cycle

Detection without a removal obligation is incomplete. The following thresholds, when crossed, mandate a dedicated cleanup cycle before any new feature work may begin. The Validator must reject new feature diffs until the cleanup cycle passes.

| Threshold | Measurement | Mandatory Action |
|---|---|---|
| Dead code symbols > 3% of total codebase symbols | `vulture` across entire codebase | Cleanup cycle: remove or justify all flagged symbols |
| Unused agents > 2 in GLOSSARY | Agents with no `taskId` reference in audit log AND zero subsystem activity (see GLOSSARY.md §1.4) | Agent deprecation sweep |
| Dependency count exceeds canvas budget | `requirements.txt` comment header count | Dependency audit: remove or justify each over-budget package |
| Test files with zero collected tests > 5 | `pytest --collect-only` | Dead test removal sweep |
| Functions exceeding 50 lines > 5 across codebase | `flake8 --max-function-length=50` on full codebase | Decomposition cycle before new features |

> **Cleanup Cycle Contract:** A cleanup cycle is a standard PROTOCOL cycle with `approvedFileSet` restricted exclusively to removal and decomposition operations. No new features, no new packages, no new abstractions may be introduced during a cleanup cycle.

---

## 4. INTER-AGENT DATA CONTRACTS (IAC)

All IAC schemas carry a `schemaVersion` field. Agents must validate the incoming `schemaVersion` against their compiled expectations before processing. A mismatch must trigger an immediate HITL escalation rather than silent degradation.

### 4.1 Orchestrator → Builder Inbound Schema (`iac_inbound.json`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OrchestratorToBuilderContract",
  "type": "object",
  "properties": {
    "schemaVersion": {
      "type": "string",
      "description": "Version of this IAC schema. Must be validated by the receiving agent.",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "taskId": { "type": "string" },
    "approvedFileSet": {
      "type": "array",
      "items": { "type": "string" }
    },
    "mutationDirectives": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "targetFile":       { "type": "string" },
          "action":           { "type": "string", "enum": ["CREATE", "MODIFY", "DELETE"] },
          "targetInterface":  { "type": "string" },
          "explicitLogic":    { "type": "string" }
        },
        "required": ["targetFile", "action", "explicitLogic"]
      }
    },
    "dependencyOverride": {
      "type": "object",
      "description": "Declares intent to add one or more third-party packages. Must include written justification — a bare boolean is insufficient.",
      "properties": {
        "approved":      { "type": "boolean" },
        "justification": { "type": "string", "minLength": 30, "description": "Minimum 30 characters. Must state why no existing package satisfies the need." },
        "packageCount":  { "type": "integer", "minimum": 1, "description": "Number of new packages being introduced in this cycle." }
      },
      "required": ["approved", "justification", "packageCount"]
    },
    "forbiddenActions":   { "type": "array", "items": { "type": "string" } }
  },
  "required": ["schemaVersion", "taskId", "approvedFileSet", "mutationDirectives", "dependencyOverride", "forbiddenActions"]
}
```

**Current Live Version:** `1.0.0`

### 4.2 Builder → Validator Outbound Schema (`iac_outbound.json`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "BuilderToValidatorPayload",
  "type": "object",
  "properties": {
    "schemaVersion": {
      "type": "string",
      "description": "Version of this IAC schema. Must be validated by the receiving agent.",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "taskId":       { "type": "string" },
    "diffHash":     { "type": "string" },
    "filesMutated": { "type": "array", "items": { "type": "string" } },
    "metrics": {
      "type": "object",
      "properties": {
        "maxNestingDepth":          { "type": "integer", "description": "Highest nesting depth found across all mutated files." },
        "linesAdded":               { "type": "integer", "description": "Total logical lines added (excluding comments and blanks)." },
        "dependenciesAdded":        { "type": "boolean", "description": "Whether any new third-party packages were introduced." },
        "lineCoverage":             { "type": "number",  "description": "Line coverage percentage over filesMutated (0–100). Must be ≥ 85 to pass." },
        "branchCoverage":           { "type": "number",  "description": "Branch coverage percentage over filesMutated (0–100). Must be ≥ 75 to pass." },
        "deadCodeSymbolCount":      { "type": "integer", "description": "Number of unreachable symbols flagged by vulture. Must be 0 to pass." },
        "banditFindingCount":       { "type": "integer", "description": "Number of bandit findings at MEDIUM severity or above. Must be 0 to pass." },
        "functionLengthViolations": { "type": "integer", "description": "Number of functions exceeding 50 logical lines. Must be 0 to pass." }
      },
      "required": [
        "maxNestingDepth", "linesAdded", "dependenciesAdded",
        "lineCoverage", "branchCoverage", "deadCodeSymbolCount",
        "banditFindingCount", "functionLengthViolations"
      ]
    }
  },
  "required": ["schemaVersion", "taskId", "diffHash", "filesMutated", "metrics"]
}
```

**Current Live Version:** `1.0.0`

### 4.3 Validator → Orchestrator Validation Report Schema (`iac_validation_report.json`)

This is the missing return leg of the IAC chain. The Validator must emit this payload to the Orchestrator after every diff audit — whether passing or failing. The Orchestrator must not proceed to the WIKI re-indexing loop without receiving a `PASS` status on this contract.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ValidatorToOrchestratorReport",
  "type": "object",
  "properties": {
    "schemaVersion": {
      "type": "string",
      "description": "Version of this IAC schema. Must be validated by the receiving agent.",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "taskId":           { "type": "string" },
    "diffHash":         { "type": "string", "description": "Must match the diffHash from the BuilderToValidatorPayload to confirm the correct diff was evaluated." },
    "validationStatus": { "type": "string", "enum": ["PASS", "FAIL", "FAIL_HITL"] },
    "failureReasons": {
      "type": "array",
      "description": "Empty array on PASS. Each entry describes one discrete failure.",
      "items": {
        "type": "object",
        "properties": {
          "ruleId":       { "type": "string", "description": "e.g. DEAD_CODE, COVERAGE_LINE, BANDIT_MEDIUM, FUNCTION_LENGTH" },
          "affectedFile": { "type": "string" },
          "detail":       { "type": "string" }
        },
        "required": ["ruleId", "affectedFile", "detail"]
      }
    },
    "metrics": {
      "$ref": "iac_outbound.json#/properties/metrics",
      "description": "Full metrics object echoed from the BuilderToValidatorPayload for Orchestrator audit logging."
    },
    "recommendedAction": {
      "type": "string",
      "enum": ["APPROVE", "RESUBMIT", "HITL"],
      "description": "APPROVE: proceed to WIKI re-index. RESUBMIT: Builder must fix and resubmit. HITL: halt and escalate to human operator."
    }
  },
  "required": ["schemaVersion", "taskId", "diffHash", "validationStatus", "failureReasons", "recommendedAction"]
}
```

**Current Live Version:** `1.0.0`

---

## 5. AUTONOMOUS REACTION PATHWAYS

When the MVAT encounters an exception state, it resolves it autonomously. There are no blocking escalations. Every situation is either fixed, quarantined, or deferred to the End-of-Session Report. The human's accountability window is the report.

```
+---------------------------+-------------------------------------------+
| Trigger Condition         | Autonomous Resolution                     |
+---------------------------+-------------------------------------------+
| Compilation Error         | `layer6-self-healing` attempts fix.       |
|                           | Max 3 iterations. If still failing:       |
|                           | skip cycle → log DEFERRED_DEFECT →        |
|                           | continue with next task.                  |
+---------------------------+-------------------------------------------+
| Contract Overlap /        | `orchestrator` locks concurrency engine.  |
| Race Condition            | Resolves conflict, retries. If core DB    |
|                           | schema conflict: quarantine affected      |
|                           | component → log → continue.              |
+---------------------------+-------------------------------------------+
| Out-Of-Scope Mutation     | Reject diff. Builder rebuilds within      |
| Attempt                   | `approvedFileSet`. If repeated: quarantine|
|                           | the task → log DEFERRED_SCOPE_REQUEST →  |
|                           | continue.                                 |
+---------------------------+-------------------------------------------+
| IAC Schema Version        | Skip affected cycle. Log                  |
| Mismatch                  | SCHEMA_MISMATCH_DEFERRED. Continue.       |
+---------------------------+-------------------------------------------+
| Dead Code Detected        | Builder removes or justifies. If still    |
| (`vulture` flag ≥ 80%)    | present after 1 attempt: log              |
|                           | DEFERRED_DEAD_CODE. Continue.             |
+---------------------------+-------------------------------------------+
| Test Coverage Below Gate  | Builder adds tests. Max 2 attempts. If    |
| (line < 85%, branch < 75%)| still failing: log DEFERRED_COVERAGE_DEBT |
|                           | → continue.                               |
+---------------------------+-------------------------------------------+
| Bare / Swallowed Exception| Builder applies typed handler. Max 2      |
| (`bandit` MEDIUM+)        | attempts. If unfixable: quarantine the    |
|                           | affected file → log DEFERRED_SECURITY_DEBT|
|                           | → continue.                               |
+---------------------------+-------------------------------------------+
| Security Finding in auth  | Do NOT deploy the affected component.     |
| or IAC path               | Quarantine it: mark QUARANTINE_NO_DEPLOY. |
|                           | All other components deploy normally.     |
|                           | Log in End-of-Session Report.             |
+---------------------------+-------------------------------------------+
| Function Exceeds 50 Lines | Builder decomposes. Max 2 attempts. If    |
|                           | still failing: log DEFERRED_TECH_DEBT →   |
|                           | continue.                                 |
+---------------------------+-------------------------------------------+
| Dependency Audit Failure  | Builder resolves or pins+documents. If    |
| (`pip-audit` any severity)| unfixable: quarantine the dependency →    |
|                           | log DEFERRED_DEPENDENCY → continue.       |
+---------------------------+-------------------------------------------+
| Execution Lock TTL        | `internal-auditor` forces release,        |
| Exceeded / No Heartbeat   | rolls back to pre-lock commit, restarts   |
|                           | the cycle. Fully autonomous. No stop.     |
+---------------------------+-------------------------------------------+
| Secrets Detected in       | Quarantine the file immediately.          |
| any file                  | Mark QUARANTINE_SECRETS. Do not deploy.   |
|                           | Continue all other work. Log in report.   |
+---------------------------+-------------------------------------------+
```

---

## 6. AUTONOMOUS RESOLUTION PROTOCOL

The system never stops for a human during a session. Every situation is resolved by one of three actions: **fix it autonomously**, **quarantine it and continue**, or **defer it to the report**. The human reviews the report after the session ends.

### 6.1 Autonomous Fix

The system attempts to resolve the issue without any human input.

| Trigger | Approach | Max Attempts | If Still Failing |
|---|---|---|---|
| Compilation error | `layer6-self-healing` | 3 | → Quarantine |
| Coverage below gate | Builder adds tests | 2 | → Quarantine |
| Function exceeds 50 lines | Builder decomposes | 2 | → Defer as `DEFERRED_TECH_DEBT` |
| Dead code (non-critical) | Builder removes | 1 | → Defer as `DEFERRED_DEAD_CODE` |
| `bandit` MEDIUM (non-auth) | Builder applies typed handler | 2 | → Quarantine |
| Scope review threshold crossed | Activate Conservative Mode — continue all existing work, no new scope additions | — | Conservative Mode stays active for session remainder |
| Lock TTL breach | `internal-auditor` full autonomous recovery | 1 | → Quarantine affected cycle, continue |

### 6.2 Quarantine

When autonomous fix fails, or when the issue involves a security-sensitive file, the Orchestrator quarantines the affected component — isolating it from deployment and further mutation — and continues all other work uninterrupted.

**Quarantine means:**
- The file is marked with a `QUARANTINE_*` flag in the audit log
- The file is excluded from the current and future deployment steps for this session
- All other files in the project continue to deploy and mutate normally
- The quarantined item appears prominently in the End-of-Session Report for human review

| Situation | Quarantine Flag | Continues? |
|---|---|---|
| Secrets detected in any file | `QUARANTINE_SECRETS` | All other files deploy normally |
| Security finding in auth/IAC path after failed fix | `QUARANTINE_NO_DEPLOY` | All other components deploy |
| Compilation error after 3 failed healing iterations | `QUARANTINE_BUILD_FAILURE` | All other cycles continue |
| `bandit` MEDIUM in auth after failed fix | `QUARANTINE_SECURITY_DEBT` | All other files proceed |
| Dependency audit failure after failed fix | `QUARANTINE_DEPENDENCY` | All other packages deploy |
| DB schema conflict that cannot be auto-resolved | `QUARANTINE_SCHEMA_CONFLICT` | All other schema changes proceed |

### 6.3 Defer to Report

Items that require a human decision but do not affect the safety or correctness of current work. Logged immediately, never acted on during the session.

| Item | Log Entry |
|---|---|
| Scope expansion requested | `DEFERRED_SCOPE_REQUEST` |
| Canvas amendment needed | `DEFERRED_AMENDMENT` |
| New agent registration needed | `DEFERRED_AGENT_REGISTRATION` |
| Subsystem ownership conflict | `DEFERRED_OWNERSHIP_CONFLICT` |
| IAC schema version mismatch | `SCHEMA_MISMATCH_DEFERRED` |
| Exclusion that cannot be expressed as a detectable pattern | `DEFERRED_EXCLUSION_REVIEW` |

### 6.4 Session Minimum Viable Brief

Before filling the canvas and starting work, the Orchestrator checks that the brief contains enough information to fill the five scope-critical fields. If any field is genuinely ambiguous, the Orchestrator asks **one targeted question** — the one that resolves the most fields at once — waits for the answer, then begins. It does not ask five separate questions. It does not present a canvas for review.

| Canvas Field | What the Brief Must Contain |
|---|---|
| §1 Problem/Pain | A concrete human problem |
| §1 Primary Workflow | An identifiable Input, Process, and Output |
| §1 Strict Exclusions | At least one explicitly out-of-scope feature |
| §2 Stack | At minimum: backend language and database type |
| §6 Dependency Budget | Enough context to infer a reasonable ceiling |
