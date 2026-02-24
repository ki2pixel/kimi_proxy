## Task 4 terminée — Dashboard « Cline (local) »

### Objectif
Ajouter une section UI dans le dashboard pour visualiser les métriques importées depuis le ledger local Cline (Solution 1) et déclencher un import manuel via l’API.

### Réalisations
- **UI (HTML)** : ajout d’une nouvelle card **“Cline (local)”** dans `static/index.html`.
  - Affiche : dernier import (`#cline-latest-import`), bouton import (`#cline-import-btn` + label `#cline-import-btn-label`), table (`#cline-usage-tbody`).
- **Module ES6** : création de `static/js/modules/cline.js`.
  - Appels API : `GET /api/cline/status`, `GET /api/cline/usage`, `POST /api/cline/import`.
  - Rendu **DOM-only** (création d’éléments, `textContent`, pas de `innerHTML`).
  - Gestion d’état du bouton (disabled + `aria-busy`).
- **Wiring** : ajout de `initClineSection()` dans `static/js/main.js` (initialisation au démarrage).

### Points clés / sécurité
- La section n’affiche **que** les champs attendus : `task_id`, `ts`, `model_id`, `tokens_in`, `tokens_out`, `total_cost`.
- Aucun rendu HTML direct dans le code ajouté (prévention XSS).
- L’import reste côté backend **allowlist strict** (déjà en place) — le frontend n’envoie pas de chemin.

### Vérifications effectuées
- Smoke tests via `TestClient` :
  - `/` contient la section Cline.
  - `/api/cline/status`, `/api/cline/usage`, `/api/cline/import` répondent en 200.
  - `/static/js/modules/cline.js` servi correctement.
- Vérification “pas d’innerHTML” : aucune occurrence dans `static/js/modules/cline.js`.

### Fichiers modifiés/créés
- `static/index.html` (modifié)
- `static/js/modules/cline.js` (créé)
- `static/js/main.js` (modifié)

Commande de re-check rapide si besoin :
```bash
PYTHONPATH=src python3 - <<'PY'
from fastapi.testclient import TestClient
from kimi_proxy.main import create_app
client = TestClient(create_app())
print(client.get('/api/cline/status').json())
PY
```

Lancer la **Task 5 (polling + WS broadcast)** via `execute_task 6d46c965-28b9-4eb5-a68d-387d02472a47`.