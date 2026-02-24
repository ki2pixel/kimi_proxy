# PRD — Intégration Kimi Proxy ↔ Cline (Solution 1 : import ledger local)

## Objectif

Implémenter **Solution 1 (recommandée)** : importer en lecture seule le ledger local de Cline afin d’afficher dans Kimi Proxy Dashboard les métriques d’usage **sans MITM** et **sans exposition de données sensibles**.

**Source de vérité** :

- Fichier allowlisté : `/home/kidpixel/.cline/data/state/taskHistory.json`

**Sorties attendues** :

- Stockage SQLite dans Kimi Proxy (table dédiée)
- Endpoint API pour déclencher un import / refresh
- Affichage Dashboard « Cline (local) » (table + éventuel graphe)
- Polling périodique sécurisé (optionnel mais prévu)

## Hors périmètre (interdictions)

- ❌ Lecture/ingestion de :
  - `/home/kidpixel/.cline/data/secrets.json`
  - `/home/kidpixel/.cline/cline-core-service.log`
  - `/home/kidpixel/.cline/data/tasks/**/api_conversation_history.json`
  - `/home/kidpixel/.cline/data/tasks/**/ui_messages.json`
- ❌ Instrumentation/patch côté Cline
- ❌ Proxy système / interception réseau / MITM
- ❌ Extraction de contenu conversationnel (prompts/réponses)

## Contraintes & standards

- **Architecture 5 couches (obligatoire)** :
  - API (FastAPI) ← Services (WebSocket/Managers) ← Features (importer/validation) ← Proxy (HTTPX) ← Core (SQLite)
- **Async obligatoire** pour toute I/O (lecture fichier, endpoints, polling)
  - Pas d’I/O bloquante en endpoint.
- **Typage strict** (pas de `Any`) et erreurs explicites (pas de `try/except: pass`).
- **Lecture seule** du ledger Cline.
- **Allowlist filesystem stricte** :
  - Seul le chemin exact `/home/kidpixel/.cline/data/state/taskHistory.json` est autorisé.
  - Refuser tout autre chemin (y compris symlinks, `..`, variantes).
- **Données minimales stockées** (privacy by design) :
  - `task_id`, `ts`, `model_id`, `tokens_in`, `tokens_out`, `total_cost`

## Risques & mitigations

### Risques

1) **Changement de format JSON** (Cline peut modifier la structure du ledger)
2) **Fichier corrompu / partiellement écrit** (lecture pendant écriture)
3) **Erreurs de parsing** (types inattendus : string vs number)
4) **Performance** : import répété, gros historique

### Mitigations

- Parsing tolérant mais strict :
  - ignorer les entrées invalides (avec comptage d’erreurs),
  - journaliser uniquement des erreurs *non sensibles*.
- Import idempotent :
  - clé unique sur `task_id` (ou `task_id+ts` si nécessaire) pour éviter doublons.
- Lecture robuste :
  - lecture atomique (read → parse → validate),
  - limites : max N entrées importées par run (configurable).

## Métriques à exposer

### Par tâche (ligne)

- `task_id` (string)
- `ts` (timestamp / ISO ou epoch ms)
- `model_id` (string)
- `tokens_in` (int)
- `tokens_out` (int)
- `total_cost` (float)

### Agrégations (dashboard)

- total tokens in/out sur période
- coût cumulé
- distribution par modèle (si `model_id` est présent)

## Interfaces à livrer (v1)

### API

- `POST /api/cline/import`
  - Body : optionnel `{"path": "..."}` (mais en pratique on impose l’allowlist ; ce champ peut être omis)
  - Réponse :
    - `imported_count`, `skipped_count`, `error_count`, `latest_ts`
  - Erreurs :
    - 400 si path non allowlisté
    - 422 si JSON invalide / schéma incompatible
    - 500 si erreur interne DB

### DB

- Nouvelle table SQLite : `cline_task_usage`

### Dashboard

- Nouvelle section : « Cline (local) »
  - Table des tâches importées
  - Indication “Dernier import : …”
  - Bouton “Importer maintenant”

### Polling

- Polling côté serveur (ou côté frontend) déclenchant l’import périodique
  - interval configurable
  - backoff en cas d’erreurs

## Critères d’acceptation

- L’import fonctionne sans lire de fichiers sensibles (liste noire explicitement assurée par allowlist).
- Aucune donnée conversationnelle n’est stockée.
- Endpoints async, pas de blocage.
- Table SQLite créée + tests unitaires pour parsing/validation.
- Dashboard affiche les métriques importées.
