# MCP Pruner (SWE‑Pruner) — Spécification d’interface (Lot A1)

## TL;DR
Cette spécification définit le **contrat d’un serveur MCP “Pruner”** (HTTP local, JSON‑RPC 2.0 sur `/rpc`) qui **réduit du texte au niveau ligne** (code/logs/docs) en fonction d’un `goal_hint`, tout en garantissant **transparence** (annotations + marqueurs) et **recovery** (récupération ciblée des lignes brutes).

Lot C1 (harmonisation): ce document précise la forme **canonique** des annotations et des markers, le protocole de recovery (règles de numérotation, erreurs), et les garde‑fous “fail‑open” pour éviter le sur‑pruning.

---

## 1) Problème (problem‑first)
Vous avez une requête `/chat/completions` dont le contexte grossit vite (fichiers, logs, sorties d’outils). Vous voulez réduire les tokens **sans résumer** et sans perdre la possibilité de vérifier ce qui a été supprimé.

Le pruner doit donc:

- **Élaguer** de façon déterministe et “task‑aware” (via `goal_hint`).
- **Ne jamais être un filtre destructif**: il doit laisser des traces (markers/annotations) et permettre la **récupération**.
- Rester **local‑first par défaut**: aucun appel réseau externe; backend cloud uniquement en opt‑in.

---

## 2) Portée et invariants

### 2.1 Objectifs
- Pruning “ligne par ligne” sur `text` (source: `code` | `logs` | `docs`).
- Transparence: retour d’annotations structurées + marqueurs optionnels dans le texte pruné.
- Recovery: récupération d’extraits bruts (plages de lignes) à partir d’un `prune_id`.
- Garde‑fous: `max_prune_ratio`, `min_keep_lines`, timeouts, et fallback no‑op.

### 2.2 Non‑objectifs (A1)
- Pas d’implémentation d’algorithme (LLM/ONNX/etc.).
- Pas de persistance durable (DB) requise dans A1; uniquement la définition du contrat.

### 2.3 Invariants fonctionnels (à respecter par toute implémentation)
1. **Ordre préservé**: les lignes conservées restent dans l’ordre original.
2. **Pas de sur‑pruning**: ne jamais dépasser `max_prune_ratio` ni descendre sous `min_keep_lines`.
3. **Fail‑open**: sur timeout/erreur, retourner un résultat utilisable (typiquement no‑op: `pruned_text == text`).
4. **Recovery best‑effort**: si `prune_id` inconnu/expiré, l’erreur doit être explicite et actionnable.

---

## 3) Transport MCP (HTTP local)

### 3.1 Endpoint
- **HTTP POST**: `http://127.0.0.1:<PORT>/rpc`
- Protocole: **JSON‑RPC 2.0**

> Alignement Kimi Proxy: le forwarder existant (`src/kimi_proxy/proxy/mcp_gateway_rpc.py`) forwarde des payloads JSON‑RPC bruts vers `.../rpc`.

### 3.2 Méthodes MCP minimales attendues
Pour compatibilité avec les serveurs MCP HTTP déjà utilisés dans ce repo (compression, sequential-thinking, fast-filesystem, json-query), le serveur pruner doit supporter:

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

Optionnel (mais recommandé):

- `resources/list`, `resources/templates/list`, `prompts/list` (retourner des listes vides)
- `health` (legacy JSON‑RPC)
- `GET /health` (health HTTP simple)

---

## 4) Tools MCP (contrat)

### 4.0 `tools/list` — schemas (JSON Schema)
Le serveur doit exposer `tools/list` et retourner des `inputSchema` conformes.

Structure attendue (résumé):

```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "prune_text",
        "description": "...",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
      }
    ]
  },
  "id": 1
}
```

#### `prune_text.inputSchema`
```json
{
  "type": "object",
  "properties": {
    "text": {"type": "string"},
    "goal_hint": {"type": "string"},
    "source_type": {"type": "string", "enum": ["code", "logs", "docs"]},
    "options": {
      "type": "object",
      "properties": {
        "max_prune_ratio": {"type": "number", "minimum": 0, "maximum": 1},
        "min_keep_lines": {"type": "integer", "minimum": 0},
        "timeout_ms": {"type": "integer", "minimum": 1},
        "annotate_lines": {"type": "boolean"},
        "include_markers": {"type": "boolean"}
      },
      "required": ["max_prune_ratio", "min_keep_lines", "timeout_ms", "annotate_lines", "include_markers"],
      "additionalProperties": false
    }
  },
  "required": ["text", "goal_hint", "source_type", "options"],
  "additionalProperties": false
}
```

