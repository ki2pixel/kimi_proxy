# Passthrough MCP Session-less

## TL;DR
Le passthrough transmet une requête OpenAI-compatible vers la cible indiquée par `X-Target-Base-URL`. Sans cet en-tête, la requête est refusée en 503 « Cible manquante ». Aucun provider n'est résolu depuis `config.toml`.

## Le problème
Un proxy multi-provider classique impose de déclarer chaque provider, sa clé et son mapping de modèle avant de pouvoir envoyer une requête. Avec les IDE, cette configuration devient une source de friction et de secrets dupliqués.

Le mode session-less inverse la responsabilité : le client choisit la cible et fournit sa propre clé. Le proxy ne connaît ni le provider ni le modèle à l'avance.

## Architecture

### En-têtes du client
- `X-Target-Base-URL` : URL de base de l'API cible, par exemple `https://api.openai.com/v1`.
- `X-Provider-Type` : `openai` par défaut, ou `gemini`.
- `Authorization: Bearer ...` : clé API du provider. Elle est transmise à la cible et n'est jamais utilisée pour l'authentification admin.
- `X-Admin-Key` : clé d'administration du proxy, uniquement si `KIMI_ADMIN_KEY` est défini.

### Pipeline
```text
Client
  ↓ X-Target-Base-URL + Authorization
Validation SSRF
  ↓
PassthroughProcessor
  1. Correction des tool calls
  2. Normalisation des arguments JSON
  3. Observation masking Schema 1
  4. Context pruning via MCP Pruner
  ↓
Provider cible
```

### Résolution de la cible
`resolve_target()` lit uniquement `X-Target-Base-URL`. Si l'en-tête est absent ou vide, la réponse est :

```json
{
  "error": "Cible manquante",
  "message": "Aucune cible specifiee. Envoyez X-Target-Base-URL avec votre requete."
}
```

Statut HTTP : `503`.

## Validation SSRF

### ❌ Ancien comportement
- Les adresses privées et link-local n'étaient filtrées qu'en production.
- Un mode « fallback legacy » résolvait un provider depuis `config.toml`, `X-Provider` ou le préfixe du modèle.

### ✅ Comportement actuel
- HTTPS est obligatoire, sauf pour le loopback en développement.
- Les adresses privées, réservées, link-local, multicast et non spécifiées sont bloquées dans tous les environnements.
- Le loopback (`localhost`, `127.0.0.1`, `::1`) n'est autorisé qu'en développement.
- En production, l'allowlist des hôtes cibles s'applique.
- La résolution DNS est asynchrone via `loop.getaddrinfo()`.

## Features MCP appliquées

### Correction des tool calls
Les IDs manquants sont générés et les arguments malformés sont réparés par un pipeline de stratégies pures, sans évaluation dynamique de code.

### Observation masking Schema 1
Les résultats d'outils anciens peuvent être tronqués selon `window_turns`, `keep_last_k_per_tool` et `keep_errors`.

### Context pruning
Les messages `role="tool"` peuvent être élagués via le serveur MCP Pruner. Toute erreur du pruner produit un no-op : le contenu original est conservé.

## Streaming et libération des ressources

Le flux SSE est relayé sans buffer intermédiaire :

```python
async for chunk in response.aiter_bytes():
    yield chunk
```

En cas d'erreur HTTP `>= 400` avant le streaming, la réponse et le client HTTPX associé sont fermés dans un bloc `finally`. En fin de flux normal, `stream_generator` applique la même fermeture déterministe.

## Endpoint

| Endpoint | Méthode | Description |
|---|---|---|
| `/v1/chat/completions` | POST | OpenAI-compatible, session-less, avec features MCP |

### Exemple

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

## Gestion des erreurs

| Erreur | Code | Détail |
|---|---|---|
| Cible manquante | 503 | `X-Target-Base-URL` absent |
| Cible invalide | 400 | Protocole, DNS ou adresse IP refusés |
| ReadError | 502 | Connexion interrompue par le provider |
| Timeout | 504 | Délai d'attente dépassé |
| Erreur provider | 4xx/5xx | Statut et corps transmis, ressources fermées |

## Trade-offs

| Approche | Avantage | Limite |
|---|---|---|
| Providers déclarés dans `config.toml` | Mapping centralisé | Configuration obligatoire et secrets dupliqués |
| Passthrough session-less | Zéro configuration provider | Pas de persistance des métriques par provider |
| Validation SSRF stricte | Réduction du risque de rebinding | Loopback limité au développement |
| Streaming pur | Latence minimale et mémoire constante | Pas d'inspection fine du contenu SSE |

## Golden Rule
**Le client choisit la cible et fournit sa clé ; le proxy valide, nettoie et relaie sans résoudre de provider implicite.**

---
*Dernière mise à jour : 2026-11-06*
*Navigation : [← Retour au proxy](./README.md) | [Validation des outils →](./tool-validation.md)*
