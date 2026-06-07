# PLAYBOOK.md — REPOSITORY STATE MUTATION OVERRIDES
> **Document Version:** 1.2.0 | **Scope:** Cross-repository, schema-migration, and critical-path override cycles

---

## 1. STRATEGIC OVERRIDE PRINCIPLE

A Playbook is a declarative execution contract that supersedes the standard autonomous planning behavior of the `ai-orchestrator` and `project-manager` subagents. When an engineering task introduces cross-repository changes, database schema migrations, or critical-path API revisions, the system transitions from **autonomous discovery mode** to **deterministic step-execution mode**.

---

## 2. PLAYBOOK RUNTIME STATE MACHINE

When a Playbook is loaded into the active state ledger, the `sdlc-orchestrator` locks the execution loop into a sequential, transaction-isolated pipeline.

```
       [ Read State from Wiki ]
                  │
                  ▼
       [ Step-by-Step Dispatch ] ──► (Verify State Constraints)
                  │
                  ▼
       [ Post-Condition Check ]  ──► (Fail: Revert Git Ledger)
                  │
                  ▼
     [ Commit & Re-Index Wiki ]
```

### 2.1 The Execution Constraints

- **Zero-Planning Mandate:** The Orchestrator subagent is **FORBIDDEN** from modifying the sequence, adding unlisted files to the scope, or generating speculative code paths. It acts purely as a mechanical dispatcher.
- **Transaction Isolation:** Playbook steps must execute in order (`01 → 02 → 03`). Parallel worker streams via the `parallel-dispatcher` are locked unless a specific step block explicitly declares `"concurrency": true` in its step object.
- **Immutable Post-Conditions:** A step is not marked complete based on standard validation heuristics. It is verified only when its `validationExpression` returns a successful exit code `0`.

### 2.2 Playbook Scope Authorization Gate

A playbook must not execute until its `approvalGate` object is fully populated and validated. The `orchestrator` must enforce this check before acquiring the Execution Lock.

**In Autonomous Session Mode:** The `orchestrator` self-approves playbooks at or below the session's declared criticality ceiling. The `approvedBy` field is populated with `AUTONOMOUS_SESSION:{sessionId}` and the `approvalTimestamp` is set automatically. Playbooks above the ceiling are classified as 🔴 Session Stop triggers — the session pauses and the user is notified.

**Authorization checks (all must pass in Supervised Mode; checks 1–3 also apply in Autonomous Mode):**

1. `canvasId` must reference an active, signed canvas in the system ledger. If the referenced canvas has been superseded or retired, the playbook is blocked until re-authorized against the current canvas.
2. `scopeJustification` must explicitly name each `targetRepository` and state how its inclusion falls within the canvas's approved scope. Generic statements ("this is needed for the project") fail the check.
3. The playbook's `forbiddenActions` must be a strict superset of the parent canvas's §1 Strict Exclusions. It may add more restrictions but may never remove a canvas exclusion.
4. `approvedBy` must be a Tier-2 or Tier-3 operator identifier from the WIKI.md §3.2 privilege matrix. Tier-1 operators cannot authorize playbooks.

### 2.3 Governance by Scope, Not by Criticality

There is no `HITL_REQUIRED` mode. All playbooks within the declared session scope auto-execute, regardless of criticality. The scope boundary — set when the brief was given — is the governance mechanism. If a playbook is within that boundary, it runs. If it is outside it, it is quarantined and deferred.

| Criticality | Execution | Condition |
|---|---|---|
| `LOW` | Auto-execute | Within session scope |
| `MEDIUM` | Auto-execute | Within session scope |
| `HIGH` | Auto-execute | Within session scope |
| `CRITICAL` | Auto-execute | Within session scope |
| Any level | Quarantine + defer | Outside session scope |

> **The single governance rule:** does this playbook fall within the scope the human declared at session start? If yes, proceed. If no, quarantine and report. Criticality affects how carefully the Orchestrator logs and verifies the execution — not whether it executes.

---

## 3. PLAYBOOK STRUCTURE SCHEMA (`playbook_schema.json`)

All system playbooks must adhere to this structured validation contract to be parsed correctly by the multi-agent orchestration engine.

