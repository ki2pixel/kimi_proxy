# TimeMachine & Checkpointing
Parent: [[index]]
Tags: #state
---

## Summary
`TimeMachine` takes snapshots of files and git references before executing high-risk tools. This allows agents or developers to branch, list milestones, or restore files to a clean state.

## Code References
*   [time_machine.py](file:///Users/k3x/Developer/MCE/mce-core/engine/time_machine.py) — Time travel checkpoint manager.
*   [test_time_machine.py](file:///Users/k3x/Developer/MCE/mce-core/tests/test_time_machine.py) — Unit tests for branches, restores, and max checkpoint limit.

## Key Features

### 1. Pre-execution Checkpoints
If a tool execution matches a high-risk signature (e.g. destructive commands or custom [[skill_forge]] profiles requiring checkpoints), MCE:
1.  Takes a git stash / index snapshot of the workspace.
2.  Assigns a chronological sequence ID (e.g. `cp1`, `cp2`).
3.  Logs the initiating tool name and arguments.

### 2. Branching & Rollback
Using CLI or HTTP state routes, developers can:
- **Restore**: Reverts the workspace filesystem to the snapshot associated with a checkpoint.
- **Branch**: Creates a new git branch from a historical checkpoint, allowing parallel experiments.
