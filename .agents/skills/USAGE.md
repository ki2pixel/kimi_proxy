# Kimi Code CLI Skills Usage Guide

This guide explains how to use each skill in the Kimi Code CLI environment.

## General Instructions

- All skills are triggered by specific commands prefixed with `/flow:` or `/skill:`.
- Ensure the required tools (e.g., `fast_read_file`, `Shell`) are available in your environment.

## Skill Usage Details

### `/flow:end`
Terminates the current session and synchronizes the Memory Bank.

**Steps**:
1. Run `/flow:end` command.
2. The system will read `activeContext.md` and `progress.md`.
3. Update Memory Bank files with session summary.
4. Confirm session closure by checking `progress.md` and `activeContext.md`.

### `/flow:enhance`
Enhances a raw prompt with project context.

**Steps**:
1. Provide the raw prompt as input to `/flow:enhance`.
2. System reads `activeContext.md` and relevant skills.
3. Generates a structured mega-prompt in Markdown format.
4. Output is a single Markdown code block without additional text.

### `/flow:docs-updater`
Updates project documentation using static analysis tools.

**Steps**:
1. Run `/flow:docs-updater`.
2. Audit project structure with `tree`, `cloc`, `radon`.
3. Identify areas needing documentation updates.
4. Update documentation files with `edit_file` tool.

### `/flow:enhance-complex`
Plans complex tasks using Shrimp Task Manager.

**Steps**:
1. Use `/flow:enhance-complex` with the task description.
2. System will create a task plan using `plan_task` and `split_tasks`.
3. Analyze technical feasibility with `analyze_task`.
4. Execute tasks step-by-step with `execute_task`.

### `/flow:commit-push`
Commits and pushes changes to the remote repository.

**Steps**:
1. Stage changes with `git add -A`.
2. Review changes with `git diff`.
3. Commit with a properly formatted message.
4. Push to the current branch.

### `/skill:documentation`
Provides guidelines for technical writing.

**Usage**:
```
/skill:documentation
```

**Content**:
- Technical article structure guidelines
- Punctuation rules
- README-specific instructions
- Checklist for avoiding AI-generated feel

## Best Practices

- Always verify changes before committing (use `git diff`).
- Ensure quality checks pass before pushing.
- Follow commit message conventions strictly.
- Use the documentation guidelines when writing technical content.