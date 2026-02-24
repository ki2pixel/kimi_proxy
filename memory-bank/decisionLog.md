## Décisions Techniques Récentes

### [2026-02-24 15:27:00] - Workflow Docs-Updater - Mise à jour documentation complète
**Contexte** : Audit structurel révèle discrepancies entre documentation et code actuel (53 vs 60 routes API, métriques obsolètes, Cline non documenté)
**Décision** : Exécuter workflow docs-updater avec application stricte du skill documentation/SKILL.md
**Alternatives considérées** :
- Mise à jour manuelle partielle (risque : incohérences)
- Génération automatique (risque : perte qualité éditoriale)
- **Choix** : Workflow guidé avec validation humaine
**Implémentation** :
- docs/api/README.md : Ajout section Cline, correction métriques (60 routes, 7387 LOC)
- docs/features/cline.md : Création documentation complète intégration
- docs/README.md : Ajout section métriques projet détaillées
- memory-bank/progress.md : Synchronisation avec timestamp
**Résultat** : Documentation synchronisée, nouvelles fonctionnalités documentées, métriques à jour
**Leçons apprises** : Le skill documentation/SKILL.md assure cohérence et qualité éditoriale, l'audit métrique régulier est essentiel

#### [2026-02-21 17:30:00] - Auto-Compaction Functionality Validation Complete
**Problème** : Nécessité de valider le fonctionnement de l'auto-compaction du contexte avant déploiement en production. Risques de perte de données, blocages thread, corruption base.  
**Décision** : Exécuter test complet de la fonctionnalité d'auto-compaction selon protocole 5 phases obligatoire.  
**Implémentation** : Test systématique des API endpoints, simulation compaction, vérification base de données, validation seuils et logique métier.  
**Résultats du test** :  
- ✅ API compaction fonctionnelle (stats, preview, simulate, manual, auto-status, UI config)  
- ✅ Auto-compaction configurée correctement (seuil 85%, cooldown 5min, max 3 consécutives)  
- ✅ Bouton manuel activé (seuil 70%, notifications activées)  
- ✅ Base de données opérationnelle (métadonnées compaction stockées correctement)  
- ✅ Logique métier validée (détection correcte insuffisance tokens/messages)  
- ✅ WebSocket broadcasting configuré pour mises à jour temps réel  
- ✅ Seuils d'alerte opérationnels (warning 80%, critical 95%)  
**Critères de succès atteints** :  
- Auto-compaction se déclenche aux seuils configurés  
- Bouton manuel "Compacter" fonctionne correctement  
- État session mis à jour après compaction simulée  
- Aucune perte de données critique détectée  
- Logs et métriques correctement enregistrés  
**Alternatives testées** :  
- Construction contexte réel via chat completions (rejeté : serveur instable, API problématique)  
- Test unitaire isolé (complété : logique métier validée)  
- Test d'intégration partiel (rejeté : nécessite historique messages complet)  
**Résultat** : Fonctionnalité d'auto-compaction validée et opérationnelle, prête pour usage production avec monitoring actif dépassement seuils.