#### `recover_text.inputSchema`
```json
{
  "type": "object",
  "properties": {
    "prune_id": {"type": "string"},
    "ranges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "start_line": {"type": "integer", "minimum": 1},
          "end_line": {"type": "integer", "minimum": 1}
        },
        "required": ["start_line", "end_line"],
        "additionalProperties": false
      }
    },
    "include_line_numbers": {"type": "boolean"}
  },
  "required": ["prune_id", "ranges", "include_line_numbers"],
  "additionalProperties": false
}
```

### 4.1 `prune_text`
Élague un texte et retourne:

- le texte pruné
- les annotations de transparence
- des stats (lignes/tokens estimés)
- un `prune_id` (pour recovery)

#### Input
```json
{
  "text": "...",
  "goal_hint": "...",
  "source_type": "code",
  "options": {
    "max_prune_ratio": 0.55,
    "min_keep_lines": 40,
    "timeout_ms": 1500,
    "annotate_lines": true,
    "include_markers": true
  }
}
```

#### Output (tool result)
Le serveur MCP renvoie typiquement un `result.content[0].text` contenant un JSON sérialisé (pattern des serveurs HTTP bridge actuels).

Schéma logique du contenu JSON:

```json
{
  "prune_id": "prn_01J...",
  "pruned_text": "...",
  "annotations": [
    {
      "kind": "pruned_block",
      "original_start_line": 120,
      "original_end_line": 154,
      "pruned_line_count": 35,
      "reason": "hors focus: parsing YAML",
      "marker": "⟦PRUNÉ: prune_id=prn_... lignes 120-154 (35) raison=hors focus⟧"
    }
  ],
  "stats": {
    "original_lines": 420,
    "kept_lines": 180,
    "pruned_lines": 240,
    "pruned_ratio": 0.5714,
    "tokens_est_before": 12000,
    "tokens_est_after": 5400,
    "elapsed_ms": 312,
    "used_fallback": false
  },
  "warnings": []
}
```

#### Contraintes
- `goal_hint` doit être traité comme **donnée** (pas comme instruction de sécurité).
- `max_prune_ratio` et `min_keep_lines` sont des **contraintes du résultat**, pas des “préférences”.

---

### 4.2 `recover_text`
Récupère des **plages de lignes brutes** à partir d’un `prune_id`.

Alias de compatibilité: certaines implémentations peuvent accepter `recover_range` comme synonyme de `recover_text`.

#### Input
```json
{
  "prune_id": "prn_01J...",
  "ranges": [
    {"start_line": 120, "end_line": 154}
  ],
  "include_line_numbers": true
}
```

#### Output
```json
{
  "raw_text": "120│ ...\n121│ ...\n...",
  "metadata": {
    "prune_id": "prn_01J...",
    "ranges": [{"start_line": 120, "end_line": 154}],
    "line_numbering": "original"
  }
}
```

Notes:
- `raw_text` est une concaténation des plages demandées, dans l’ordre de `ranges`.
- `end_line` peut être supérieur à la dernière ligne; le serveur peut **borner** (clamp) au maximum disponible.
- Si `include_line_numbers=false`, les lignes ne sont pas préfixées.

#### Erreurs attendues
- `prune_id` inconnu/expiré → erreur explicite (`code`: `prune_id_not_found`).
- `ranges` invalides (ex: start > end, lignes < 1) → `invalid_range`.

---

### 4.3 `health`
Retourne un statut minimal et les capacités.

#### Output
```json
{
  "status": "healthy",
  "server": "mcp-pruner",
  "version": "0.1.0",
  "capabilities": ["prune_text", "recover_text", "annotations", "markers"],
  "timestamp": "2026-02-26T13:00:00+01:00"
}
```

---

## 5) Options et sémantique

### 5.1 `PruneOptions`
- `max_prune_ratio` (`float`, 0..1): ratio max de lignes supprimées.
- `min_keep_lines` (`int`, >= 0): minimum de lignes à conserver.
- `timeout_ms` (`int`, > 0): timeout “soft” pour l’opération.
- `annotate_lines` (`bool`): si `true`, préfixer les lignes conservées par `N│` (numéro de ligne original).
- `include_markers` (`bool`): si `true`, insérer une ligne marqueur pour chaque bloc pruné.

