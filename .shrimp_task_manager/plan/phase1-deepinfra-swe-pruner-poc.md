# PRD — SWE‑Pruner Cloud via DeepInfra (Architecture hybride unifiée) — Phase 1 (POC minimal)

## TL;DR
Objectif: ajouter un **backend cloud opt‑in** (DeepInfra) au **serveur MCP Pruner** existant, tout en conservant le comportement actuel **par défaut** (heuristique locale), avec:

- Sélecteur global via variables d’environnement: `KIMI_PRUNING_BACKEND`.
- **Fail‑open contrôlé**: en cas d’erreur DeepInfra → fallback heuristique dans le même appel.
- Compatibilité **Continue + Cline**: aucun changement d’interface MCP (`tools/list`, `tools/call`) ni de route `/chat/completions`.
- Observabilité minimale: latence, tokens économisés (estimés), coût estimé, taux de fallback.

---

## 1) Problème
Le contexte des agents de code (Continue/Cline) grossit rapidement (logs, sorties d’outils, gros fichiers). Le repo dispose déjà d’un **MCP Pruner** heuristique local et d’un point d’intégration proxy (`/chat/completions` → `proxy/context_pruning.py`), mais il n’existe pas de backend cloud unifié.

On veut un POC minimal cloud‑only (DeepInfra) pour tester:

- la faisabilité technique,
- la robustesse (fallback),
- l’observabilité et l’impact coût.

---

## 2) Objectifs (Phase 1)

### 2.1 Fonctionnels
1. Ajouter un backend pruning **DeepInfra** utilisant l’endpoint:
   - `https://api.deepinfra.com/v1/inference/Qwen/Qwen3-Reranker-0.6B`
2. Sélection du backend via env globale:
   - `KIMI_PRUNING_BACKEND=heuristic|deepinfra` (défaut: `heuristic`)
3. Fallback automatique (fail‑open contrôlé):
   - erreurs réseau, timeout, 401/403, 429, 5xx, réponse invalide → fallback heuristique.
4. **Compatibilité Continue + Cline**:
   - pas de modifications breaking sur:
     - route `/chat/completions`
     - protocole MCP (`initialize`, `tools/list`, `tools/call`)
     - schémas d’entrées `prune_text`/`recover_text`

### 2.2 Observabilité (obligatoire)
Pour chaque pruning (tool `prune_text`):
- `latency_ms` (mesure end‑to‑end)
- `tokens_est_before/after` (déjà présent)
- `tokens_saved_est` (= before-after, clamp >=0)
- `cost_estimated_usd` (basé sur $0.01 / 1M tokens)
- `backend` (= `heuristic` ou `deepinfra`)
- `used_fallback` + `warnings[]`

Agrégé via `health`:
- `calls_total`, `calls_deepinfra`, `fallbacks_deepinfra`, `cost_estimated_total_usd`

---

## 3) Non‑objectifs
- Pas d’optimisation de batch côté proxy (hors Phase 1).
- Pas de persistance durable de métriques côté DB (hors Phase 1).
- Pas de déploiement VRAM local (interdit par mission).

---

## 4) Contraintes non négociables
- Respect strict des standards (`.clinerules/codingstandards.md`): async/await, httpx only, typage strict (pas de Any), pas de secrets en dur.
- Priorité de config: **env vars > config.toml**.
- Fail‑open contrôlé: ne jamais casser le pipeline `/chat/completions`.

---

## 5) Architecture cible (Phase 1)

### 5.1 Point d’unification
Le point d’intégration le plus stable est le **serveur MCP Pruner**:

- `src/kimi_proxy/features/mcp_pruner/server.py`

Pourquoi:
- Continue passe déjà par `proxy/context_pruning.py` → `forward_jsonrpc('pruner')`.
- Cline peut appeler le pruner directement ou via gateway.

=> un seul flag (`KIMI_PRUNING_BACKEND`) suffit à unifier.

### 5.2 Composants à introduire
- `DeepInfraClient` (httpx.AsyncClient)
- `DeepInfraPruningEngine` (sélection top‑K lignes à conserver)
- `PruningBackendManager` (routing env/config + fallback)

---

## 6) Configuration

### 6.1 Variables d’environnement (prioritaires)
- `KIMI_PRUNING_BACKEND` : `heuristic` (défaut) | `deepinfra`
- `DEEPINFRA_API_KEY` : clé d’API DeepInfra
- (optionnel) `DEEPINFRA_TIMEOUT_MS`
- (optionnel) `DEEPINFRA_MAX_DOCS`

### 6.2 config.toml (fallback)
Ajout d’une section *non bloquante* (les env gardent priorité) pour documenter:
- backend par défaut
- seuils de sécurité

---

## 7) Critères d’acceptation
1. Par défaut (pas d’env): comportement identique à aujourd’hui.
2. Avec `KIMI_PRUNING_BACKEND=deepinfra` et `DEEPINFRA_API_KEY`:
   - `prune_text` effectue un appel DeepInfra, prune réellement (pruned_text plus court) et retourne `backend=deepinfra`.
3. Avec `KIMI_PRUNING_BACKEND=deepinfra` mais erreur DeepInfra:
   - fallback heuristique sans crash, `used_fallback=true`, warning explicite.
4. Tests:
   - unit tests couvrent success + timeout + 401/429 + réponse invalide.
5. Coût:
   - `cost_estimated_usd` est calculé et non négatif.
6. Aucun secret en dur; aucune fuite de contenu dans logs (metadata-only).

---

## 8) Risques & mitigations

### 8.1 Schéma de réponse DeepInfra incertain
Mitigation:
- parsing best‑effort (plusieurs formes)
- fallback heuristique systématique

### 8.2 Explosion du coût (proxy appelle `prune_text` par message tool)
Mitigation Phase 1:
- augmenter/paramétrer `min_chars_to_prune`
- caching in‑memory (hash text+goal) TTL (optionnel)

---

## 9) Plan de rollback
- Remettre `KIMI_PRUNING_BACKEND=heuristic` (ou unset) → retour au comportement actuel.