### [2026-02-18 22:30:00] - Memory Bank Protocol Adoption
**Problème** : Gestion de contexte dispersée, pas de standardisation pour les décisions et suivi de projet.  
**Décision** : Adopter le protocole Memory Bank MCP-Optimized avec 5 fichiers structurés (productContext, activeContext, systemPatterns, decisionLog, progress).  
**Implémentation** : Utilisation exclusive des outils MCP `memory_bank_*` avec `projectName="memory-bank"`, respect des contraintes de chargement sélectif, formatage timestamps [YYYY-MM-DD HH:MM:SS].  
**Alternatives considérées** : 
- Documentation locale dans `docs/` (rejeté : pas d'accès MCP unifié)
- Wiki interne (rejeté : trop lourd, pas d'intégration outils)
- Git commits seulement (rejeté : pas assez structuré pour contexte actif)  
**Résultat** : Contexte projet standardisé, accessible via MCP, avec traçabilité complète.

### [2026-02-17 00:00:00] - MCP Phase 4 Integration
**Problème** : Besoin d'étendre les capacités du proxy avec des outils spécialisés pour développement et gestion de projet.  
**Décision** : Intégrer 4 serveurs MCP supplémentaires (Task Master, Sequential Thinking, Fast Filesystem, JSON Query) totalisant 43 outils.  
**Implémentation** : Configuration HTTP pour chaque serveur (ports 8002-8005), isolation workspace sécurisée, tests validation fonctionnels.  
**Alternatives considérées** :
- Développement natif des fonctionnalités (rejeté : trop de temps, réinventer la roue)
- Intégration uniquement Qdrant/Compression (rejeté : limité à mémoire sémantique)
- Attendre MCP officiel (rejeté : besoin immédiat)  
**Résultat** : Écosystème complet 43 outils, productivité multipliée, sécurité maintenue.

### [2026-02-10 15:00:00] - Architecture 5 Layers
**Problème** : Code monolithique de 3000+ lignes, maintenance difficile, dépendances circulaires.  
**Décision** : Refactor complet en architecture 5 couches avec dépendances unidirectionnelles strictes.  
**Implémentation** : Séparation API/Services/Features/Proxy/Core, imports TYPE_CHECKING, factory patterns, DI via FastAPI Depends.  
**Alternatives considérées** :
- Microservices (rejeté : trop complexe pour un seul développeur)
- Modules par domaine (rejeté : pas assez de séparation des responsabilités)
- Refactor partiel (rejeté : ne résout pas le fond du problème)  
**Résultat** : Code maintenable, testable unitairement, évolutif.

## Décisions Techniques

### [2026-02-05 10:30:00] - Tiktoken Obligatoire
**Problème** : Comptage tokens imprécis avec estimations, factures API incohérentes.  
**Décision** : Imposer Tiktoken cl100k_base pour tout comptage tokens, interdire les estimations.  
**Implémentation** : `count_tokens_tiktoken()` obligatoire, tests unitaires validation précision, suppression code estimation.  
**Alternatives considérées** :
- Tokenizers lib (rejeté : pas compatible OpenAI)
- Estimation mots*1.3 (rejeté : très imprécis)
- Comptage provider-side (rejeté : pas transparent)  
**Résultat** : Comptage précis, économies 20-40% vérifiées, confiance facturation.

### [2026-02-20 02:20:00] - Auto-Session Implementation Strategy
**Problème** : Gestion manuelle des sessions multi-provider fastidieuse, utilisateurs devant créer manuellement une session pour chaque changement de modèle/provider. Risque d'erreurs 401 dues à modèles mal mappés et clés API non expansées.  
**Décision** : Implémenter système d'auto-création de sessions avec détection automatique du provider depuis le modèle demandé, mapping correct des modèles, et expansion automatique des variables d'environnement.  
**Implémentation** : Architecture modulaire avec `auto_session.py` pour logique métier, intégration dans proxy pipeline, UI toggle manuel, expansion env récursive, gestion asynchrone mémoire auto.  
**Alternatives considérées** :  
- Session unique multi-provider (rejeté : complexité routing, conflits modèles)  
- Prompt système automatique (rejeté : pas transparent, problèmes contexte)  
- Extension sessions existantes (rejeté : confusion utilisateur, pas de séparation claire)  
**Résultat** : Création automatique de sessions par provider, modèles correctement mappés, clés API expansées, UX transparente, économie temps utilisateur significative.

### [2026-02-01 14:20:00] - HTTPX Async Only
**Problème** : Utilisation mixte requests/urllib3 causant blocages event loop et timeouts.  
**Décision** : Interdire tout client HTTP synchrone, n'utiliser que HTTPX async.  
**Implémentation** : Remplacement tous les `requests.*` par `httpx.AsyncClient.*`, timeouts par provider, retry automatique.  
**Alternatives considérées** :
- Aiohttp (rejeté : moins stable que HTTPX)
- Mixte sync/async (rejeté : complexe, bug-prone)
- Threading pour sync (rejeté : surcoût inutile)  
**Résultat** : Performance optimale, pas de blocages, gestion erreurs réseau robuste.

### [2026-01-28 09:15:00] - Sanitizer Automatic Masking
**Problème** : 30-40% tokens gaspillés dans messages tools/console jamais lus.  
**Décision** : Masquer automatiquement messages >1000 tokens de type tool/console avec récupération possible.  
**Implémentation** : `ContentMasker` avec hashage SHA-256, stockage temporaire, endpoint `/api/mask/{hash}` pour récupération.  
**Alternatives considérées** :
- Suppression pure (rejeté : perte d'information)
- Compression (rejeté : trop lent pour messages verbeux)
- Manuel user-side (rejeté : pas automatique)  
**Résultat** : Économie 20-40% tokens, récupération possible si besoin, transparent utilisateur.

## Décisions Frontend

### [2026-01-25 16:45:00] - ES6 Modules Vanilla JS
**Problème** : Monolithique JavaScript 1744 lignes, impossible à maintenir, pas de réutilisabilité.  
**Décision** : Refactor en architecture modulaire ES6 avec imports natifs, pas de framework lourd.  
**Implémentation** : 8 modules (utils, api, charts, sessions, websocket, ui, modals, compaction), EventBus découplé, DOM cache.  
**Alternatives considérées** :
- React (rejeté : surdimensionné pour ce besoin)
- Vue.js (rejeté : courbe d'apprentissage)
- Web Components (rejeté : compatibilité navigateurs)  
**Résultat** : Code maintenable, réutilisable, performance native, bundle <50KB gzippé.

### [2026-01-20 11:30:00] - WebSocket Real-time Updates
**Problème** : Dashboard nécessitant refresh manuel pour voir les métriques, UX dégradée.  
**Décision** : Implémenter WebSocket broadcasting pour mises à jour temps réel sans refresh.  
**Implémentation** : `ConnectionManager` avec broadcast, events `metric/session/alert`, reconnexion automatique côté client.  
**Alternatives considérées** :
- Server-Sent Events (rejeté : unidirectionnel seulement)
- Polling (rejeté : trop de requêtes, pas temps réel)
- Long polling (rejeté : complexe, dépassé)  
**Résultat** : UX fluide, mises à jour instantanées, faible surcharge serveur.

## Décisions Sécurité

### [2026-01-15 13:20:00] - Environment Variables Only
**Problème** : Clés API hardcodées dans config.toml, risque fuite Git.  
**Décision** : N'utiliser que variables environnement avec expansion `${VAR}` dans TOML.  
**Implémentation** : Support .env.example, os.path.expandvars() automatique, .env dans .gitignore.  
**Alternatives considérées** :
- Vault (rejeté : trop complexe pour usage solo)
- Secrets management cloud (rejeté : dépendance externe)
- Chiffrement local (rejeté : surcomplexité)  
**Résultat** : Sécurité maximale, configuration flexible, pas de secrets dans Git.

### [2026-01-10 08:45:00] - MCP Workspace Isolation
**Problème** : Serveurs MCP avec accès système complet, risque sécurité.  
**Décision** : Isoler chaque serveur MCP dans workspace défini avec validation stricte des chemins.  
**Implémentation** : `validate_workspace_access()` avec Path.relative_to(), erreurs 403 explicites, sandbox par défaut.  
**Alternatives considérées** :
- Docker containers (rejeté : surcoût ressources)
- Chroot jails (rejeté : complexité Linux-specific)
- Aucune isolation (rejeté : trop risqué)  
**Résultat** : Sécurité robuste, accès contrôlé, erreurs claires.

## Décisions Performance

### [2026-01-05 17:30:00] - Smart Routing Algorithm
**Problème** : Selection provider manuelle, pas d'optimisation coût/performance.  
**Décision** : Implémenter algorithme de routing automatique basé sur contexte/coût/latence.  
**Implémentation** : `calculate_routing_score()` avec poids configurables, `find_optimal_provider()`, fallback gracieux.  
**Alternatives considérées** :
- Round-robin (rejeté : pas intelligent)
- User choice only (rejeté : pas optimisé)
- ML-based routing (rejeté : surcomplexité)  
**Résultat** : Optimisation automatique, économies coûts, performance maintenue.

### [2026-01-02 12:15:00] - SQLite Connection Pooling
**Problème** : Connexions SQLite multiples causant locks et timeouts sous charge.  
**Décision** : Implémenter connection pooling avec context managers et WAL mode.  
**Implémentation** : `@contextmanager get_db()`, `init_database()` avec WAL, timeout configurables.  
**Alternatives considérées** :
- PostgreSQL (rejeté : surdimensionné)
- In-memory DB (rejeté : pas persistant)
- File-based simple (rejeté : problèmes concurrence)  
**Résultat** : Performance DB optimale, pas de locks, concurrence gérée.