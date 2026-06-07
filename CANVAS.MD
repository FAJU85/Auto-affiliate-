# MISSION CRITICAL PROTOCOL: PROJECT INITIALIZATION CANVAS
> **Document Version:** 1.3.0 | **Governance Baseline:** WIKI 1.2.0 / PROTOCOL 1.2.0 / PLAYBOOK 1.2.0 / GLOSSARY 1.1.0
> **Canvas Schema Version:** `1.0.0`

## How This Canvas Works

**The Orchestrator reads the brief and starts work immediately. No confirmation token is required.**

The user provides a natural language brief — with or without a declared duration. The Orchestrator fills every canvas field from it, logs the canvas as `CANVAS_LOGGED`, and begins the first execution cycle. The canvas is a transparency record and a scope contract. It is not a gate.

The only pre-work pause is when the brief cannot fill a critical scope field (PROTOCOL.md §6.4 Minimum Viable Brief). The Orchestrator asks one targeted question, waits for the answer, then begins immediately. This is disambiguation, not governance.

**There is no `CANVAS_APPROVED` token. There is no `SESSION_APPROVED` token. Work begins when the brief is given.**

> **Scope Boundary:** The brief defines the scope. Everything within it runs autonomously for the declared duration or until complete. Everything outside it is quarantined and surfaced in the End-of-Session Report. The human's accountability window is the report — not real-time interruptions. Once work begins, all execution is governed by **PROTOCOL.md**.

---

## 1. REALITY BOUNDARY

* **One-Sentence Problem/Pain:**
  `[Fill in: What is the specific human pain point? Describe the concrete problem — not the technology, not the multi-agent architecture. One sentence maximum.]`

* **Primary Workflow (Success Path):**
  `[Fill in: Map exactly one happy-path: Input → Process → Output. This is the success path only. Failure paths, error states, and recovery routes are NOT defined here — they are governed by PROTOCOL.md §3.3 and §5. Do not conflate the primary workflow with total system behavior.]`

  > **Clarification:** "Single workflow" means one primary user journey, not one total code path. Every workflow has a success branch and failure branches. The failure branches are non-negotiable and are defined by PROTOCOL.md §3.3 — they do not appear in this canvas.

* **Strict Exclusions (WILL NOT DO):**
  `[Fill in: List exactly 3–5 features strictly banned from this initial build. Be specific enough that an agent cannot reintroduce them under a different name.]`

  1. `[Exclusion 1]`
  2. `[Exclusion 2]`
  3. `[Exclusion 3]`
  4. `[Exclusion 4 — optional]`
  5. `[Exclusion 5 — optional]`

---

## 2. THE ABSOLUTE MINIMUM ENGINE

* **Single Stack Components:**
  * Database: `[Fill in: Exactly 1 database type]`
  * Backend Language/Framework: `[Fill in: Exactly 1 language/framework]`
  * Frontend Framework: `[Fill in: Exactly 1 UI framework, or "None — API only"]`

* **Boring Technologies Used:**
  `[Fill in: List the most mature, unglamorous libraries that minimize unknown technical variables. Justify any library that is less than 2 years old or has fewer than 1,000 GitHub stars — it must pass the §5 experiment time-box before inclusion.]`

* **Static/Hardcoded Elements:**
  `[Fill in: Specify which subsystems will remain hardcoded as raw arrays or static assets to bypass early dynamic state tracking. These must be explicitly converted to dynamic implementations via a PLAYBOOK migration — they cannot be silently upgraded mid-cycle.]`

* **Dependency Compliance:**
  All packages listed above are subject to PROTOCOL.md §3.5. Before any package is added to the build:
  - Exact version string must be declared (e.g., `requests==2.31.0`). Range specifiers are forbidden.
  - SHA-256 hash must accompany the version pin.
  - `pip-audit` must return zero findings at any severity.
  - A `DEPENDENCY_ADDED` audit log entry (WIKI.md §3.3 schema) must be produced.

---

## 3. VALUE MATRIX

* **Core User Outcome:**
  `[Fill in: The absolute bare-minimum functional success criterion for a single end-to-end execution. This is the acceptance criterion for the first deployable increment.]`

