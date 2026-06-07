# WIKI.md — CENTRALIZED ARCHITECTURE & SYSTEM INDEX
> **Document Version:** 1.2.0 | **Schema Baseline:** draft-07 | **Sync Policy:** Automated post-commit via `orchestrator`

This component establishes the centralized, machine-readable repository indexing strategy, defining how state, architecture, data contracts, and cross-repository dependencies are cataloged and systematically updated by the agent fleet.

---

## 1. REPOSITORY INDEXING SPECIFICATION

The WIKI.md acts as the single source of truth (SSOT) for the multi-agent system's structural context. It does not contain documentation or conversational guides. It serves as a structured index that the `orchestrator` reads during its mandatory Pre-Build Research phase to resolve system dependencies, file locations, and structural data models before producing any execution graph. There is no separate `layer1-research` agent — context gathering is an internal phase of the `orchestrator`, not a delegated call.

---

## 2. THE GRAPH ARCHITECTURE INDEX

The topology below reflects the **baseline architecture at document version 1.1.0** and is a human-readable orientation aid — not a machine-enforced contract. Agents must use the Service Mapping Ledger (§2.2) and Cumulative Scope Ledger (§6) for authoritative blast radius calculations. `internal-auditor` must raise a `WIKI_SYNC_FAILURE` if any subsystem registered in §2.2 has no representation in this diagram and the diagram has not been updated within the current release cycle.

### 2.1 Domain Dependency Matrix

```
       [ Core Shared Types ] ──► [ Database / Memory Layer ]
                   │                        │
                   ▼                        ▼
       [ GitHub / Groq Integrations ] ──► [ Core API Services ]
                                            │
                                            ▼
                                  [ Telegram UI Framework ]
```

### 2.2 System Service Mapping Ledger

This ledger is the canonical registry of every subsystem component. It must include all path roots referenced by any active agent. Manual additions outside the automated sync loop require an immediate `internal-auditor` sweep.

**Subsystem Fleet Limits:**
- **Maximum registered subsystems: 15.** With a 6-agent fleet, 30 subsystems was disproportionate. 15 is the new hard upper bound. A decommission review is required before any registration that would exceed it.
- **Dormant subsystem policy:** Any subsystem that has not appeared in a `filesMutated` array in the Cumulative Scope Ledger (§7) for **60 or more days** is automatically flagged as dormant by `internal-auditor`. Dormant subsystems must be reactivated (with justification) or decommissioned within 14 days. Decommissioning produces a `SUBSYSTEM_DECOMMISSIONED` audit event.
- **Ownership limit:** No single agent may own more than **3 subsystems**. Reduced from 4 to match the smaller fleet — concentration of ownership is higher risk with fewer agents.

| Subsystem Component           | Root Path Location          | Target Schema Contract                    | Primary Owner Agent     |
|-------------------------------|-----------------------------|-------------------------------------------|-------------------------|
| **Core State Engine**         | `src/core/state/`           | `src/core/schemas/state.json`             | `layer3-development`    |
| **Multi-Agent Routing**       | `src/engine/hermes/`        | `src/core/schemas/hermes_workflow.json`   | `orchestrator`          |
| **API Integration Layer**     | `src/integrations/`         | `src/core/schemas/api_contracts.json`     | `layer3-development`    |
| **UI Keyboard Manager**       | `src/ui/telegram/`          | `src/core/schemas/ui_layouts.json`        | `layer3-development`    |
| **Self-Healing Engine**       | `src/engine/self_healing/`  | `src/core/schemas/healing_contract.json`  | `layer6-self-healing`   |
| **Documentation Pipeline**    | `src/ops/docs/`             | `src/core/schemas/docs_schema.json`       | `documentation-agent`   |
| **SDLC & Orchestration**      | `src/engine/sdlc/`          | `src/core/schemas/sdlc_manifest.json`     | `orchestrator`          |
| **Audit & Integrity**         | `src/ops/audit/`            | `src/core/schemas/audit_log.json`         | `internal-auditor`      |
| **UI Layout Config**          | `src/config/ui_config.py`   | `src/core/schemas/ui_layout_config.json`  | `layer4-testing`        |
| **E2E Test Suite**            | `tests/e2e/`                | `src/core/schemas/e2e_manifest.json`      | `layer4-testing`        |
| **CI/CD Pipeline**            | `.github/workflows/`        | `src/core/schemas/cicd_manifest.json`     | `orchestrator`          |
| **Production Telemetry**      | `src/ops/telemetry/`        | `src/core/schemas/telemetry_config.json`  | `documentation-agent`   |