> **Schema Alignment Note:** The `validationExpression` field in `postConditions` is the canonical field name used throughout this document and in all runtime references. The `expression` alias is deprecated and must not be used in new playbooks.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PlaybookExecutionContract",
  "type": "object",
  "properties": {
    "playbookId": {
      "type": "string",
      "description": "Unique playbook identifier. Must follow the format PB-{YEAR}-{SEQ}-{slug}.",
      "pattern": "^PB-\\d{4}-\\d{3}-[a-z0-9-]+$"
    },
    "schemaVersion": {
      "type": "string",
      "description": "Semantic version of this playbook schema. Must match the engine's compiled expectation.",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "criticality": { "type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"] },
    "targetRepositories": {
      "type": "array",
      "items": { "type": "string" },
      "maxItems": 5,
      "description": "Maximum 5 repositories per playbook. Playbooks targeting more than 5 repositories must be split into sequenced playbooks with explicit dependency declarations."
    },
    "executionSequence": {
      "type": "array",
      "maxItems": 20,
      "description": "Maximum 20 steps per playbook. Playbooks requiring more than 20 steps must be decomposed into sequential playbooks with explicit handoff contracts.",
      "items": {
        "type": "object",
        "properties": {
          "stepId":             { "type": "string" },
          "actionType":         { "type": "string", "enum": ["MIGRATE", "PATCH", "BUILD", "DEPLOY"] },
          "targetRepository":   { "type": "string" },
          "concurrency": {
            "type": "boolean",
            "default": false,
            "description": "If true, this step may be dispatched in parallel with other concurrency-enabled steps in the same sequence block. Default is false (sequential)."
          },
          "targetScope": {
            "type": "object",
            "properties": {
              "files": { "type": "array", "items": { "type": "string" } }
            },
            "required": ["files"]
          },
          "executionDirectives": { "type": "string" }
        },
        "required": ["stepId", "actionType", "targetRepository", "targetScope", "executionDirectives"]
      }
    },
    "forbiddenActions": { "type": "array", "items": { "type": "string" } },
    "postConditions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "validationType": {
            "type": "string",
            "enum": [
              "AST_MATCH",
              "TEST_SUITE",
              "SCHEMA_VERIFY",
              "SECURITY_SCAN",
              "STATIC_ANALYSIS",
              "DEAD_CODE_SCAN",
              "UI_STRUCTURE_LINT",
              "E2E_WEB",
              "VISUAL_REGRESSION",
              "TELEGRAM_E2E",
              "DEPLOYMENT_GATE"
            ],
            "description": "AST_MATCH: structural AST comparison. TEST_SUITE: pytest-based coverage. SCHEMA_VERIFY: JSON schema conformance. SECURITY_SCAN: bandit/secrets detection. STATIC_ANALYSIS: flake8/radon. DEAD_CODE_SCAN: vulture. UI_STRUCTURE_LINT: Telegram API constraint validation via test_ui_structures.py. E2E_WEB: Playwright headless browser journey. VISUAL_REGRESSION: Percy/Applitools pixel diff. TELEGRAM_E2E: MTProto headless bot simulation via Telethon/Pyrogram. DEPLOYMENT_GATE: conditional production deploy + telemetry hook."
          },
          "validationExpression": {
            "type": "string",
            "description": "A shell-executable expression. The step is only marked complete when this returns exit code 0."
          }
        },
        "required": ["validationType", "validationExpression"]
      }
    },
    "approvalGate": {
      "type": "object",
      "description": "Mandatory scope authorization. Must be completed before the playbook may execute.",
      "properties": {
        "canvasId":          { "type": "string", "description": "The canvas ID this playbook falls under. Must reference an active, signed canvas. Use 'SYSTEM' only for infrastructure-level playbooks with no parent canvas." },
        "approvedBy":        { "type": "string", "description": "Identifier of the Tier-2 or Tier-3 operator who authorized this playbook." },
        "approvalTimestamp": { "type": "string", "description": "ISO 8601 UTC timestamp of approval." },
        "scopeJustification":{ "type": "string", "minLength": 50, "description": "Minimum 50 characters. Must state how this playbook's scope falls within the referenced canvas's approved scope and does not violate any canvas §1 Strict Exclusion." },
        "cabReviewLevel": {
          "type": "string",
          "enum": ["APPROVED"],
          "description": "All playbooks within the declared session scope are auto-approved. There is no HITL_REQUIRED mode — if a playbook is within scope, it executes. If it is outside scope, it is quarantined and deferred to the End-of-Session Report."
        }
      },
      "required": ["canvasId", "approvedBy", "approvalTimestamp", "scopeJustification", "cabReviewLevel"]
    }
  },
  "required": ["playbookId", "schemaVersion", "criticality", "targetRepositories", "executionSequence", "forbiddenActions", "postConditions", "approvalGate"]
}
```

**Current Live Schema Version:** `1.1.0`

---

## 4. ENFORCEMENT & FAILURE PATHWAYS

The `sdlc-manager` and `cab` (Change Advisory Board) subagents monitor live telemetry during playbook runs. Any state anomaly triggers immediate rollback routines.

### 4.1 Anti-Pattern Gate

The Builder subagent's generated AST or unified git diff is scanned before staging. If any mutation pattern intersects with a rule listed in `forbiddenActions`, the engine forces a hard stop.

In addition to playbook-specific `forbiddenActions`, the following **system-level anti-patterns** are permanently forbidden across all playbook runs and cannot be overridden by a playbook author:

| Anti-Pattern | Detection Method | Severity |
|---|---|---|
| **No tests shipped with mutated code** | `pytest --collect-only` returns zero new test functions for any mutated file | CRITICAL — hard stop |
| **Dead code introduced** | `vulture --min-confidence=80` flags any new unreachable symbol | HIGH — hard stop; HITL if in auth/IAC path |
| **Function exceeds 50 logical lines** | `flake8 --max-function-length=50` | HIGH — reject diff, force decomposition |
| **Bare or swallowed exception** | `bandit -l` severity MEDIUM+ | HIGH — hard stop; HITL if in IAC handler |
| **Error path returns `None` silently** | AST pattern match on `except` blocks with bare `return None` | MEDIUM — reject diff |
| **Untyped exception class** | AST check for `except Exception` without re-raise or structured payload | MEDIUM — reject diff |

### 4.2 Automated State Rollback (Git Ledger Reversion)

If a step fails its targeted `postConditions` check, or if a downstream block is blocked by an unhandled runtime error, the pipeline must execute the following sequence:

1. Halt all active execution queues across the `parallel-dispatcher`.
2. Issue a deterministic hard reset (`git reset --hard`) on all impacted `targetRepositories` to the exact commit hash captured at step initiation.
3. Broadcast a fatal error status payload back to the primary system tracking ledger.
4. **HITL Interception:** Do not trigger `layer6-self-healing` when a playbook fails. Escalate directly to human operators to preserve state safety.

### 4.3 WIKI Re-Indexing Failure Recovery

A gap in the original design: if code commits successfully but the WIKI re-indexing sync then fails, the repository is in a valid but unindexed state. This is distinct from a code failure and requires a separate recovery path.

**Detection:** `schema-debugger` raises a `WIKI_SYNC_FAILURE` error code after the re-indexing validation gate fails.

**Recovery Sequence:**

1. **Do not roll back the code commit.** The code is valid — only the index is stale. A `git reset --hard` here would destroy verified work.
2. `sdlc-orchestrator` sets a `pendingSync: true` flag on the `UserSessionContext.stateManifest` for all affected users and writes a `WIKI_SYNC_FAILURE` entry to the audit log.
3. `sdlc-orchestrator` holds the Execution Lock — **no new execution cycles may begin** while `pendingSync: true` is set.
4. `internal-auditor` is dispatched to perform a targeted re-indexing sweep of only the `filesMutated` from the failed cycle. It does not regenerate the full WIKI.
5. If the targeted sweep succeeds: `pendingSync` is cleared, Execution Lock is released, cycle completes normally.
6. If the targeted sweep fails a second time: HITL escalation. `sdlc-orchestrator` must not attempt a third autonomous re-index. Human operators resolve the discrepancy manually, then explicitly clear `pendingSync` to release the lock.

---

## 5. WORKED EXAMPLE: USER SESSION SCHEMA MIGRATION

This example demonstrates a minimal two-step playbook for the scenario of adding the `schemaVersion` field to `UserSessionContext` (as required by WIKI.md §3.1). It is provided as a concrete reference for playbook authors.

```json
{
  "playbookId": "PB-2024-001-add-schema-version",
  "schemaVersion": "1.1.0",
  "criticality": "HIGH",
  "targetRepositories": ["core-services", "agent-fleet"],
  "executionSequence": [
    {
      "stepId": "01-migrate-session-schema",
      "actionType": "MIGRATE",
      "targetRepository": "core-services",
      "concurrency": false,
      "targetScope": {
        "files": [
          "src/core/schemas/state.json",
          "src/core/state/session_model.py"
        ]
      },
      "executionDirectives": "Add required field 'schemaVersion' (type: string, pattern: semver) to UserSessionContext. Default value for existing records: '1.0.0'. Update the Pydantic model to include a validator enforcing semver format. Do not alter any other fields."
    },
    {
      "stepId": "02-patch-consumer-agents",
      "actionType": "PATCH",
      "targetRepository": "agent-fleet",
      "concurrency": false,
      "targetScope": {
        "files": [
          "src/engine/hermes/session_reader.py",
          "src/integrations/github/auth_handler.py",
          "src/integrations/groq/session_bridge.py"
        ]
      },
      "executionDirectives": "Update all sites that instantiate or deserialise UserSessionContext to pass schemaVersion='1.0.0' as a default. Add a version-mismatch guard: if the received schemaVersion does not match the agent's compiled expectation, raise a SchemaVersionError and halt processing. Do not alter business logic."
    }
  ],
  "forbiddenActions": [
    "ALTER existing required fields in UserSessionContext",
    "Remove the securityTier field or change its type",
    "Add new third-party dependencies",
    "Modify files outside targetScope"
  ],
  "postConditions": [
    {
      "validationType": "SCHEMA_VERIFY",
      "validationExpression": "python -m pytest tests/schemas/test_user_session_context.py -v --tb=short"
    },
    {
      "validationType": "TEST_SUITE",
      "validationExpression": "python -m pytest tests/integration/test_session_migration.py -v --tb=short --cov=src/core/state --cov=src/engine/hermes --cov-fail-under=85 --cov-branch"
    },
    {
      "validationType": "AST_MATCH",
      "validationExpression": "python scripts/ast_verify.py --schema src/core/schemas/state.json --model src/core/state/session_model.py"
    },
    {
      "validationType": "DEAD_CODE_SCAN",
      "validationExpression": "vulture src/core/state/session_model.py src/engine/hermes/session_reader.py src/integrations/ --min-confidence=80"
    },
    {
      "validationType": "SECURITY_SCAN",
      "validationExpression": "bandit -r src/core/state/ src/engine/hermes/ src/integrations/ -l --severity-level medium"
    },
    {
      "validationType": "STATIC_ANALYSIS",
      "validationExpression": "flake8 src/core/state/ src/engine/hermes/ src/integrations/ --max-function-length=50 --max-complexity=5"
    }
  ]
}
```

**What this example demonstrates:**

- `schemaVersion` is declared at the root, satisfying the new required field.
- `concurrency: false` is explicit on both steps, enforcing sequential execution.
- `postConditions` use `validationExpression` consistently (not the deprecated `expression` alias).
- `forbiddenActions` are concrete and scoped — not generic catch-alls.
- Both steps together cover the full blast radius: the schema definition *and* every known consumer agent.
- Post-condition 2 enforces **≥ 85% line coverage and branch coverage** on the exact files mutated — not global coverage.
- Post-condition 4 runs `vulture` to confirm **no dead code** was introduced.
- Post-condition 5 runs `bandit` to confirm **no bare or swallowed exceptions** at MEDIUM severity or above.
- Post-condition 6 runs `flake8` to confirm **no function exceeds 50 lines** and cyclomatic complexity stays within bounds.

---

## 6. DEPLOYMENT PLAYBOOK TEMPLATE (WEB + TELEGRAM BOT)

This template is the canonical starting point for any deployment playbook on a dual-platform project (Web Frontend + Telegram Bot). It implements the four-gate CI/CD pipeline defined in PROTOCOL.md §3.8 as a structured playbook contract.

**When to use this template:** Any time a change is ready to be promoted to production on a project that has both a web frontend and a Telegram bot backend. Copy, fill in the project-specific values, and submit for approval per §2.2–§2.3.

```json
{
  "playbookId": "PB-YYYY-NNN-deploy-<project-slug>",
  "schemaVersion": "1.1.0",
  "criticality": "HIGH",
  "targetRepositories": ["<web-frontend-repo>", "<telegram-bot-repo>"],
  "approvalGate": {
    "canvasId": "<active-canvas-id>",
    "approvedBy": "<tier-3-operator-id>",
    "approvalTimestamp": "<ISO-8601-UTC>",
    "scopeJustification": "Production deployment of <feature>. All four CI/CD gates have passed locally. No canvas §1 exclusions are affected. Branch is main. Staging bot tests passed against @<staging-bot-username>.",
    "cabReviewLevel": "HITL_REQUIRED"
  },
  "executionSequence": [
    {
      "stepId": "01-ui-structure-lint",
      "actionType": "BUILD",
      "targetRepository": "<telegram-bot-repo>",
      "concurrency": false,
      "targetScope": {
        "files": ["src/config/ui_config.py", "tests/test_ui_structures.py"]
      },
      "executionDirectives": "Run pytest on test_ui_structures.py. Validate all keyboard schemas in ui_config.py against Telegram API constraints: callback_data ≤ 64 bytes, ≤ 8 rows per keyboard, message text ≤ 4096 chars, button text ≤ 40 chars. Run AST scan to confirm no inline keyboard definitions exist outside ui_config.py. All assertions must pass before proceeding."
    },
    {
      "stepId": "02-web-e2e-visual",
      "actionType": "BUILD",
      "targetRepository": "<web-frontend-repo>",
      "concurrency": false,
      "targetScope": {
        "files": ["playwright.config.ts", "tests/e2e/web_journey.spec.ts"]
      },
      "executionDirectives": "Run npx playwright test against the staging web environment. All critical user journey assertions must pass. Then run Percy CLI (npx percy exec -- npx playwright test) using PERCY_TOKEN from environment. Zero unreviewed visual diffs permitted. If Applitools is used instead, run Eyes CLI with APPLITOOLS_API_KEY. Do not proceed if any visual diff is flagged as unreviewed."
    },
    {
      "stepId": "03-telegram-e2e",
      "actionType": "BUILD",
      "targetRepository": "<telegram-bot-repo>",
      "concurrency": false,
      "targetScope": {
        "files": ["tests/telegram_e2e_test.py"]
      },
      "executionDirectives": "Run telegram_e2e_test.py using Telethon or Pyrogram with TG_SESSION_STRING, TG_API_ID, TG_API_HASH from environment. Target staging bot username only — never production. Send /start, extract inline keyboards, assert structure matches ui_config.py definitions, click target button, assert response text and keyboard match expected outcomes. TG_SESSION_STRING must not appear in any log output — mask it explicitly. All assertions must pass."
    },
    {
      "stepId": "04-deploy-and-telemetry",
      "actionType": "DEPLOY",
      "targetRepository": "<primary-repo>",
      "concurrency": false,
      "targetScope": {
        "files": [".github/workflows/autonomous_gate.yml"]
      },
      "executionDirectives": "Execute deployment only if branch is main and all previous steps passed. Run deployment script (project-specific). After successful deployment, post a release event to Sentry using SENTRY_DSN or Datadog using DATADOG_API_KEY from environment. If telemetry hook fails, log the failure but do not roll back — telemetry failure is not a deployment failure. If deployment itself fails: execute git reset --hard to pre-deploy commit, raise SESSION_STOP (Autonomous Mode) or HITL (Supervised Mode)."
    }
  ],
  "forbiddenActions": [
    "Deploy to production bot username from a non-main branch",
    "Hardcode TG_SESSION_STRING, PERCY_TOKEN, APPLITOOLS_API_KEY, SENTRY_DSN, or DATADOG_API_KEY anywhere in source",
    "Skip Gate 1 (UI structure lint) because 'ui_config.py was not changed'",
    "Deploy if any Gate 1–3 post-condition returned non-zero exit code",
    "Define inline keyboard schemas outside ui_config.py",
    "Run MTProto tests against the production bot username"
  ],
  "postConditions": [
    {
      "validationType": "UI_STRUCTURE_LINT",
      "validationExpression": "pytest tests/test_ui_structures.py -v --tb=short"
    },
    {
      "validationType": "E2E_WEB",
      "validationExpression": "npx playwright test tests/e2e/web_journey.spec.ts --reporter=list"
    },
    {
      "validationType": "VISUAL_REGRESSION",
      "validationExpression": "npx percy exec -- npx playwright test tests/e2e/web_journey.spec.ts"
    },
    {
      "validationType": "TELEGRAM_E2E",
      "validationExpression": "python tests/telegram_e2e_test.py"
    },
    {
      "validationType": "SECURITY_SCAN",
      "validationExpression": "detect-secrets scan tests/ src/ --baseline .secrets.baseline"
    },
    {
      "validationType": "DEPLOYMENT_GATE",
      "validationExpression": "bash scripts/deploy.sh && bash scripts/telemetry_hook.sh"
    }
  ]
}
```

**GitHub Actions Structure Reference (`.github/workflows/autonomous_gate.yml`):**

The workflow must implement the four gates as sequential jobs. Each job declares `needs:` pointing to the prior job, ensuring strict sequential execution. The deployment job additionally guards on `github.ref == 'refs/heads/main'`.

```
jobs:
  gate-1-ui-structure:    # pytest test_ui_structures.py
  gate-2-web-e2e:         # playwright + percy — needs: gate-1-ui-structure
  gate-3-telegram-e2e:    # python telegram_e2e_test.py — needs: gate-2-web-e2e
  gate-4-deploy:          # deploy + telemetry — needs: gate-3-telegram-e2e
                          #   if: github.ref == 'refs/heads/main'
```

All secrets are injected via `${{ secrets.NAME }}`. No secret value is ever echoed, printed, or passed as a positional argument visible in process listings.