Table de lecture rapide:

| Option | Effet sur `pruned_text` | Effet sur `annotations` |
| --- | --- | --- |
| `annotate_lines=true` | Les **lignes conservées** deviennent `N│ <ligne>` | Aucun (inchangé) |
| `include_markers=true` | Ajoute des lignes `⟦PRUNÉ: ...⟧` | Le champ `marker` doit correspondre |
| `include_markers=false` | Aucun marker inséré | Le champ `marker` reste utile pour audit |

### 5.2 Numérotation de lignes
- Les numéros de ligne sont **1‑indexés** et correspondent au texte original.
- Format recommandé: `"{line_no}│ {content}"`.

---

## 6) Transparence: annotations + marqueurs

### 6.1 Annotation (`pruned_block`)
Chaque bloc supprimé doit être représenté par une annotation structurée:

- `original_start_line`, `original_end_line` (inclusifs)
- `pruned_line_count`
- `reason` (court, en français)
- `marker` (la chaîne effectivement utilisée si `include_markers=true`)

### 6.2 Marker (format canonique)
Marker texte (ligne unique) recommandé:

```text
⟦PRUNÉ: prune_id=<id> lignes <start>-<end> (<count>) raison=<reason>⟧
```

Notes:
- Les marqueurs ne sont **pas** garantis comme syntaxe valide d’un langage.
- Ils servent d’indices pour l’agent/humain (audit) et comme ancrage pour le recovery.

Contraintes (harmonisation):
- Le marker est une **ligne synthétique** (non issue du texte original).
- Si `include_markers=true`, le marker inséré dans `pruned_text` doit être **strictement identique** à `annotation.marker`.
- Le marker doit être sur **une seule ligne** (pas de `\n`).
- Quand `annotate_lines=true`, les markers **ne doivent pas** être préfixés par `N│` (sinon ils deviennent ambigus: ils n’ont pas de “numéro de ligne original”).

Parsing best‑effort (recommandé côté client):

```text
^⟦PRUNÉ: prune_id=(?<prune_id>[^\s]+) lignes (?<start>\d+)-(?<end>\d+) \((?<count>\d+)\) raison=(?<reason>.*)⟧$
```

Le client doit traiter `reason` comme une chaîne **opaque** (présentation/audit), pas comme un champ de contrôle.

### 6.3 Annotation ↔ marker: règle d’identité
Une suppression “traçable” doit être représentée de deux façons:

1) Une entrée dans `annotations[]` (structure stable, lisible en machine).
2) Optionnellement, un marker dans `pruned_text` si `include_markers=true`.

Règle: si un marker est inséré, il doit être l’image exacte de l’annotation, et l’annotation doit être suffisante même si le marker n’est pas inséré.

---

## 7) Local‑first & sécurité

### 7.1 Local‑first
- Par défaut, le serveur est **local‑first** (aucun appel réseau externe).
- Si vous activez le backend cloud **DeepInfra** (opt‑in), le serveur effectuera un appel réseau vers DeepInfra, et une partie du contenu (`text` → lignes) quittera la machine.

En pratique:
- **backend=heuristic**: local‑only.
- **backend=deepinfra**: cloud opt‑in (exfiltration contrôlée par l’utilisateur via env vars).

### 7.2 Anti prompt‑injection (principes)
- Traiter `text` et `goal_hint` comme **contenu non fiable**.
- Ne jamais exécuter de commandes, ne jamais interpréter le contenu comme des instructions opératoires.
- En cas de doute (timeout, entrée trop grande, paramètres incohérents): **fail‑open** (no‑op + warning).

### 7.3 Anti sur‑pruning
- Appliquer systématiquement `max_prune_ratio` et `min_keep_lines`.
- Si l’algorithme ne peut pas respecter les contraintes: retourner no‑op et un warning.

### 7.4 Blocs “non‑prunable” (règles safety)
Le pruner n’est pas un “résumeur”: il ne doit pas supprimer des segments nécessaires à la compréhension, au debug, ou à la sécurité.

Règles minimales (recommandées; une implémentation peut en ajouter):