> **Consolidations from previous version:** The former `Changelog Pipeline` and `Technical Docs Pipeline` rows are merged into `Documentation Pipeline` (owned by `documentation-agent`). The former `SDLC Orchestration` and `Change Advisory Board` rows are merged into `SDLC & Orchestration` (owned by `orchestrator`). The `Schema Debugger` and `Parallel Dispatcher` rows are removed — both are now internal capabilities of `layer4-testing` and `orchestrator` respectively. **Ownership distribution:** `layer4-testing` owns `UI Layout Config` and `E2E Test Suite` because it validates both via `test_ui_structures.py` and the E2E gate respectively. `documentation-agent` owns `Production Telemetry` because it manages all post-cycle output including the deployment release event. This keeps all agents at ≤ 3 owned subsystems.

---

## 3. STATIC DATA SCHEMAS & INTERFACES

### 3.1 Core User Session Schema

This absolute Pydantic/JSON layout maps the structure of `ctx.user_data` across all integration tracks. Changes to this model require a mandatory PLAYBOOK.md migration route.

> **⚠ Schema Mutation Policy:** Any modification to `UserSessionContext` must increment `schemaVersion`, update this block atomically via the re-indexing loop, and trigger a `SCHEMA_VERIFY` post-condition check on all consumer agents before deployment.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "UserSessionContext",
  "type": "object",
  "properties": {
    "schemaVersion": {
      "type": "string",
      "description": "Semantic version of this schema. Must be incremented on any structural change.",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "userId":        { "type": "string" },
    "activeTrack": {
      "type": "string",
      "enum": ["PROTOCOL", "PLAYBOOK", "AUDIT", "MAINTENANCE", "RECOVERY", "AUTONOMOUS"],
      "description": "The operational mode the session is currently executing under. AUTONOMOUS activates when the user declares a session duration — governed by CANVAS.md §8.7 and PROTOCOL.md §6."
    },
    "securityTier":  { "type": "integer", "minimum": 1, "maximum": 3 },
    "stateManifest": {
      "type": "object",
      "properties": {
        "lastCommitHash":    { "type": "string" },
        "pendingSync":       { "type": "boolean" },
        "autonomousSessionId": {
          "type": "string",
          "description": "ID of the active autonomous session, if any. Empty string when activeTrack is not AUTONOMOUS. Used by internal-auditor to associate audit events with their session."
        },
        "conservativeMode":  {
          "type": "boolean",
          "description": "True when a scope review threshold has been crossed during an autonomous session. Blocks new subsystems, packages, and agents for the remainder of the session."
        }
      },
      "required": ["lastCommitHash", "pendingSync", "autonomousSessionId", "conservativeMode"]
    }
  },
  "required": ["schemaVersion", "userId", "activeTrack", "securityTier", "stateManifest"]
}
```

**Current Live Version:** `1.0.0`

### 3.2 Security Tier Privilege Matrix

`securityTier` in `UserSessionContext` is a first-class access control field. Every agent that branches on this value must validate it against this matrix — not against hardcoded assumptions.

| Tier | Label | Permitted Operations | Forbidden Operations |
|---|---|---|---|
| `1` | **Standard** | Read-only access to WIKI index and schema definitions. May submit task requests to the Orchestrator. May not approve diffs or release locks. | Modifying `approvedFileSet`, issuing IAC contracts, triggering playbooks, accessing audit logs. |
| `2` | **Operator** | All Tier 1 permissions. May define `approvedFileSet`, issue inbound IAC contracts, trigger standard PROTOCOL cycles, and review `BuilderToValidatorPayload` reports. | Issuing or approving Playbooks with `criticality: CRITICAL`, overriding `forbiddenActions`, releasing Execution Locks manually, accessing raw credential stores. |
| `3` | **Administrator** | All Tier 2 permissions. May trigger and approve PLAYBOOK cycles at any criticality, override `forbiddenActions` with written justification, manually release Execution Locks, and access full audit logs. | No additional restrictions — Tier 3 is the ceiling. All Tier 3 actions must produce a mandatory audit log entry. |

> **Enforcement:** Any agent that receives a payload with `securityTier` below the required threshold for the requested operation must reject the request and emit a `TIER_INSUFFICIENT` error payload. It must not attempt partial execution.

### 3.3 Audit Log Entry Schema

The `internal-auditor` writes to `src/ops/audit/` using `audit_log.json`. Every agent that produces an audit event must conform to this schema. Consumers of audit data must validate against it.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AuditLogEntry",
  "type": "object",
  "properties": {
    "logId":           { "type": "string", "description": "UUID v4. Must be unique across all entries." },
    "timestamp":       { "type": "string", "description": "ISO 8601 UTC. Set at the moment of event capture, not at write time." },
    "agentId":         { "type": "string", "description": "Identifier of the agent that produced the event." },
    "taskId":          { "type": "string", "description": "Execution cycle task ID. Empty string if the event occurred outside a cycle." },
    "eventType": {
      "type": "string",
      "enum": [
        "LOCK_ACQUIRED", "LOCK_RELEASED", "LOCK_TIMEOUT",
        "DIFF_SUBMITTED", "DIFF_REJECTED", "DIFF_APPROVED",
        "PLAYBOOK_STARTED", "PLAYBOOK_COMPLETED", "PLAYBOOK_FAILED",
        "WIKI_SYNC_SUCCESS", "WIKI_SYNC_FAILURE",
        "DEPENDENCY_ADDED", "SECURITY_FINDING",
        "TIER_INSUFFICIENT", "HITL_TRIGGERED",
        "SYSTEM_DRIFT_DETECTED", "SCHEMA_VERSION_MISMATCH",
        "CAB_VETO", "CAB_VETO_OVERRIDE",
        "CANVAS_APPROVED", "CANVAS_AUTO_APPROVED", "CANVAS_AMENDED",
        "SESSION_APPROVED", "SESSION_STARTED", "SESSION_PAUSED",
        "SESSION_RESUMED", "SESSION_ENDED", "SESSION_STOP_TRIGGERED",
        "CONSERVATIVE_MODE_ACTIVE",
        "DEFERRED_DEFECT", "DEFERRED_COVERAGE_DEBT", "DEFERRED_TECH_DEBT",
        "DEFERRED_DEAD_CODE", "DEFERRED_SECURITY_DEBT",
        "SCHEMA_MISMATCH_DEFERRED", "DEFERRED_SCOPE_REQUEST",
        "DEFERRED_AMENDMENT", "DEFERRED_AGENT_REGISTRATION",
        "DEFERRED_OWNERSHIP_CONFLICT",
        "DEPRECATION_CANDIDATE", "AGENT_DECOMMISSIONED",
        "DEPRECATION_OVERRIDDEN", "DEPRECATION_CONFIRMED",
        "SUBSYSTEM_DECOMMISSIONED", "SCOPE_FREEZE_LIFTED"
      ]
    },
    "severity":        { "type": "string", "enum": ["INFO", "WARNING", "ERROR", "CRITICAL"] },
    "message":         { "type": "string", "description": "Human-readable event description." },
    "affectedFiles":   { "type": "array", "items": { "type": "string" }, "description": "Files implicated in the event. Empty array if not applicable." },
    "resolutionStatus":{ "type": "string", "enum": ["OPEN", "RESOLVED", "ESCALATED", "ACKNOWLEDGED"] }
  },
  "required": ["logId", "timestamp", "agentId", "taskId", "eventType", "severity", "message", "affectedFiles", "resolutionStatus"]
}
```

