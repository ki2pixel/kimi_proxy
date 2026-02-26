---
title: "RCA + plan: timeouts MCP ripgrep-agent (-32001) via scripts/mcp_bridge.py"
date: "2026-02-26"
status: "draft"
---

## TL;DR (symptôme → cause → fix)

- **Symptôme côté IDE/Cline**: erreurs récurrentes `MCP error -32001: Request timed out` sur l’outil `ripgrep-agent` après quelques appels.
- **Signal runtime bridge**: dans `/tmp/kimi-proxy/mcp-bridge-filesystem.jsonl`, on voit `tools/call` avec **réponse OK** (id=5,6) puis à partir d’un appel (id=7) **plus aucune réponse serveur** et uniquement des `notifications/cancelled` ~**60s** après chaque requête.
- **Cause racine confirmée**: le bridge Python lit `child.stdout` avec `StreamReader.readline()` et la **limite asyncio par défaut est 65536 bytes** (cf. signature `create_subprocess_exec(..., limit=65536)`).
  - Un `tools/call` qui produit une réponse JSON-RPC **très volumineuse** (ex: résultats rg sur un repo entier) génère **une ligne JSON unique** (JSON stringify) pouvant dépasser 64KB.
  - Résultat: `asyncio.exceptions.LimitOverrunError` → `ValueError: Separator is not found, and chunk exceed the limit` dans `_pipe_child_stdout_jsonrpc_only()`.
  - Le **task stdout** du relay tombe en erreur (non supervisé), donc **plus rien n’est forwardé vers stdout**, le client attend puis **timeout + cancel**.

## Preuves (repro locale)

### Repro contrôlée

Harness stdio (bridge → ripgrep-agent) avec une recherche volontairement “large”:

- Commande (résumé):
  - `initialize`, `tools/list`, puis `tools/call advanced-search` sur `/home/kidpixel/kimi-proxy` avec `pattern="import"` et `maxResults=5000`.

### Trace d’erreur observée

Dans stderr du bridge:

```text
asyncio.exceptions.LimitOverrunError: Separator is not found, and chunk exceed the limit
...
ValueError: Separator is not found, and chunk exceed the limit
```

Ce stacktrace pointe sur:

- `scripts/mcp_bridge.py::_pipe_child_stdout_jsonrpc_only()`
- `line = await stream.readline()`

## Hypothèses secondaires (non bloquantes)

- **Cold start `npx -y mcp-ripgrep`**: peut contribuer à une latence initiale, mais ne suffit pas à expliquer le basculement “OK → plus aucune réponse” après un gros appel.
- **Charge / requêtes non bornées**: amplifie la probabilité de dépasser 64KB (réponse JSON unique).
- **Timeout client à 60s**: visible comme `notifications/cancelled` → symptôme, pas la cause.

## Correctifs proposés (priorisés)

### S0 — Stopper l’hémorragie (robustesse bridge)

1. **Augmenter la limite `limit=`** lors de `asyncio.create_subprocess_exec` en stdio-relay (ex: 1–8MB) pour tolérer des réponses raisonnables.
2. **Superviser le task stdout**:
   - inclure `stdout_task` dans le `asyncio.wait()` principal
   - si `stdout_task` termine avec exception → log clair en stderr + terminer le child + exit non-zero
   - objectif: éviter les timeouts silencieux et rendre l’échec immédiat.
3. (Optionnel) **Message d’erreur explicite** dans stderr (sans polluer stdout) indiquant “réponse trop grosse / augmenter limite / borner maxResults”.

### S1 — Réduire la probabilité (bornage + préflight)

1. **Bornage côté bridge (ripgrep-agent uniquement)**: intercepter `tools/call` et appliquer des garde-fous configurables:
   - clamp `maxResults`
   - forcer `showFilenamesOnly=true` au-delà d’un seuil
   - option “soft cap” sur taille de réponse (truncate) avec message explicite (à discuter car peut casser attentes).
2. **Préflight / warmup**:
   - option pour faire un `tools/list` au démarrage (ou une recherche minimale) afin de vérifier la chaîne stdio avant usage.

### S2 — Structurel (mode résilient)

1. **Observabilité**: événements JSONL dédiés “bridge_error” (metadata-only) pour exceptions relay.
2. **Retry/backoff** côté client/IDE (si support) ou côté bridge (reconnexion contrôlée).
3. **Mode secours automatique**:
   - si ripgrep-agent est indisponible → basculer vers `rg` local (shell) via un runbook/documentation.

## Impacts / compat

- Ne doit pas impacter les serveurs gateway HTTP.
- Attention: augmenter `limit=` augmente la mémoire potentielle; choisir un défaut raisonnable + config via env.

## Fichiers concernés

- `scripts/mcp_bridge.py` (S0/S1/S2)
- `cline_mcp_settings.json`, `mcp_config.json`, `config.yaml` (timeouts + monitoring log path distinct)
- `docs/troubleshooting/MCP_Bridge_Stdio_Servers.md` (runbook + limites + garde-fous)
