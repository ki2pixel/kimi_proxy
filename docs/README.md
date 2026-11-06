# 📚 Documentation Kimi Proxy MCP (anciennement Dashboard)

**TL;DR**: Proxy LLM orienté MCP-first qui fait économiser 20-40% de tokens. Le frontend Dashboard est **déprécié** — le flux de travail passe désormais exclusivement par les serveurs MCP et l'API REST.

> **⚠️ Dépréciation du Frontend** (2026-05-12)
> Le frontend Dashboard (HTML/CSS/JS, Chart.js, sessions visuelles) est déprécié. L'utilisation quotidienne passe par Cline et `scripts/start-mcp-servers.sh`. L'API FastAPI (`/api/*`, `/api/mcp-gateway/*`) et les features MCP restent pleinement opérationnelles.

## L'histoire derrière cette documentation

### Pourquoi j'écris tout ça
Après 3 mois de développement intensif, j'ai réalisé que j'oubliais pourquoi j'avais pris certaines décisions. "Pourquoi est-ce que j'ai utilisé Tiktoken et pas une autre librairie?" "Pourquoi cette architecture en 5 couches?"

Sans documentation, chaque décision devient une boîte noire. Avec la documentation, je peux retracer mon raisonnement.

### L'honnêteté avant tout
Je ne vais pas te raconter que tout était parfait. Il y a eu des dead ends, des refactors complets, des nuits blanches de debugging. Documenter les échecs est aussi important que documenter les succès.

## Ce que tu trouveras ici

### 🏛️ [Architecture](./architecture/) - Les Fondations Techniques
Comment j'ai transformé un monolithe de 3,073 lignes en une maison modulaire de 52 pièces.

- **[Architecture Modulaire v2.0](./architecture/modular-architecture-v2.md)** ⭐ **Le cœur du système**
  - Pourquoi j'ai tout démantelé
  - Les 5 étages de la maison (API/Services/Features/Proxy/Core)
  - Mes patterns préférés et les défis que j'ai surmontés

