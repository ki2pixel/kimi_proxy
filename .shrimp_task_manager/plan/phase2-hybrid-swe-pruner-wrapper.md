# PRD — Architecture hybride SWE‑Pruner : wrapper/intercepteur des outils MCP (Continue/Windsurf/Cline)

## TL;DR
Objectif : implémenter une **couche d’interception unique** qui **prune automatiquement** (conditionnellement) les **sorties des outils MCP existants** — sans exposer de nouveaux outils côté client — afin de réduire la pression sur la fenêtre de contexte (Continue, Windsurf, Cline), avec :

- **Compatibilité totale** : mêmes noms d’outils, mêmes transports (stdio vs gateway HTTP), mêmes formats JSON‑RPC.
- **Pruning conditionnel** : déclenché selon seuils (chars/tokens estimés), configurable et désactivable.
- **Priorité de configuration** : `ENV > config.toml`.
- **Fail‑open** : sur toute erreur du backend pruning, ne jamais casser l’appel outil (retour original + fallback heuristique optionnel).
- **Observabilité** : métriques réduction/latence/fallback/coût, vérifiables (bridge + serveur pruner).

---

## 1) Problème (problem‑first)
Dans les IDE agents (Continue/Windsurf/Cline), la consommation de contexte provient très souvent de **tool outputs volumineux** : lectures de fichiers, recherches ripgrep, dumps JSON, logs. Même si le modèle a un contexte énorme, ces sorties bruyantes dégradent la qualité (lost-in-the-middle) et augmentent les coûts.

Le repo dispose déjà :

- d’un **serveur MCP Pruner** local (`:8006`, JSON‑RPC `/rpc`) avec backends `heuristic` + `deepinfra` (opt-in), cache TTL et métriques.
- d’un **bridge MCP unique côté IDE** : `scripts/mcp_bridge.py` (stdio-relay pour 3 serveurs; gateway-http pour 3 serveurs).
- d’un **MCP Gateway API** côté Kimi Proxy qui forwarde les serveurs HTTP et applique un *observation masking* (troncature head/tail).

Il manque une brique : **pruning task-aware automatique et transparent** appliqué à *tous* les serveurs MCP ciblés, sans changer l’interface publique.

---

## 2) Portée

### 2.1 Serveurs MCP ciblés (contrats inchangés)

**Stdio (bridge relai)**
- `filesystem-agent`
- `ripgrep-agent`
- `shrimp-task-manager`

**Gateway HTTP (via Kimi Proxy /api/mcp-gateway/{server}/rpc)**
- `sequential-thinking`
- `fast-filesystem`
- `json-query`

### 2.2 Invariants non négociables
1. Les outils publics restent inchangés (noms, schémas, réponses JSON‑RPC).
2. Le pruning est **conditionnel** et **désactivable**.
3. Priorité config : **ENV > config.toml**.
4. En cas d’échec : **fail‑open** (ne jamais casser un tool call); fallback heuristique automatique requis.
5. Pas de logs stdout en mode stdio (sinon corruption JSON‑RPC).

### 2.3 Non-objectifs
- Ne pas introduire un nouveau serveur MCP côté client.
- Ne pas changer Continue/Windsurf/Cline (configs existantes doivent continuer à fonctionner).
- Ne pas faire de persistance DB pour la télémétrie (métriques in-memory + endpoints health suffisent).

---

## 3) Architecture cible (hybride)

### 3.1 Point unique d’interception
Le point d’entrée unique côté IDE est `scripts/mcp_bridge.py`.

Stratégie :

- **Pour les serveurs stdio** : intercept/rewrite côté `server_to_client` dans le bridge (là où les lignes JSON‑RPC sortent du child).
- **Pour les serveurs HTTP via gateway** : deux options compatibles
  1) Interception côté bridge (réécriture après réception du JSON-RPC masqué) — simple mais peut perdre du signal si masking a déjà tronqué.
  2) Interception côté Kimi Proxy Gateway (avant masking) — meilleure qualité (prune sur output brut), garde masking comme garde‑fou final.

Décision attendue : adopter (2) pour gateway-http, et garder (1) comme fallback optionnel.

### 3.2 Intercepteur (comportement)
Pour chaque réponse JSON‑RPC correspondant à un `tools/call` :

1) Détecter si `result.content[*].text` contient :
   - un texte brut volumineux, ou
   - un JSON sérialisé volumineux (pattern courant : `text` est un JSON string).
