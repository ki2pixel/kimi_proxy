# Brief d’audit — Conformité DeepInfra pour MCP SWE-Pruner

## Objectifs d’audit
- Vérifier la conformité de l’intégration DeepInfra du MCP Pruner avec la documentation officielle DeepInfra.
- Établir une matrice traçable **exigence officielle ↔ implémentation ↔ statut ↔ impact**.
- Évaluer la robustesse opérationnelle: erreurs HTTP, parsing, fallback/fail-open, cache/TTL, métriques.
- Statuer sur la décision finale: **conforme**, **conforme avec réserves**, ou **non conforme**.

## Périmètre
- Documentation officielle DeepInfra locale (`docs/deepinfra/**`), avec priorité à:
  - `quickstart.mdx`
  - `models.mdx`
  - `apis/reranker.mdx`
  - `account/authentication.mdx`
  - `chat/**`
  - `integrations/**`
  - `api-reference/**` (vérification d’applicabilité)
- Implémentation Kimi Proxy (lecture seule):
  - `src/kimi_proxy/features/mcp_pruner/deepinfra_client.py`
  - `src/kimi_proxy/features/mcp_pruner/deepinfra_engine.py`
  - `src/kimi_proxy/features/mcp_pruner/server.py`
  - `src/kimi_proxy/config/loader.py`
  - `config.toml`
- Tests associés:
  - `tests/mcp/test_mcp_pruner_deepinfra_client.py`
  - `tests/unit/features/test_mcp_pruner_deepinfra.py`
  - `tests/unit/features/test_mcp_pruner_deepinfra_engine.py`
  - `tests/integration/test_proxy_context_pruning_c2.py`

## Critères d’acceptation
- 100% des affirmations du rapport final sont rattachées à une preuve vérifiable (fichier + ligne + extrait).
- Couverture complète des axes critiques:
  - conformité API DeepInfra (endpoint, méthode, headers, payload, response)
  - configuration (priorité `ENV > TOML`, absence de secret en dur)
  - gestion d’erreurs (401/429/5xx/timeout/JSON invalide)
  - fallback/fail-open et continuité de service
  - compatibilité MCP SWE-Pruner
  - sécurité des logs et des secrets
- Scoring explicite des sous-tâches et score global /100.

## Contraintes sécurité
- Audit uniquement: **aucune modification du code de production**.
- Ne jamais exposer de secrets (API key/token/.env) dans le rapport.
- Limiter les preuves aux extraits strictement nécessaires.
- Toute conclusion doit citer la source documentaire DeepInfra et la preuve d’implémentation locale.
