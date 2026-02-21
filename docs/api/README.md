# API Layer - Routes et Endpoints

## TL;DR
Couche interface utilisateur FastAPI orchestrant 73 routes REST/WebSocket avec gestion erreurs streaming, extraction tokens partielle, et retry automatique.

## Problème
L'API Kimi Proxy expose une surface complexe de 73 endpoints Python (8883 LOC) sans documentation centralisée, créant une courbe d'apprentissage abrupte pour les développeurs et des difficultés de maintenance.

## Architecture 5 Couches
L'API Layer est la couche supérieure de l'architecture Kimi Proxy, dépendant des Services, Features, Proxy et Core layers.

```
API Layer (FastAPI) ← Services (WebSocket) ← Features (MCP) ← Proxy (HTTPX) ← Core (SQLite)
```

## Routes Principales

### Sessions Management
- `GET /api/sessions` - Liste toutes les sessions
- `POST /api/sessions` - Crée une nouvelle session
- `GET /api/sessions/active` - Récupère la session active avec statistiques
- `POST /api/sessions/{id}/activate` - Active une session spécifique
- `GET /api/sessions/auto-status` - Statut auto-session pour session active
- `POST /api/sessions/toggle-auto` - Active/désactive auto-session
- `DELETE /api/sessions/{id}` - Supprime une session
- `POST /api/sessions/vacuum` - Exécute VACUUM sur base de données
- `GET /api/sessions/diagnostic` - Informations diagnostiques sessions

### Providers Configuration
- `GET /api/providers` - Liste providers configurés avec modèles groupés

### Models Management
- `GET /api/models` - Liste modèles disponibles (format OpenAI-compatible)
- `GET /api/models/all` - Liste détaillée de tous les modèles

### Exports
- `GET /api/export/csv` - Export métriques session active en CSV
- `GET /api/export/json` - Export métriques session active en JSON

### Sanitizer (Phase 1)
- `GET /api/mask/{hash}` - Récupère contenu masqué par hash
- `GET /api/mask` - Liste contenus masqués récents
- `GET /api/sanitizer/stats` - Statistiques du sanitizer
- `POST /api/sanitizer/toggle` - Active/désactive sanitizer

### Memory Operations (MCP Phase 2-3)
- `GET /api/sessions/{id}/memory` - Stats mémoire d'une session (Phase 2)
- `GET /api/memory/stats` - Stats globales mémoire (Phase 2)
- `GET /api/memory/servers` - Statuts serveurs MCP externes (Phase 3)
- `POST /api/memory/similarity` - Recherche sémantique via Qdrant
- `POST /api/memory/compress` - Compression contenu via Context Compression MCP
- `POST /api/memory/store` - Stockage nouvelle mémoire standardisée
- `GET /api/memory/frequent` - Mémoires fréquemment utilisées
- `POST /api/memory/cluster/{session_id}` - Clustering mémoires d'une session
- `GET /api/memory/similar/{session_id}` - Mémoires similaires à une session
- `GET /api/memory/stats/advanced` - Stats avancées mémoire MCP
- `POST /api/memory/cleanup` - Nettoie mémoires épisodiques anciennes
- `POST /api/memory/promote-patterns/{session_id}` - Promeut patterns fréquents
- `GET /api/memory/all-servers` - Statuts tous serveurs MCP

### Compaction & Compression
- `POST /api/compaction/{session_id}` - Compactage manuel session
- `GET /api/compaction/{session_id}/stats` - Stats compactage session
- `GET /api/compaction/stats` - Stats globales compactage
- `POST /api/compress/{session_id}` - Compression manuelle session
- `GET /api/compress/{session_id}/stats` - Stats compression session
- `GET /api/compress/stats` - Stats globales compression

### Proxy Endpoint
- `POST /chat/completions` - Proxy transparent vers APIs LLM

### Health & Monitoring
- `GET /health` - Health check avec infos session/log watcher
- `GET /api/rate-limit` - Statut rate limiting actuel

### WebSocket Endpoint
- `WS /ws` - Communication temps réel avec dashboard

## Haute Complexité - Pattern 6

### Fonction `proxy_chat` (Score F - 40+)
**Localisation** : `src/kimi_proxy/api/routes/proxy.py`
**Complexité** : Orchestration complexe du routage proxy avec gestion erreurs streaming, extraction tokens partielle, retry automatique.

```python
# Points critiques
- Gestion asynchrone des flux SSE
- Extraction tokens depuis streams partiellement corrompus  
- Retry exponentiel avec backoff
- Transformation formats (Gemini ↔ OpenAI)
```

### Fonction `_proxy_to_provider` (Score E - 30-39)
**Localisation** : `src/kimi_proxy/api/routes/proxy.py`
**Complexité** : Appel HTTPX asynchrone avec transformation formats, gestion timeouts, et récupération erreurs.

## Patterns Système Appliqués
- **Pattern 1** : Architecture 5 couches stricte
- **Pattern 2** : Dependency Injection via FastAPI Depends
- **Pattern 6** : Error Handling robuste avec extraction tokens partielle
- **Pattern 14** : Async/Await obligatoire pour toutes les opérations I/O

## Error Handling Stratégique

### ❌ Approche Naïve
```python
try:
    response = await client.post(url, json=data)
    return response.json()
except Exception:
    return {"error": "Failed"}
```

### ✅ Approche Kimi Proxy
```python
try:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        return response.json()
except httpx.TimeoutException:
    # Extraction tokens partiels du stream corrompu
    partial_usage = extract_usage_from_stream(corrupted_stream)
    return {"error": "Timeout", "partial_usage": partial_usage}
except httpx.ConnectError:
    # Retry avec backoff exponentiel
    return await retry_with_backoff(url, data, max_retries=3)
```

## Trade-offs
| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Routes séparées | Clarté, testabilité | Plus de boilerplate |
| Routes génériques | DRY, flexibilité | Complexité accrue |
| **Choix Kimi Proxy** | **Équilibre maintenabilité** | **Documentation essentielle** |

## Golden Rule
**Toute nouvelle route API doit inclure :**
1. Documentation FastAPI (`@app.get(..., summary="...")`)
2. Gestion erreurs Pattern 6
3. Tests unitaires async
4. Mise à jour cette documentation

## Métriques Actuelles
- **53 endpoints API** répartis sur 11 fichiers route
- **15 fichiers Python** dans l'API layer (2318 LOC total)
- **Complexité moyenne** : C (17.42)
- **Points chauds** : 2 fonctions E/F nécessitant attention
- **Coverage** : Tests en cours d'implémentation

## Prochaines Évolutions
- [ ] Auto-génération OpenAPI/Swagger
- [ ] Rate limiting par endpoint
- [ ] Monitoring temps réel des performances
- [ ] Documentation interactive avec exemples

---
*Dernière mise à jour : 2026-02-20*  
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*