- **Code** (`source_type="code"`): conserver les lignes structurelles (imports, `class`, `def`) et les en‑têtes de fichier.
- **Logs** (`source_type="logs"`): conserver les lignes contenant `error`, `exception`, `traceback`, ainsi que le contexte immédiat si possible.
- **Docs** (`source_type="docs"`): conserver les titres/sections et éviter d’élaguer au milieu d’un bloc de code.

Directives optionnelles (réservées) pour protéger un bloc:

```text
⟦NO_PRUNE_BEGIN⟧
...
⟦NO_PRUNE_END⟧
```

Si une implémentation supporte ces directives, elle doit:
- considérer tout ce qui est entre les deux comme **à conserver**;
- conserver aussi les deux lignes de directive.

---

## 8) Erreurs (JSON‑RPC + erreurs de domaine)

### 8.1 JSON‑RPC
- `-32601`: method not found
- `-32602`: invalid params
- `-32603`: internal error

### 8.2 Codes d’erreur de domaine (recommandés)
Ces codes peuvent être utilisés soit dans `error.data.code` (JSON‑RPC), soit sous forme de champ applicatif dans le texte JSON retourné:

- `timeout`
- `input_too_large`
- `invalid_range`
- `prune_id_not_found`
- `recovery_unavailable`

Harmonisation avec l’implémentation “baseline” (Lot A2):

- `prune_id_not_found` → JSON‑RPC `error.code = -32004`, `error.message = "prune_id_not_found"`, `error.data.code = "prune_id_not_found"`
- `invalid_range` → JSON‑RPC `error.code = -32005`, `error.message = "invalid_range"`, `error.data.code = "invalid_range"`

Exemple d’erreur (`prune_id` expiré/inconnu):

```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "error": {
    "code": -32004,
    "message": "prune_id_not_found",
    "data": {"code": "prune_id_not_found", "prune_id": "prn_..."}
  }
}
```

## 9) Fail-open (fallback raw)
Dans tous les cas où le serveur ne peut pas produire un pruning correct (entrée trop grande, timeout, contraintes impossibles à respecter, erreur interne), le serveur doit **laisser passer** le texte brut.

Contrat recommandé pour un fallback no‑op:

- `pruned_text == text`
- `annotations == []`
- `stats.used_fallback == true`
- `warnings` contient au moins un code (ex: `input_too_large`, `timeout`, `constraints_unmet`)
- `prune_id` est tout de même renvoyé, et doit permettre un recovery tant que le TTL n’est pas dépassé

---

## 10) Exemples testables

### 10.1 `tools/list`

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  http://127.0.0.1:8006/rpc | jq
```

### 10.2 `tools/call` → `prune_text`

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"prune_text",
      "arguments":{
        "text":"L1\nL2\nL3\nL4",
        "goal_hint":"garder L1",
        "source_type":"docs",
        "options":{
          "max_prune_ratio":0.75,
          "min_keep_lines":1,
          "timeout_ms":1500,
          "annotate_lines":true,
          "include_markers":true
        }
      }
    }
  }' \
  http://127.0.0.1:8006/rpc | jq -r '.result.content[0].text' | jq
```

### 10.3 Recovery après pruning

1) Récupérer le `prune_id` depuis la réponse `prune_text`.
2) Appeler `recover_text`:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"recover_text",
      "arguments":{
        "prune_id":"prn_...",
        "ranges":[{"start_line":1,"end_line":50}],
        "include_line_numbers":true
      }
    }
  }' \
  http://127.0.0.1:8006/rpc | jq -r '.result.content[0].text' | jq
