# Passthrough MCP Session-less

## TL;DR
Le passthrough permet à n'importe quel modèle de transiter via Kimi Proxy sans session pré-configurée dans `config.toml`. Cline envoie directement `X-Target-Base-URL` + `Authorization`, et le proxy applique les features MCP (tool fixing, observation masking, context pruning) avant d'forwarder.

## Le problème: la friction du setup

Avant, pour utiliser Kimi Proxy avec un nouveau modèle, il fallait:
1. Ajouter le provider dans `config.toml`
2. Redémarrer le serveur
3. Vérifier que le mapping modèle/provider fonctionne

Avec Cline et d'autres IDEs, je voulais que le proxy soit transparent: l'IDE choisit le modèle, le proxy optimise la requête.

## Architecture radicale

### Cline contrôle la cible

Cline envoie deux headers critiques:
- `X-Target-Base-URL`: L'URL de l'API cible (ex: `https://api.openai.com/v1`)
- `Authorization`: La clé API de l'utilisateur (Bearer token)

Le proxy n'a plus besoin de connaître le provider à l'avance.

```
Cline → X-Target-Base-URL + Authorization
        ↓
    PassthroughProcessor
        ↓
    1. Fix tool calls
    2. Observation masking schema 1
    3. Context pruning (MCP Pruner)
        ↓
    Provider cible (OpenAI, Gemini, etc.)
```

### Fallback legacy

Si `X-Target-Base-URL` est absent, le passthrough retombe sur la résolution classique via `config.toml`:
1. Header `X-Provider`
2. Champ `provider` dans le body JSON
3. Préfixe du modèle (`provider/model`)
4. `DEFAULT_PROVIDER` configuré

## Features MCP appliquées

Avant même d'atteindre le provider cible, le passthrough nettoie la requête:

### 1. Fix tool calls
- IDs manquants générés automatiquement
- Arguments malformés normalisés

### 2. Observation Masking Schema 1
- Résultats tool anciens tronqués
- Paramètres configurables:
  - `window_turns`: Nombre d'échanges récents à préserver
  - `keep_last_k_per_tool`: Derniers résultats conservés par outil
  - `keep_errors`: Toujours préserver les erreurs

### 3. Context Pruning (MCP Pruner)
- Élagage intelligent des messages tool
- Goal hint dérivé automatiquement de la conversation
- Fallback silencieux si le pruner est indisponible

## Implémentation

### `PassthroughProcessor`

```python
class PassthroughProcessor:
    async def apply_features(self, body_json: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Fix tool calls
        body_json = fix_tool_calls_in_request(body_json)
        body_json, fixed_count = normalize_tool_call_arguments(body_json)

        # 2. Observation masking
        if schema1_cfg.enabled:
            masked_messages = mask_old_tool_results(messages, policy)
            body_json["messages"] = masked_messages

        # 3. Context pruning
        if pruning_cfg.enabled:
            pruned_messages, summary = await prune_tool_messages_best_effort(
                messages=body_json["messages"],
                goal_hint=derive_goal_hint(body_json["messages"]),
                cfg=pruning_cfg,
                source_type="logs",
            )
            body_json["messages"] = pruned_messages

        return body_json

    async def forward(self, body_json, raw_headers, request) -> Response:
        base_url, provider_type, api_key = resolve_target(
            request, body_json, self.providers
        )
        # ... forward vers le provider avec gestion streaming
```

### Mapping modèle

En mode legacy, le préfixe provider est retiré:
```
"openai/gpt-4" → "gpt-4" (si "openai" est dans providers)
"kimi/k1"      → "k1" (si "kimi" est dans providers)
```

En mode radicale, le modèle est transmis tel quel à la cible.

## Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/v1/chat/completions` | POST | OpenAI-compatible session-less avec features MCP |

### Exemple avec Cline

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Target-Base-URL: https://api.openai.com/v1" \
  -H "Authorization: Bearer sk-xxx" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

### Exemple fallback legacy

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Provider: openai" \
  -d '{
    "model": "openai/gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Gestion des erreurs

| Erreur | Code | Détail |
|--------|------|--------|
| Cible manquante | 503 | Ni X-Target-Base-URL ni provider config.toml |
| ReadError | 502 | Connexion interrompue par le provider |
| Timeout | 504 | Délai d'attente dépassé |
| Erreur provider | 4xx/5xx | Transmis tel quel depuis le provider |

## Trade-offs

| Approche | Avantage | Limite |
|----------|----------|--------|
| Session-based | Historique, métriques détaillées | Configuration requise |
| **Passthrough session-less** | **Zéro configuration, agnostique** | **Pas de persistance métriques** |
| Proxy direct | Latence minimale | Aucune feature MCP |

## Golden Rule

**Le passthrough est l'interface par défaut pour les IDE. La session classique reste le mode privilégié pour le dashboard et les métriques détaillées.**

L'architecture radicale élimine la friction, mais les sessions continuent de fournir le comptage précis, l'historique et les optimisations avancées.

---

*Navigation : [← Retour au proxy](./README.md) | [Logique Routage Proxy →](./proxy-route-logic.md)*
