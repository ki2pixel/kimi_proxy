# Features du middleware

**TL;DR** : les features actives réduisent le contexte avant l'envoi au provider et exposent une mémoire MCP. Les features de compaction, compression applicative, multi-provider et WebSocket ont été supprimées.

## Features conservées

| Feature | Fichier | État par défaut | Rôle |
| :--- | :--- | :--- | :--- |
| Tool fixing | `proxy/tool_utils.py` | actif | Réparer les `tool_calls` et arguments JSON |
| Observation masking | `features/observation_masking/` | désactivé | Masquer les vieux tool results |
| Context pruning | `proxy/context_pruning.py` + `features/mcp_pruner/` | désactivé | Élaguer les messages `role=tool` |
| MCP tool pruning | `features/mcp_tool_pruning/` | désactivé | Élaguer les réponses MCP volumineuses |
| Mémoire MCP | `features/mcp/memory.py` | actif sur appel API | Stockage SQLite + recherche Qdrant |
| Compression MCP | `features/mcp/servers/compression.py` | actif sur appel API | Compression via serveur externe |
| Log watcher | `features/log_watcher/` | désactivé | Lire les logs Continue/Kimi |
| Sanitizer | `features/sanitizer/storage.py` | lecture seule | Lire les contenus masqués |

## Documentation disponible

- [MCP et mémoire](./mcp.md)
- [MCP Pruner](./mcp-pruner.md)
- [Sanitizer](./sanitizer.md)
- [Log Watcher](./log-watcher.md)

## Features retirées

Les fonctionnalités suivantes ont été supprimées le 2026-11-06, avec leurs routes et leur code :

- Compaction de contexte.
- Compression applicative.
- Auto-session.
- Intégration Cline spécifique.
- WebSocket et dashboard.

Le runtime actuel ne les expose plus. Voir `docs/audit/audit-code-mort-2026-11-06.md`.

## Golden Rule

Une feature désactivée par défaut n'est pas morte si elle est câblée et testée. Une feature dont le point d'entrée a été supprimé est morte et doit être retirée de la documentation.
