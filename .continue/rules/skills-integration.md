---
trigger: kimi_proxy_task
description: Automatic skill detection and routing matrix for kimi-proxy development based on pattern matching and priority hierarchy
globs:
alwaysApply: false
---

# Skills Integration Matrix

## Detection Patterns

| Pattern | Skill | Priority |
|---------|-------|----------|
| `config`, `provider`, `api key`, `toml`, `settings` | kimi-proxy-config-manager | 1 |
| `frontend`, `dashboard`, `websocket`, `chart.js`, `ui`, `vanilla` | kimi-proxy-frontend-architecture | 1 |
| `mcp`, `memory`, `semantic`, `search`, `qdrant`, `compression` | kimi-proxy-mcp-integration | 1 |
| `performance`, `optimize`, `latency`, `async`, `database`, `sqlite` | kimi-proxy-performance-optimization | 1 |
| `streaming`, `error`, `ReadError`, `Timeout`, `debug`, `sse` | kimi-proxy-streaming-debug | 1 |
| `test`, `pytest`, `async`, `coverage`, `unit` | kimi-proxy-testing-strategies | 1 |
| `task`, `plan`, `expand`, `pr`, `analysis`, `backlog` | taskmaster | 1 |
| `think`, `analyze`, `reason`, `logic`, `architecture` | sequentialthinking | 1 |
| `file`, `read`, `edit`, `large`, `compress`, `directory` | fast-filesystem | 2 |
| `json`, `query`, `path`, `structure`, `inspect` | json-query | 2 |
| `docs`, `README`, `guide`, `documentation` | documentation | 3 |
| `python`, `typing`, `pep8`, `clean`, `standards` | python-coding-standards | 3 |

## Auto-Loading Logic

When patterns detected, automatically load:
```
read_file(".windsurf/skills/[SKILL_NAME]/SKILL.md")
```

## Multi-Skill Support

For complex requests, combine multiple skills based on pattern detection priority.

## Skills Usage Policy

- **Local Skills** (`.windsurf/skills/`) : kimi-proxy-config-manager, kimi-proxy-frontend-architecture, kimi-proxy-mcp-integration, kimi-proxy-performance-optimization, kimi-proxy-streaming-debug, kimi-proxy-testing-strategies, taskmaster, sequentialthinking, fast-filesystem, json-query
- **Global Skills** : documentation, python-coding-standards
- **Detection** : Automatic via pattern matching above
- **Priority** : Local skills first, then global fallback
- **Hierarchy** : kimi-proxy skills > taskmaster > documentation > coding standards > global skills