* **Time-to-Value Bottleneck:**
  `[Fill in: The specific technical barrier that slows the user from landing to achieving the Core User Outcome. All initial code focus must be here — not on ancillary features.]`

* **Manual Testing Protocol:**
  `[Fill in: A numbered step-by-step checklist the agent or developer must execute manually to verify the primary workflow before automated testing begins. Each step must be a binary pass/fail check — not a subjective observation.]`

  1. `[Step 1: specific action → expected observable result]`
  2. `[Step 2: specific action → expected observable result]`
  3. `[Step N: ...]`

  > **Automated Testing Gate:** Once the manual checklist passes, the automated coverage gates defined in PROTOCOL.md §3.4 apply unconditionally. The manual checklist does not substitute for automated coverage — it precedes it.

---

## 4. AI CO-PILOT GUARDRAILS

* **Prompt Constraints & Max Output:**
  - Maximum **50 logical lines of code per file change** (comments and blank lines excluded). This is the hard ceiling defined in PROTOCOL.md §3.2 — it is not configurable per-project.
  - Multi-file scaffolding injections are absolutely forbidden. One file mutation per prompt response.
  - Agents may not generate placeholder comments, `// TODO` markers, or partial code blocks. See PROTOCOL.md §2.2 Forbidden Actions.

* **Verification & Testing Loop:**
  Before any change is committed, the following must return exit code 0:
  ```
  1. flake8 <mutated_file> --max-function-length=50 --max-complexity=5
  2. bandit -r <mutated_file> -l --severity-level medium
  3. vulture <mutated_file> --min-confidence=80
  4. detect-secrets scan <mutated_file>
  5. pytest tests/ -v --tb=short --cov=<mutated_file> --cov-fail-under=85 --cov-branch
  ```
  These are the same gates defined in PROTOCOL.md §3.2, §3.3, §3.4, and GLOSSARY.md (Secrets Scanning). They are listed here for agent visibility during the build phase — they are not a separate, lighter standard.

* **Explicit vs. Magical Verification:**
  Generated code is accepted only if ALL of the following are true:
  - Every variable has an explicit type annotation.
  - Every function has a docstring with `Args:` and `Returns:` blocks.
  - No runtime-injected abstractions (dynamic `getattr`, `__getattr__`, metaclasses, monkey-patching).
  - No string-based dispatch (e.g., `getattr(obj, action_name)()`).
  - No implicit framework magic (e.g., auto-registered routes, auto-discovered plugins) unless the framework's behavior is explicitly documented inline.

---

## 5. ANTI-COMPLEXITY WATCHLIST

* **Abstraction Drift Indicators:**
  The following code patterns trigger a forced rejection if introduced. The agent must not rationalize them as "future-proofing":

  | Forbidden Pattern | Reason |
  |---|---|
  | Generic factory functions (`create_handler(type)`) | Premature abstraction — no verified call sites yet |
  | Dynamic routing via string dispatch | Magical, untraceable execution path |
  | Base classes with more than 2 concrete subclasses pending | Inheritance before repetition is confirmed |
  | Generic wrapper modules that re-export other modules | Indirection with no current benefit |
  | `**kwargs` in public-facing functions | Hides the actual contract; breaks static analysis |
  | Any class named `Manager`, `Handler`, `Factory`, `Base`, or `Mixin` at this build stage | Signals abstraction before need |

* **Rule of Three Counter:**
  Zero code optimization, interfaces, or inheritance wrappers are permitted unless the pattern has been confirmed to repeat in **3 or more verified call sites** in the active codebase. This is the Two-Strike Rule defined in PROTOCOL.md §3.1. First duplication is logged; second duplication requires a refactor proposal to the Orchestrator; third triggers mandatory consolidation. The canvas does not relax this rule.

* **Experimentation Time-Boxes:**
  Maximum **2 hours** for testing any alternative library or architectural spike before falling back to the boring technology declared in §2. If the 2-hour window expires without a working proof of concept, the spike is moved to the Tooling Parking Lot below and the original boring choice is restored.

