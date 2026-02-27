# Memory Bank Protocol

## Overview

The Memory Bank Protocol defines the mandatory lifecycle of project context. It uses fast-filesystem and filesystem-agent MCP tools to minimize token overhead while maintaining precise documentation.

**Token-Saver Mode**: Minimize context usage by leveraging tools instead of pre-loading data.

## Selective Initialization Protocol

**Trigger**: `first_interaction` | **Priority**: `immediate` | **Required**: `true`

**Actions Required:**
1. **Start with MCP Pull**: Call `fast_read_file(path="/home/kidpixel/kimi-proxy/memory-bank/activeContext.md")`
2. **Internalize Status**: Verify blockers, current focus, and next steps
3. **Strict Constraint**: Do NOT load `productContext.md` or `systemPatterns.md` unless the task specifically requires architectural or strategic depth
4. **Prefix Requirement**: Begin responses with `[MEMORY BANK: ACTIVE (MCP-PULL)]`
5. **Fault Tolerance**: If `fast_read_file` fails, state unavailability and proceed without context
6. **Prohibition**: Never load more than one file at a time
7. **Locking Instruction**: Use absolute paths exclusively for memory-bank files

## File Structure & Responsibilities

Access via `fast_read_file`, `edit_file`, or `fast_list_directory` using absolute paths:

- **`productContext.md`**: Project scope, goals, and standards
- **`activeContext.md`**: Current session state, active decisions, and blockers
- **`systemPatterns.md`**: Recurring patterns (coding, architecture, testing)
- **`decisionLog.md`**: Technical decisions, implementations, and alternatives
- **`progress.md`**: Work status tracking (completed, current, next, issues)

## Update & Quality Standards

### Update Protocol
- **Frequency**: Update at task completion or via `UMB` command
- **Timestamp Format**: `[YYYY-MM-DD HH:MM:SS] - [Summary]` (Required for every entry)
- **Conciseness**: Keep entries focused and actionable
- **Cross-References**: Link related entries across files for logical web

### Retention Policy
- **90-day Detail**: Keep full details for last 90 days in `decisionLog.md` and `progress.md`
- **Archiving**: Summarize older entries and move to `memory-bank/archives/*.md`
- **Archiving Tool**: Use `fast_write_file(path="/home/kidpixel/kimi-proxy/memory-bank/archives/...")` for archiving
- **Creation Restriction**: `fast_write_file` only for initialization or archiving
- **Traceability**: Mention archive path in active file

## Context-Specific Rules

### Documentation Context
**Trigger**: Questions about 'docs', 'guides', 'guidelines', or 'API reference'
**Instruction**: State *"I will consult the project's internal documentation."*
**Priority Pull**: Read `docs/` and root markdown files (e.g., `README.md`)
**Conflict Resolution**: If code and docs conflict, cite both and ask for clarification

### Coding & Architecture Context
**Trigger**: Requests to generate, modify, refactor code, or architectural questions
**Instruction**: State *"I will adhere to the project's mandatory architectural and coding standards."*
**Selective Pull**: Immediately call `read_file` for `.clinerules/codingstandards.md`
**Constraint**: Formulate plan strictly based on standards principles

## Special Command: Update Memory Bank (UMB)

**Trigger**: User inputs `^(Update Memory Bank|UMB)$`
**Process**:
1. **Halt**: Stop current activity
2. **Acknowledge**: Respond with `[MEMORY BANK: UPDATING]`
3. **Audit**: Review current chat for decisions, changes, or clarifications
4. **Sync**: Call `edit_file` on relevant files (usually `progress.md` and `activeContext.md`)
5. **Clean**: Do NOT summarize entire project history, only current session deltas

## Observability & Dashboard Triggers

To assist Kimi Proxy monitoring, explicitly state intent during pulls:
- *"Initiating Pre-Flight Validation (Pulling activeContext)"*
- *"Pulling architectural patterns for coding task"*
- *"Synchronizing memory bank (UMB mode)"*