# 📚 Documentation Kimi Proxy Dashboard

**TL;DR**: C'est ici que j'ai documenté tout ce que j'ai appris en construisant un proxy LLM qui me fait économiser 20-40% de tokens. Pas de jargon, juste les vrais problèmes et solutions.

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

### ⚡ [Fonctionnalités](./features/) - Les Superpouvoirs
Les 3 phases qui me sauvent la vie quand mon contexte explose.

- **[Support Multi-Provider](./features/multi-provider-support.md)** - L'Orchestre LLM
  - Comment j'ai connecté 8 providers et 20+ modèles
  - Mon workflow quotidien (matin: Kimi Code, après-midi: NVIDIA, soir: Mistral)
  - Les vrais économies que j'ai réalisées

- **[Gestion Active du Contexte](./features/active-context-manager-plan.md)** - Mon Système de Survie
  - Le crash qui m'a tout fait changer
  - Les 3 phases : Sanitizer, MCP, Compression
  - Les économies mesurées : 38% de réduction des coûts

### 🛠️ [Développement](./development/) - Le Journal de Bord
Mon histoire de développement, avec les vrais problèmes et solutions.

- **[Journal de Développement](./development/README.md)**
  - Pourquoi je documente tout
  - Mon approche "Build, Measure, Learn"
  - Les leçons apprises

- **[Session 2026-02-15](./development/sessions/2026-02-15-modular-restructure.md)** ⭐ **La transformation majeure**
  - Le matin du drame : pourquoi j'ai tout démantelé
  - Les 10 phases de migration avec heures et défis réels
  - Comment j'ai surmonté les imports circulaires et autres pièges

- **[Migration v1.0 vers v2.0](./development/migration-v2.md)**
  - Le grand déménagement : du studio 10m² à la maison organisée
  - Instructions étape par étape pour faire pareil

- **[Rapport Refactorisation MCP](./development/mcp-refactoring-report.md)** ⭐ **Nouveau**
  - Transformation monolithe 1,230 lignes → 9 modules + 169 tests
  - Réduction 90% taille fichier, compatibilité 100% préservée
  - Les défis techniques et solutions de la refactorisation majeure

### 🚀 [Déploiement](./deployment/) - Installation et Utilisation
Comment installer et utiliser le système en 5 minutes.

- **[Guide d'Installation](./deployment/README.md)**
  - Installation en 5 minutes, pas de jargon
  - Configuration Continue.dev pour PyCharm/VS Code
  - Les vrais problèmes que j'ai rencontrés et leurs solutions

## Comment naviguer intelligemment

### Si tu veux comprendre le système
Commence par **Architecture Modulaire v2.0**. C'est le cœur de tout.

### Si tu veux économiser des tokens
Va directement à **Support Multi-Provider** et **Gestion Active du Contexte**.

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
- **[Sessions de développement](./development/sessions/)**
  - **[Session 2026-02-20 : Auto-Session Mistral Large 2411](./development/sessions/2026-02-20-auto-session-mistral.md)** ⭐ **Nouveau**
  - Création automatique de sessions par modèle (au lieu de par provider)
  - Mapping dynamique des providers basé sur les préfixes de modèles
  - Expansion automatique des variables d'environnement
  - [2026-02-20 : WebSocket Memory Operations Infrastructure](./development/sessions/2026-02-20-websocket-memory-ops.md) ⭐ **Nouveau**
  - [2026-02-20 : Modal Display Bug Fix](./development/sessions/2026-02-20-modal-display-fix.md) ⭐ **Nouveau**
    - Dropdown de sélection des sessions dans l'UI mémoire
    - Possibilité de suppression des sessions avec VACUUM automatique
    - Gestion complète des modales (ouverture/fermeture, événements)
  - [2026-02-15 : Restructuration architecture modulaire](./development/sessions/2026-02-15-modular-restructure.md)
  - [2026-02-11 : Implémentation multi-provider](./development/sessions/2026-02-11-multi-provider-implementation.md)
  - [2026-02-14 : Correction routing modèles](./development/sessions/2026-02-14-model-routing-fix.md)
  - [2026-02-14 : Corrections multi-provider](./development/sessions/2026-02-14-multi-provider-fixes.md)

- **[Guides techniques](./development/guides/)**
  - [Gestion fenêtre contexte Continue IDE](./development/guides/continue-ide-context-management.md)
  - [Guide création système gestion contexte](./development/guides/context-window-management-guide.md)
  - [Top 6 techniques gestion contexte](./development/guides/top-6-context-management-techniques.md)
  - [Analyse enrichissement dashboard](./development/guides/dashboard-enhancement-analysis.md)

- **[Migration](./development/)**
  - [Migration v1.0 vers v2.0](./development/migration-v2.md) ⭐ **Nouveau**
  - [Plan de restructuration](./development/plan-restructuration-scripts.md)

### 🚀 Déploiement
- [Installation](./deployment/installation.md)
- [Configuration](./deployment/configuration.md)
- [Utilisation](./deployment/usage.md)

## 🔗 Liens Rapides

- [**README principal**](../README.md) - Vue d'ensemble du projet
- [**Guide agents IA**](../AGENTS.md) - Référence développeur IA
- [**CLI**](../bin/kimi-proxy) - Commandes de gestion (v2.0)

## 📋 État du Projet

### ✅ v2.0 - Architecture Modulaire (2026-02-15)
- **Restructuration complète** : 52 fichiers modulaires
- **Nouvelle CLI** : `./bin/kimi-proxy` avec sous-commandes
- **Tests structurés** : Unit, integration, E2E
- **Setup script** : Installation via `pip install -e .`

### ✅ Fonctionnalités
- **Multi-provider** : 8 providers, 20+ modèles supportés
- **Sanitizer Phase 1** : Masking automatique contenus verbeux
- **MCP Phase 2** : Intégration mémoire standardisée
- **Compression Phase 3** : Bouton d'urgence compression
- **MCP Phase 4** : 4 serveurs MCP (Task Master, Sequential Thinking, Fast Filesystem, JSON Query) - **Exécution locale dans Continue.dev**
- **Monitoring temps réel** : WebSockets, Log Watcher, dashboard
- **Persistance** : SQLite avec historique complet

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

*Dernière mise à jour : 2026-02-21*
*Version: 2.0.2*
