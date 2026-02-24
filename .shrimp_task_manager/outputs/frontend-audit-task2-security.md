# Audit sécurité frontend (Task 2) — Kimi Proxy Dashboard

**TL;DR**: le risque principal est **XSS** via des rendus `innerHTML`/templates qui interpolent des champs retournés par l’API (ex: `content_preview`, `title`, `provider.name`). Tant que le dashboard accepte des données dynamiques (WebSocket/API), ces sinks doivent être considérés comme exposés. Deuxième risque: **supply-chain** (CDN sans SRI, `lucide@latest`) et **CSP** difficile à activer à cause des scripts/handlers inline. **CSRF** dépend du mode d’auth (cookies vs token), mais les appels mutatifs existent et ne portent pas de mécanisme explicite.

## Portée et hypothèses

- Cible: `static/index.html` et `static/js/**` (Vanilla JS, ES6 modules).
- Hypothèse raisonnable: les valeurs venant de `/api/**` et du WebSocket sont **non fiables par défaut** (même si le backend est “local”, un XSS transforme une page en exfiltration/commande locale).
- Objectif: inventorier les sinks DOM, analyser la provenance des données, prioriser les mitigations sans casser l’architecture.

---

## 1) Inventaire des sinks DOM (XSS)

### 1.1 Sinks à risque élevé (données non fiables interpolées)

| Emplacement | Sink | Données interpolées (sources probables) | Gravité | Pourquoi |
|---|---|---|---|---|
| `static/index.html:1012–1033` | `resultsContainer.innerHTML = ...` | `r.content_preview`, `error.message` (retour `window.searchSimilar` = `/api/memory/similarity`) | **P0** | Si `content_preview` contient du HTML/JS, exécution directe. Même risque pour `error.message` si une erreur applicative remonte un message non contrôlé. |
| `static/js/modules/mcp.js:391–418` | `container.innerHTML = ...` | `mem.content_preview` (retour `fetchFrequentMemories()` = `/api/memory/frequent`) | **P0** | `content_preview` est inséré tel quel dans du HTML construit en string. |
| `static/js/modules/modals.js:1125–1143` (grep `content_preview`) | `resultsContainer.innerHTML = ...` | `mem.title`, `mem.content_preview`, `mem.type`, `mem.created_at` (retour `similarityService.findSimilarMemories(...)`) | **P0** | Les champs affichés dans les résultats sont des vecteurs XSS classiques (`title`, `preview`). |
| `static/js/modules/modals.js:175–260` | `container.innerHTML = html` | `provider.name`, `provider.type`, `provider.icon`, `provider.color`, `model.name`, `model.capabilities` (retour `loadProviders()`/`loadModels()` depuis `/api/providers` & `/api/models`) | **P0** | Rend un gros bloc HTML par string concaténée; injection possible via n’importe quel champ (y compris attributs/classes). |
| `static/js/modules/modals.js:300–355` | attribut `onclick="window.selectModel(...)"` dans HTML généré | `model.name` (échappe seulement les `'`), `provider.key`, `model.key` | **P0** | Un `onclick` inline est un “super-sink”: si l’attaquant injecte une séquence cassant la chaîne JS, l’exécution est immédiate. |
| `static/js/modules/modals.js:1271–1326` | `messagesPreview.innerHTML = ...` | `compactionPreview.message`, `msg.preview` (retour `/api/compaction/{id}/preview`) | **P0** | `message` et `preview` proviennent du serveur; insertion brute dans HTML via template string. |
| `static/js/modules/modals.js:975–1007` | `previewContainer.innerHTML = ...` | `item.action`, `item.preview` (retour `memoryCompressionService.previewCompression(...)`) | **P1** | L’API semble interne, mais c’est néanmoins du contenu dynamique inséré dans du HTML. |

### 1.2 Sinks “contrôlés” (à garder sous surveillance)

Ces occurrences semblent composer du HTML uniquement à partir de constantes ou de valeurs numériques; elles restent néanmoins des points à fort impact si la notion de “contrôlé” dérive dans le temps.

- `static/js/modules/mcp.js:292–350`: `statusContainer.innerHTML = overallStatus`, `phase3Content.innerHTML = phase3Html`, `phase4Content.innerHTML = phase4Html`.
- `static/js/modules/ui.js:626–640`: `tokensContainer.innerHTML = tokensDisplay` (dérivé de nombres).
- `static/js/modules/modals.js:486`: `document.body.insertAdjacentHTML('beforeend', modalHTML)` (template local, contrôlé par `type`).

### 1.3 Absence de patterns critiques supplémentaires

Recherche `eval`, `new Function`, `document.write`, `outerHTML`: **aucune occurrence** dans `static/` (commande `rg`).

---

## 2) Inline scripts et inline handlers (amplificateur XSS, bloqueur CSP)

### Constat

- Handlers inline nombreux: `onclick=...`, `oninput=...`, `onkeypress=...` dans `static/index.html` et `static/memory-section.html`.
- Scripts inline présents en bas de page: fonctions MCP (`executeMCPSearch`, `executeMCPCompression`) et modal “mémoriser” (`executeStoreMemory`).

### Impact sécurité

1) **CSP strict pratiquement impossible** sans `'unsafe-inline'` tant que ces scripts/handlers existent.
2) Les `onclick` inline favorisent les injections “attribute breaking” et augmentent la surface d’attaque.

