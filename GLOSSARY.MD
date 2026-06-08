# GLOSSARY.md — AGENT & TERM REGISTRY
> **Document Version:** 1.1.0 | **Scope:** Canonical definitions for every agent identifier and system term used across WIKI.md, PROTOCOL.md, PLAYBOOK.md, and CANVAS.md

This file is the single source of truth for agent identities and system terminology. No other document defines agent roles — they only reference identifiers listed here. Any new agent introduced to the system must be registered here before it may be referenced elsewhere.

**Agent Fleet Limits:**
- **Maximum registered agents: 8** across all layers. This ceiling is set close to the actual minimum to prevent casual proliferation. The current fleet of 6 leaves 2 buffer slots — not 14.
- **Maximum subsystem ownership per agent: 3** (enforced by WIKI.md §2.2). With a smaller fleet, concentration of ownership is the primary sprawl risk.
- **No layer reservation policy.** Reserving layer numbers for agents that do not yet exist is speculative architecture applied to documentation. Layers are assigned when agents are registered, not before.

---

## 1. AGENT REGISTRY

### 1.1 Core MVAT Triad

These three agents are the irreducible minimum. No execution cycle may begin without all three named and active.

| Agent Identifier | Aliases | Role & Responsibilities |
|---|---|---|
| `orchestrator` | `sdlc-orchestrator`, `ai-orchestrator`, `project-manager` | Single unified lifecycle and planning agent. **Planning phase:** ingests objectives, gathers pre-build context by reading WIKI.md (absorbs the former `layer1-research` role — this is a mandatory internal step, not a separate agent), produces deterministic execution graphs, and defines the `approvedFileSet`. **Lifecycle phase:** owns the Execution Lock, emits heartbeats, enforces atomic sync loops after every cycle, triggers the documentation pipeline, and is the only agent authorised to free the lock. **Concurrency capability:** when a Playbook step declares `"concurrency": true`, the Orchestrator manages parallel worker dispatch directly — this is an internal scheduling capability, not a delegated agent. The two formerly distinct orchestrators (`sdlc-orchestrator`, `ai-orchestrator`) created coordination overhead and a disambiguation problem. They are now one. |
| `layer3-development` | Builder, `specialized-devs` | Primary code mutation agent. Ingests the Orchestrator's inbound contract (`iac_inbound.json`) and generates file diffs strictly within the `approvedFileSet`. Responsible for static typing, inline documentation, and self-correcting localized compilation failures. Before submitting any diff, must run `detect-secrets scan` on all mutated files — any finding is a hard stop. |
| `layer4-testing` | Validator, `sdlc-manager` | Post-build validation agent. Audits Builder diffs against the original task contract, enforces all quality gates (linting, coverage, dead code, security, complexity), verifies scope containment, and issues the `ValidatorToOrchestratorReport`. **Also absorbs the former `schema-debugger` role:** after every WIKI re-indexing cycle, the Validator runs schema integrity checks against live codebase imports. Schema validation is a quality gate — it does not require a separate agent identity. |

### 1.2 Support Layer

These three agents operate outside the normal MVAT cycle flow. They are genuinely distinct roles that cannot be absorbed into the triad without violating single-responsibility.

| Agent Identifier | Aliases | Role & Responsibilities |
|---|---|---|
| `layer6-self-healing` | — | Autonomous error recovery agent. Receives failed compilation logs from the Builder and attempts remediation up to 3 iterations before mandatory HITL escalation. Operates outside normal cycle flow — it is triggered by failure, not by plan. Must not be triggered when a PLAYBOOK fails; playbook failures always escalate to HITL. |
| `internal-auditor` | — | Background integrity agent. Detects System Drift Exceptions (manual commits bypassing agent loops), monitors Execution Lock TTL via 5-minute polls, manages dormant subsystem flagging, and maintains the Cumulative Scope Ledger triggers. Operates independently of active cycles. When drift is detected, locks all execution queues and initiates a full WIKI re-baseline. |
| `documentation-agent` | `changelog-writer`, `technical-writer` | Post-cycle documentation agent. Invoked by the Orchestrator after every successful cycle. In a single pass: generates structured changelog entries from `filesMutated` AND performs AST analysis to update human-readable technical documentation. These were formerly two separate agents (`changelog-writer`, `technical-writer`) invoked simultaneously — two agents doing one job with no handoff between them. They are now one. |

### 1.3 Eliminated Agent Inventory

