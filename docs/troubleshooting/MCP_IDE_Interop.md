# Interop MCP IDE : Windsurf, Cline, Continue.dev

**TL;DR**: Correction des échecs de connexion MCP dans Windsurf et Cline en basculant les serveurs stdio (filesystem-agent, ripgrep-agent, shrimp-task-manager) sur un bridge Python avec shim roots/list. Continue.dev déjà aligné.

## Problème

Les IDE Windsurf et Cline échouaient à se connecter aux serveurs MCP stdio `filesystem-agent`, `ripgrep-agent`, `shrimp-task-manager`. Le MCP Gateway HTTP ne mappe que les serveurs gateway (`context-compression`, `sequential-thinking`, etc.), retournant `unknown_server` (JSON-RPC `-32001`, HTTP 404) pour les stdio.

Cause racine : `get_mcp_server_base_url()` ne connaissait que les serveurs HTTP.

## Solution Appliquée

### Alignement sur Continue.dev
Basculement des 3 serveurs stdio vers un bridge Python `scripts/mcp_bridge.py` qui relaie stdin/stdout et filtre les logs.

### Shim Roots/List pour Shrimp Task Manager
Shrimp Task Manager appelle `roots/list` du serveur vers le client. Le shim intercepte ces requêtes et répond avec une racine `file://` (voir `_run_shrimp_task_manager_stdio_with_roots_shim`).

## Configurations Modifiées

### Repo (mcp_config.json pour Windsurf)
```json
{
  "mcpServers": {
    "filesystem-agent": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/kidpixel/kimi-proxy/scripts/mcp_bridge.py", "filesystem-agent"],
      "env": {
        "MCP_FILESYSTEM_ALLOWED_ROOT": "/home/kidpixel",
        "MCP_BRIDGE_PATH_ENV": "/usr/bin:/bin:/usr/local/bin",
        "PATH": "/usr/bin:/bin:/usr/local/bin"
      }
    },
    "ripgrep-agent": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/kidpixel/kimi-proxy/scripts/mcp_bridge.py", "ripgrep-agent"],
      "env": {
        "MCP_BRIDGE_PATH_ENV": "/usr/bin:/bin:/usr/local/bin",
        "PATH": "/usr/bin:/bin:/usr/local/bin"
      }
    },
    "shrimp-task-manager": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/kidpixel/kimi-proxy/scripts/mcp_bridge.py", "shrimp-task-manager"],
      "env": {
        "MCP_SHRIMP_TASK_MANAGER_COMMAND": "/home/kidpixel/.local/bin/shrimp-task-manager",
        "DATA_DIR": "/home/kidpixel/kimi-proxy/shrimp_data",
        "MCP_BRIDGE_PATH_ENV": "/usr/bin:/bin:/usr/local/bin",
        "PATH": "/usr/bin:/bin:/usr/local/bin"
      }
    }
  }
}
```

### Repo (cline_mcp_settings.json pour Cline)
Même structure que ci-dessus, avec `type: "stdio"` et bridge.

### Hors Repo (../.cline/data/settings/cline_mcp_settings.json)
Aligné automatiquement via session.

### Hors Repo (../.codeium/mcp_config.json)
Aligné automatiquement via session.

## Validation

- **Gateway HTTP** : Curl OK pour serveurs HTTP (ex: `sequential-thinking`).
- **Shrimp Task Manager** : Harness Python OK (`initialize` → `tools/list` → `tools/call` avec `split_tasks`).

## Points à Faire (Suite) - Terminés

- ✅ Vérifier/aligner configs réellement utilisées par les IDE.
- ✅ Exécuter workflow Shrimp via outils MCP (plan_task → analyze_task → split_tasks → execute_task → verify_task).
- ✅ Phase 5 : validation JSON/YAML + tests manuels + mise à jour documentation.

## Golden Rule

Documenter systématiquement les interops IDE pour éviter les régressions. Utiliser le bridge stdio pour les serveurs MCP locaux, gateway HTTP pour les distants.

## Patterns Système Appliqués

- **Pattern 14** : Async/Await obligatoire pour I/O.
- **Pattern 6** : Error Handling robuste avec extraction tokens partielle.

## Trade-offs

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Bridge stdio | Compatible tous IDE | Complexité ajoutée |
| Gateway HTTP | Simple, sécurisé | Limité aux serveurs supportés |

**Choix Kimi Proxy** : Bridge stdio pour flexibilité maximale.

---

*Dernière mise à jour : 2026-02-25*  
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ❌/✅ ✔, Trade-offs ✔, Golden Rule ✔*
