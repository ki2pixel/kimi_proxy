# Sanitizer - Le Tri Automatique Intelligent

## TL;DR
Le sanitizer détecte et masque automatiquement les messages tools et console verbeux (1000+ tokens) pendant l'envoi aux APIs LLM, les remplaçant par des placeholders récupérables. Économie: 20-40% de tokens sans perte d'information.

## Le problème qui m'a réveillé la nuit

J'analysais mes logs après une session de debugging de 2 heures. Résultat:
- **35% des tokens** étaient dans des messages tools/console que je ne lisais jamais
- **20% étaient** de l'historique ancien sans influence sur la tâche actuelle
- **Seulement 45%** servaient réellement la conversation en cours

J'envoyais $0.36/heure de bruit aux APIs.

## Comment ça marche

### Détection automatique

Le sanitizer identifie les contenus verbeux à la volée:
- Messages tool avec résultats JSON massifs
- Logs console répétitifs
- Stack traces longues

### Masquage avec récupération

Au lieu d'envoyer 1500 tokens de JSON tool au LLM, le sanitizer:
1. Remplace par un placeholder de 50 tokens
2. Stocke le contenu original indexé par hash
3. Permet la récupération via `/api/mask/{hash}`

### Configuration dynamique

```python
# Seuils configurables
threshold_tokens = 1000      # Masquer si > 1000 tokens
preview_length = 200         # Conserver un aperçu descriptif
tmp_dir = "/tmp/kimi_proxy_masked"  # Stockage temporaire
```

## Endpoints API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/mask/{content_hash}` | GET | Récupérer un contenu masqué par son hash |
| `/api/mask` | GET | Lister les contenus masqués récents |
| `/api/sanitizer/stats` | GET | Statistiques du sanitizer |
| `/api/sanitizer/toggle` | POST | Activer/désactiver le sanitizer |

### Exemples

```bash
# Récupérer un contenu masqué
curl http://localhost:8000/api/mask/abc123def456

# Lister les masquages récents
curl "http://localhost:8000/api/mask?limit=20"

# Statistiques
curl http://localhost:8000/api/sanitizer/stats

# Désactiver temporairement
curl -X POST http://localhost:8000/api/sanitizer/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

## ❌ Avant / ✅ Après

### ❌ Sans sanitizer
```json
{
  "role": "tool",
  "content": "{\"status\":200,\"data\":[{\"id\":1,\"name\":...1500 tokens de JSON...}]}",
  "tool_call_id": "call_123"
}
```

### ✅ Avec sanitizer
```json
{
  "role": "tool",
  "content": "[MASKED: hash=abc123, preview=API response with 47 items, tags=api,json]",
  "tool_call_id": "call_123"
}
```

## Routing avancé

Le sanitizer intègre un système de routing avec fallback:
- **Seuil principal** : Masquage standard à 1000 tokens
- **Fallback lourd** : Activation pour les messages > 90% du seuil si configuré
- **Catégorisation** : Tags automatiques (api, json, console, stacktrace)

## Trade-offs

| Approche | Avantage | Limite |
|----------|----------|--------|
| Masquage complet | Économie maximale | Perte de contexte si récupération échoue |
| Aperçu seul | Conservation partielle | Moins d'économie |
| **Choix actuel** | **Placeholder + stockage récupérable** | **Nécessite stockage temporaire** |

## Golden Rule

**Le sanitizer ne supprime jamais de données.** Il remplace temporairement et stocke pour récupération. Si vous avez besoin du contenu complet dans la conversation, récupérez-le via `/api/mask/{hash}`.

---

*Navigation : [← Retour aux fonctionnalités](./README.md) | [Support Multi-Provider →](./multi-provider-support.md)*