2) Appliquer pruning sur les **string fields** pertinents :
   - si `text` n’est pas du JSON : pruner `text` directement.
   - si `text` est un JSON : parser → traverser récursivement → pruner les strings longues (`content`, `stdout`, `matches[*].line`, etc.) sans casser la structure JSON.
3) Conserver le format de réponse : remplacer uniquement les strings prunées; ne pas changer les clés JSON‑RPC.
4) Ajouter de l’observabilité **sans fuite** : métriques agrégées (counters, latence, ratio), et marqueurs in-band uniquement dans les strings (ex: markers pruner), pas de nouveaux champs requis.

### 3.3 Goal hint & source_type
Le pruner attend `goal_hint` + `source_type`.

Règles :
- `goal_hint` prioritaire via env `KIMI_MCP_PRUNING_GOAL_HINT` (si présent).
- Sinon dérivation best-effort depuis la requête (pattern, path, query) via une table par outil.
- `source_type` best-effort :
  - extensions de fichiers -> `code|docs`.
  - outputs ripgrep -> `code`.
  - outputs task manager / thinking -> `docs`.
  - outputs “diagnostic/logs” -> `logs`.

---

## 4) Configuration (ENV > TOML)

### 4.1 Variables d’environnement (prioritaires)
- `KIMI_MCP_TOOL_PRUNING_ENABLED` (bool; défaut: `0`)
- `KIMI_MCP_TOOL_PRUNING_MIN_CHARS` (int; seuil déclenchement)
- `KIMI_MCP_TOOL_PRUNING_MAX_CHARS_FALLBACK` (int; si pruning backend KO, masking heuristique)
- `KIMI_MCP_TOOL_PRUNING_TIMEOUT_MS` (int; timeout appel pruner)
- `KIMI_MCP_PRUNING_GOAL_HINT` (str; override)

Options transmises au pruner (`prune_text.options`):
- `KIMI_MCP_TOOL_PRUNING_MAX_PRUNE_RATIO`
- `KIMI_MCP_TOOL_PRUNING_MIN_KEEP_LINES`
- `KIMI_MCP_TOOL_PRUNING_ANNOTATE_LINES`
- `KIMI_MCP_TOOL_PRUNING_INCLUDE_MARKERS`

Backend (déjà existant côté pruner) :
- `KIMI_PRUNING_BACKEND` (env > toml côté serveur pruner)

### 4.2 config.toml (fallback)
Ajouter une section dédiée (sans secrets) :

```toml
[mcp_tool_pruning]
enabled = false
min_chars = 4000
timeout_ms = 1500

[mcp_tool_pruning.options]
max_prune_ratio = 0.55
min_keep_lines = 40
annotate_lines = true
include_markers = true
```

---

## 5) Observabilité (obligatoire)

### 5.1 Bridge (stdio)
Métriques agrégées en mémoire (dump summary sur stderr si activé) :
- `pruning_enabled`
- `responses_seen_total`
- `responses_pruned_total`
- `pruner_calls_total`
- `pruner_failures_total`
- `fallback_masked_total`
- `added_latency_ms_total` + p95 best-effort

### 5.2 Serveur pruner
Déjà existant : `GET /health` expose `metrics` (calls_total, deepinfra, fallback_rate, cost_estimated_total_usd).

---

## 6) Risques critiques

1) **Double appels / latence** : chaque tool result peut déclencher un call `pruner`.
   - mitigation : seuil min_chars, timeouts courts, cache TTL côté pruner, allowlist outils.

2) **Boucle involontaire** : si le pruner passait par le bridge.
   - mitigation : le pruner est HTTP direct (`:8006/rpc`) ; exclure explicitement `server_name == "pruner"`.

3) **Rupture JSON-RPC** : modification des champs structuraux.
   - mitigation : ne toucher qu’à des strings; jamais écrire de logs sur stdout.

4) **Régression IDE** : tools/list / initialize prunés accidentellement.
   - mitigation : n’appliquer pruning que sur réponses correspondant à `tools/call`.

---

## 7) Critères d’acceptation
1. Les 6 serveurs MCP ciblés sont wrappés sans nouveaux outils côté client.
2. Continue/Windsurf/Cline gardent la même interface fonctionnelle.
3. Pruning conditionnel, paramétrable, désactivable.
4. ENV > TOML, strict.
5. Fail-open systématique + fallback heuristique.
6. Métriques réduction/latence/coût/fallback disponibles.
7. Suite de tests non-régression verte (stdio + HTTP).

---

## 8) Plan de rollback
- `KIMI_MCP_TOOL_PRUNING_ENABLED=0` (désactivation immédiate).
- Conserver le masking gateway existant en garde-fou.
