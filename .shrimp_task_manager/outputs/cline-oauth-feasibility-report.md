# Rapport — Faisabilité d’intégration Kimi Proxy ↔ Extension Cline (OAuth 2.0 / ChatGPT Subscription)

## TL;DR (à compléter)
- Verdict: **Partiellement faisable**
- Principale contrainte: le provider **Codex Subscription** route vers `chatgpt.com/backend-api/codex` (HTTPS + WebSocket). Sans MITM, un proxy HTTP(S) ne permet pas à Kimi Proxy d’observer les payloads ni les champs `usage` “en transit”.
- Recommandation: s’appuyer d’abord sur la **comptabilité locale déjà disponible** dans `/home/kidpixel/.cline/data/state/taskHistory.json` (`tokensIn/tokensOut/totalCost`) ; éviter d’extraire des métriques depuis `cline-core-service.log` car il contient aussi des marqueurs auth (`access_token`, `refresh_token`, `Authorization`, etc.).

---

## 1) Protocole sécurité & redaction (OBLIGATOIRE)

### 1.1 Données interdites à afficher / copier (même partiellement)
Ne jamais inclure dans ce rapport (ni dans les extraits affichés pendant l’analyse):
- Valeurs de champs: `access_token`, `refresh_token`, `id_token`
- En-têtes: `Authorization` (Bearer, Basic, etc.)
- Cookies de session (ex: `__Secure-`, `session`, `cf_*`, etc.)
- Clés API / secrets (`api_key`, `.env`, tokens MCP, etc.)
- Tout identifiant secret persisté (keychain/secret storage) s’il contient une valeur

### 1.2 Règle d’or de redaction
Si un champ sensible est rencontré:
1. **Ne pas afficher la valeur**.
2. Consigner uniquement:
   - le **chemin du fichier**
   - le **jsonpath** (pour JSON) ou le **symbole/fonction/classe** (pour code)
   - la **présence** (booléen) et la **catégorie** (auth/storage/transport)
3. Dans tout extrait ou exemple, remplacer par `"<redacted>"`.

### 1.3 Politique d’extraction safe (logs JSON volumineux)
- Utiliser `json_query_jsonpath` pour extraire uniquement:
  - schémas / clés / structures
  - existence de clés (présence/absence)
  - champs `usage` / `prompt_tokens` / `completion_tokens` / `total_tokens` si présents
- Éviter les extractions qui dumpent de longues listes d’historique.

---

## 2) Format de preuve (Evidence Format)

Chaque “fait” doit être traçable et citer sa source.

### 2.1 Enregistrement de preuve (modèle)

| Catégorie | Source | Symbole / JSONPath | Observation (sans secret) | Sensibilité | Impact |
|---|---|---|---|---|---|
| auth | `path/to/file` | `Class.method()` / `$.path` | ex: “déclenche redirect callback” | faible/moyenne/élevée | ex: “flow PKCE probable” |

**Champs**
- **Catégorie**: `auth` | `storage` | `transport` | `config` | `usage` | `telemetry`
- **Source**: chemin de fichier exact
- **Symbole / JSONPath**: fonction/classe (code) ou chemin JSONPath (logs)
- **Observation**: constats factuels (noms de champs, comportements) sans valeurs sensibles
- **Sensibilité**: faible/moyenne/élevée
- **Impact**: conséquence pour intégration proxy / compat IDE

---

## 3) Faits — Code Cline (à remplir)

### 3.1 Architecture & points d’entrée

Cartographie (non exhaustive) des modules pertinents repérés dans `research/cline-main/src/`:

- `src/integrations/openai-codex/`
  - `oauth.ts`: configuration OAuth + PKCE + échange/refresh + persistance des credentials (via `StateManager`).
- `src/core/controller/account/`
  - `openAiCodexSignIn.ts` / `openAiCodexSignOut.ts`: points d’entrée UI/commandes pour démarrer/arrêter l’auth OAuth.
- `src/core/api/providers/`
  - `openai-codex.ts`: handler réseau “Codex via subscription” (HTTP + WebSocket) vers l’API backend ChatGPT + extraction usage.
