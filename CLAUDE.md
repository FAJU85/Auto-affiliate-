# CLAUDE.md — GOVERNANCE OPERATING SYSTEM ENTRY POINT
> **Document Version:** 1.0.0 | **Scope:** All sessions, all projects, all agents
> **Authority:** This file is the mandatory bootstrap for every Claude Code session.

---

## MANDATORY PRE-TASK PROTOCOL

Before touching any code, file, or external system in a new project or session, you MUST read and internalize all six governance files in this order:

| # | File | Purpose |
|---|------|---------|
| 1 | [GLOSSARY.MD](./GLOSSARY.MD) | Canonical agent/term definitions — the shared vocabulary |
| 2 | [WIKI.MD](./WIKI.MD) | System architecture index and schema registry (SSOT) |
| 3 | [PROTOCOL.MD](./PROTOCOL.MD) | Universal multi-agent execution engine — MVAT triad, quality gates, IAC contracts |
| 4 | [PLAYBOOK.MD](./PLAYBOOK.MD) | Override layer — pre-approved mutation patterns, CI/CD pipeline template |
| 5 | [CANVAS.MD](./CANVAS.MD) | Project initialization canvas — scope contract, session mode, MVB §6.4 |
| 6 | [CLAUDE.md](./CLAUDE.md) | This file — entry point and enforcement summary |

**There are no exceptions.** A brief is not enough to start work. The governance system is already decided.

---

## OPERATING RULES (SUMMARY)

### Identity & Roles
- You operate within the **MVAT triad**: Orchestrator → Builder → Validator.
- Never collapse roles. The Validator is always a separate reasoning pass.
- Consult GLOSSARY.MD §AGENT-REGISTRY for full role definitions.

### Before Every Task
1. Read the task brief.
2. If the brief is ambiguous, ask **ONE targeted question** (CANVAS.MD §6.4 Minimum Viable Brief).
3. Never ask more than one question. Never ask the same question twice.
4. Confirm scope against CANVAS.MD before writing code.

### Quality Gates (non-negotiable)
- Cyclomatic complexity: **max 3** per function
- Function length: **max 50 lines**
- Dead code: **zero tolerance**
- Line coverage: **≥ 85%**
- Branch coverage: **≥ 75%**
- Full gate definitions in PROTOCOL.MD §QUALITY-GATES

### Execution Lock
- One active task at a time. No parallel mutations on the same file.
- IAC contract must be drafted before any cross-agent handoff.
- Schema in PROTOCOL.MD §IAC-CONTRACT

### Autonomy Thresholds
- **Session mode** (default): no approval tokens required for in-scope work.
- Escalate to human only for: out-of-scope changes, irreversible destructive actions, credential exposure.
- Autonomous reaction pathways defined in PROTOCOL.MD §AUTONOMOUS-REACTIONS

### State & History
- All architecture decisions logged in WIKI.MD as SSOT.
- All overrides and mutations logged via PLAYBOOK.MD execution contract.
- Never duplicate information across files — single source of truth always.

---

## ENFORCEMENT

Violation of any rule in this governance system is a **blocking error**.  
Stop. Log the violation. Ask one clarifying question if needed. Never silently skip a gate.

---

*This governance operating system was designed to run without human intervention for every routine task. The brief is all you need. Everything else is already decided here.*
