# Brief de Transition Kimi Proxy vers Middleware Minimaliste et Performant

Ce brief définit les exigences techniques détaillées pour transformer Kimi Proxy en un middleware minimal, modulaire et performant, conformément aux recommandations de l'audit de `docs/audit/audit_backend_kimi-proxy.md`.

## Objectifs Détaillés par Phase

### Phase 1 : Désactivation et Isolation (Court Terme)

1. **Log Watcher (`features/log_watcher/`)** :
   - Désactiver le démarrage automatique du Log Watcher par défaut dans le cycle de vie principal (`main.py`).
   - Rendre le démarrage configurable via la variable d'environnement `LOG_WATCHER_ENABLED` (défaut : `false`) et via la configuration TOML.
   
2. **MCP Pruning (`features/mcp/pruner/`)** :
   - Modifier la configuration par défaut pour définir `enabled = false` pour le pruner d'outils/contexte.
   
3. **Gestion de Sessions (`core/database.py`, `core/auto_session.py`)** :
   - Rendre la persistance des sessions SQLite optionnelle.
   - Par défaut, stocker les sessions dans un cache en mémoire (LRU avec TTL court).
   - N'activer la persistance SQLite que si `database.persist_sessions = true` (ou équivalent) est activé dans la configuration.

### Phase 2 : Extraction et Modularisation (Moyen Terme)

1. **Préparation à l'extraction du Log Watcher** :
   - Isoler clairement la logique dans `features/log_watcher/` pour qu'elle puisse être facilement extraite en package séparé (`kimi-log-watcher`).
   
2. **Préparation à l'extraction de la Gestion de Sessions** :
   - Modulariser la logique pour préparer l'extraction vers un service dédié (`kimi-session-service`).
   
3. **Configuration Centralisée** :
   - Assurer que la configuration des serveurs MCP est centralisée dans le fichier de configuration global du middleware.

### Phase 3 : Simplification du Coeur (Long Terme)

1. **MCP Gateway** :
   - Fusionner `mcp_gateway.py` et `mcp_gateway_rpc.py` en un seul fichier propre.
   - Extraire la logique de circuit breaker et retry dans un décorateur ou middleware dédié.
   
2. **Observation Masking** :
   - Fusionner les 3 schémas de masking (`features/observation_masking/`) en un unique module configurable.
   - Simplifier la détection d'erreurs en éliminant les heuristiques redondantes.

## Critères de Validation et Non-Régression
- Tous les tests existants (`./bin/kimi-proxy test`) doivent passer avec succès.
- Aucune régression ne doit être introduite sur les appels de passerelle RPC ou les flux SSE.
- La complexité cognitive des modules modifiés doit rester sous le seuil critique (<= 15 par fonction).
- Logs et diagnostics doivent continuer à être traduits en français conformément aux coding standards.
