# MCE Typer CLI Suite
Parent: [[index]]
Tags: #orchestrator
---

## Summary
The MCE CLI is a command-line interface built on Typer. It enables developers to query session statistics, switch profiles, manage checkpoints, and inspect database memory.

## Code References
*   [cli/main.py](file:///Users/k3x/Developer/MCE/mce-core/cli/main.py) — CLI entrypoint.
*   [profile.py](file:///Users/k3x/Developer/MCE/mce-core/cli/commands/profile.py) — Enforces comment-preserving profile rewrites and HTTP notifying.
*   [checkpoint.py](file:///Users/k3x/Developer/MCE/mce-core/cli/commands/checkpoint.py) — Manage manual restoration points.
*   [cost.py](file:///Users/k3x/Developer/MCE/mce-core/cli/commands/cost.py) — CostWatch budget queries.
*   [memory.py](file:///Users/k3x/Developer/MCE/mce-core/cli/commands/memory.py) — Memory store inspections.
*   [skills.py](file:///Users/k3x/Developer/MCE/mce-core/cli/commands/skills.py) — List registered profiles.

## Profile Switching Mechanics
When running `mce profile switch <profile>`:
1.  **YAML Rewrite**: Reads `config.yaml` and updates the active profile parameter using comment-preserving regex.
2.  **HTTP Notify**: Issues a `POST /profile/switch` call to uvicorn. If uvicorn is running, uvicorn updates uvicorn's state instantly in-memory. If offline, fails gracefully.
