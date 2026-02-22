---
trigger: model_decision
description: Automatic skill detection and routing matrix for kimi-proxy development based on pattern matching and priority hierarchy
globs: 
---

# Skills Integration Matrix

## Detection Patterns

| Pattern | Skill | Priority | MCP Available |
|---------|-------|----------|---------------|
| `config`, `provider`, `api key`, `toml`, `settings` | kimi-proxy-config-manager | 1 | ✅ API proxy |
| `frontend`, `dashboard`, `websocket`, `chart.js`, `ui`, `vanilla` | kimi-proxy-frontend-architecture | 1 | ✅ API proxy |
| `mcp`, `memory`, `semantic`, `search`, `qdrant`, `compression` | kimi-proxy-mcp-integration | 1 | ✅ API proxy |
| `performance`, `optimize`, `latency`, `async`, `database`, `sqlite` | kimi-proxy-performance-optimization | 1 | ✅ API proxy |
| `streaming`, `error`, `ReadError`, `Timeout`, `debug`, `sse` | kimi-proxy-streaming-debug | 1 | ✅ API proxy |
| `test`, `pytest`, `async`, `coverage`, `unit` | kimi-proxy-testing-strategies | 1 | ✅ API proxy |
| `task`, `plan`, `expand`, `pr`, `analysis`, `backlog` | shrimp-task-manager | 1 | ✅ Local MCP |
| `think`, `analyze`, `reason`, `logic`, `architecture` | sequentialthinking-logic | 1 | ✅ Local MCP |
| `file`, `read`, `edit`, `large`, `compress`, `directory` | fast-filesystem-ops | 2 | ✅ Local MCP |
| `json`, `query`, `path`, `structure`, `inspect` | json-query-expert | 2 | ✅ Local MCP |
| `docs`, `README`, `guide`, `documentation` | documentation | 3 | ✅ Lecture fichier |
| `python`, `typing`, `pep8`, `clean`, `standards` | python-coding-standards | 3 | ✅ Lecture fichier |

## Auto-Loading Logic

When patterns detected, automatically load:
```
read_file(".windsurf/skills/[SKILL_NAME]/SKILL.md")
```

## Multi-Skill Support

For complex requests, combine multiple skills based on pattern detection priority.

## Skills Usage Policy

- **Local Skills** (`.windsurf/skills/`) : kimi-proxy-config-manager, kimi-proxy-frontend-architecture, kimi-proxy-mcp-integration, kimi-proxy-performance-optimization, kimi-proxy-streaming-debug, kimi-proxy-testing-strategies, shrimp-task-manager, sequentialthinking, fast-filesystem, json-query
- **Global Skills** : documentation, python-coding-standards
- **Detection** : Automatic via pattern matching above
- **Priority** : Local skills first, then global fallback
- **Hierarchy** : kimi-proxy skills > shrimp-task-manager > documentation > coding standards > global skills

## ✅ Important: MCP Tools Active in Windsurf

Les skills référencent des outils MCP (shrimp-task-manager, sequential-thinking, fast-filesystem, json-query) qui sont configurés dans l'environnement Windsurf.

### Configuration actuelle
- Windsurf utilise `config.yaml` avec les serveurs MCP Phase 4 actifs (voir lignes 305-330)
- Ces serveurs fonctionnent en local via commandes npx/node
- Ils sont disponibles comme outils MCP directs

### Utilisation
Utiliser directement les outils MCP locaux pour :
- shrimp-task-manager : gestion de tâches et planning
- sequential-thinking : raisonnement structuré
- fast-filesystem : opérations fichiers haute performance
- json-query : requêtes JSON avancées