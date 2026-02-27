# Changelog - Kimi Proxy Dashboard

Toutes les modifications notables de ce projet seront documentées ici.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère à [Semantic Versioning](https://semver.org/lang/fr/).

## [Unreleased]

### Removed - Nettoyage du Code Hérité MCP
- **Suppression fonctions obsolètes** : Retrait de 3 fonctions développées pour l'intégration MCP Phase 4 mais non utilisées en production
  - `validate_and_fix_tool_calls` - Validation complexe des tool calls MCP (127 LOC)
  - `reconstruct_from_corrupted_arguments` - Reconstruction paramètres MCP corrompus (54 LOC)  
  - `infer_function_name_from_arguments` - Inférence noms de fonctions MCP (58 LOC)
- **Mise à jour tests** : Suppression des tests associés aux fonctions supprimées
- **Raison du nettoyage** : MCP Phase 4 (Task Master, Sequential Thinking, Fast Filesystem, JSON Query) désormais exécutés localement, plus dans le proxy
- **Impact** : Réduction code mort sans perte de fonctionnalité active

## [2.4.1] - 2026-02-19

### Refactored - MCP Client Modularization
- **Refactorisation majeure du client MCP** : Transformation du monolithe `features/mcp/client.py` (1,230 lignes) en architecture modulaire
- Architecture modulaire : 9 fichiers spécialisés (base, servers, client facade)
- **Réduction taille** : 90% de réduction pour le fichier principal (200 lignes max)
- **Compatibilité 100% préservée** : Singleton `get_mcp_client()` et API publique intactes
- **Suite de tests complète** : 169 tests unitaires couvrant tous les serveurs MCP (Qdrant, Compression, Task Master, Sequential Thinking, Fast Filesystem, JSON Query)
- **Correction imports cycliques** : Résolution complète des dépendances circulaires
- **Documentation détaillée** : [Rapport de refactorisation](./docs/development/mcp-refactoring-report.md)

## [2.4.0] - 2026-02-17

### Added - Phase 4: Intégration de 4 Nouveaux Serveurs MCP

#### Task Master MCP (14 outils)
- **Gestion de tâches complète** avec priorisation et dépendances
- Outils disponibles:
  - `get_tasks`, `next_task`, `get_task` - Gestion des tâches
  - `set_task_status`, `update_subtask` - Mise à jour du statut
  - `parse_prd` - Analyse de documents PRD
  - `expand_task`, `expand_all` - Expansion en sous-tâches
  - `initialize_project` - Initialisation de projet
  - `analyze_project_complexity`, `complexity_report` - Analyse de complexité
  - `add_subtask`, `remove_task`, `add_task` - CRUD tâches
- Configuration: `[mcp.task_master]` dans `config.toml` (port 8002)
- Statistiques en temps réel via `/api/memory/task-master/stats`

#### Sequential Thinking MCP (1 outil)
- **Raisonnement séquentiel structuré** pour résolution de problèmes complexes
- Outil `sequentialthinking_tools` avec support de branches et révisions
- Paramètres: pensée actuelle, numéro d'étape, total prévu, besoin de continuation
- Configuration: `[mcp.sequential_thinking]` dans `config.toml` (port 8003)
- Timeout étendu (60s) pour le raisonnement complexe

#### Fast Filesystem MCP (25 outils)
- **Opérations fichiers haute performance** avec API optimisée
- Catégories d'outils:
  - **Lecture**: `fast_read_file`, `fast_read_multiple_files`, `fast_extract_lines`
  - **Écriture**: `fast_write_file`, `fast_large_write_file`
  - **Navigation**: `fast_list_directory`, `fast_get_directory_tree`
  - **Recherche**: `fast_search_files`, `fast_search_code`
  - **Édition**: `edit_file`, `fast_safe_edit`, `fast_edit_multiple_blocks`
  - **Gestion**: `fast_copy_file`, `fast_move_file`, `fast_delete_file`
  - **Batch**: `fast_batch_file_operations`
  - **Compression**: `fast_compress_files`, `fast_extract_archive`
  - **Sync**: `fast_sync_directories`
- Configuration: `[mcp.fast_filesystem]` dans `config.toml` (port 8004)

#### JSON Query MCP (3 outils)
- **Requêtes JSON avancées** avec JSONPath et recherche
- Outils disponibles:
  - `json_query_jsonpath` - Requêtes JSONPath complexes
  - `json_query_search_keys` - Recherche de clés
  - `json_query_search_values` - Recherche de valeurs
- Configuration: `[mcp.json_query]` dans `config.toml` (port 8005)

#### Patterns de Détection MCP
- Nouveaux patterns regex dans `constants.py` pour détection automatique:
  - `mcp_task_master` - Détection des 14 outils Task Master
  - `mcp_sequential_thinking` - Détection du raisonnement séquentiel
  - `mcp_fast_filesystem` - Détection des 25 outils filesystem
  - `mcp_json_query` - Détection des 3 outils JSON Query
- Détecteur étendu dans `MCPDetector` avec méthodes Phase 4

#### Client MCP Étendu
- Extension de `MCPExternalClient` avec 4 nouveaux serveurs:
  - `check_task_master_status()`, `call_task_master_tool()`, `get_task_master_tasks()`
  - `check_sequential_thinking_status()`, `call_sequential_thinking()`
  - `check_fast_filesystem_status()`, `call_fast_filesystem_tool()`
  - `check_json_query_status()`, `call_json_query_tool()`
  - `call_mcp_tool()` - Appel générique d'outil MCP
  - `get_all_phase4_server_statuses()` - Statuts de tous les serveurs Phase 4

#### Modèles de Données Phase 4
- `TaskMasterTask` - Tâche avec métadonnées
- `TaskMasterStats` - Statistiques de projet
- `SequentialThinkingStep` - Étape de raisonnement
- `FileSystemResult` - Résultat d'opération fichier
- `JsonQueryResult` - Résultat de requête JSON
- `MCPToolCall` - Appel d'outil MCP intercepté
- `MCPPhase4ServerStatus` - Statut d'un serveur Phase 4

#### Nouveaux Endpoints API
- `GET /api/memory/servers/phase4` - Statuts des serveurs MCP Phase 4
- `GET /api/memory/task-master/tasks` - Liste des tâches
- `GET /api/memory/task-master/stats` - Statistiques Task Master
- `POST /api/memory/task-master/call` - Appel outil Task Master
- `POST /api/memory/sequential-thinking/call` - Raisonnement séquentiel
- `POST /api/memory/filesystem/call` - Opération Fast Filesystem
- `POST /api/memory/json-query/call` - Requête JSON Query
- `POST /api/memory/tool/call` - Appel générique d'outil MCP
- `GET /api/memory/all-servers` - Tous les serveurs MCP (Phase 3 + Phase 4)

#### Configuration
- Section `[mcp.phase4]` dans `config.toml`:
  - `[mcp.task_master]` - Port 8002, timeout 30s
  - `[mcp.sequential_thinking]` - Port 8003, timeout 60s
  - `[mcp.fast_filesystem]` - Port 8004, timeout 10s
  - `[mcp.json_query]` - Port 8005, timeout 5s
- Activation/désactivation globale via `[mcp.phase4].enabled`
- Auto-détection des serveurs démarrés

### Changed
- Mise à jour de `MCPClientConfig` avec URLs et timeouts des 4 nouveaux serveurs
- Extension de la section MCP dans `AGENTS.md` avec documentation Phase 4

## [2.3.0] - 2026-02-15

### Added - Phase 3: Intégration MCP Avancée

#### Serveurs MCP Externes
- **Qdrant MCP** (`github.com/qdrant/mcp-server-qdrant`)
  - Recherche sémantique en <50ms
  - Détection automatique des redondances (seuil 0.85)
  - Clustering sémantique des mémoires
  - Stockage vectoriel avec embeddings

- **Context Compression MCP** (`github.com/rsakao/context-compression-mcp-server`)
  - Compression avancée 20-80%
  - Algorithmes: `context_aware` et `zlib`
  - Stockage persistant SQLite
  - Fallback automatique si serveur indisponible

#### Client MCP JSON-RPC 2.0
- `MCPExternalClient` avec protocole JSON-RPC 2.0
- Retry automatique avec backoff exponentiel (max 3 tentatives)
- Timeouts configurables par serveur
- Gestion gracieuse des erreurs de connexion

#### Mémoire Standardisée
- Types de mémoire:
  - `frequent` : Patterns et snippets fréquemment utilisés
  - `episodic` : Conversations et événements spécifiques
  - `semantic` : Concepts avec vecteurs Qdrant
- Auto-promotion des patterns fréquents (seuil: 3 accès)
- Recherche similaire sémantique ou fallback textuel
- Nettoyage automatique des mémoires anciennes (>30 jours)

#### Routage Provider Optimisé
- Algorithme de scoring combiné:
  - Capacité contexte restant (40%)
  - Coût relatif (30%)
  - Latence estimée (20%)
  - Marge de sécurité (10%)
- `find_optimal_provider()` : Sélection intelligente basée sur le contexte disponible
- Fallback automatique vers modèles avec plus de contexte si nécessaire
- Historique des décisions dans `mcp_routing_decisions`

#### Nouveaux Endpoints API
- `GET /api/memory/servers` : Statuts des serveurs MCP externes
- `POST /api/memory/similarity` : Recherche sémantique
- `POST /api/memory/compress` : Compression de contenu
- `POST /api/memory/store` : Stockage mémoire standardisée
- `GET /api/memory/frequent` : Mémoires fréquemment utilisées
- `POST /api/memory/cluster/{id}` : Clustering sémantique
- `GET /api/memory/stats/advanced` : Statistiques avancées

#### UI Dashboard Étendu
- Panneau statuts serveurs MCP (indicateurs violet)
- Visualisation des mémoires fréquentes avec métadonnées
- Modale de recherche sémantique
- Modale de compression de contenu
- Indicateurs temps réel de connexion

#### Configuration
- Section `[mcp]` complète dans `config.toml`:
  - `[mcp.qdrant]` : URL, timeouts, seuils de similarité
  - `[mcp.compression]` : Algorithme, ratio cible, min tokens
  - `[mcp.routing]` : Smart routing, marges, facteurs coût/latence

#### Base de données
- Nouvelle table `mcp_memory_entries` avec indexes optimisés
- Nouvelle table `mcp_compression_results` pour logs de compression
- Nouvelle table `mcp_routing_decisions` pour historique de routage

#### Tests
- `tests/test_mcp_phase3.py` : 20+ tests unitaires
- Couverture: Client MCP, Memory Manager, Routage Provider, Modèles de données

### Changed
- Mise à jour de `AGENTS.md` avec documentation Phase 3
- Mise à jour de `README.md` avec description des nouvelles fonctionnalités
- Version passée à 2.3.0

## [2.2.0] - 2026-02-15

### Added - Phase 2: Fonctionnalités Utilisateur - Compaction
- UI Compaction Manuelle avec modal preview
- Preview d'impact tokens avant compaction
- Toggle Auto-Compaction par session avec persistance DB
- Triggers automatiques configurables
- Jauges multi-couches (usage + réservé + seuil)
- Graphique historique des compactions
- Alertes WebSocket temps réel
- Service AutoTrigger avec cooldown

### Added - Gestion Erreurs Streaming Robuste
- Exception `StreamingError` dédiée
- Gestion `httpx.ReadError` pour interruptions de connexion
- Timeouts par provider (Gemini 180s, Groq 60s, etc.)
- Retry avec backoff exponentiel
- Extraction tokens partiels même si stream échoue
- Broadcast WebSocket des erreurs streaming

## [2.1.0] - 2026-02-15

### Added - Phase 1: Context Compaction Infrastructure
- Service `SimpleCompaction` inspiré de Kimi CLI
- Extensions DB: colonnes `reserved_tokens`, `compaction_count`
- Table `compaction_history` pour historique des compactions
- API Endpoints `/api/compaction/*`
- WebSocket Events pour compaction temps réel

### Changed - Architecture Restructuring
- Modularisation complète: 52 fichiers Python extraits du monolithe
- Architecture propre: Core/Features/Services/API
- Nouveau CLI unifié: `./bin/kimi-proxy`
- Structure de tests: Unit/Integration/E2E

### Changed - Frontend Modularization
- Migration vers ES6 Modules (9 modules)
- Pattern Event Bus pour communication découplée
- DOM Cache pour optimisations performances

## [2.0.0] - 2026-02-14

### Added - Phase 2: MCP Memory
- Détection balises MCP (`<mcp-memory>`, `@memory[]`, `@recall()`)
- Analyseur de mémoire dans les messages
- Stockage métriques mémoire (`memory_tokens`, `memory_ratio`)
- Table `memory_metrics` et `memory_segments`

### Added - Phase 1: Sanitizer
- Masquage automatique contenus verbeux (>1000 tokens)
- Tags déclencheurs: `@file`, `@codebase`, `@tool`, `@console`
- Stockage `masked_content` avec hash unique
- Routing fallback vers modèles "Heavy Duty"

## [1.0.0] - 2026-02-13

### Added - Version Initiale
- Proxy transparent FastAPI + SQLite
- Comptage tokens avec Tiktoken
- Dashboard temps réel avec WebSocket
- Support 8 providers (Kimi, NVIDIA, Mistral, OpenRouter, SiliconFlow, Groq, Cerebras, Gemini)
- Streaming SSE et non-streaming
- Log Watcher PyCharm avec parsing CompileChat
- Export CSV/JSON

---

## Guide de migration

### De 2.2.0 à 2.3.0
Aucune action requise. Les nouvelles tables MCP sont créées automatiquement au démarrage.

### De 2.1.0 à 2.2.0
Exécuter `scripts/migrate_compaction.sh` pour les migrations de compaction.

### De 2.0.0 à 2.1.0
Les tables MCP Phase 2 sont créées automatiquement.

### De 1.0.0 à 2.0.0
Refactorisation majeure - suivre `docs/development/plan-restructuration-scripts.md`
