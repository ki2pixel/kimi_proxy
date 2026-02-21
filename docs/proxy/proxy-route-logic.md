# Logique de Routage Proxy - `_proxy_to_provider`

**TL;DR**: Cette fonction orchestre le proxy vers les providers IA avec gestion d'erreurs robuste, comptage tokens précis, et notifications temps réel. Elle transforme les requêtes OpenAI-like en appels provider spécifiques tout en maintenant la transparence streaming.

## Le Problème du Routage Multi-Provider

Vous construisez un proxy transparent pour APIs d'IA. Vous voulez supporter 8+ providers (OpenAI, Gemini, NVIDIA) avec leurs formats différents. Vous devez gérer:

- Authentification par provider
- Transformation de format (OpenAI ↔ Gemini)
- Streaming avec gestion d'erreurs réseau
- Comptage tokens précis pour facturation
- Notifications temps réel via WebSocket
- Gestion des limites de contexte

La fonction `_proxy_to_provider` résout cette complexité en centralisant toute la logique de routage dans une seule fonction de 320+ lignes.

### ❌ L'Approche Éparpillée
```python
# Dans proxy.py
def proxy_chat(request):
    # Duplication: chaque route fait son propre proxy
    body = await request.body()
    headers = dict(request.headers)

    # Répétition: même logique d'authentification partout
    if provider == "openai":
        headers["Authorization"] = f"Bearer {api_key}"
    elif provider == "gemini":
        # Logique différente...

    # Répétition: même gestion d'erreurs partout
    try:
        response = await client.post(url, json=body, headers=headers)
        return response.json()
    except httpx.TimeoutException:
        return {"error": "timeout"}  # Gestion pauvre
```

### ✅ L'Approche Centralisée
```python
async def _proxy_to_provider(
    body: bytes, headers: dict, provider_key: str,
    providers: dict, models: dict, target_url: str,
    session: dict, metric_id: int, max_context: int,
    request_tokens: int
):
    """Orchestration complète du proxy avec gestion unifiée."""
    # Authentification unifiée
    provider_config = providers.get(provider_key, {})
    api_key = provider_config.get("api_key", "")

    # Headers selon le type de provider
    proxy_headers = build_headers_for_provider(provider_type, api_key)

    # Transformation de format
    clean_body = transform_request_body(body, provider_type, models)

    # Proxy avec gestion d'erreurs complète
    return await execute_proxy_request(
        target_url, proxy_headers, clean_body,
        session, metric_id, max_context, request_tokens
    )
```

## Architecture de la Fonction

La fonction suit une séquence claire de 8 étapes:

1. **Configuration Provider**: Extraction clés API, type provider
2. **Construction Headers**: Authentification + headers standards
3. **Nettoyage Body**: Parsing JSON + mapping modèles + suppression métadonnées
4. **Transformation Format**: Conversion OpenAI ↔ format provider (Gemini)
5. **Construction Requête**: URL finale + body nettoyé
6. **Exécution Proxy**: Streaming vs non-streaming avec retry
7. **Gestion Erreurs**: Context limit, timeout, read errors avec notifications WebSocket
8. **Extraction Métriques**: Comptage tokens réels + mise à jour base de données

### Gestion d'Erreurs Robuste

| Type d'Erreur | Stratégie | Notification |
|---------------|-----------|--------------|
| **Context Limit** | Détection message + recommandations automatiques | WebSocket broadcast + JSON structuré |
| **Timeout** | Retry automatique (2 tentatives) + timeout 120s | Erreur 504 avec détails |
| **ReadError** | Gestion streaming interrompu | Erreur 502 avec diagnostic |
| **4xx/5xx** | Propagation avec body erreur | Erreur HTTP correspondante |

### Notifications Temps Réel

Chaque événement critique déclenche une notification WebSocket:

```python
# Exemple: dépassement limite contexte
await manager.broadcast({
    "type": "provider_context_limit_error",
    "session_id": session["id"],
    "error": error_text,
    "provider": provider_key,
    "estimated_tokens": request_tokens,
    "max_context": max_context,
    "recommendations": [
        "Réduire la taille du contexte historique",
        "Utiliser le sanitizer pour nettoyer les messages verbeux",
        "Compresser la conversation avec le bouton 'Compresser'"
    ]
})
```

## Exemples Concrets

### Exemple 1: Proxy OpenAI Standard
```python
# Requête entrante OpenAI-like
body = b'{"model": "gpt-4", "messages": [...], "stream": true}'

# Après transformation dans _proxy_to_provider:
# - Headers: Authorization: Bearer sk-...
# - URL: https://api.openai.com/v1/chat/completions
# - Body: identique (pas de transformation)
# - Mode: streaming avec gestion d'erreurs
```

### Exemple 2: Proxy Gemini avec Transformation
```python
# Requête entrante OpenAI-like
body = b'{"model": "gemini-pro", "messages": [...], "stream": false}'

# Après transformation:
# - Headers: pas d'Authorization (injection dans URL)
# - URL: https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=...
# - Body: converti au format Gemini {"contents": [...], "generationConfig": {...}}
# - Mode: non-streaming avec extraction tokens
```

### Exemple 3: Gestion Erreur Context Limit
```python
# Provider rejette: "context length exceeded"
# Fonction détecte et:
# 1. Parse le message d'erreur
# 2. Notifie via WebSocket avec recommandations
# 3. Retourne JSON structuré avec suggestions d'actions
# 4. Status code 413 (Payload Too Large)
```

## Trade-offs de Conception

| Aspect | Choix | Avantages | Inconvénients |
|--------|-------|-----------|---------------|
| **Centralisation** | Une fonction pour tout | Maintenance facile, logique cohérente | Complexité élevée (320+ lignes) |
| **Gestion Erreurs** | Très détaillée | Robustesse maximale, diagnostic précis | Code verbeux, nombreux try/catch |
| **Streaming** | Gestion spécialisée | Performance optimale, erreurs granulaires | Logique dupliquée stream/non-stream |
| **WebSocket** | Notifications temps réel | UX améliorée, monitoring live | Couplage avec couche services |
| **Transformation** | À la volée | Flexibilité, support nouveaux providers | Parsing répété du body JSON |

## Patterns Système Appliqués

- **Pattern 6 (Error Handling)**: Gestion d'erreurs hiérarchisée avec récupération automatique
- **Pattern 14 (Streaming)**: Support complet streaming avec retry et extraction tokens partiels
- **Pattern 4 (MCP Integration)**: Intégration transparente avec couche MCP pour notifications
- **Pattern 2 (Dependency Injection)**: Injection de managers et clients via paramètres

## Golden Rule: Proxy Transparent avec Gestion d'Erreurs Robuste

**Chaque appel provider doit réussir ou échouer avec un diagnostic complet et des recommandations d'actions.** La fonction `_proxy_to_provider` incarne cette règle en transformant les échecs techniques en réponses structurées avec contexte et solutions.

---

*Cette documentation explique la logique complexe derrière le routage proxy transparent. Pour les détails d'implémentation, voir `src/kimi_proxy/api/routes/proxy.py:157`.*