**Current Live Version:** `1.0.0`

---

### 3.4 UI Layout Config Schema (`ui_layout_config.json`)

This schema governs `ui_config.py` — the Single Source of Truth for all Telegram bot menus, inline keyboard schemas, and expected text outcomes. Every keyboard definition must be traceable to a validated entry here. The Validator enforces this via AST scan at every cycle.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "UILayoutConfig",
  "type": "object",
  "properties": {
    "schemaVersion": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "menus": {
      "type": "object",
      "description": "Named menu definitions. Key is the menu identifier used in handler imports.",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "maxLength": 4096,
            "description": "Message text. Telegram API limit."
          },
          "keyboard": {
            "type": "array",
            "maxItems": 8,
            "description": "Inline keyboard rows. Telegram API maximum: 8 rows.",
            "items": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "text":          { "type": "string", "maxLength": 40, "description": "Button label." },
                  "callback_data": { "type": "string", "maxLength": 64, "description": "Telegram API hard limit: 64 bytes." }
                },
                "required": ["text", "callback_data"]
              }
            }
          },
          "expected_response": {
            "type": "string",
            "description": "Expected bot response text after this menu's primary action. Used by telegram_e2e_test.py for assertion matching."
          }
        },
        "required": ["text", "keyboard"]
      }
    }
  },
  "required": ["schemaVersion", "menus"]
}
```

**Current Live Version:** `1.0.0`

> **Enforcement:** `test_ui_structures.py` loops through every `menus` entry, asserts each constraint, and fails the entire run on any single violation. Handler code that constructs inline keyboards without importing from `ui_config.py` is rejected as an out-of-scope mutation.

---

## 4. WIKI SYNC & COGNITIVE RE-INDEXING LOOP

The WIKI.md must never drift from the physical state of the repository files. It is strictly maintained via an automated post-commit pipeline.

### 4.1 The Re-Indexing Automation Workflow

Upon successful completion of an execution cycle (standard PROTOCOL.md or override PLAYBOOK.md), the `orchestrator` must enforce the following atomic sync loop before freeing the Execution Lock:

1. **Trigger Engine:** Invoke the `documentation-agent` to begin the post-cycle documentation pass.
2. **AST Analysis:** Scan all mutated files listed in the task's `filesMutated` array. Extract updated function signatures, new class paths, and model structural shifts.
3. **Atomic Modification:** Update the relevant tables and JSON schemas inside WIKI.md. Do not rewrite the entire file — perform targeted, block-level line modifications using strict regex anchors.
4. **Validation Gate:** The `layer4-testing` (Validator) agent must parse the updated WIKI.md against the codebase's live imports. If a discrepancy or broken link is found, the sync is aborted and a `WIKI_SYNC_FAILURE` error code is raised.

### 4.2 Handling Synchronization Drift

If a manual developer commit introduces state changes that bypass the automated agent indexing loops, the `internal-auditor` will flag a **System Drift Exception** during its scheduled sweep.

**Remediation Strategy:** The system locks all active execution queues. The `orchestrator` runs a full WIKI re-baseline sweep using its Pre-Build Research phase — scanning the entire workspace directory and regenerating the index from scratch. There is no separate `layer1-research` agent for this — the orchestrator's context-gathering capability is invoked directly.

### 4.3 WIKI Re-Indexing Failure After a Successful Commit

If the code commit succeeds but the WIKI re-indexing sync fails, do **not** roll back the code. The recovery procedure is defined in **PLAYBOOK.md §4.3**. The key rule: the `orchestrator` sets `pendingSync: true` on the affected sessions and holds the Execution Lock until the targeted re-index sweep succeeds or HITL resolves the issue.

**In Autonomous Session Mode:** A `WIKI_SYNC_FAILURE` is classified as a 🟡 Autonomous Fallback trigger. The `orchestrator` retries the targeted re-index once. If the second attempt also fails, the item is logged as `DEFERRED_DEFECT` and the session continues — the broken sync does not stop autonomous work, but the End-of-Session Report will surface it for human resolution.

---

## 5. AGENT REGISTRY

For canonical agent definitions, roles, and ownership boundaries, see **GLOSSARY.md — Agent & Term Registry**. The WIKI does not duplicate that content. The Service Mapping Ledger (§2.2) references agent identifiers only; their behavioral contracts are defined in GLOSSARY.md.

---

## 6. CONSERVATIVE MODE PROTOCOL

When certain thresholds are crossed, the system activates **Conservative Mode** — it narrows what it will add autonomously, but it never stops working. There is no scope freeze that halts execution. Work continues at all times.

**Conservative Mode activation triggers:**

| Trigger | Condition |
|---|---|
| Cumulative Scope Review (PROTOCOL §3.6) | Any scope review threshold crossed |
| Mandatory Cleanup threshold (PROTOCOL §3.8) | Any cleanup threshold crossed — cleanup runs inline before next feature cycle |
| Subsystem ceiling reached | §2.2 count hits 15 |
| Agent fleet ceiling reached | GLOSSARY §1 count hits 8 |
| Dependency budget exceeded | Running package count exceeds canvas §6 budget |

**In Conservative Mode:**
- All existing in-flight cycles continue normally to completion.
- New cycles continue — but the `approvedFileSet` may not include new subsystems, new packages, or new agents.
- Playbooks at any criticality level continue if they fall within the session scope and do not add new-scope elements.
- Conservative Mode is logged as `CONSERVATIVE_MODE_ACTIVE` and surfaces in the End-of-Session Report.

**Returning from Conservative Mode:**
- Happens automatically when the cleanup cycle passes (PROTOCOL §3.8) or the threshold is resolved.
- No human action required to resume full operation — the system resumes on its own.
- The End-of-Session Report shows when Conservative Mode was active and when it ended.

---

## 7. CUMULATIVE SCOPE LEDGER

This ledger is the cross-cycle accumulator that enables detection of scope explosion over time. It is updated by the Validator after every passing cycle and by the `orchestrator` after every completed playbook.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CumulativeScopeLedger",
  "type": "object",
  "properties": {
    "schemaVersion":             { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "projectCanvasId":           { "type": "string", "description": "The active canvas ID this ledger belongs to." },
    "totalCyclesCompleted":      { "type": "integer", "description": "Incremented after every passing ValidatorToOrchestrator PASS report." },
    "totalFilesCreated":         { "type": "integer", "description": "Running count of net-new files added across all cycles." },
    "totalFilesMutated":         { "type": "integer", "description": "Running count of unique files ever modified (not double-counted)." },
    "totalPackagesAdded":        { "type": "integer", "description": "Running total of third-party packages introduced. Must not exceed canvas dependency budget." },
    "totalSubsystemsRegistered": { "type": "integer", "description": "Current registered subsystem count. Must not exceed 15." },
    "totalAgentsRegistered":     { "type": "integer", "description": "Current registered agent count. Must not exceed 8." },
    "lastScopeReviewCycle":      { "type": "integer", "description": "Cycle number at which the last mandatory scope review was completed." },
    "scopeFreeze":               { "type": "boolean", "description": "Whether a scope freeze is currently active." },
    "conservativeMode":          { "type": "boolean", "description": "Whether the session is in Conservative Mode — no new subsystems, packages, or agents permitted. Activated by a scope review threshold during an autonomous session." },
    "activeAutonomousSessionId": { "type": "string", "description": "ID of the current autonomous session, if any. Empty string when not in autonomous mode." },
    "totalDeferredItems":        { "type": "integer", "description": "Running count of items deferred during autonomous sessions. High counts indicate quality debt accumulating faster than it is being resolved." },
    "cycleLog": {
      "type": "array",
      "description": "One entry per completed cycle, newest first.",
      "items": {
        "type": "object",
        "properties": {
          "cycleId":              { "type": "string" },
          "sessionId":            { "type": "string", "description": "Autonomous session ID if this cycle ran in Autonomous Mode. Empty string if Supervised." },
          "timestamp":            { "type": "string" },
          "filesCreated":         { "type": "integer" },
          "filesMutated":         { "type": "integer" },
          "packagesAdded":        { "type": "integer" },
          "newSubsystems":        { "type": "integer" },
          "repositoriesTouched":  { "type": "integer" },
          "cleanupCycle":         { "type": "boolean", "description": "True if this was a mandatory cleanup cycle." },
          "deferredItemsThisCycle": { "type": "integer", "description": "Count of items deferred during this cycle. Non-zero only in Autonomous Mode." }
        },
        "required": ["cycleId", "sessionId", "timestamp", "filesMutated", "packagesAdded", "repositoriesTouched"]
      }
    }
  },
  "required": ["schemaVersion", "projectCanvasId", "totalCyclesCompleted", "totalFilesCreated", "totalFilesMutated", "totalPackagesAdded", "scopeFreeze", "conservativeMode", "activeAutonomousSessionId", "totalDeferredItems", "cycleLog"]
}
```

**Current Live Version:** `1.1.0`