- `src/shared/`
  - `net.ts`: wrapper réseau central (fetch + proxy support) utilisé par les clients (dont Codex) + doc proxy.
  - `api.ts`: inventaire providers/modèles; contient un commentaire explicitant le routage Codex via backend ChatGPT.
- `src/hosts/external/`
  - `AuthHandler.ts`: serveur local 127.0.0.1 (plage ports) pour callbacks OAuth dans certains modes (VSCode/JetBrains/CLI) et délégation à `SharedUriHandler`.
- `src/shared/storage/`
  - `state-keys.ts`: “single source of truth” pour les clés de storage, dont la clé secret utilisée pour les credentials OAuth Codex.
- `src/`
  - `config.ts`: lecture/validation de `~/.cline/endpoints.json` pour mode self-hosted (endpoints app/api/mcp).

### 3.1.A Evidence (architecture)

| Catégorie | Source | Symbole / JSONPath | Observation (sans secret) | Sensibilité | Impact |
|---|---|---|---|---|---|
| auth | `research/cline-main/src/core/controller/account/openAiCodexSignIn.ts` | `openAiCodexSignIn()` | Démarre le flow OAuth Codex (génère URL via manager, ouvre le navigateur, attend le callback, puis met à jour l’état webview). | faible | Point d’entrée fonctionnel pour “hooker” une future intégration (sans modifier OAuth). |
| auth | `research/cline-main/src/core/controller/account/openAiCodexSignOut.ts` | `openAiCodexSignOut()` | Efface les credentials persistés et annule le flow OAuth en cours, puis refresh l’état webview. | faible | Confirme l’existence d’un cycle d’auth complet (sign-in/out). |
| transport | `research/cline-main/src/core/api/providers/openai-codex.ts` | `OpenAiCodexHandler.createMessage()` | Récupère un jeton d’accès via `openAiCodexOAuthManager.getAccessToken()` puis effectue requêtes streaming vers le backend Codex. | moyenne | Point d’observation principal des flux “subscription Codex” (requêtes/réponses, usage). |

### 3.2 Auth / OAuth

Faits observés dans les sources:

- Le flow “OpenAI Codex” est implémenté comme **OAuth 2.0 Authorization Code + PKCE (S256)**.
- Le callback est reçu sur un **serveur HTTP local** (port fixé 1455) et la route attendue est `/auth/callback`.
- Le scope inclut `offline_access`, ce qui correspond à un mécanisme de **refresh** (persisté côté extension).
- Le code mentionne explicitement des paramètres “Codex-specific” (originator/flow simplifié).

### 3.2.A Evidence (OAuth Codex)

| Catégorie | Source | Symbole / JSONPath | Observation (sans secret) | Sensibilité | Impact |
|---|---|---|---|---|---|
| auth | `research/cline-main/src/integrations/openai-codex/oauth.ts` | `OPENAI_CODEX_OAUTH_CONFIG` | Définit endpoints OAuth (issuer `auth.openai.com`), callback local `http://localhost:1455/auth/callback`, scopes incluant `offline_access`. | moyenne | Confirme le type de flow (auth code) et la présence d’un refresh. |
| auth | `research/cline-main/src/integrations/openai-codex/oauth.ts` | `buildAuthorizationUrl()` | Construit URL d’auth avec PKCE (S256), `response_type=code`, `state`, et paramètres “codex_cli_simplified_flow/originator”. | moyenne | Indique un flow PKCE standard (points d’intégration: ouverture URL et callback). |
| auth | `research/cline-main/src/integrations/openai-codex/oauth.ts` | `exchangeCodeForTokens()` | Échange “code” contre des tokens via POST `application/x-www-form-urlencoded` avec `code_verifier`; note: `state` validé mais non envoyé au token endpoint. | élevée | Identifie précisément la frontière réseau où les tokens sont obtenus (à ne pas logger). |
| auth | `research/cline-main/src/integrations/openai-codex/oauth.ts` | `refreshAccessToken()` / `OpenAiCodexOAuthTokenError.isLikelyInvalidGrant()` | Refresh via `grant_type=refresh_token` + déduplication; si “invalid grant” probable → efface les credentials persistés. | élevée | Confirme la stratégie de refresh + invalidation, utile pour évaluer robustesse proxy (éviter de casser refresh). |
| auth | `research/cline-main/src/integrations/openai-codex/oauth.ts` | `extractAccountId()` / `parseJwtClaims()` | Extrait un “account id” depuis claims JWT (racine / namespace `https://api.openai.com/auth` / org[0]). | moyenne | Explique l’existence d’un identifiant utilisé ensuite comme header optionnel côté backend Codex. |

