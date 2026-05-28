# LLM Wiki Schema & Guidelines
Parent: [[index]]
Tags: #meta, #instructions
---

This document outlines the rules and conventions for managing this wiki, inspired by Andrej Karpathy's compiled knowledge pattern.

## Core Directives

1.  **Compiled Knowledge**: The wiki represents digested, summarized, and synthesized information. Do not dump raw console logs or raw source code files. Condense code concepts into dense descriptions, flowcharts, or small snippet mappings.
2.  **Explicit Cross-Linking**: Every entity page MUST be linked using standard wiki double brackets (`[[page-name]]`). Use links when referencing other components, files, or concepts.
3.  **Strict File Association**: Always map concepts directly to code paths using absolute links, e.g. `[proxy_server.py](file:///Users/k3x/Developer/MCE/mce-core/core/proxy_server.py)`.
4.  **Append-only Changelog**: Any modification to the wiki (creation of pages, edits, deletions) MUST be appended chronologically to [[log]] with a timestamp and a brief explanation of the change.

## Page Template

Every wiki page must adhere to the following template:

```markdown
# Page Title
Parent: [[parent-page]]
Tags: #tag1, #tag2
---

## Summary
[Concise 1-2 sentence description of what this component is]

## Code References
*   [file_name.py](file:///absolute/path/to/file_name.py) — Description of role

## Details
...
```

## Tag Registry
- `#orchestrator`: Proxy server and main pipeline orchestration.
- `#safeguard`: CircuitBreaker, PermissionGate, and DriftSentinel.
- `#optimization`: TokenEconomist, Pruner, and SemanticRouter.
- `#state`: TimeMachine, MemVault, and context persistence.
- `#meta`: System guidelines, indexing, and logs.
