# Cline (local) : import du ledger d’usage vers Kimi Proxy

## TL;DR
**Kimi Proxy peut importer en lecture seule les métriques d’usage de Cline depuis un fichier local allowlisté** (`taskHistory.json`), les stocker en SQLite (données minimales) et les exposer via 3 endpoints (`/api/cline/*`).

## Le problème

Tu utilises Cline en local. Tu vois passer des tokens et des coûts, mais tu n’as pas une vue consolidée dans Kimi Proxy.

L’objectif de cette intégration est simple: récupérer des métriques d’usage existantes, sans importer de contenu sensible, et sans ouvrir un accès fichier générique.

## Ce que cette feature fait (et ne fait pas)

### ✅ Ce que ça fait

- Lit un unique fichier local allowlisté (chemin exact): `/home/kidpixel/.cline/data/state/taskHistory.json`.
- Extrait uniquement des métriques numériques par tâche.
- Upsert ces métriques dans SQLite (`cline_task_usage`).
- Expose les métriques via API.
- Peut notifier le dashboard via WebSocket quand de nouvelles données sont détectées.

### ❌ Ce que ça ne fait pas

- Ne récupère pas de conversations, prompts, réponses, logs, ni “sessions Cline”.
- Ne détecte pas une “version Cline” et ne maintient pas un “état de connexion Cline”.
- N’autorise pas l’utilisateur à fournir un chemin arbitraire à importer.

## Architecture (résumé)

```
Ledger Cline local (taskHistory.json)
  -> Feature ClineImporter (parsing strict + allowlist)
  -> Core (SQLite: cline_task_usage)
  -> API (/api/cline/*)
  -> UI dashboard (+ WebSocket optionnel)
```

Fichiers de référence:

- Feature: `src/kimi_proxy/features/cline_importer/importer.py`
- DB: `src/kimi_proxy/core/database.py`
- API: `src/kimi_proxy/api/routes/cline.py`
- Polling/WS: `src/kimi_proxy/services/cline_polling.py`

## Endpoints API

Tous les endpoints sont sous le prefix `/api/cline`.

### POST /api/cline/import

Déclenche l’import (idempotent via upsert).

Body optionnel:

```json
{ "path": null }
```

Réponse (exemple):

```json
{
  "imported_count": 42,
  "skipped_count": 3,
  "error_count": 0,
  "latest_ts": 1739999999999
}
```

Codes d’erreur:

- 400: chemin non allowlisté (ou détection de symlink/redirection)
- 404: fichier introuvable
- 422: JSON invalide ou schéma inattendu

### GET /api/cline/usage

Retourne les métriques importées.

Query params:

- `limit` (défaut 100, clamp à 1000)
- `offset` (défaut 0)

Réponse (exemple):

```json
{
  "items": [
    {
      "task_id": "task-123",
      "ts": 1739999999999,
      "model_id": "kimi",
      "tokens_in": 1200,
      "tokens_out": 450,
      "total_cost": 0.031,
      "imported_at": "2026-02-24 13:00:00"
    }
  ],
  "limit": 100,
  "offset": 0
}
```

### GET /api/cline/status

Retourne un statut minimal pour l’UI.

Réponse (exemple):

```json
{ "latest_ts": 1739999999999 }
```

## Sécurité: allowlist strict + données minimales

### ✅ Le “Allowlist Exact Path”

Le code valide le chemin avec des règles volontairement strictes:

- le chemin demandé doit être exactement égal au chemin allowlisté;
- le fichier doit exister et être un fichier régulier;
- tout symlink ou redirection est refusé.

L’objectif est d’éviter un glissement vers un “lecteur de fichiers” générique.

Note: l’allowlist est actuellement codée en dur (chemin exact). Ce n’est pas un mécanisme générique de lecture de fichiers.

### ❌ Exemple à ne pas faire

Importer un chemin arbitraire fourni par l’utilisateur:

```json
{ "path": "/home/kidpixel/.ssh/id_rsa" }
```

Même avec de bonnes intentions, ça devient une surface d’exfiltration.

### ✅ Exemple correct

Importer uniquement le fichier allowlisté, puis stocker des métriques numériques:

```json
{ "path": null }
```

## Temps réel (optionnel): polling + WebSocket

Le service `ClinePollingService` peut importer périodiquement le ledger et envoyer un message WebSocket uniquement quand une nouvelle donnée est détectée.

Message envoyé:

```json
{
  "type": "cline_usage_updated",
  "latest_ts": 1739999999999,
  "latest_count": 123,
  "imported_count": 3,
  "timestamp": "2026-02-24T15:22:15.123456"
}
```

## Trade-offs

| Choix | Avantage | Inconvénient |
| --- | --- | --- |
| Allowlist strict + refus symlink | Surface d’attaque minimale | Moins flexible (pas de path custom) |
| Stockage “metrics only” | Privacy-by-design | Pas de debug via payload détaillé |
| Polling serveur + WS best-effort | UI plus vivante sans charge excessive | Nécessite un cycle d’import périodique |

## Golden Rule

Quand tu bridges un outil local vers une API, tu gardes la frontière nette: **métadonnées minimales, chemin allowlisté, lecture seule**.

---
Dernière mise à jour: 2026-02-24