### 3.3 Stockage des secrets

Faits observés:

- La persistance des credentials OAuth Codex se fait via un mécanisme de **secret storage** abstrait par `StateManager`.
- Une clé dédiée existe pour stocker un **blob JSON** de credentials OAuth Codex.
- Le code de migrations VS Code interroge explicitement cette clé dans `context.secrets`.

### 3.3.A Evidence (secret storage)

| Catégorie | Source | Symbole / JSONPath | Observation (sans secret) | Sensibilité | Impact |
|---|---|---|---|---|---|
| storage | `research/cline-main/src/shared/storage/state-keys.ts` | `SECRETS_KEYS` | Liste des clés secret contient une entrée dédiée aux credentials OAuth Codex (blob JSON). | moyenne | Indique un stockage “secret” (probablement keychain/SecretStorage) plutôt qu’un log en clair. |
| storage | `research/cline-main/src/integrations/openai-codex/oauth.ts` | `OpenAiCodexOAuthManager.loadCredentials()` | Charge les credentials via `StateManager.getSecretKey(...)` puis parse/valide la structure via Zod. | élevée | Point où une intégration “observer” doit éviter toute fuite (ne jamais logger). |
| storage | `research/cline-main/src/integrations/openai-codex/oauth.ts` | `OpenAiCodexOAuthManager.saveCredentials()` / `clearCredentials()` | Écrit/supprime les credentials via `StateManager.setSecret(...)` puis `flushPendingState()`. | élevée | Confirme persistance et invalidation maîtrisées. |
| storage | `research/cline-main/src/core/storage/state-migrations.ts` | `migrateWelcomeViewCompleted()` | Lit la clé secret Codex via `context.secrets.get(...)` pour déterminer si l’onboarding “welcome view” est complété. | moyenne | Confirme que la clé existe au niveau SecretStorage VS Code. |

### 3.4 Transport réseau (HTTP/SSE/WebSocket) et configurabilité proxy/baseURL

Faits observés:

- Cline fournit un wrapper central `@/shared/net` qui impose un **fetch configuré pour proxy** (VSCode: fetch global; JetBrains/CLI: undici + ProxyAgent via variables d’environnement `HTTP(S)_PROXY`).
- Le provider “openai-codex” route vers un **backend ChatGPT** via une base URL constante (`https://chatgpt.com/backend-api/codex`) et une URL WebSocket (`wss://chatgpt.com/backend-api/codex/responses`).
- Le provider Codex est implémenté en **streaming** avec:
  - mode WebSocket optionnel (“responses_websockets”) + fallback HTTP
  - extraction et normalisation de champs “usage” (input/output/cache/reasoning) dans `normalizeUsage()`.

### 3.4.A Evidence (transport + proxy)

