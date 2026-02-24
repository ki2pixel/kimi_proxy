#+#+#+#+-----------------------------------------------------------------------
# PRD / Brief — Cline (local) : Tests + Documentation
# Date: 2026-02-24
# Portée: Finaliser les tâches Shrimp
#   - 70d77851-b202-49da-b46f-45f47e0aba8b (Tests unitaires + intégration)
#   - e19fa00b-168a-49e3-8e1b-e49a1d4c1aa0 (Documentation)
#+#+#+#+-----------------------------------------------------------------------

## 1) TL;DR

Ajouter une couverture de tests fiable (unit + intégration) pour l’import Cline local (ledger allowlisté) et mettre à jour la documentation pour refléter le comportement réel (endpoints, garanties de sécurité, limites).

## 2) Contexte et composants

### Feature — Importer (Features layer)
- Fichiers: `src/kimi_proxy/features/cline_importer/*`
- Entrée unique allowlistée (chemin exact, pas de symlink):
  `ALLOWED_LEDGER_PATH = /home/kidpixel/.cline/data/state/taskHistory.json`
- Parsing strict + extraction minimale:
  - `task_id`, `ts`, `model_id`, `tokens_in`, `tokens_out`, `total_cost`
- Stockage: table SQLite `cline_task_usage` via `core.database` (écriture sync encapsulée via `asyncio.to_thread`).

### API — Routes (API layer)
- Fichier: `src/kimi_proxy/api/routes/cline.py`
- Prefix: `/api/cline`
- Endpoints:
  - `POST /api/cline/import` (body optionnel: `{ "path": string|null }`, validé via allowlist strict)
  - `GET /api/cline/usage?limit=100&offset=0` (retourne `items`, `limit`, `offset`)
  - `GET /api/cline/status` (retourne `latest_ts`)

### Services — Polling + WebSocket (Services layer)
- Fichier: `src/kimi_proxy/services/cline_polling.py`
- Message WebSocket: `type = cline_usage_updated`.
- Tests existants: `tests/unit/test-cline-polling.py` + `tests/unit/test-cline-ws-update.test.js`.

## 3) Objectifs

### Objectifs tests
1. **Unit tests**: valider parsing, coercions et règles de sécurité (allowlist + anti-symlink), sans dépendre de `/home/kidpixel/.cline`.
2. **Unit/DB tests**: importer end-to-end sur DB de test isolée (fichier temp), avec ledger JSON factice.
3. **Integration tests API**:
   - `POST /api/cline/import` importe et renvoie des compteurs cohérents.
   - `GET /api/cline/usage` retourne les lignes attendues, triées, et respecte limit/offset.
   - `GET /api/cline/status` reflète le `latest_ts` en DB.
4. **Non-régression sécurité**: un chemin non allowlisté doit retourner **400**; un ledger introuvable **404**; JSON invalide **422**.

### Objectifs documentation
1. Mettre `docs/features/cline.md` à jour pour être **fidèle au code**:
   - Pas de claims (ex: “version Cline”, “état de connexion”) si non implémentés.
   - Décrire les endpoints réels + schémas de réponse.
2. Documenter clairement les garanties de sécurité:
   - chemin exact + refus symlink
   - lecture seule + données minimales stockées
   - pas de logs/historiques/sessions Cline importés
3. Documenter les limites/trade-offs:
   - dépendance à un fichier local
   - tests doivent mocker/patcher `ALLOWED_LEDGER_PATH` et DB path

## 4) Contraintes techniques (obligatoires)

- Respect de l’architecture 5 couches: API → Services → Features → Proxy → Core.
- Async/await obligatoire (I/O async, et sync DB via `to_thread` seulement).
- Typing strict (pas de `Any` ajouté).
- Tests isolés:
  - **Ne jamais lire** le vrai `/home/kidpixel/.cline/...` en tests.
  - Utiliser `tmp_path` + monkeypatch pour `ALLOWED_LEDGER_PATH` et DB (`kimi_proxy.core.database.DATABASE_FILE`).
- Pas de secrets dans les fixtures.

## 5) Livrables attendus

### Tests (Python)
- Nouveau fichier: `tests/unit/test_cline_importer.py`
  - `validate_allowlisted_path`: accepte chemin exact patché, refuse chemins alternatifs, refuse symlink.
  - Parsing: `_parse_entry` via import (ou tests par `import_ledger` avec ledger synthétique).
- Nouveau fichier: `tests/integration/test_cline_api.py`
  - App FastAPI de test incluant `cline.router`.
  - Cas OK + cas erreurs (400/404/422).

### Documentation
- Mise à jour: `docs/features/cline.md` (méthodologie documentation skill obligatoire: TL;DR, problème, ❌/✅, trade-offs, golden rule).

## 6) Critères d’acceptation

1. `pytest` passe localement (`./bin/kimi-proxy test`).
2. Les tests ne dépendent pas d’un état machine spécifique (pas de fichier réel dans `/home/kidpixel/.cline`).
3. Documentation Cline reflète les endpoints et payloads réellement implémentés.
4. Les tâches Shrimp 70d... et e19... obtiennent un score ≥ 80 via `verify_task`.
