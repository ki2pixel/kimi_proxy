# Compression Intelligente - Le Bouton d'Urgence

## TL;DR
La compression réduit instantanément le contexte d'une session de 60% en préservant les échanges récents et en résumant l'historique ancien via le LLM actuel. C'est le filet de sécurité quand le compteur atteint 85%.

## Le problème qui m'a fait ajouter ce bouton

J'étais à 90% du contexte. Encore 2-3 messages et tout allait exploser. La compaction (Phase 1) est préventive, mais parfois on arrive trop tard.

Ce que je voulais: un bouton "Sauve-moi" qui compresse l'historique existant sans perdre la trame de la conversation.

## Ce que fait la compression

Contrairement à la compaction qui réduit en supprimant, la compression résume:
- Préserve les messages système (instructions critiques)
- Garde les 5 derniers échanges (contexte immédiat)
- Résume tout le reste avec le modèle LLM actuel
- Notifie le dashboard en temps réel via WebSocket

## Architecture

```
API (/api/compress/*) → Features (compression/storage.py) → Core (database, tiktoken)
```

### Pipeline de compression

```python
# 1. Vérification du seuil (sauf force=true)
session_totals = get_session_total_tokens(session_id)
current_percentage = (session_totals / max_context * 100)

# 2. Compression avec résumé LLM
result = await compress_session_history(session_id)
# → original_tokens: 10000
# → compressed_tokens: 4000
# → tokens_saved: 6000

# 3. Notification WebSocket
await manager.broadcast({
    "type": "compression_event",
    "session_id": session_id,
    "compression": {
        "compressed": True,
        "tokens_saved": 6000,
        "compression_ratio": 60.0
    }
})
```

## Endpoints API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/compress/{session_id}` | POST | Compresser manuellement une session |
| `/api/compress/{session_id}/stats` | GET | Statistiques de compression d'une session |
| `/api/compress/stats` | GET | Statistiques globales de compression |

### Exemple d'utilisation

```bash
# Compression manuelle (vérifie le seuil)
curl -X POST http://localhost:8000/api/compress/1

# Forcer la compression (ignore le seuil)
curl -X POST http://localhost:8000/api/compress/1 \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Statistiques d'une session
curl http://localhost:8000/api/compress/1/stats
```

## Configuration

```toml
[sanitizer.compression]
threshold_percentage = 85          # Seuil minimum pour compression non-forcée
preserve_recent_exchanges = 5      # Nombre d'échanges récents à préserver
summary_max_tokens = 500           # Longueur max du résumé LLM
```

## ❌ Avant / ✅ Après

### ❌ Sans compression
```
Session: 15000 tokens / 16000 max (93.7%)
→ 2 messages plus tard: "Context length exceeded"
→ Perte de la session, restart à zéro
```

### ✅ Avec compression
```
Session: 15000 tokens / 16000 max (93.7%)
→ POST /api/compress/1
→ Résultat: 6000 tokens (37.5%)
→ Conversation continue sans interruption
```

## Différence compaction vs compression

| Aspect | Compaction (Phase 1) | Compression (Phase 3) |
|--------|---------------------|----------------------|
| Quand | Préventif (seuil 80%) | Urgence (seuil 85%+) |
| Méthode | Suppression sélective | Résumé LLM |
| Préservation | N derniers échanges | N derniers échanges + résumé |
| Coût | Gratuit (règles) | 1 appel LLM pour résumer |
| Cas d'usage | Maintenance régulière | Sauvetage d'urgence |

## Golden Rule

**La compression est un filet de sécurité, pas une stratégie quotidienne.**

Si vous compressez plus d'une fois par session, augmentez la fréquence de compaction automatique ou réduisez la fenêtre de contexte.

---

*Navigation : [← Retour aux fonctionnalités](./README.md) | [MCP →](./mcp.md)*