| Catégorie | Source | Symbole / JSONPath | Observation (sans secret) | Sensibilité | Impact |
|---|---|---|---|---|---|
| transport | `research/cline-main/src/shared/net.ts` | `export const fetch` | Wrapper fetch “platform-configured” avec support proxy: en mode standalone (JetBrains/CLI) configure undici + EnvHttpProxyAgent; doc indique que ne pas utiliser ce wrapper casse le support proxy. | faible | Point clé: une interception “sans MITM” peut passer par proxy env + usage de `fetch`/OpenAI SDK. |
| transport | `research/cline-main/src/core/api/providers/openai-codex.ts` | `CODEX_API_BASE_URL` / `CODEX_RESPONSES_WEBSOCKET_URL` | URLs constantes vers backend Codex (HTTP + WebSocket) sur le domaine ChatGPT. | moyenne | Réduit la configurabilité “baseURL” spécifique à Codex (contrairement aux providers OpenAI-compatible). |
| transport | `research/cline-main/src/core/api/providers/openai-codex.ts` | `new OpenAI({ baseURL, fetch })` | Le client OpenAI SDK est instancié avec `baseURL` Codex + `fetch` partagé (proxy-aware). | moyenne | Confirme que le chemin “proxy env vars” est le mécanisme prévu côté Cline (JetBrains/CLI). |
| usage | `research/cline-main/src/core/api/providers/openai-codex.ts` | `normalizeUsage()` | Transforme les champs “usage” en chunk interne (input/output/cache/reasoning), coût total forcé à 0 (subscription). | faible | Indique une source de “token accounting” possible sans introspection du prompt (si usage disponible). |
| transport | `research/cline-main/src/hosts/external/AuthHandler.ts` | `AuthHandler.createServer()` / `handleRequest()` | Serveur local 127.0.0.1 sur une plage de ports (48801-48811) pour recevoir un callback, puis délègue à `SharedUriHandler.handleUri(fullUrl)`; tente une redirection IDE si disponible. | moyenne | Confirme la présence d’un mécanisme callback local “générique” (VSCode/JetBrains/CLI) distinct du port fixe 1455 du flow Codex. |
| config | `research/cline-main/src/config.ts` | `ClineEndpoint.loadEndpointsFile()` / `EndpointsFileSchema` | Charge et valide `~/.cline/endpoints.json` (ou fichier bundlé) avec `appBaseUrl/apiBaseUrl/mcpBaseUrl`; si non initialisé, safety fallback “selfHosted”. | faible | Prouve un point d’accès local (`~/.cline`) pour config enterprise + potentiel routage endpoints internes. |

---

## 4) Faits — Artefacts locaux `/home/kidpixel/.cline` (à remplir)

### 4.1 Inventaire fichiers (métadonnées)

Constats factuels (lecture seule, **aucun contenu de logs/messages n’a été dumpé**) :

**Top-level**

| Chemin | Taille approx. | Nature | Observation (sans secret) | Sensibilité |
|---|---:|---|---|---|
| `/home/kidpixel/.cline/cline-plugin.log` | ~49.8 MB | log | Log “plugin/extension”. Les marqueurs `usage/tokens/auth` n’y apparaissent pas (comptage, pas d’extraits). | élevée (log) |
| `/home/kidpixel/.cline/cline-core-service.log` | ~8.1 MB | log | Log “core service”. Présence de marqueurs `usage/tokens` **et** de marqueurs auth (`access_token`, `refresh_token`, `Authorization`, etc.) ; à traiter comme **hautement sensible**. | critique (log) |
| `/home/kidpixel/.cline/data/` | n/a | dossier | Racine des états, settings, secrets, tâches. | moyenne |
| `/home/kidpixel/.cline/skills/` | n/a | dossier | Répertoire skills local. Non exploré ici. | faible |

**Sous `data/` (fichiers repérés)**