```

## 11) Golden Rule
Le pruner doit être **audit‑friendly**: chaque suppression doit être traçable (annotation + marker optionnel) et **récupérable** (recovery), et en cas d’échec il doit **laisser passer** le texte brut plutôt que casser le pipeline.

---

## 12) Notes d’alignement implémentation (A2)

État vérifié dans `src/kimi_proxy/features/mcp_pruner/server.py`.

- Serveur HTTP local FastAPI sur `/rpc` (JSON-RPC 2.0) + `GET /health`.
- Handshake MCP minimal implémenté: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`.
- Alias supporté: `recover_range` est accepté comme synonyme de `recover_text`.
- Outil `health` disponible en mode `tools/call` et en méthode JSON-RPC legacy `health`.
- Fallback `input_too_large` actif avec contrat no-op (`pruned_text == text`, `used_fallback=true`, warning explicite).
- Stockage recovery en mémoire avec TTL (`MCP_PRUNER_PRUNE_ID_TTL_S`), sans persistance DB.
- Variables d’environnement supportées:
  - `MCP_PRUNER_HOST`
  - `MCP_PRUNER_PORT`
  - `MCP_PRUNER_MAX_INPUT_CHARS`
  - `MCP_PRUNER_PRUNE_ID_TTL_S`
  - Cache (env > TOML):
    - `MCP_PRUNER_CACHE_TTL_S`
    - `MCP_PRUNER_CACHE_MAX_ITEMS` (alias compat: `MCP_PRUNER_CACHE_MAX_ENTRIES`)
  - Sélection backend pruning (env > TOML):
    - `KIMI_PRUNING_BACKEND` (`heuristic` | `deepinfra`, alias: `cloud`)
  - DeepInfra (cloud opt‑in, secrets uniquement en env):
    - `DEEPINFRA_API_KEY` (obligatoire si backend deepinfra)
    - `DEEPINFRA_ENDPOINT_URL` (optionnel)
    - `DEEPINFRA_TIMEOUT_MS` (optionnel; fallback TOML `mcp_pruner.deepinfra_timeout_ms`)
    - `DEEPINFRA_MAX_DOCS` (optionnel; fallback TOML `mcp_pruner.deepinfra_max_docs`)

---

## 13) Backend DeepInfra (cloud, opt‑in)

### TL;DR
Le pruner est **heuristique et local** par défaut. Si vous avez besoin d’un pruning plus “task‑aware”, vous pouvez activer DeepInfra via `KIMI_PRUNING_BACKEND=deepinfra` et `DEEPINFRA_API_KEY=...`.

Règles importantes:
- **Priorité**: `env > config.toml`.
- **Secrets**: la clé DeepInfra reste **uniquement** en variable d’environnement.
- **Fail‑open**: en cas d’erreur DeepInfra (timeout/401/429/JSON invalide…), le serveur ne crash pas; il retombe sur la baseline heuristique avec `stats.used_fallback=true`.

### Le problème
La baseline heuristique est robuste, mais elle ne “comprend” pas votre objectif. Sur des logs ou du code très longs, elle peut garder trop de bruit ou supprimer des lignes importantes.

DeepInfra ajoute un signal: un reranker score vos lignes en fonction de `goal_hint`, puis le pruner conserve les meilleures lignes **sans violer** `max_prune_ratio` et `min_keep_lines`.

### Activation (env > TOML)

#### ❌ À éviter: mettre des secrets dans `config.toml`
```toml
[mcp_pruner]
backend = "deepinfra"
deepinfra_api_key = "sk-..." # interdit: secrets dans le TOML
```

#### ✅ Recommandé: backend en env, secrets en env
```bash
export KIMI_PRUNING_BACKEND=deepinfra
export DEEPINFRA_API_KEY="sk_deepinfra_..."

# optionnels
export DEEPINFRA_TIMEOUT_MS=20000
export DEEPINFRA_MAX_DOCS=128
```

### Paramètres supportés

#### Sélection backend
- `KIMI_PRUNING_BACKEND`:
  - `deepinfra` (ou alias `cloud`) pour activer DeepInfra.
  - toute autre valeur (ou variable absente) => heuristique, sauf si TOML demande DeepInfra.

Fallback TOML (si env absent):
```toml
[mcp_pruner]
backend = "heuristic" # ou "deepinfra"
deepinfra_timeout_ms = 20000
deepinfra_max_docs = 64
cache_ttl_s = 30
cache_max_entries = 256
```

#### DeepInfra (cloud)
- `DEEPINFRA_API_KEY` (obligatoire si backend deepinfra)
- `DEEPINFRA_ENDPOINT_URL` (optionnel; défaut: `https://api.deepinfra.com/v1/inference/Qwen/Qwen3-Reranker-0.6B`)
- `DEEPINFRA_TIMEOUT_MS` (optionnel; sinon fallback TOML `mcp_pruner.deepinfra_timeout_ms`)
- `DEEPINFRA_MAX_DOCS` (optionnel; sinon fallback TOML `mcp_pruner.deepinfra_max_docs`)

#### Cache (réduction appels cloud)
Le serveur maintient un cache TTL in‑memory pour éviter de reranker deux fois le même contenu.

