# Interop MCP IDE : Windsurf, Cline, Continue.dev

**TL;DR**: Correction des échecs de connexion MCP dans Windsurf et Cline en basculant les serveurs stdio (filesystem-agent, ripgrep-agent, shrimp-task-manager) sur un bridge Python avec shim roots/list. Continue.dev déjà aligné.

Si tu vois une erreur JSON-RPC `-32001`, ne pars pas du principe que c’est toujours `unknown_server`. Dans notre stack, ce code peut aussi apparaître quand le **bridge stdio** ne parvient pas à relayer une réponse (ex: sortie trop volumineuse côté ripgrep-agent).

## Problème

Tu peux rencontrer deux problèmes distincts qui se ressemblent côté IDE:

1) **Interop / routage**: les IDE Windsurf et Cline échouaient à se connecter aux serveurs MCP stdio `filesystem-agent`, `ripgrep-agent`, `shrimp-task-manager`. Le MCP Gateway HTTP ne mappe que les serveurs gateway (`context-compression`, `sequential-thinking`, etc.), retournant `unknown_server` (JSON-RPC `-32001`, HTTP 404) pour les stdio.

2) **Timeout ripgrep-agent**: certaines requêtes `ripgrep-agent` renvoient une réponse JSON-RPC énorme sur une seule ligne (beaucoup de matches). Par défaut, `asyncio` impose une limite (~64KiB) sur `StreamReader.readline()`. Si la réponse dépasse cette limite, la lecture stdout côté bridge peut échouer et l’IDE remonte un timeout / `-32001`.

Cause racine (interop): `get_mcp_server_base_url()` ne connaissait que les serveurs HTTP.

Cause racine (timeouts): limite interne `readline()` sur stdout quand une réponse JSON-RPC dépasse la limite de stream.

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
        "MCP_BRIDGE_STDIO_STREAM_LIMIT": "8388608",
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

### Hors repo (config réellement utilisée par l’IDE)

Selon l’IDE, le fichier réellement utilisé n’est pas forcément celui du repo. Par exemple:

- VS Code + Cline: `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- Windsurf/Codeium: fichier `mcp_config.json` spécifique (selon installation)

Si tu modifies le repo mais que l’IDE continue à échouer, commence par vérifier le chemin de config chargé par l’IDE.

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

## Diagnostiquer un `-32001`

Même code, causes différentes. Voici un tri rapide.

### ❌ Interprétation automatique: "-32001 = unknown_server"

Tu perds du temps si tu cherches uniquement du côté routing/gateway alors que le bridge a juste échoué à relayer une réponse trop grosse.

### ✅ Lecture pragmatique: regarde le message + stderr

1) Si le message parle de `unknown_server` ou HTTP 404: tu n’es pas sur la bonne route (gateway au lieu de stdio bridge).
2) Si le message parle de stdout/limit/"chunk exceed the limit": c’est une réponse trop volumineuse.

### Runbook (ripgrep-agent)

1) **Borne la requête**: réduis `maxResults`, cible un dossier, ou scinde le pattern.
2) **Augmente la limite**: `MCP_BRIDGE_STDIO_STREAM_LIMIT=8388608` (ou plus si nécessaire).
3) **Fallback shell** si tu as besoin d’un résultat volumineux:

```bash
rg -n "pattern" . | head -n 200
```

Tu récupères un extrait exploitable, puis tu raffines la requête dans l’IDE.

---

*Dernière mise à jour : 2026-02-26*  
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ❌/✅ ✔, Trade-offs ✔, Golden Rule ✔*