* **Tooling Parking Lot:**
  Any speculative or downstream idea that surfaces during the build must be written here immediately and removed from active memory. This list is read-only during the current build cycle — nothing here may be implemented until a new canvas is initialized.

  ```
  PARKING LOT:
  - [Item 1: idea description — date added]
  - [Item 2: idea description — date added]
  ```

---

## 6. ENGINEERING HYGIENE

* **Rollback & Backup Mechanics:**
  - Git commit checkpoint after every completed, passing file mutation (not after every attempt).
  - Branch naming convention: `build/<canvas-id>/<stepId>` (e.g., `build/PB-2024-001/01-migrate-session-schema`).
  - If a change fails the §4 verification loop, do NOT commit. Revert locally and resubmit.
  - For cross-repository or schema-migration changes, a PLAYBOOK must be initialized (PLAYBOOK.md §1). The canvas does not substitute for a PLAYBOOK in those scenarios.
  - Rollback procedure for failed commits follows PLAYBOOK.md §4.2.

* **Logging & Visibility Anchors:**
  Standard output logs must capture state at the following choke points. These are not optional:

  | Choke Point | Required Log Data | Audit Event Type |
  |---|---|---|
  | Any I/O operation entry/exit | Operation type, target, success/failure, duration | `INFO` or `ERROR` |
  | IAC payload receipt | `schemaVersion`, `taskId`, `sourceAgent` | `INFO` |
  | IAC schema version mismatch | Received version vs expected version | `SCHEMA_VERSION_MISMATCH` |
  | Any exception caught | Full structured error payload (PROTOCOL.md §3.3 schema) | `ERROR` or `CRITICAL` |
  | Execution lock acquired/released | `taskId`, `timestamp`, agent identifier | `LOCK_ACQUIRED` / `LOCK_RELEASED` |
  | Dependency added | Package name, version, hash, `taskId` | `DEPENDENCY_ADDED` |

  All audit event types reference the `AuditLogEntry` schema in WIKI.md §3.3.

* **Dependency Budget Limit:**
  Maximum external packages for this project scope must be declared here with a written justification for the chosen ceiling. The number is not fixed at 15 for all projects — it must be appropriate for the stack declared in §2 and must be defended.

  ```
  # Dependency Budget: 0 / [FILL IN CEILING]
  # Justification: [FILL IN — state why this ceiling is appropriate for this project type]
  ```

  The budget ceiling declared here is binding. It is enforced by PROTOCOL.md §3.6 and the Cumulative Scope Ledger. It cannot be silently increased mid-project — an amendment (§8.6) is required.

---

## 7. PSYCHOLOGICAL ANCHORS

* **Code Deletion Threshold:**
  At least **30% of speculative or layout code** is expected to be deleted during the first refactoring pass. This is not aspirational — it is a quality signal. If less than 30% is deleted, the build likely contains scope creep or untrimmed scaffolding that was not caught by the §5 watchlist.

  **Deletion Trigger Condition:** Deletion occurs when the manual testing protocol in §3 passes end-to-end for the first time. At that moment, a mandatory deletion review is initiated before any new feature is started. An agent may not proceed to the next feature without completing the deletion review.

* **Focus Window Boundary:**
  `[Fill in: One sentence describing the single task currently occupying active memory. This must be updated every time the focus shifts. An agent that cannot state the current Focus Window in one sentence has lost focus and must stop and re-read this canvas.]`

* **Architectural Regret Disclosures:**
  `[Fill in: List the technical debts and ugly shortcuts intentionally tolerated right now to expedite shipping. Each entry must include:]`

  | Shortcut Description | Why Tolerated | Repayment Trigger | Assigned To |
  |---|---|---|---|
  | `[e.g., hardcoded config values]` | `[e.g., dynamic config adds 2 days scope]` | `[e.g., when second environment is needed]` | `[agent or human]` |

  > **Repayment Policy:** Technical debt without a Repayment Trigger is not tolerated debt — it is abandoned debt. Every entry in this table must have a concrete, observable trigger condition. When the trigger fires, a new canvas or PLAYBOOK must be initialized to address it. It does not self-resolve.

---

## 8. GOVERNANCE INTEGRATION LAYER

This section defines how the canvas connects to the four governance documents. It is non-negotiable and cannot be modified per-project.