- **[Vue d'ensemble](./architecture/README.md)**
  - L'analogie de la maison expliquée
  - Les règles de dépendances
  - Pour qui cette documentation

### ⚡ [Fonctionnalités](./features/) - Optimisation du contexte
Les features qui réduisent le contexte avant l'envoi au provider.

- **[Passthrough MCP](./proxy/passthrough.md)** - Route `/v1/chat/completions`
  - `X-Target-Base-URL` + `Authorization` provider
  - Tool fixing, observation masking, context pruning
- **[MCP Pruner](./features/mcp-pruner.md)** - Élagage récupérable
- **[Mémoire MCP](./features/mcp.md)** - SQLite + Qdrant
- **[Log Watcher](./features/log-watcher.md)** - Lecture des logs Continue/Kimi

### 🛠️ [Développement](./development/) - Le Journal de Bord
Mon histoire de développement, avec les vrais problèmes et solutions.

- **[Journal de Développement](./development/README.md)**
  - Pourquoi je documente tout
  - Mon approche "Build, Measure, Learn"
  - Les leçons apprises

- **[Migration v1.0 vers v2.0](./development/migration-v2.md)**
  - Le grand déménagement : du studio 10m² à la maison organisée
  - Instructions étape par étape pour faire pareil

### 🚀 [Déploiement](./deployment/) - Installation et Utilisation
Comment installer et utiliser le système en 5 minutes.

- **[Guide d'Installation](./deployment/README.md)**
  - Installation en 5 minutes, pas de jargon
  - Configuration Continue.dev pour PyCharm/VS Code
  - Les vrais problèmes que j'ai rencontrés et leurs solutions

### 🔧 [Dépannage](./troubleshooting/) - Résoudre les Problèmes
Les solutions aux problèmes courants rencontrés.

- **[Bridge MCP stdio](./troubleshooting/MCP_Bridge_Stdio_Servers.md)** - Configuration serveurs MCP locaux avec filtrage JSON-RPC
- **[Interop IDE MCP](./troubleshooting/MCP_IDE_Interop.md)** ⭐ **Nouveau** - Configuration MCP dans Windsurf, Cline, Continue.dev avec shim roots/list
- **[MCP Bridge stdio Serveurs](./troubleshooting/MCP_Bridge_Stdio_Servers.md)** - Configuration détaillée bridge stdio
- **[Task Master Persistence Containment](./troubleshooting/TASK_MASTER_PERSISTENCE_CONTAINMENT.md)** - Containment persistance tâches MCP

### 🏛️ [Core](./core/) - Logique Fondamentale
Les fondations techniques du système.

- **[Architecture Core](./core/README.md)** - Database SQLite, tokens Tiktoken, structures typées

### 🔌 [API](./api/) - Routes et Endpoints
L'interface REST du middleware.

- **[Documentation API](./api/README.md)** - Surface OpenAI-compatible et gateway MCP

### 🌐 [Proxy](./proxy/) - Passthrough vers APIs LLM
Le cœur du proxy session-less.

- **[Passthrough MCP Session-less](./proxy/passthrough.md)** - Route `/v1/chat/completions` avec features MCP
- **[Tool Validation](./proxy/tool-validation.md)** - Validation outils proxy

## Comment naviguer intelligemment

### Si tu veux comprendre le système
Commence par **Architecture Modulaire v2.0**. C'est le cœur de tout.

### Si tu veux économiser des tokens
Va directement à **Passthrough MCP** et **Gestion Active du Contexte**.

### Si tu veux installer et utiliser
Le **Guide de Déploiement** te donne tout ce qu'il faut.

### Si tu veux apprendre de mes erreurs
Le **Journal de Développement** est plein de leçons apprises.

## Pour qui cette documentation?

### Pour moi-même dans 6 mois
Quand j'oublierai pourquoi j'ai fait certains choix, ces docs me rafraîchiront la mémoire.

### Pour les contributeurs
Si quelqu'un veut contribuer, il comprendra la philosophie derrière les décisions techniques.

### Pour les curieux techniques
Ceux qui veulent voir comment un projet évolue dans la vraie vie, avec ses hauts et ses bas.

### Pour les apprenants
Si tu veux apprendre l'architecture logicielle pratique, c'est mieux qu'un tutoriel théorique.

## La Règle d'Or : Documenter le Pourquoi, pas le Quoi

**Le principe** : Le code explique ce que fait le système. La documentation explique pourquoi il le fait.

Je ne documente pas chaque fonction. Je documente les décisions importantes, les trade-offs, les leçons apprises.

---

*Navigation : [← Retour au projet](../README.md) | [Architecture →](./architecture/)*

### 🛠️ Développement
- **[Guide agent](./development/agent-coding-guide.md)** — conventions actuelles pour les agents IA.
- **[Journal historique](./development/migration-v2.md)** — document de migration v1 → v2, conservé comme archive.
- **Sessions de développement** : les anciens journaux de session décrivaient l'architecture sessions/WebSocket et ont été retirés avec les fonctionnalités correspondantes.

- **[Guides techniques](./development/guides/)**
  - [Gestion fenêtre contexte Continue IDE](./development/guides/continue-ide-context-management.md)
  - [Guide création système gestion contexte](./development/guides/context-window-management-guide.md)
  - [Top 6 techniques gestion contexte](./development/guides/top-6-context-management-techniques.md)

- **[Migration](./development/)**
  - [Migration v1.0 vers v2.0](./development/migration-v2.md) ⭐ **Nouveau**

### 🚀 Déploiement
- [Installation](./deployment/installation.md)
- [Configuration](./deployment/configuration.md)
- [Utilisation](./deployment/usage.md)

## 🔗 Liens Rapides

- [**README principal**](../README.md) - Vue d'ensemble du projet
- [**Guide agents IA**](../AGENT.md) - Configuration de l'agent et prompt système
- [**CLI**](../bin/kimi-proxy) - Commandes de gestion (v2.0)

## 📋 État du Projet

### ✅ État actuel (2026-11-06)
- **63 fichiers Python de production**, 11 457 LOC.
- **35 fichiers de tests**, 4 532 LOC.
- **19 routes applicatives** : health, modèles, passthrough, gateway MCP, mémoire, sanitizer.
- **2 tables SQLite** : `masked_content`, `mcp_memory_entries`.
- **CLI** : `./bin/kimi-proxy` (`start`, `stop`, `restart`, `status`, `logs`, `test`, `shell`).
- **Tests** : `./bin/kimi-proxy test` propage désormais les arguments à pytest.

> Les métriques et fonctionnalités des sections historiques ci-dessous peuvent décrire l'ancienne architecture (sessions, compaction, compression, dashboard). Voir `docs/audit/audit-code-mort-2026-11-06.md`.

### ✅ Fonctionnalités
- **Passthrough session-less** : `/v1/chat/completions` avec `X-Target-Base-URL` et `Authorization`.
- **MCP Gateway** : forwarding JSON-RPC vers `context-compression`, `sequential-thinking`, `fast-filesystem`, `json-query`, `pruner`.
- **Mémoire MCP** : stockage SQLite `mcp_memory_entries`, recherche Qdrant, compression contextuelle.
- **Observation masking** : réduction des vieux tool results (flag désactivé par défaut).
- **Context pruning** : élagage via MCP Pruner (flag désactivé par défaut).
- **MCP Tool Pruning** : élagage des réponses `tools/call` (flag désactivé par défaut).
- **Log Watcher** : lecture des logs Continue/Kimi (désactivé par défaut).
- **Streaming SSE** : `StreamingResponse` exclusivement, aucun WebSocket.
- **Persistance** : SQLite minimale (`masked_content`, `mcp_memory_entries`), mémoire par défaut.

> Les routes sessions, compaction, compression, providers, export et WebSocket ont été supprimées le 2026-11-06. Voir `docs/audit/audit-code-mort-2026-11-06.md`.

## 🆕 Nouveautés v2.0

### Architecture
- Modularisation complète du codebase
- Séparation Core/Features/Services/API
- Injection de dépendances
- Typage strict

### CLI
```bash
./bin/kimi-proxy start      # Démarrer
./bin/kimi-proxy stop       # Arrêter
./bin/kimi-proxy restart    # Redémarrer
./bin/kimi-proxy status     # Statut
./bin/kimi-proxy logs       # Logs
./bin/kimi-proxy test       # Tests
./bin/kimi-proxy shell      # Shell Python
```

### Tests
```bash
PYTHONPATH=src python -m pytest tests/ -v
```

## 🤝 Contribution

Voir [Contributing](./development/contributing.md) pour les guidelines de contribution.

---

*Dernière mise à jour : 2026-06-04*
*Version: 2.0.5*
