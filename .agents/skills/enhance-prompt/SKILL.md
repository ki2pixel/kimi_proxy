---
name: enhance-prompt
description: Transform a raw request into a structured technical mega-prompt for Kimi Proxy without executing the task, modifying files, or generating functional code.
metadata:
  source_workflow: /home/kidpixel/kimi-proxy/.windsurf/workflows/enhance.md
  legacy_slash_command: /enhance
  invocation:
    - /skill:enhance-prompt
---

# Purpose
**TL;DR**: Use this skill when a raw request must be rewritten into a single, ready-to-send Markdown mega-prompt that carries the right project context without performing the underlying task.

# When to Use
- Use when the user wants prompt enhancement, prompt reframing, or a structured technical brief for another agent.
- Use when the task must remain purely at the specification level.
- Do not use when the user is asking for direct implementation.
- Do not use when file edits, executable code, or task execution are expected outputs.

# Inputs
- The raw user request to transform.
- `/home/kidpixel/kimi-proxy/memory-bank/activeContext.md` read with `fast_read_file`.
- Only the specialized skills or architectural patterns that are directly relevant to the request.

# Workflow
1. Assume the role of Prompt Engineer and Technical Architect.
2. Read `/home/kidpixel/kimi-proxy/memory-bank/activeContext.md` with `fast_read_file` using an absolute path.
3. Analyze the raw request and determine which project skills or architectural patterns are relevant.
4. Read only the necessary contextual files; never index the whole project.
5. Synthesize the result into one Markdown code block containing the required sections: `MISSION`, `CONTEXTE TECHNIQUE (via MCP)`, `INSTRUCTIONS PAS-À-PAS`, and `CONTRAINTES`.
6. Stop immediately after producing that block.

# Guardrails
- Never execute the requested task.
- Never modify any file.
- Never generate functional code.
- Never output anything outside a single Markdown code block.
- Always preserve the required section names in the final block.
- Use absolute paths for memory-bank file access.

# Output Contract
- The response must be exactly one Markdown code block.
- That block must contain these sections in order:
  1. `# MISSION`
  2. `# CONTEXTE TECHNIQUE (via MCP)`
  3. `# INSTRUCTIONS PAS-À-PAS`
  4. `# CONTRAINTES`
- No preface, no explanation, and no follow-up text outside the block.

# Legacy Trigger Mapping
- Ancien trigger : `/enhance`
- Nouveau trigger standard : `/skill:enhance-prompt`
