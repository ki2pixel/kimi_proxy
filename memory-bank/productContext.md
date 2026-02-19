# Contexte Produit : Kimi Proxy Dashboard

## Objectif du Produit
Le projet est un proxy transparent FastAPI + SQLite qui intercepte les requêtes LLM, compte précisément les tokens avec Tiktoken, et optimise la consommation via sanitizer/compression. Le système offre une visibilité temps réel sur les coûts API et économise 20-40% de tokens sans perte d'information.

## Architecture Générale
Le système suit une **architecture modulaire en 5 couches** avec séparation stricte des responsabilités et dépendances unidirectionnelles.

### Note de version (v2.5) — Février 2026
- **Architecture 5 couches** : API (FastAPI) ← Services (WebSocket) ← Features (MCP/Sanitizer) ← Proxy (HTTPX) ← Core (SQLite/Tokens)
- **MCP Phase 4** : 4 serveurs MCP intégrés (Task Master, Sequential Thinking, Fast Filesystem, JSON Query) - 43 outils fonctionnels
- **Smart Routing** : Sélection automatique provider basée sur capacité contexte/coût/latence
- **Streaming Robuste** : Gestion gracieuse des erreurs réseau (ReadError, Timeout) avec retry et extraction tokens partiels
- **Frontend Modulaire** : JavaScript vanilla ES6 avec architecture découplée (modules utils/api/charts/sessions/websocket/ui/modals)

### Pipeline de Traitement
Le cœur du système est un pipeline proxy transparent en plusieurs phases :

1.  **Interception Proxy** : Capture des requêtes `/chat/completions` et `/models` avec injection transparente des clés API
2.  **Comptage Tokens** : Tiktoken cl100k_base pour comptage précis input/output avec métriques cumulatives
3.  **Sanitizer Phase 1** : Masquage automatique des messages tools/console verbeux (>1000 tokens) avec récupération possible
4.  **MCP Phase 2** : Détection balises `<mcp-memory>`, `@memory[]`, `@recall()` pour mémoire standardisée
5.  **MCP Phase 3** : Intégration serveurs externes (Qdrant recherche sémantique <50ms, Context Compression)
6.  **Compression Phase 3** : Compression intelligente préservant messages système et 5 derniers échanges
7.  **MCP Phase 4** : Écosystème étendu avec 4 serveurs spécialisés (Task Management, Sequential Thinking, File Operations, JSON Query)

### Intégrations Clés
-   **Multi-Provider** : 8 providers supportés (Kimi Code, NVIDIA, Mistral, OpenRouter, SiliconFlow, Groq, Cerebras, Gemini)
-   **Continue.dev/PyCharm** : Log Watcher temps réel avec parsing CompileChat blocks et priorité de fusion
-   **WebSockets** : Broadcasting temps réel des métriques et mises à jour sans refresh
-   **SQLite Persistence** : Sessions multiples avec historique complet, métriques détaillées, et export CSV/JSON

### Interface Utilisateur
Le dashboard (vanilla JS + TailwindCSS) offre :
-   **Jauge Contexte** : Indicateur visuel temps réel (Vert → Jaune → Rouge) avec alertes seuils
-   **Graphiques Interactifs** : Chart.js pour historique tokens, distribution par source, et métriques avancées
-   **Gestion Sessions** : Création/sélection sessions avec choix provider/modèle granulaire
-   **Contrôles MCP** : Interface complète pour serveurs MCP Phase 3/4 avec statuts temps réel
-   **Export Données** : CSV et JSON pour analyse coûts et tendances consommation

### Gestion des Providers
-   **Configuration Centralisée** : TOML/YAML avec support variables environnement (.env)
-   **Injection Automatique** : Clés API injectées transparentement avec mise à jour headers Host
-   **Timeouts Spécifiques** : Configuration par provider (Gemini 180s, Kimi 120s, NVIDIA 150s, etc.)
-   **Retry Intelligent** : Gestion automatique des erreurs réseau avec backoff exponentiel

### Nouvelles Fonctionnalités Ajoutées
-   **Task Master MCP** : Gestion complète de tâches avec analyse PRD, expansion automatique, et suivi complexité
-   **Sequential Thinking MCP** : Raisonnement structuré étape par étape avec support branches et révisions
-   **Fast Filesystem MCP** : Opérations fichiers haute performance (25 outils) avec isolation workspace sécurisée
-   **JSON Query MCP** : Requêtes JSON avancées avec JSONPath pour fichiers configuration complexes
-   **Smart Routing** : Algorithme optimisé pour sélection provider basé sur contexte requis, coût, et latence
-   **Memory Standardization** : Types frequent/episodic/semantic avec auto-promotion patterns et clustering sémantique