The following identifiers existed in previous document versions. They are recorded here to prevent re-introduction under the same names.

| Former Identifier | Disposition | Absorbed By |
|---|---|---|
| `sdlc-orchestrator` | Merged | `orchestrator` (lifecycle phase) |
| `ai-orchestrator` | Merged | `orchestrator` (planning phase) |
| `layer1-research` | Absorbed as phase | `orchestrator` pre-build context step |
| `schema-debugger` | Absorbed as function | `layer4-testing` post-reindex gate |
| `changelog-writer` | Merged | `documentation-agent` |
| `technical-writer` | Merged | `documentation-agent` |
| `cab` | Converted to mode | HITL escalation pathway in PLAYBOOK.md §2.3 |
| `parallel-dispatcher` | Converted to capability | `orchestrator` internal scheduling |

### 1.4 Agent Deprecation & Sunset Process

Agents that are no longer needed must be formally decommissioned. The following process is mandatory:

**Deprecation Triggers (any one is sufficient):**
- Agent has not appeared in any `taskId` reference in the audit log AND all owned subsystems have had zero `filesMutated` activity — both conditions must be true. An idle agent that owns an active subsystem is waiting, not dead.
- Agent's owned subsystems have all been transferred to other agents.
- A mandatory cleanup cycle (PROTOCOL §3.7) identifies the agent as unused.
- The agent fleet ceiling (8) is reached and a new agent registration is needed.

**Deprecation Procedure:**

| Step | Action | Owner |
|---|---|---|
| 1 | `internal-auditor` flags the agent and logs `DEPRECATION_CANDIDATE` | `internal-auditor` |
| 2 | 14-day review window. Any Tier-2+ operator may file an objection with written justification | Any stakeholder |
| 3 | If no objection: `orchestrator` transfers subsystem ownerships, removes entry, logs `AGENT_DECOMMISSIONED` | `orchestrator` |
| 4 | If objection: HITL. Tier-3 operator decides within 7 days. Logged as `DEPRECATION_OVERRIDDEN` or `DEPRECATION_CONFIRMED` | Tier-3 operator |
| 5 | IAC and WIKI references patched via a `LOW` criticality playbook | `layer3-development` |

> **Reactivation:** A decommissioned agent may be re-registered but must go through the full new-agent registration process. Its previous entry is not restored.

---

## 2. TERM GLOSSARY

