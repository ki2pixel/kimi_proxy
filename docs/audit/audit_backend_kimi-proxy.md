## Analyse des Composants Obsolètes ou Optionnels

### 1. Composants à Extraire ou Déprécier

#### 1.1. Gestion de Sessions (core/database.py, core/auto_session.py)
- **Problème :** Le middleware devrait être "session-less" (stateless). La persistance des sessions dans SQLite et la logique d'auto-session introduisent un état interne qui contredit l'architecture radicale.
- **Impact :** Complexité inutile, dépendance à SQLite, risque de fuites mémoire si les sessions ne sont pas nettoyées.
- **Recommandation :** 
  - Déplacer toute la logique de persistance des sessions dans un service séparé (ex: `kimi-session-service`).
  - Dans le middleware, ne garder qu'un cache en mémoire (LRU) pour les sessions actives, avec un TTL court.
  - Rendre la persistance optionnelle via une configuration explicite.

#### 1.2. Log Watcher (features/log_watcher/)
- **Problème :** C'est un service lourd (thread, file system watching, WebSocket push) qui est démarré au lancement de l'application. Pour un middleware, c'est un service auxiliaire, pas un composant core.
- **Impact :** Consommation de ressources (thread, watcher inotify), complexité de cycle de vie dans `main.py`.
- **Recommandation :** 
  - Extraire dans un micro-service indépendant (`kimi-log-watcher`).
  - Communiquer via un message broker léger (Redis Pub/Sub, NATS) ou via le WebSocket Manager existant.
  - Le middleware peut optionnellement se connecter à ce service si configuré.

#### 1.3. MCP Pruning (features/mcp/pruner/)
- **Problème :** Le "pruning" d'outils et de contexte est une fonctionnalité avancée qui ajoute une latence et une complexité significatives. Pour un middleware, c'est un "plugin" optionnel, pas un composant core.
- **Impact :** Complexité cognitive élevée dans `mcp_gateway.py`, dépendances à des serveurs MCP externes (Qdrant, Compression).
- **Recommandation :** 
  - Rendre le pruning désactivable via configuration (déjà partiellement fait avec `MCPToolPruningConfig`).
  - Par défaut, le désactiver complètement pour un fonctionnement "middleware pur".
  - N'activer que si explicitement configuré par l'utilisateur.

### 2. Composants à Consolider

#### 2.1. Observation Masking (features/observation_masking/)
- **Problème :** Plusieurs schémas de masking (schema1, schema2, schema3) avec des heuristiques différentes. C'est redondant et peut mener à des comportements incohérents.
- **Recommandation :** 
  - Fusionner en un seul module avec des règles configurables.
  - Simplifier la détection d'erreur (remplacer l'heuristique de mots-clés par une approche plus robuste).

#### 2.2. MCP Gateway (features/mcp/gateway/)
- **Problème :** Le gateway est divisé entre `mcp_gateway.py` (logique métier) et `mcp_gateway_rpc.py` (logique RPC). La frontière est floue, ce qui augmente la complexité.
- **Recommandation :** 
  - Fusionner les deux fichiers en un seul module cohérent.
  - Extraire la logique de circuit breaker et de retry dans un décorateur ou un middleware séparé.

### 3. Plan de Migration Recommandé

#### Phase 1: Désactivation et Isolation (Court Terme)
1. **Désactiver le Log Watcher par défaut** : rendre son démarrage optionnel via une variable d'environnement (`LOG_WATCHER_ENABLED=false`).
2. **Désactiver le MCP Pruning par défaut** : mettre `enabled = false` dans la configuration par défaut.
3. **Rendre la persistance des sessions optionnelle** : utiliser un cache mémoire par défaut, SQLite uniquement si configuré.

#### Phase 2: Extraction et Modularisation (Moyen Terme)
1. **Extraire le Log Watcher** : créer un package séparé avec son propre `main.py` et sa propre configuration.
2. **Extraire la gestion de sessions** : créer un service REST/WebSocket dédié.
3. **Centraliser la configuration des serveurs MCP** : un seul fichier de configuration pour tous les serveurs.

#### Phase 3: Simplification du Coeur (Long Terme)
1. **Fusionner les modules MCP Gateway** : un seul fichier, une seule responsabilité.
2. **Simplifier l'Observation Masking** : un seul schéma, des règles configurables.
3. **Nettoyer les dépendances** : retirer les imports inutiles et les fonctions obsolètes.

### 4. Résumé des Actions

| Composant | Statut Actuel | Action Recommandée | Priorité |
|---|---|---|---|
| Log Watcher | Core (démarré au lancement) | Extraire en service indépendant | Haute |
| Gestion de Sessions | Core (SQLite) | Rendre optionnelle, cache mémoire par défaut | Haute |
| MCP Pruning | Core (activé par défaut) | Désactiver par défaut, plugin optionnel | Moyenne |
| Observation Masking | Core (3 schémas) | Fusionner en 1 module configurable | Basse |
| MCP Gateway | 2 fichiers (flou) | Fusionner en 1 module | Basse |

**Conclusion :** L'objectif est de transformer Kimi Proxy en un **middleware véritablement minimal et performant**, où les fonctionnalités avancées deviennent des plugins optionnels ou des services externes. Cela améliorera la maintenabilité, les performances et la clarté architecturale. La priorité immédiate est de désactiver et d'isoler le Log Watcher et la persistance des sessions, qui sont les plus lourds et les plus contradictoires avec la vision "middleware pur".