| Chemin | Taille (bytes) | Type | Observation (sans secret) | Sensibilité |
|---|---:|---|---|---|
| `/home/kidpixel/.cline/data/globalState.json` | 3697 | JSON | État global UI/config (provider, baseURL, headers, toggles). | moyenne |
| `/home/kidpixel/.cline/data/secrets.json` | 2294 | JSON | Secrets (API keys + credentials OAuth Codex) ; valeurs non consultées. | critique |
| `/home/kidpixel/.cline/data/settings/cline_mcp_settings.json` | 3193 | JSON | Configuration serveurs MCP (command/args/env/timeout…). | moyenne |
| `/home/kidpixel/.cline/data/state/taskHistory.json` | 36767 | JSON | Historique de tâches avec champs `tokensIn/tokensOut/totalCost`. | moyenne |
| `/home/kidpixel/.cline/data/tasks/<taskId>/api_conversation_history.json` | 78 KB → 705 KB | JSON | Historique conversation API (probablement prompts/réponses) ; **non lu**. | critique |
| `/home/kidpixel/.cline/data/tasks/<taskId>/ui_messages.json` | 100 KB → 1.27 MB | JSON | Messages UI (texte) ; **non lu**. | critique |
| `/home/kidpixel/.cline/data/tasks/<taskId>/task_metadata.json` | 456 B → 3.8 KB | JSON | Métadonnées de tâche (env/files/model_usage). | moyenne |
| `/home/kidpixel/.cline/data/cache/openrouter_models.json` | 266931 | JSON | Cache des modèles OpenRouter (mapping id → metadata). | faible |
| `/home/kidpixel/.cline/data/cache/vercel_ai_gateway_models.json` | 91202 | JSON | Cache des modèles Vercel AI Gateway (id → metadata, inclut `thinkingConfig`). | faible |
| `/home/kidpixel/.cline/data/cache/mcp_marketplace_catalog.json` | 2077732 | JSON | Catalogue marketplace MCP (items + readmeContent). | faible |
| `/home/kidpixel/.cline/data/locks.db` | 24576 | SQLite? | Locking local ; non inspecté. | moyenne |

**Fichier attendu par le code Cline**

- `/home/kidpixel/.cline/endpoints.json` : **absent** sur cette machine (constat local). Le code `research/cline-main/src/config.ts` mentionne ce fichier pour le mode self-hosted ; ici il n’est pas initialisé.

### 4.2 Schémas JSON pertinents (clés/structures)

Objectif : identifier des **structures** utiles (config, routing, tokens accounting) sans jamais exposer de valeurs.

#### 4.2.1 `globalState.json` (top-level keys)

Clés observées (extraits de clés, sans valeurs) :

- `actModeApiProvider`, `planModeApiProvider`
- `actModeApiModelId`, `planModeApiModelId`
- `openAiBaseUrl`, `openAiHeaders`
- `workspaceRoots`, `primaryRootIndex`
- `mcpDisplayMode`, `mcpResponsesCollapsed`
- `useAutoCondense`, `autoApprovalSettings`

#### 4.2.2 `secrets.json` (top-level keys + schéma interne OAuth Codex)

Top-level keys :

- `openAiApiKey`
- `openRouterApiKey`
- `openai-codex-oauth-credentials`

`openai-codex-oauth-credentials` est une **string JSON** ; une fois parsée, elle contient un objet avec les clés suivantes (valeurs non consultées) :

- `access_token`
- `refresh_token`
- `expires`
- `accountId`
- `type`

#### 4.2.3 `cline_mcp_settings.json` (structure MCP)

Structure : `{ "mcpServers": { ... } }`.

Serveurs déclarés (noms) :

- `context7`
- `fast-filesystem`
- `filesystem-agent`
- `json-query`
- `photomaton-postgres`
- `redis-signal-mcp-server`
- `ripgrep-agent`
- `sequential-thinking`
- `shrimp-task-manager`
- `switchbot-postgres`

Chaque entrée serveur est un objet contenant typiquement : `type`, `command`, `args`, `env`, `timeout` (et parfois `autoApprove`).

#### 4.2.4 `taskHistory.json` (structure)

Type : array. Clés par entrée (sans valeurs) :

- `id`, `ulid`, `ts`
- `cwdOnTaskInitialization`, `size`
- `modelId`
- `tokensIn`, `tokensOut`, `totalCost`
- `cacheReads`, `cacheWrites`

#### 4.2.5 `data/tasks/<taskId>/task_metadata.json`

Top-level keys :

- `environment_history`
- `files_in_context`
- `model_usage`

`model_usage` : array ; le premier élément observé est un objet avec clés :

- `mode`
- `model_id`
- `model_provider_id`
- `ts`

#### 4.2.6 `data/tasks/<taskId>/*history*` (schéma minimal)

Sans lecture de contenu :