| Term | Definition |
|------|------------|
| **MVAT** | Minimum Viable Agent Team. The irreducible three-agent triad (Orchestrator → Builder → Validator) required to execute any task cycle. No task may begin without a complete, named MVAT. |
| **approvedFileSet** | The explicit, locked list of file paths that a Builder agent is permitted to mutate in a given execution cycle. Any mutation outside this set is a hard validation failure. Defined by the Orchestrator at plan time. |
| **filesMutated** | The array of file paths actually modified by the Builder, included in the `BuilderToValidatorPayload`. Used by the Validator for scope verification and by the WIKI re-indexing loop for AST analysis. |
| **Execution Lock** | A system-wide mutex held by `sdlc-orchestrator` during an active execution cycle. No other cycle may begin until the lock is released. The lock is only freed after the WIKI sync loop completes successfully. |
| **System Drift Exception** | An error state raised by `internal-auditor` when the physical repository state diverges from the WIKI index due to a manual commit that bypassed agent indexing. Triggers a full WIKI re-baseline. |
| **HITL** | Human-In-The-Loop. Redefined: HITL is now an **async notification mechanism**, not a blocking gate. When the system quarantines an item or defers a decision, it logs a structured entry that surfaces in the End-of-Session Report. The human sees it after the session ends and acts on it then. HITL no longer pauses or stops any execution cycle. |
| **IAC** | Inter-Agent Contract. A machine-readable JSON payload that defines the data exchanged between two agents. All IACs are versioned with `schemaVersion`. See PROTOCOL.md §4. |
| **Playbook** | A declarative execution contract that overrides standard autonomous planning. Used for cross-repository changes, schema migrations, and critical-path revisions. Defined in PLAYBOOK.md. |
| **Post-Condition** | A `validationExpression` (shell-executable, must return exit code `0`) that a Playbook step must satisfy before it is marked complete. Steps are never marked complete on heuristic judgment alone. |
| **Synchronization Drift** | See *System Drift Exception*. |
| **Zero-Planning Mandate** | The constraint applied to the Orchestrator when a PLAYBOOK is active. The Orchestrator may not modify step sequence, add files to scope, or generate speculative code. It acts as a mechanical dispatcher only. |
| **Two-Strike Rule** | The anti-abstraction duplication policy in PROTOCOL.md §3.1. First duplication of a pattern is permitted; second duplication of the same pattern requires a refactor proposal. Three or more call sites mandate abstraction. |
| **schemaVersion** | A required semver string field present in all IAC payloads, the `UserSessionContext`, and Playbook contracts. Agents must validate this field on receipt; a mismatch triggers HITL escalation rather than silent coercion. |
| **Dead Code** | Any function, class, variable, or import that is unreachable during normal execution. Treated as a security risk in this system — dead code is an attack surface for injection and confused-deputy vulnerabilities. Detected by `vulture --min-confidence=80`. Any dead code in an auth, crypto, or IAC path triggers immediate HITL escalation. |
| **Error Payload** | The mandatory structured JSON object that every caught exception must produce. Contains `errorCode`, `errorMessage`, `sourceAgent`, `taskId`, `timestamp`, and `recoverable`. Free-form string logging is not a valid substitute. See PROTOCOL.md §3.3. |
| **Coverage Gate** | The minimum test coverage thresholds that a diff must satisfy before a `BuilderToValidatorPayload` can pass: ≥ 85% line coverage and ≥ 75% branch coverage, measured over `filesMutated` only. Global project coverage does not satisfy the gate. |
| **Bare Exception** | An `except:` or `except Exception:` block with no typed exception class, no structured error payload, and no re-raise. Permanently forbidden. Detected by `bandit -l` at severity MEDIUM or above; triggers an immediate diff rejection. |
| **Speculative Architecture** | Any code construct with no current call sites or verified consumers. Includes: abstraction layers, plugin systems, generic base classes with fewer than 3 subclasses, event buses with no subscribers, feature flags for unapproved features, and schema fields not read by any active code path. Fully defined in PROTOCOL.md §2.1. Forbidden in all execution cycles. |
| **Cumulative Scope Ledger** | The cross-cycle accumulator maintained in WIKI.md §7 that tracks total files created, files mutated, packages added, subsystems registered, and agents deployed over the full lifetime of a project. The primary instrument for detecting scope explosion. Updated after every passing cycle. |
| **Scope Freeze** | A system-wide halt on new feature development, triggered automatically when any threshold in WIKI.md §6 is crossed. During a freeze, no new files may be created, no new packages added, and no new subsystems or agents registered. Lifted only by a Tier-3 operator with a written `SCOPE_FREEZE_LIFTED` audit entry. |
| **Cleanup Cycle** | A mandatory PROTOCOL cycle restricted exclusively to removal and decomposition operations. Triggered by thresholds in PROTOCOL.md §3.7. No new features, packages, or abstractions may be introduced. Unblocks new feature work once all cleanup post-conditions pass. |
| **Dormant Subsystem** | A subsystem registered in WIKI.md §2.2 that has not appeared in any `filesMutated` array for 60 or more days. Flagged automatically by `internal-auditor`. Must be reactivated with justification or decommissioned within 14 days. |
| **Supervised Mode** | Removed. There is only one operating mode: the system works autonomously from brief to report. The distinction between "supervised" and "autonomous" no longer exists — all sessions are autonomous. |
| **Autonomous Session Mode** | The only operating mode. User gives a brief with or without a duration. The Orchestrator starts immediately with no confirmation token. Everything resolves autonomously, via quarantine, or via deferral. The human reviews the End-of-Session Report. Governed by CANVAS.md §8.7 and PROTOCOL.md §6. |
| **Session Contract** | Removed. There is no session contract to present or approve. The brief IS the contract. The canvas log is the transparency record. |
| **Conservative Mode** | A sub-state activated when scope review thresholds are crossed. No new subsystems, packages, or agents are added, but all existing work continues. Not a freeze — a narrowing. Automatically deactivated when thresholds resolve. Defined in WIKI.md §6. |
| **End-of-Session Report** | The mandatory report generated when a session ends (duration elapsed or user sends `SESSION_STOP`). The human's primary and only accountability window during an autonomous session. Contains: elapsed duration, canvases logged, cycles completed, files mutated, packages added, quarantined items (most important), deferred items, Conservative Mode history, cumulative ledger totals, and next recommended focus. |
| **Deferred Defect** | A quality violation the system attempted and failed to fix within the retry limit. Quarantined or logged, then surfaced in the End-of-Session Report for human resolution. Never blocks the session. |
| **Quarantine** | The primary resolution mechanism for unfixable or security-sensitive situations. The affected file or component is isolated from deployment and further mutation. All other work continues normally. Quarantined items are flagged with `QUARANTINE_*` event types and appear prominently in the End-of-Session Report. Quarantine is not a pause — it is a surgical skip. |
| **MTProto** | The Telegram Mobile Protocol — the native encryption protocol used by all Telegram clients. In this system, MTProto is used to authenticate a real developer user session (via `TG_SESSION_STRING`) for headless E2E bot testing. Distinct from the Bot API: MTProto can read inline keyboards and interact with them as a human user would; the Bot API cannot. |
| **Telethon** | A Python MTProto client library used in `telegram_e2e_test.py` to simulate a real user interacting with the staging bot. The canonical choice for Telegram E2E testing in this system. Pyrogram is the permitted alternative. |
| **Pyrogram** | A Python MTProto client library. The permitted alternative to Telethon for `telegram_e2e_test.py`. Functionally equivalent for E2E testing purposes. |
| **TG_SESSION_STRING** | A serialised Telethon or Pyrogram session token that authenticates a real user MTProto session without requiring phone number re-entry. Stored exclusively as a GitHub Actions encrypted secret. Must never appear in source code, logs, diffs, or environment variable printouts. |
| **Staging Bot** | A separate Telegram bot instance used exclusively for automated E2E testing. Must have a different username and token than the production bot. All MTProto E2E tests must target the staging bot. Running automated tests against the production bot is forbidden. |
| **ui_config.py** | The Single Source of Truth file for all Telegram bot UI definitions — bot menus, inline keyboard schemas, button labels, callback data values, and expected response text. Handler code must import from this file; it must never define keyboard structures inline. Validated by `test_ui_structures.py` at Gate 1 and by AST scan at every Validator cycle. Schema defined in WIKI.md §3.4. |
| **UI Structure Lint** | Gate 1 of the CI/CD pipeline. A pytest-based validation of `ui_config.py` against Telegram API structural constraints: `callback_data` ≤ 64 bytes, ≤ 8 keyboard rows, message text ≤ 4096 characters, button text ≤ 40 characters. Runs before any browser or bot tests. `validationType: UI_STRUCTURE_LINT`. |
| **Visual Regression** | A test technique that captures pixel-level screenshots of web UI states and compares them against an approved baseline. Any unreviewed diff fails the gate. Implemented via Percy (`PERCY_TOKEN`) or Applitools (`APPLITOOLS_API_KEY`). `validationType: VISUAL_REGRESSION`. |
| **Percy** | A visual regression testing SaaS platform. Integrated via the Percy CLI (`npx percy exec`). Requires `PERCY_TOKEN` from GitHub Actions secrets. The canonical visual regression tool in this system. |
| **Applitools** | A visual regression testing SaaS platform. The permitted alternative to Percy. Requires `APPLITOOLS_API_KEY` from GitHub Actions secrets. |
| **Playwright** | A headless browser automation framework used for Web E2E testing. Configured via `playwright.config.ts`, with test journeys in `web_journey.spec.ts`. `validationType: E2E_WEB`. The canonical Web E2E tool in this system. |
| **Headless E2E** | An end-to-end test that runs without a visible UI — either a headless browser (Playwright) or a headless Telegram client (Telethon/Pyrogram). Both produce the same quality guarantees as manual testing without requiring human interaction. |
| **RUM** | Real User Monitoring. Production telemetry that tracks runtime errors, performance metrics, and user interactions in the live environment. Implemented via Sentry (`SENTRY_DSN`) or Datadog (`DATADOG_API_KEY`). A release event is posted to the RUM provider at Gate 4 after successful deployment. |
| **Sentry** | An error tracking and RUM platform. The canonical production telemetry tool in this system. Configured via `SENTRY_DSN` GitHub Actions secret. A release event is posted after every successful deployment. |
| **Datadog** | An observability and RUM platform. The permitted alternative to Sentry. Configured via `DATADOG_API_KEY` GitHub Actions secret. |
| **Four-Gate Pipeline** | The mandatory CI/CD sequence for dual-platform projects: Gate 1 (UI Structure Lint) → Gate 2 (Web E2E + Visual Regression) → Gate 3 (Telegram MTProto E2E) → Gate 4 (Conditional Deploy + Telemetry). Gates are strictly sequential. Failure at any gate aborts all subsequent gates. Defined in PROTOCOL.md §3.8 and implemented in `.github/workflows/autonomous_gate.yml`. |
| **Autonomous Session** | A pre-authorized work period during which the Orchestrator fills and self-approves canvases without interrupting the user. Activated by a single `SESSION_APPROVED` from the user. Governed by a declared duration, scope boundary, and criticality ceiling. All HITL triggers remain active. Ends with a mandatory End-of-Session Report. Defined in CANVAS.md §8.7. |
| **SESSION_APPROVED** | The literal string the user sends to start an Autonomous Session after reviewing the Orchestrator-generated Session Contract. Analogous to `CANVAS_APPROVED` but session-scoped. "ok" or "go ahead" are not valid substitutes. |
| **SESSION_STOP** | The literal string the user sends to cleanly end an Autonomous Session after the current cycle completes. Triggers the End-of-Session Report. |
| **SESSION_RESUME** | The literal string the user sends to resume a paused Autonomous Session after resolving a HITL trigger or scope boundary question. |
| **CANVAS_AUTO_APPROVED** | An audit log event type recording that the Orchestrator self-approved a canvas during an active Autonomous Session. Every auto-approval is logged — nothing is hidden from the audit trail. |
| **Secrets Scanning** | The mandatory pre-submission scan run by `layer3-development` using `detect-secrets scan` on all files in `filesMutated`. Detects high-entropy strings, API key patterns, and credential-shaped values. A secrets finding is a hard stop — the diff must not be submitted. The Validator also runs `detect-secrets` as a secondary gate. Any finding at any confidence level is a CRITICAL rejection, with immediate HITL if the finding is in an auth or IAC path. |
| **Dependency Pinning** | The requirement that all third-party packages be declared with exact version strings and SHA-256 hashes. Range specifiers (`>=`, `~=`, `^`) are forbidden. Enforced by `pip-audit` during Validator review whenever `dependenciesAdded: true` in the outbound IAC. Every new dependency addition must produce a `DEPENDENCY_ADDED` audit log entry. |

