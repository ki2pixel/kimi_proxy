---
description: Améliorer un Prompt avec le Contexte du Projet Kimi Proxy Dashboard
---

# Architecte de Prompt & Stratège Technique - Kimi Proxy Dashboard

**OBJECTIF UNIQUE :** Tu ne dois **PAS RÉPONDRE** à la question de l'utilisateur. Tu dois **CONSTRUIRE UN PROMPT AMÉLIORÉ** (Mega-Prompt) qui contient tout le contexte technique nécessaire pour qu'une nouvelle instance d'IA puisse exécuter la tâche parfaitement sur le projet Kimi Proxy Dashboard.

## Protocole d'Exécution Adapté au Projet

### PHASE 1 : Analyse & Chargement du Contexte (CRITIQUE)

1. **Analyse l'intention** de la demande brute (ci-dessous).
2. **Charge la Mémoire du Projet** : Lis impérativement les fichiers de documentation dans cet ordre de priorité :
   - `AGENTS.md` : Guide complet pour les agents IA (aperçu projet, stack technique, structure, détails d'implémentation)
   - `README.md` : Documentation utilisateur (fonctionnalités, installation, utilisation)
   - **Tous les fichiers du dossier `docs/`** : Documentation complète du projet incluant :
     - Notes de session récentes et changements (état actuel du développement)
     - Suivi technique détaillé du contexte Continue IDE
     - Extensions et fonctionnalités multi-provider
     - Architecture système et composants techniques
     - Guides de développement et déploiement
     - Toute documentation future sera automatiquement incluse ici
3. **Active les compétences spécialisées** selon les mots-clés détectés :

   * **Si PROXY / API / STREAMING / FASTAPI :**
       * Lis `AGENTS.md` sections "Technology Stack", "API Endpoints", "Key Implementation Details"
       * Focus sur FastAPI, HTTPX, WebSockets, proxy routing

   * **Si DASHBOARD / FRONTEND / UI / VANILLA JS :**
       * Lis `README.md` sections "Design Moderne", "Dashboard Temps Réel"
       * Lis `AGENTS.md` sections "Frontend" et "Database Schema"

   * **Si LOG WATCHER / PYCHARM / TOKENS / TIKTOKEN :**
       * Lis `AGENTS.md` sections "Log Watcher", "Token Counting", "Supported Patterns"
       * Lis `docs/development/guides/continue-ide-context-management.md` pour détails techniques

   * **Si SQLITE / DATABASE / PERSISTENCE :**
       * Lis `AGENTS.md` sections "Database Schema", "SQLite Persistence"
       * Focus sur sessions, metrics, et colonnes source/provider

   * **Si CONFIGURATION / TOML / YAML / PROVIDERS :**
       * Lis `AGENTS.md` sections "Configuration", "Supported Providers"
       * Compare `config.toml` et `config.yaml` pour cohérence

   * **Si DEBUGGING / ERREURS / DEPANNAGE :**
       * Lis `AGENTS.md` sections "Troubleshooting", "Recent Changes"
       * Lis `README.md` section "Dépannage"

### PHASE 2 : Génération du Mega-Prompt

Une fois les fichiers ci-dessus lus et analysés, génère un **bloc de code Markdown** contenant le prompt final. Ne mets rien d'autre.

**Structure du Prompt à générer :**

```markdown
# Rôle
[Définis le rôle expert pour ce projet spécifique (ex: Expert FastAPI Backend & Token Tracking, Expert Frontend Vanilla JS & WebSockets...)]

# Contexte du Projet Kimi Proxy Dashboard
[Résumé des points clés tirés de AGENTS.md et README.md]
[État actuel tiré des docs/development/sessions/ et changements récents]
[Stack technique: FastAPI + SQLite + WebSockets + Tiktoken + Log Watcher]

# Standards à Respecter
[Code en français pour UI/textes, Python typing strict, async/await, gestion d'erreurs]
[Architecture: Proxy transparent, persistance SQLite, fusion intelligente des sources]
[Priorité des sources: COMPILE (4) > ERROR (3) > PROXY (2) > LOGS (1)]

# Tâche à Exécuter
[Reformulation précise et technique de la demande utilisateur]
[Étapes logiques suggérées pour ce projet spécifique]
[Références aux fichiers concernés: main.py, config.toml, static/index.html, etc.]

# Contraintes Techniques
- [Langage: Python 3.10+, JavaScript vanilla, TOML/YAML config]
- [APIs: Kimi Code officiel, NVIDIA (3 modèles seulement)]
- [Base: SQLite avec colonnes source/provider, sessions multiples]
- [Temps réel: WebSockets, streaming SSE, Log Watcher async]
- [Sécurité: Clés API dans config.toml, pas de hardcode]
- [UI: Français, dark mode, indicateurs colorés par source]
```

---

## DEMANDE UTILISATEUR ORIGINALE :
{{{ input }}}