- `api_conversation_history.json` : array d’objets `{ role, content }`
- `ui_messages.json` : array d’objets contenant notamment `type`, `say`, `text`, `ts`, `files`, `images`, `modelInfo`

#### 4.2.7 `data/cache/*models*.json` (schéma)

`openrouter_models.json` : objet `model_id → { contextWindow, maxTokens, inputPrice, outputPrice, supportsImages, supportsPromptCache, ... }`.

`vercel_ai_gateway_models.json` : objet `model_id → { contextWindow, maxTokens, inputPrice, outputPrice, supportsPromptCache, thinkingConfig, cacheReadsPrice, cacheWritesPrice, ... }`.

#### 4.2.8 `mcp_marketplace_catalog.json`

Top-level key : `items` (array, 185 items). Un item contient (clés) : `name`, `mcpId`, `githubUrl`, `tags`, `requiresApiKey`, `readmeContent`, `downloadCount`, etc.

### 4.3 Présence de champs “usage/tokens” (si existants)

Constats (comptages uniquement, sans extraits) :

1) **Dans les JSON de `data/tasks/`**

- Aucune occurrence des clés `"usage"`, `"prompt_tokens"`, `"completion_tokens"`, `"total_tokens"` dans les fichiers JSON de tâches inspectés via recherche globale (niveau chaîne de caractères).

2) **Dans `taskHistory.json`**

- Présence explicite de `tokensIn`, `tokensOut`, `totalCost` (5 entrées dans ce snapshot). C’est, à ce stade, la meilleure source structurée pour un “token accounting” **sans introspection du contenu**.

3) **Dans les logs**

- `cline-core-service.log` contient des occurrences de `usage`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `tokensIn`, `tokensOut`.
- Le même fichier contient aussi des marqueurs auth (`access_token`, `refresh_token`, `Authorization`, `Bearer`, `Set-Cookie`).

Conclusion : **ne pas miner ce log** pour extraire des tokens tant qu’on n’a pas une stratégie de redaction outillée (par ex. extraction “keys only” et suppression systématique des lignes contenant `access_token/refresh_token/Authorization/Set-Cookie`).

---

## 5) Inférences / Impacts (basées sur les faits ci-dessus)

### 5.1 Ce que l’on peut affirmer sans spéculation

1) **Stockage OAuth Codex présent localement**

- Le fichier `/home/kidpixel/.cline/data/secrets.json` contient la clé `openai-codex-oauth-credentials`.
- Cette clé est une string JSON ; son schéma interne inclut `access_token` et `refresh_token` (valeurs non consultées).

Impact : sur cette machine, il existe une surface d’exposition “fichier local” pour des credentials OAuth ; toute intégration doit considérer `secrets.json` comme **hautement sensible** et l’exclure explicitement.

2) **Endpoints self-hosted non configurés localement**

- `/home/kidpixel/.cline/endpoints.json` est absent.

Impact : on ne peut pas compter sur un mécanisme “endpoints.json” pour rerouter Cline vers un backend custom sur cet hôte (constat local).

3) **Token accounting agrégé présent, sans lire de prompts**

- `/home/kidpixel/.cline/data/state/taskHistory.json` expose `tokensIn`, `tokensOut`, `totalCost` au niveau “tâche”.

Impact : c’est un point d’intégration solide pour un dashboard: métriques utilisables sans parsing de conversations.

4) **Logs core service : métriques + auth dans le même flux**

- `cline-core-service.log` contient à la fois `usage/tokens*` et des marqueurs auth.

Impact : extraire des tokens depuis ce log est techniquement possible mais à risque élevé ; il faut un pipeline de redaction strict, sinon c’est un vecteur de fuite.

### 5.2 Ce que cela implique pour “Kimi Proxy ↔ OAuth Codex”

- Kimi Proxy ne peut pas “récupérer” les tokens OAuth Codex sans lire un secret local ; cela n’est pas acceptable pour un mode d’observation.
- Sans modification côté Cline et sans MITM, Kimi Proxy ne peut pas compter les tokens en inspectant le trafic Codex “en transit”.
- Le chemin le plus sûr pour obtenir des métriques reste l’export **déjà structuré** (`taskHistory.json`), ou une future instrumentation Cline qui expose uniquement des nombres (pas de payload).
---