---

## 3. NAMING CONVENTIONS & DISAMBIGUATION

The following identifiers are **aliases for active agents**, not distinct agents. Using them as if they were separate entities is a fleet proliferation error:

| Alias | Resolves To | Common Mistake to Avoid |
|---|---|---|
| `sdlc-orchestrator` | `orchestrator` | Treating lifecycle control as a separate agent from planning |
| `ai-orchestrator` | `orchestrator` | Same |
| `project-manager` | `orchestrator` | Same |
| `sdlc-manager` | `layer4-testing` | Treating the Validator as a separate quality manager role |
| `changelog-writer` | `documentation-agent` | Invoking documentation as two parallel agents |
| `technical-writer` | `documentation-agent` | Same |
| `layer1-research` | `orchestrator` pre-build phase | Treating context gathering as a delegated agent invocation |
| `parallel-dispatcher` | `orchestrator` concurrency capability | Treating internal scheduling as a named third-party agent |

---

## 4. DOCUMENT VERSION COMPATIBILITY MATRIX

All five governance documents must be deployed as a compatible set.

| WIKI | PROTOCOL | PLAYBOOK | GLOSSARY | CANVAS | Status |
|---|---|---|---|---|---|
| `1.2.0` | `1.2.0` | `1.2.0` | `1.1.0` | `1.3.0` | ✅ **Current compatible baseline** |
| `1.2.0` | `1.2.0` | `1.2.0` | `1.1.0` | `1.2.0` | ❌ CANVAS still has CANVAS_APPROVED / SESSION_APPROVED and session pause mechanics |
| `1.2.0` | `1.2.0` | `1.1.0` | `1.1.0` | `1.3.0` | ❌ PLAYBOOK still has HITL_REQUIRED and four-tier governance table |
| `1.2.0` | `1.1.0` | `1.2.0` | `1.1.0` | `1.3.0` | ❌ PROTOCOL still has HITL escalation column and Session Stop triggers |

**Compatibility Rules:**
- All five documents must be at the versions in the current baseline before any session begins.
- `internal-auditor` validates document versions at startup and after any update.
- A version mismatch surfaces as `SYSTEM_DRIFT_DETECTED` in the next End-of-Session Report.
- New document versions must update this matrix before being merged.
