# Remédiations prioritaires DeepInfra (P1 / P2 / P3)

## Contexte exécutable
- Source de vérité: `docs/features/mcp-pruner.md` (section "Réserves et remédiations priorisées").
- Cible: corriger les écarts de conformité DeepInfra sans casser:
  - le contrat MCP JSON-RPC (`initialize`, `tools/list`, `tools/call`, `recover_text`),
  - le fail-open côté serveur pruner,
  - la priorité de configuration `ENV > TOML`.

## P1 — Payload reranker DeepInfra doc-strict
Objectif:
- Aligner le payload envoyé au reranker DeepInfra sur le format top-level:
  - `{"query": "...", "documents": ["..."]}`

Contraintes:
- Conserver timeouts et exceptions typées existantes.
- Ne pas modifier les contrats d’entrée/sortie du serveur MCP.

Critères d’acceptation:
- Le client envoie `query` et `documents` au top-level (pas de wrapper `input`).
- Les tests échouent si l’ancien format est réintroduit.

## P2 — Hardening sécurité `response_preview`
Objectif:
- Réduire/neutraliser l’exposition de contenu brut dans `DeepInfraHTTPError.details.response_preview`.

Politique attendue:
- Niveau de log élevé (warning/error): preview supprimé ou strictement neutralisé.
- Niveau debug: preview possible mais tronqué et redacted.

Critères d’acceptation:
- Aucune fuite de payload brut sensible dans les erreurs HTTP DeepInfra.
- Les métadonnées d’erreur restent actionnables (status_code, endpoint, code erreur).

## P3 — Test strict anti-régression payload
Objectif:
- Ajouter un test unitaire strict garantissant la conformité doc du payload top-level.

Critères d’acceptation:
- Test dédié qui échoue si le payload n’est pas strictement top-level (`query/documents`).
- Couverture de non-régression fail-open maintenue.

## Zones de code
- `src/kimi_proxy/features/mcp_pruner/deepinfra_client.py`
- `src/kimi_proxy/features/mcp_pruner/server.py`
- `tests/unit/features/test_mcp_pruner_deepinfra.py`
- `tests/mcp/test_mcp_pruner_deepinfra_client.py`
- `docs/features/mcp-pruner.md`

## Risques et garde-fous
- Risque compat provider: format payload strict requis → mitigé par test P3.
- Risque perte de diagnostic: hardening preview trop agressif → conserver status_code + endpoint.
- Risque régression pipeline: fail-open à préserver et valider par tests ciblés.