## 6) Options d’intégration Kimi Proxy (sans MITM)

| Option | Pré-requis factuel | Ce que Kimi Proxy verrait | Comptage tokens possible | Risques | Verdict |
|---|---|---|---|---|---|
| A) BaseURL OpenAI-compatible (providers “classiques”, hors Codex subscription) | `globalState.json` contient `openAiBaseUrl` et `openAiHeaders` | Requêtes/réponses HTTP (payload) | ✅ oui (tiktoken +/ou `usage`) | compat providers, mapping modèles | ✅ faisable (mais ne couvre pas Codex subscription) |
| B) Proxy système HTTP(S) (env vars) | `research/cline-main/src/shared/net.ts` supporte proxy env | CONNECT/TLS sans MITM: hôte/port, pas de contenu | ❌ non (payload non visible) | valeur limitée | ⚠️ utile pour connectivité, pas pour tokens |
| C) Comptage via ledger local Cline (`taskHistory.json`) | `taskHistory.json` contient `tokensIn/tokensOut/totalCost` | Nombres agrégés par tâche | ✅ oui (agrégé) | parsing de fichiers locaux, format changeant | ✅ faisable (recommandé en premier) |
| D) Comptage via logs internes | `cline-core-service.log` contient `usage/tokens*` | potentiellement des métriques (et d’autres données) | ✅ oui (si redaction fiable) | **critique**: mélange avec marqueurs auth | ❌ déconseillé (sauf pipeline redaction) |
| E) Instrumentation Cline (export “usage-only”) | Preuve côté code: `normalizeUsage()` existe | Nombres (usage) exportés vers localhost | ✅ oui (fin et sûr) | nécessite patch Cline | ⚠️ faisable mais hors scope “lecture seule” |

---

## 7) Risques & mitigations

### 7.1 Risques majeurs

1) **Fuite de secrets OAuth / headers auth**

- Sources sensibles identifiées: `secrets.json` et `cline-core-service.log`.

2) **Exposition de contenu conversationnel**

- Sources sensibles: `data/tasks/*/api_conversation_history.json` et `data/tasks/*/ui_messages.json`.

3) **Fragilité de parsing**

- Les formats `.cline` et les schémas JSON peuvent évoluer (version extension).

### 7.2 Mitigations concrètes

- Interdire explicitement la lecture de `secrets.json` et des logs dans tout outil d’analyse automatisée.
- Pour l’ingestion `taskHistory.json`: extraire uniquement `{ id, ts, modelId, tokensIn, tokensOut, totalCost, cacheReads, cacheWrites }` et ignorer toute clé de type `task`.
- Implémenter un “mode lecture seule” avec allowlist de chemins et filtrage strict.
- Ajouter une stratégie de compat: détection version (`clineVersion` via `globalState.json`) + migrations.
---

## 8) Recommandation finale et prochaines étapes

### Recommandation

Si l’objectif est le **suivi tokens/coût** sans MITM et sans toucher à OAuth:

1) **Démarrer par l’option C (ledger local)**: importer `taskHistory.json` dans Kimi Proxy Dashboard comme source de métriques.
2) Garder `secrets.json`, les logs et les historiques de conversation **hors périmètre**.

### Prochaines étapes (Phase 4 → implémentation)

1) Définir un “importer” lecture seule côté Kimi Proxy:

- Entrée: `/home/kidpixel/.cline/data/state/taskHistory.json`
- Sortie: table SQLite (ou endpoint) “cline_task_usage” avec les champs token/cost.

2) Ajouter un écran/section dashboard “Cline (local)” affichant:

- tokens in/out par tâche
- cacheReads/cacheWrites si exploitable
- modèle/provider (si présent, sans lire de prompt)

3) Optionnel: proposer un mode “Cline patch” qui exporte uniquement `normalizeUsage()` vers localhost (aucun payload, aucun secret).