- `MCP_PRUNER_CACHE_TTL_S` (optionnel; sinon fallback TOML `mcp_pruner.cache_ttl_s`)
- `MCP_PRUNER_CACHE_MAX_ITEMS` (optionnel; sinon fallback TOML `mcp_pruner.cache_max_entries`)
  - Alias compat: `MCP_PRUNER_CACHE_MAX_ENTRIES`

### Ce que vous verrez dans la réponse

#### Champs `stats` (DeepInfra)
En plus des champs standards (`tokens_est_*`, `pruned_ratio`, `elapsed_ms`, `used_fallback`), le backend DeepInfra peut fournir:

- `backend`: `"deepinfra"`
- `deepinfra_latency_ms`: latence rerank (0 en `cache_hit`)
- `deepinfra_docs_scored`: nombre de lignes réellement scorées
- `deepinfra_docs_total`: nombre total de lignes
- `deepinfra_http_status`: `200` en nominal; présent aussi en cas d’erreur HTTP (ex: `429`)
- `deepinfra_cached`: bool (si le résultat provient du cache)
- `tokens_saved_est`: estimation des tokens économisés (`tokens_est_before - tokens_est_after`)
- `cost_estimated_usd`: coût estimé associé aux tokens économisés (formule côté serveur)

#### Warnings (liste non exhaustive)
- `cache_hit`
- `deepinfra_docs_truncated` (si `deepinfra_docs_total > deepinfra_docs_scored`)
- `deepinfra_error` + un code plus précis:
  - `deepinfra_http_error` (HTTP 401/429/etc. ou transport)
  - `deepinfra_parse_error` (JSON inattendu / non-JSON)
  - `deepinfra_config_error` (ex: `DEEPINFRA_API_KEY` absente)

### Exemples testables

#### 1) Vérifier la santé du serveur
```bash
curl -sS http://127.0.0.1:8006/health | jq
```

#### 2) Appeler `prune_text` (backend DeepInfra)
```bash
export KIMI_PRUNING_BACKEND=deepinfra
export DEEPINFRA_API_KEY="sk_deepinfra_..."

curl -sS \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"prune_text",
      "arguments":{
        "text":"L1 keep\nL2 prune\nL3 prune\nL4 keep",
        "goal_hint":"keep",
        "source_type":"docs",
        "options":{
          "max_prune_ratio":0.75,
          "min_keep_lines":1,
          "timeout_ms":1500,
          "annotate_lines":true,
          "include_markers":true
        }
      }
    }
  }' \
  http://127.0.0.1:8006/rpc | jq -r '.result.content[0].text' | jq
```

### Trade-offs (heuristic vs DeepInfra)

| Backend | Appel réseau | Qualité “task‑aware” | Coût | Mode échec |
| --- | --- | --- | --- | --- |
| `heuristic` | Non | Moyenne | 0$ | Pas de dépendance externe |
| `deepinfra` | Oui (opt‑in) | Meilleure sur contextes longs | $ (provider) | **Fail‑open** vers heuristique (`used_fallback=true`) |

## Golden Rule (DeepInfra)
Activez DeepInfra **uniquement** si vous acceptez un appel cloud; gardez les secrets en env, et gardez en tête que le système est conçu pour **ne jamais casser** votre pipeline: en cas d’erreur, il retombe sur l’heuristique.

### ❌ Hypothèse erronée
Le pruner baseline implémente déjà un modèle externe SWE-Pruner/ONNX complet.

### ✅ État réel
Le lot A2 implémente une baseline heuristique locale. Le contrat d’interface reste stable et compatible pour brancher ensuite un moteur de pruning plus avancé.

---

## 14) Troubleshooting démarrage MCP Pruner (incident 2026-02-27)

### TL;DR
Si `start-mcp-servers.sh` annonce un échec pruner alors que le serveur est sain, la cause la plus probable est un **faux négatif de readiness** (démarrage > 2s). Le correctif est une boucle d’attente bornée (12s) avec vérification `kill -0` et diagnostic de log.

### Problème observé
- Symptôme: `Échec du démarrage du serveur MCP Pruner` lors de `./start.sh` ou `./scripts/start-mcp-servers.sh start`.
- Faux indice fréquent: `/tmp/mcp_pruner.log` vide (0 octet).

### Cause racine validée
- L’ancienne logique utilisait `sleep 2` + check port unique.
- Le pruner peut ouvrir le port après ~2.6s selon la charge/imports.
- Résultat: le script échouait trop tôt alors que le serveur devenait disponible juste après.

