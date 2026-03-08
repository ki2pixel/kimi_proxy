---
name: commit-push
description: Stage repository changes, create a conventional commit from reviewed diffs, and push the current branch to origin with a guarded non-interactive workflow.
metadata:
  source_workflow: /home/kidpixel/kimi-proxy/.windsurf/workflows/commit-push.md
  legacy_slash_command: /commit-push
  invocation:
    - /skill:commit-push
---

# Purpose
**TL;DR**: Use this skill to publish local work safely with a fixed sequence: review repository state, run quality checks, stage all changes, create a commit that follows `/home/kidpixel/kimi-proxy/.windsurf/rules/commit-message-format.md`, then push the current branch to `origin`.

# When to Use
- Use when the user explicitly wants to commit and push the current branch.
- Use when a non-interactive Git publication flow is preferred.
- Do not use when the repository is in a detached HEAD state, the branch is unknown, `origin` is missing, or there are unresolved conflicts.
- Do not use when there are no effective changes to commit.

# Inputs
- A commit message provided by the user or an environment variable.
- The current Git branch resolved from the repository state.
- The current uncommitted diff reviewed from the working tree and staged changes.
- Optional quality commands requested by the user or required by the repository context.

# Workflow
1. Read `/home/kidpixel/kimi-proxy/.windsurf/rules/commit-message-format.md` before generating the commit message.
2. Inspect repository state with `git status --short --branch` and resolve the current branch with `git branch --show-current`.
3. Stop if the branch is empty, detached, conflicted, or if remote `origin` is not configured.
4. Propose a quick review step with `git status` and, if needed, `git diff` or `git diff --cached` before publication.
5. Run quality checks appropriate to the change set such as lint, test, or build commands.
6. Stage the full change set with `git add -A`.
7. Verify that the staged diff is not empty before attempting the commit.
8. Create the commit message from the actual diff, not from the branch name alone, and keep it aligned with the Conventional Commits-based rule file.
9. Run `git commit` non-interactively with the prepared message.
10. Push with `git push -u origin <current-branch>`.

# Guardrails
- Never skip repository state inspection.
- Never create a commit without reviewing the actual diff.
- Never proceed if `origin` is missing or the current branch cannot be resolved.
- Never create an empty commit unless the user explicitly asks for one.
- Never invent a commit message from issue titles or branch names alone.
- Prefer non-interactive commands throughout the sequence.
- Preserve the execution order: quality checks, `git add -A`, `git commit`, `git push`.

# Output Contract
- Return a concise publication summary containing the current branch, the quality checks executed, the commit message used, and the push target.
- If the workflow is blocked, return the exact blocking condition and the next corrective action.
- Mention that the commit message rule source is `/home/kidpixel/kimi-proxy/.windsurf/rules/commit-message-format.md`.

# Legacy Trigger Mapping
- Ancien trigger : `/commit-push`
- Nouveau trigger standard : `/skill:commit-push`
