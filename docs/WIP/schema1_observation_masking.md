# Schéma 1 : Observation Masking (côté proxy)

**TL;DR** : quand tes conversations contiennent beaucoup de sorties d’outils (logs, JSON, dumps), **Schéma 1** masque uniquement le `content` des anciens messages `role="tool"` *avant* l’envoi au provider. L’ordre, les IDs et `assistant.tool_calls` sont strictement préservés.

## Le problème (concret)

Tu utilises `/chat/completions` avec du tool-calling. Tout se passe bien… jusqu’au moment où un outil renvoie 5 000 lignes.

Ensuite, chaque tour suivant ré-envoie ce texte dans le contexte :

- la facture token explose,
- tu n’as pas envie de résumer au LLM (latence + coût + risque),
- tu ne peux pas juste “supprimer” des messages `tool` sans casser la cohérence `tool_calls[].id` ↔ `tool_call_id`.

## La solution : une fenêtre en “tours tool”, pas en messages

Schéma 1 garde intacts les résultats d’outil des **N derniers tours tool** et remplace les plus anciens par un placeholder court.

Définition : un **tour tool** est un message `role="assistant"` qui contient `tool_calls` (liste). Un tour peut contenir plusieurs `tool_calls`.

### ❌ Ce qu’on évite

Supprimer ou réordonner des messages :

```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "...gros output..."
}
```

Si tu le supprimes, tu risques de casser la structure tool-calling et de rendre la trace inutilisable.

### ✅ Ce qu’on fait à la place

On ne touche qu’à `content` :

```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "[Observation masquée: résultat d’outil ancien (tool_call_id=call_123, outil=ls, chars=5186)]"
}
```

## Invariants (non négociables)

Le masking ne doit jamais :

1) ajouter/supprimer des éléments dans `messages`,
2) réordonner les messages,
3) modifier `assistant.tool_calls` (contenu ou IDs),
4) modifier `tool_call_id`.

Il remplace uniquement `message["content"]` des messages `role="tool"` éligibles.

## Activation et réglage (config.toml)

La configuration est gérée via :

```toml
[observation_masking.schema1]
enabled = false
window_turns = 8
keep_errors = true
keep_last_k_per_tool = 0
placeholder_template = "[Observation masquée: résultat d'outil ancien (tool_call_id={tool_call_id}, outil={tool_name}, chars={original_chars})]"
```

Notes :

- **Rollback instantané** : mettre `enabled=false`.
- `window_turns` est en **tours tool** (pas en messages).
- `keep_errors=true` évite de masquer des sorties qui ressemblent à une erreur (Traceback, Exception, timeout, JSON `{ "error": ... }`).
- `keep_last_k_per_tool` permet de garder au moins K derniers résultats pour chaque outil (si `>0`).
- Le placeholder doit rester **court** ; sinon, il peut coûter plus de tokens que l’observation originale.

## Où c’est appliqué dans le proxy

Schéma 1 est appliqué dans la route `POST /chat/completions` :

- avant le comptage des tokens (`src/kimi_proxy/core/tokens.py`),
- avant l’auto-session/auto-compaction,
- avant l’envoi au provider.

Le code de masking est dans :

- `src/kimi_proxy/features/observation_masking/schema1.py`.

## Limitations

- La fenêtre est une heuristique simple : elle n’est pas “state-aware” (elle ne sait pas si un tool output ancien est redevenu pertinent).
- L’heuristique `keep_errors` est volontairement conservatrice : elle privilégie la non-régression à l’économie maximale.
- Les messages `tool` “orphelins” (tool_call_id non retrouvé dans `assistant.tool_calls`) ne sont pas masqués.

## Benchmark offline

Un petit benchmark permet de rejouer une conversation tool-heavy (zéro réseau) :

```bash
python3 scripts/bench_observation_masking_schema1.py --json --window-turns 1
```

Output JSON :

- `masked_tool_results` : nombre de messages `role="tool"` dont `content` a été remplacé
- `tool_chars_before/after`
- `tokens_before/after`

## Trade-offs

| Approche | Coût tokens | Risque de perte de contexte | Complexité | Remarques |
| --- | --- | --- | --- | --- |
| Tout envoyer (baseline) | Élevé | Faible | Faible | Simple, mais la fenêtre explose vite |
| Summarisation LLM | Moyen | Moyen | Élevée | Coût + latence + dépend d’un modèle |
| Observation masking (Schéma 1) | Bas à moyen | Moyen | Modérée | Efficace si les outputs tool dominent |

## Différence avec le masking du MCP Gateway

Schéma 1 est **conversationnel** : il modifie les `messages` envoyés au provider.

Le MCP Gateway applique un masking **sur des payloads JSON-RPC** (anti log-bomb) ; c’est un mécanisme distinct (`src/kimi_proxy/features/mcp/gateway.py`).

## Golden Rule

Si tu dois choisir une seule règle : **ne jamais casser la structure tool-calling**. On masque le `content` ; on ne touche pas aux IDs, ni à l’ordre.