### 8.1 How Work Begins

The Orchestrator reads the brief, fills every canvas field, logs `CANVAS_LOGGED`, and begins the first cycle immediately. There is no confirmation token. There is no Scope Summary to approve. There is no waiting.

The canvas log is written to the audit trail so the human can see what scope was understood at session start. This is transparency, not a gate.

**If the brief is sufficient** (PROTOCOL.md §6.4): work begins with no interaction.

**If one critical field is genuinely ambiguous**: the Orchestrator surfaces one targeted question. After the answer, work begins immediately. The Orchestrator does not present the filled canvas for review or ask follow-up questions.

**What replaces the approval gate:** The End-of-Session Report. Every canvas that was auto-filled, every autonomous scope decision, every quarantined item — all surfaced at the end for the human to review. The human governs outcomes, not inputs.

### 8.2 Governance Document Hierarchy

Once work begins, the following hierarchy governs execution for the full session:

```
CANVAS.md  (scope record — locked once work begins)
    │
    ▼
PROTOCOL.md  (governs all execution cycles)
    │
    ├──► WIKI.md  (SSOT for architecture, schemas, agent registry)
    │
    ├──► PLAYBOOK.md  (governs cross-repo, schema-migration changes)
    │
    └──► GLOSSARY.md  (canonical agent and term definitions)
```

The canvas is locked once work begins. Mid-session scope changes are logged as `DEFERRED_AMENDMENT` and presented in the End-of-Session Report. They are not applied mid-session.

### 8.3 Build Phase Transition Checklist

Before the first code file is created, the Orchestrator confirms all of the following autonomously. No human sign-off required.

- [ ] Canvas fields filled from brief and logged as `CANVAS_LOGGED`.
- [ ] WIKI.md Service Mapping Ledger (§2.2) consulted — all affected subsystems identified.
- [ ] `approvedFileSet` defined by `orchestrator` and locked.
- [ ] MVAT Triad assigned: Orchestrator, Builder, Validator all named (GLOSSARY.md §1).
- [ ] Execution Lock acquired by `orchestrator` with heartbeat initialized.
- [ ] Document version compatibility confirmed against GLOSSARY.md §4 compatibility matrix.
- [ ] If any step in §2 Static/Hardcoded Elements touches a schema defined in WIKI.md §3: a PLAYBOOK migration route is declared and queued before the first cycle.
- [ ] Exclusion scan patterns generated from §1 Strict Exclusions and registered in `forbiddenActions` of every `iac_inbound.json` for this project. Exclusions that cannot be expressed as a detectable pattern are logged as `DEFERRED_EXCLUSION_REVIEW` in the report.
- [ ] Cumulative Scope Ledger entry initialized in WIKI.md §7 for this canvas ID with `totalCyclesCompleted: 0` and `scopeFreeze: false`.
- [ ] **If the project has a Telegram bot or web frontend:** §8.8 Dual-Platform requirements satisfied before the first cycle.

### 8.4 Canvas-to-IAC Mapping

When the `orchestrator` converts this canvas into an execution graph, the following canvas fields map directly to IAC contract fields:

| Canvas Field | IAC Field | Contract |
|---|---|---|
| §1 Strict Exclusions | `forbiddenActions` array | `iac_inbound.json` (PROTOCOL.md §4.1) |
| §2 Stack + Hardcoded Elements | `mutationDirectives[].targetFile` | `iac_inbound.json` |
| §2 Static/Hardcoded Elements → future dynamic | `executionDirectives` in PLAYBOOK step | `playbook_schema.json` (PLAYBOOK.md §3) |
| §6 Dependency Budget | `dependencyOverride` + `pip-audit` gate | `iac_inbound.json` + PROTOCOL.md §3.5 |
| §7 Architectural Regret Disclosures | `forbiddenActions` (future cycle) | Next canvas or PLAYBOOK |

### 8.5 When a PLAYBOOK Is Required Instead of a Canvas

This canvas is for **greenfield initialization and single-repository standard builds only**. A PLAYBOOK must be initialized instead of (or in addition to) this canvas when any of the following are true:

- The build touches more than one repository.
- The build modifies a schema defined in WIKI.md §3 (requires `SCHEMA_VERIFY` post-condition).
- The build's `criticality` would be rated `HIGH` or `CRITICAL` in the Playbook schema.
- Any Static/Hardcoded Element in §2 is being converted to a dynamic implementation.
- The build introduces a new agent that must be registered in GLOSSARY.md.

---

### 8.6 Canvas Amendment Protocol

A signed canvas is read-only. Scope changes cannot be made by editing a signed canvas. However, "initialize a new canvas" without continuity creates a loophole — exclusions from the old canvas can be silently dropped. The following protocol closes that gap:

**When a legitimate scope change is needed:**

| Step | Action | Requirement |
|---|---|---|
| 1 | Author a **Canvas Amendment Request** — a written document naming: (a) the specific field being changed, (b) the old value, (c) the new value, (d) why the change is necessary | Tier-2+ operator |
| 2 | Submit the Amendment Request for review. Criticality matches impact: adding a §1 exclusion is `LOW`; removing a §1 exclusion is `HIGH` requiring HITL | `orchestrator` |
| 3 | If approved: create a new canvas version (e.g., `v1.1`) that carries forward ALL existing §1 Strict Exclusions unchanged, plus the approved amendment. The old canvas version is archived, not deleted. | `orchestrator` |
| 4 | The new canvas version must re-trigger the §8.3 Build Phase Transition Checklist, including regenerating exclusion scan patterns | `orchestrator` |
| 5 | Log a `CANVAS_AMENDED` audit entry naming the old version, new version, what changed, and who approved it | `internal-auditor` |

**What is never permitted:**
- Removing a §1 Strict Exclusion without a `HIGH` criticality HITL review and Tier-3 co-sign
- Increasing the dependency budget ceiling without a new `pip-audit` baseline
- Changing the stack declared in §2 after the first cycle has completed — a new canvas must be initialized from scratch with a scope review
- Amending a canvas during an active Autonomous Session — amendments are queued and presented in the End-of-Session Report
- Amending a canvas that is currently under a Scope Freeze (WIKI.md §6) — amendments are blocked until the freeze is lifted

---

### 8.7 Session Mode

When the user declares a duration — "work for 3 hours", "build this over the next 3 days", "keep working until it's done" — the Orchestrator initializes a session, logs `SESSION_STARTED`, and begins immediately. There is no Session Contract to review. There is no `SESSION_APPROVED` token. Work starts.

**The session runs until:**
- The declared duration elapses, or
- The user sends `SESSION_STOP`

Nothing else ends or pauses the session. The Orchestrator handles every situation it encounters — autonomously, via quarantine, or via deferral — without interrupting the human.

#### What Happens During the Session

| Situation | What the Orchestrator Does |
|---|---|
| Canvas needed for a new task | Auto-fill from context, log `CANVAS_LOGGED`, begin immediately |
| Quality violation (coverage, complexity, dead code) | Attempt autonomous fix. If unfixable after retries: quarantine the affected file, log `DEFERRED_DEFECT`, continue with next task |
| Security finding in non-critical code | Attempt autonomous fix. If unfixable: quarantine the file, mark `QUARANTINE_SECURITY`, continue |
| Security finding that would affect a live deployment | Skip the deployment for that component only. Quarantine the file, mark `QUARANTINE_NO_DEPLOY`. Continue all other deployments |
| Scope review threshold crossed | Activate Conservative Mode (no new subsystems/packages/agents). Continue all existing work |
| Scope boundary breach attempt | Quarantine the out-of-scope request, log `DEFERRED_SCOPE_REQUEST`, continue |
| HIGH or CRITICAL playbook within declared scope | Auto-approve and execute. Scope boundary is the authority |
| Compilation error | `layer6-self-healing` attempts fix up to 3 times. If still failing: skip the cycle, log `DEFERRED_DEFECT`, continue |
| Lock TTL breach | `internal-auditor` autonomous recovery. Continue |
| Schema version mismatch | Skip the affected cycle, log `SCHEMA_MISMATCH_DEFERRED`, continue |
| Canvas amendment requested mid-session | Log `DEFERRED_AMENDMENT`, continue |
| Anything not in the scope boundary | Quarantine, log, continue — never ask |

