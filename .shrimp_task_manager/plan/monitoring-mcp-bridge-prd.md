# PRD — Monitoring simple des requêtes MCP (stdio relay) dans `scripts/mcp_bridge.py`

## TL;DR

Ajouter un **monitoring opt-in** (désactivé par défaut) dans `scripts/mcp_bridge.py` pour les serveurs MCP relayés en **stdio**:

- `filesystem-agent`
- `ripgrep-agent`
- `shrimp-task-manager`

Le monitoring doit:

- **compter** les requêtes JSON-RPC (par méthode) et les réponses
- optionnellement **logger** des événements en **JSONL** vers un fichier (sans jamais polluer `stdout`)
- rester **compatible** avec le relay existant (filtrage anti-bannières/logs sur stdout child)
- rester **léger** (impact perf minimal, parsing JSON best-effort)

## Contexte

Le bridge MCP (`scripts/mcp_bridge.py`) est lancé par l’IDE en stdio. Il relaie:

- `stdin` du client IDE → `stdin` du serveur MCP stdio (child)
- `stdout` du child → `stdout` du client IDE

Et il applique déjà un filtrage strict pour ne pas corrompre le flux JSON-RPC.

## Objectifs

1. **Observabilité locale**: permettre de diagnostiquer facilement les appels JSON-RPC transitant par le bridge.
2. **Zéro pollution de stdout**: le monitoring ne doit jamais écrire autre chose que des messages JSON-RPC sur `stdout`.
3. **Activation simple**: opt-in via variables d’environnement (ou config future), sans modifier les IDE.
4. **Sécurité**: pas d’exposition réseau par défaut.

## Non-objectifs

- Ne pas ajouter de compatibilité IDE supplémentaire (hors monitoring).
- Ne pas implémenter un système complet de métriques Prometheus.
- Ne pas écrire de secrets (tokens, clés) dans les logs.

## Approches envisagées

### Option A (retenue) — Logging fichier + compteurs en mémoire

- Activation via env var.
- Enregistre des événements JSONL vers un fichier (append).
- Maintient des compteurs en mémoire par méthode.
- Écrit un **résumé final** sur `stderr` à l’arrêt (optionnel) pour debugging.

### Option B (non retenue pour cette itération) — Endpoint HTTP de métriques

- Risque de conflits de port (plusieurs instances du bridge), surface d’attaque, complexité.
- Peut être implémenté plus tard côté API Kimi Proxy (meilleur endroit architectural).

## Spécification fonctionnelle

### Événements à monitorer

1. **Client → Server** (messages lus depuis `stdin` du bridge)
2. **Server → Client** (messages lus depuis `stdout` du child)

Pour chaque ligne JSON (best-effort):

- Détecter si c’est un objet JSON-RPC (`jsonrpc == "2.0"`)
- Si `method` présent: requête/notification → incrémenter compteur `method`
- Si `result`/`error` présent: réponse → incrémenter compteur réponses

### Format JSONL (suggestion)

Chaque ligne est un objet JSON:

```json
{
  "ts": "2026-02-25T19:57:00.123Z",
  "server": "filesystem-agent",
  "direction": "client_to_server",
  "type": "request",
  "method": "tools/call",
  "id": 12
}
```

Règles:

- Ne pas inclure `params` (réduire taille + éviter fuite d’info)
- Ne pas inclure `result` (peut être volumineux)
- Ne pas logguer les lignes non-JSON (déjà redirigées vers `stderr` par le bridge)

### Configuration (variables d’environnement)

- `MCP_BRIDGE_MONITORING_ENABLED` ("0"/"1", défaut: "0")
- `MCP_BRIDGE_MONITORING_LOG_PATH` (chemin fichier JSONL, optionnel)
- `MCP_BRIDGE_MONITORING_SUMMARY_ON_EXIT` ("0"/"1", défaut: "1" si monitoring activé)

## Contraintes techniques

- Ne jamais écrire sur `stdout` hors JSON-RPC.
- Éviter le blocage de l’event loop: les écritures fichiers doivent être faites de façon non-bloquante (ex: `asyncio.to_thread` + queue).
- Typage strict Python (pas de `Any`).
- Compatibilité avec le filtrage actuel `*_jsonrpc_only`.

## Sécurité

- Logs: pas de `params`, pas de contenus potentiellement sensibles.
- Chemin log: opt-in uniquement. Documenter que c’est local et peut contenir métadonnées.

## Critères d’acceptation

- Monitoring désactivé par défaut → comportement inchangé.
- Monitoring activé → compteurs mis à jour sans casser le flux JSON-RPC.
- Aucun log sur stdout (tests).
- Fichier JSONL créé et alimenté si `LOG_PATH` fourni.

## Tests

- Tests unitaires: valider que l’activation n’altère pas le filtering JSON-RPC.
- Tests d’intégration (ou unit + mocks): simuler stdin/stdout et vérifier:
  - compteurs incrémentés
  - format JSONL
  - absence de pollution stdout