### Correctif appliqué
Dans `scripts/start-mcp-servers.sh`, `start_pruner_server()`:
- démarre le pruner avec `PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"`;
- attend jusqu’à 12 secondes avec boucle (`check_port` chaque seconde);
- arrête l’attente si le process meurt (`kill -0`);
- en échec réel, affiche un diagnostic actionnable (`tail -n 80 /tmp/mcp_pruner.log`).

### Pourquoi le log peut rester vide
Un `/tmp/mcp_pruner.log` vide n’implique pas un crash:
- `uvicorn` est lancé en `log_level="warning"`;
- `access_log=False`;
- au démarrage nominal, aucune ligne n’est forcément écrite.

### Commandes de vérification recommandées

```bash
./scripts/start-mcp-servers.sh restart
./scripts/start-mcp-servers.sh status

ss -ltn | grep -E ':8001 |:8003 |:8004 |:8005 |:8006 '

curl -sS http://localhost:8006/health | jq
curl -sS -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","clientInfo":{"name":"diag","version":"1.0.0"}}}' \
  http://localhost:8006/rpc | jq
```

### Cas particulier rencontré pendant validation globale
Un échec de `./start.sh` peut venir d’un wrapper shell invalide ou d’un process orphelin sur `:8000`, indépendamment du pruner:
- wrapper corrigé: `start.sh` pointe vers `bin/kimi-proxy`;
- si `:8000` est déjà occupé par un ancien process non référencé, stopper ce process avant la validation.

### Golden Rule (ops)
Pour diagnostiquer un démarrage MCP: **privilégier les probes réseau (`/health`, JSON-RPC `initialize`) et l’état des ports**; ne pas utiliser la taille de `/tmp/mcp_pruner.log` comme signal principal de santé.

---

## 15) Troubleshooting DeepInfra (401/429/timeout/parse)

### TL;DR
Si DeepInfra est instable, vous ne devez pas “réparer” le proxy en urgence: le serveur pruner est déjà **fail‑open**. Votre priorité est d’identifier la cause (clé API, rate limit, timeout) et, si besoin, de **rollback** vers l’heuristique.

### 1) DeepInfra ne s’active pas (reste en heuristique)
Checklist:
- Vérifier `KIMI_PRUNING_BACKEND=deepinfra` (ou `cloud`).
- Si `KIMI_PRUNING_BACKEND` est absent, vérifier le fallback TOML `[mcp_pruner].backend`.

### 2) 401 Unauthorized
Symptômes:
- `warnings` contient `deepinfra_error` + `deepinfra_http_error`.
- `stats.deepinfra_http_status == 401`.

Causes fréquentes:
- `DEEPINFRA_API_KEY` absente ou invalide.

Actions:
- Vérifier que la variable d’environnement est chargée (ex: `.env` → `./scripts/start.sh`).
- Regénérer la clé côté DeepInfra si nécessaire.

### 3) 429 Rate limited
Symptômes:
- `stats.deepinfra_http_status == 429`.
- `warnings` inclut `deepinfra_http_error`.

Actions:
- Réduire la cadence; augmenter le cache TTL (`MCP_PRUNER_CACHE_TTL_S`).
- Réduire la charge par appel en diminuant `DEEPINFRA_MAX_DOCS`.

### 4) Timeout
Symptômes:
- `warnings` contient `deepinfra_http_error` (timeout transport).
- Le résultat est pruné en heuristique avec `stats.used_fallback=true`.

Actions:
- Augmenter `DEEPINFRA_TIMEOUT_MS`.
- Vérifier la connectivité réseau et le DNS.

### 5) JSON invalide / parse error
Symptômes:
- `warnings` contient `deepinfra_parse_error`.

Causes fréquentes:
- Endpoint custom (`DEEPINFRA_ENDPOINT_URL`) renvoie un format incompatible.

Actions:
- Revenir au `DEEPINFRA_ENDPOINT_URL` par défaut.
- Vérifier la réponse brute côté réseau (hors pruner) uniquement si vous savez ce que vous faites.

### 6) Rollback rapide (recommandé)
```bash
export KIMI_PRUNING_BACKEND=heuristic
```

Ou simplement unset la variable (et garder `backend=heuristic` côté TOML).