#### End-of-Session Report (mandatory)

```
SESSION REPORT

Duration:            [Actual elapsed time]
Canvases Logged:     [Count and IDs — auto-filled during session]
Cycles Completed:    [Count with pass/fail breakdown]
Files Mutated:       [Total unique files touched]
Packages Added:      [Count and names, if any]
Quarantined Items:   [Files or deployments quarantined — requires human review]
Deferred Work:       [Out-of-scope requests and amendments logged]
Conservative Mode:   [Active or not — reason if active]
Cumulative Ledger:   [Updated totals from WIKI.md §7]
Next Recommended:    [Orchestrator's proposed next focus window]
```

The Quarantined Items section is the most important part of the report. These are the items the Orchestrator could not resolve autonomously and isolated rather than blocking on. The human reviews and acts on them after the session ends — not during it.

---

### 8.8 Dual-Platform Project Requirements (Web Frontend + Telegram Bot)

When a project includes a Web Frontend, a Telegram Bot, or both, the following additional requirements apply from canvas initialization. They are not optional and are not deferred to later cycles.

**Mandatory §2 Stack Additions:**

The following must be explicitly declared in the canvas §2 Stack alongside the standard backend/database/frontend:

| Component | Canonical Tool | Alternative | Purpose |
|---|---|---|---|
| UI Layout SSOT | `ui_config.py` (Python dict/JSON) | — | Single source of truth for all keyboard schemas and text |
| Telegram E2E | Telethon | Pyrogram | MTProto headless bot testing |
| Web E2E | Playwright | — | Headless browser user journey testing |
| Visual Regression | Percy | Applitools | Pixel-level snapshot comparison |
| CI/CD Pipeline | GitHub Actions | — | Four-gate autonomous quality gate |
| Error Tracking | Sentry | Datadog | Production RUM telemetry |

**Mandatory §1 Strict Exclusions for dual-platform projects (always include these):**

1. Inline keyboard definitions outside `ui_config.py` — all keyboard schemas must import from the SSOT
2. Hardcoded secret values (`TG_SESSION_STRING`, `PERCY_TOKEN`, API keys) anywhere in source
3. Running MTProto E2E tests against the production bot — staging only
4. Deploying from any branch other than `main` or the declared production branch
5. Skipping Gate 1 (UI structure lint) on the grounds that `ui_config.py` was not modified

**Mandatory §6 Secrets Declaration:**

The dependency budget comment header must list all CI/CD secrets as non-package line items so they are visible at a glance:

```
# Dependency Budget: X / [CEILING]
# CI/CD Secrets required (not packages — governance visibility):
#   TG_SESSION_STRING  — GitHub Actions secret
#   TG_API_ID          — GitHub Actions secret
#   TG_API_HASH        — GitHub Actions secret
#   PERCY_TOKEN or APPLITOOLS_API_KEY — GitHub Actions secret
#   SENTRY_DSN or DATADOG_API_KEY    — GitHub Actions secret
```

**Mandatory §7 Architectural Regret Disclosures for first deployment:**

| Shortcut | Why Tolerated | Repayment Trigger |
|---|---|---|
| `ui_config.py` starts as a flat dict, not a versioned schema | Schema versioning adds scope; flat dict is sufficient for first deploy | When a second bot or second environment is added |
| Visual regression baseline is established on first passing run, not a pre-approved design spec | No design spec exists yet | When a design system is adopted |
| Telethon session string is generated manually and stored as a secret | Automated session rotation is a separate system | When the bot has more than 2 developers |

**Build Phase Transition additions for dual-platform projects (append to §8.3 checklist):**
- [ ] `ui_config.py` created and validated against WIKI.md §3.4 schema before first bot handler is written
- [ ] Staging bot username declared and confirmed separate from production bot username
- [ ] `.github/workflows/autonomous_gate.yml` skeleton committed before first feature cycle — CI must be green from day one, not retrofitted
- [ ] All five CI/CD secrets registered in GitHub Actions encrypted secrets before Gate 3 is first run
- [ ] Percy or Applitools baseline established after Gate 2 first passes — not before