---

## 3) CSRF (dépend du mode d’auth, mais appels mutatifs présents)

### Appels mutatifs observés côté frontend

Exemples (non exhaustif):

- `static/index.html:1184–1197`: `POST /api/memory/store?session_id=...` (store memory).
- `static/js/main.js`:
  - `POST /api/memory/store?session_id=...` (store memory via module)
  - `POST /api/sessions/{id}/activate`
  - `DELETE /api/sessions/{id}`
  - `DELETE /api/sessions` (bulk)
- `static/js/modules/api.js`:
  - `POST /api/sessions` (create session)
  - `POST /api/compaction/{id}/toggle-auto`
  - `POST /api/compaction/{id}` (execute compaction)
  - `POST /api/sessions/toggle-auto`
- `static/js/modules/mcp.js`:
  - `POST /api/memory/similarity`
  - `POST /api/memory/compress`
  - `POST /api/memory/store`

### Risque

- Si l’authentification repose sur **cookies de session** (même locaux), les requêtes `fetch()` same-origin enverront ces cookies automatiquement; sans token CSRF côté serveur, une page tierce pourrait déclencher des actions.
- Si l’authentification repose sur un token en header (type `Authorization: Bearer`), le risque CSRF est généralement plus faible; il reste pertinent de durcir les endpoints mutatifs.

### Indice technique

- Aucune occurrence de `X-CSRF-*`, `csrf`, `credentials:` côté frontend (grep `CSRF|X-CSRF|credentials:`). Donc aucune protection explicite au niveau client.

---

## 4) Supply-chain (CDN, pinning, SRI)

### Constat

- `static/index.html` charge des scripts externes:
  - Chart.js via cdnjs: `https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js`
  - Lucide via unpkg: `https://unpkg.com/lucide@latest`

### Risque

- Absence de **SRI** (`integrity`) et `crossorigin` sur les scripts CDN.
- `lucide@latest` n’est pas “pinné”; un changement upstream peut casser l’UI ou injecter une version compromise.

---

## Recommandations priorisées (P0/P1/P2)

### P0 — Bloquer l’exécution de HTML non fiable (XSS)

1) **Interdire `innerHTML` avec données API/WS**.
   - Remplacer par DOM APIs (`createElement`, `textContent`, `appendChild`).
   - Pour les listes (résultats, mémoires, sessions): générer des nodes et utiliser `DocumentFragment`.

2) **Supprimer les `onclick` inline générés** (notamment `renderModelCard()` dans `modals.js`).
   - Créer des éléments DOM et binder les handlers via `addEventListener`.
   - Éviter de passer des strings user-controlled dans du code JS inline.

3) Si une partie doit rester en rendu “template string” temporairement:
   - appliquer `escapeHtml()` à **toutes** les interpolations (`content_preview`, `title`, `provider.name`, etc.).
   - whitelister strictement toute valeur interpolée dans des classes (ex: `provider.color`).

### P1 — Rendre une CSP réaliste (progressive hardening)

1) **Migrer les scripts inline** de `index.html` vers un module ES6 (`static/js/modules/mcp-ui.js` par exemple), et binder les events dans `main.js`.

2) Une fois les inline supprimés, activer CSP progressivement:
   - commencer par `Content-Security-Policy-Report-Only`.
   - cible: `script-src 'self' https://cdnjs.cloudflare.com` avec SRI, sans `'unsafe-inline'`.

3) En option avancée: **Trusted Types** (si on veut verrouiller `innerHTML` côté navigateur), mais cela demande une migration plus structurée.

### P1 — Supply-chain

1) **Pinner Lucide**: remplacer `lucide@latest` par une version (`lucide@0.xx.y`) et idéalement auto-héberger.
2) Ajouter **SRI** (integrity) sur Chart.js et Lucide si CDN maintenu.

### P1 — CSRF

1) Côté backend: exiger une stratégie claire pour les endpoints mutatifs:
   - Cookies: `SameSite=Lax` ou `Strict` + token CSRF côté serveur.
   - Token header: validation stricte `Origin`/`Referer` et CORS fermé.

2) Côté frontend: homogénéiser les appels via `apiRequest()` pour centraliser headers, erreurs, et (si choisi) propagation d’un token CSRF.

### P2 — Gardes de régression

1) Ajouter un garde CI simple (test/grep) qui échoue si:
   - `innerHTML =` est introduit hors d’une allowlist commentée.
   - de nouveaux handlers inline apparaissent dans `static/*.html`.

2) Ajouter des tests unitaires JS ciblés (ex: “`content_preview` doit être rendu via `textContent`”).

---

## Conclusion

L’application a déjà des efforts visibles (usage fréquent de `textContent`, présence de `escapeHtml()`), mais il reste plusieurs rendus HTML “string-based” où des champs backend sont interpolés sans échappement. Tant que ces chemins existent, **un payload XSS est plausible** via n’importe quel champ `*preview`, `title`, ou métadonnée provider/modèle.

La trajectoire recommandée est une migration progressive: **P0** remplacer les sinks critiques par du DOM sécurisé; **P1** supprimer inline scripts/handlers pour permettre CSP et renforcer supply-chain; **P1** clarifier CSRF selon le modèle d’auth.
