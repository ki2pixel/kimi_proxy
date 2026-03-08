---
name: end-session-memory-bank
description: Close a work session, synchronize the memory bank with selective reads and minimal edits, then verify a neutral end-of-session state.
metadata:
  source_workflow: /home/kidpixel/kimi-proxy/.windsurf/workflows/end.md
  legacy_slash_command: /end
  invocation:
    - /skill:end-session-memory-bank
---

# Purpose
**TL;DR**: Use this skill to end a session cleanly: load only the minimum memory-bank context, apply the memory bank protocol, update the relevant records with minimal edits, then verify that the repository context is back to a neutral state.

# When to Use
- Use when a task batch or work session is complete and the memory bank must be synchronized.
- Use when the user asks to close the current session and record decisions or progress.
- Do not use as a generic history dump.
- Do not use when implementation work is still active and the session state is not ready to be neutralized.

# Inputs
- The current session summary.
- The task outcomes, decisions, blockers, and next-step status from the current conversation.
- The memory-bank files under `/home/kidpixel/kimi-proxy/memory-bank/`.

# Workflow
1. Read only `/home/kidpixel/kimi-proxy/memory-bank/activeContext.md` and `/home/kidpixel/kimi-proxy/memory-bank/progress.md` with `fast_read_file` for the initial session summary.
2. Do not read `/home/kidpixel/kimi-proxy/memory-bank/productContext.md`, `/home/kidpixel/kimi-proxy/memory-bank/systemPatterns.md`, or `/home/kidpixel/kimi-proxy/memory-bank/decisionLog.md` unless a major architectural decision was made.
3. If older context is needed, use targeted search instead of loading whole files.
4. Apply `/home/kidpixel/kimi-proxy/.clinerules/memorybankprotocol.md` and suspend the active task flow before writing updates.
5. Use search tools to identify only the additional files needed to summarize the session accurately.
6. Before each edit, re-read the relevant section with `fast_read_file` to keep the change set minimal.
7. Update the relevant memory-bank files with `edit_file`, documenting decisions, progress, and active context according to the protocol.
8. Verify the neutral end state with `fast_read_file`: `progress.md` must indicate `Aucune tâche active` and `activeContext.md` must be back to a neutral state.
9. Return a short user-facing closure summary.

# Guardrails
- Always use absolute paths for memory-bank files.
- Prioritize selective reading over broad context loading.
- Do not load the entire memory bank without a concrete justification.
- Do not finish the workflow until the neutral-state verification passes.
- Keep edits concise, protocol-compliant, and timestamped where required.

# Output Contract
- Return a concise closure summary of completed work.
- Confirm which memory-bank files were updated.
- Explicitly confirm the final neutral-state check: `Aucune tâche active` and neutral `activeContext.md`.

# Legacy Trigger Mapping
- Ancien trigger : `/end`
- Nouveau trigger standard : `/skill:end-session-memory-bank`
