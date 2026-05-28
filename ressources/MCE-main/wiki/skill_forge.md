# SkillForge Workflow Engine
Parent: [[index]]
Tags: #orchestrator
---

## Summary
`SkillForge` (driven by `SkillLoader`) processes domain-specific instructions (`.skill.md` files) to check tool name or keyword matches. It appends constraints or workflows to tool results, and enforces pre-execution checkpoints.

## Code References
*   [skill_loader.py](file:///Users/k3x/Developer/MCE/mce-core/engine/skills/skill_loader.py) — Parser and matcher for skill markdown profiles.
*   [test_skill_loader.py](file:///Users/k3x/Developer/MCE/mce-core/tests/test_skill_loader.py) — Skill parsing unit tests.

## Skill Configuration Schema
Skills are structured as Markdown files with YAML frontmatter:
```markdown
---
name: sql-safety
version: 1.0.0
triggers:
  tool_names: ["execute_sql"]
  keywords: ["SELECT", "UPDATE"]
risk_level: high
requires_checkpoint: true
---
## Constraints
- Never select all columns without limit.

## Workflow
1. Append LIMIT 10 if not present.
```

## Runtime Matching & Injection
1.  **Intercept**: The [[proxy_server]] intercepts an incoming tool call (e.g. `execute_sql`).
2.  **Match**: `SkillLoader` matches the command parameters against `triggers.tool_names` or regex/keyword matches in `triggers.keywords`.
3.  **Checkpoint**: If `requires_checkpoint` is set to `true`, MCE calls [[time_machine]] to snapshot the environment before running.
4.  **Inject Notices**: Post-execution, the skill's Constraints and Workflow are appended to the response payload under the `_mce_notices` key. This instructs the client agent on how to proceed.
