# Session 2026-02-14 : Correction du Routing des Modèles & Endpoint /models

## Résumé

Correction de l'erreur **"Model/deployment not found for: nvidia/kimi-k2-thinking"** de Continue.dev en ajoutant l'endpoint OpenAI-compatible `GET /models` et en fixant la logique de mapping des noms de modèles.

---

## 🎯 Problème Identifié

### Symptôme
Continue.dev affichait l'erreur :
```
Model/deployment not found for: nvidia/kimi-k2-thinking
```

### Causes Racines

1. **Endpoint `GET /models` manquant** : Continue valide les modèles via cet endpoint OpenAI standard, mais le proxy retournait 404

2. **Nettoyage incorrect du nom de modèle** : Le proxy utilisait `split('/')` pour retirer le préfixe provider, transformant :
   - `nvidia/kimi-k2-thinking` → `kimi-k2-thinking` ❌
   - Au lieu de `moonshotai/kimi-k2-thinking` ✅ (nom attendu par l'API NVIDIA)

---

## ✅ Solutions Implémentées

### 1. Endpoint OpenAI-Compatible `GET /models`

**Fichier** : `main.py`

```python
@app.get("/models")
async def openai_models():
    """
    Endpoint OpenAI-compatible GET /models pour validation Continue.dev.
    Retourne la liste des modèles au format OpenAI standard.
    """
    models_list = []
    
    for model_key, model_data in MODELS.items():
        # Le nom exposé est le model_key client (ex: "nvidia/kimi-k2-thinking")
        client_model_id = model_key
        
        models_list.append({
            "id": client_model_id,
            "object": "model",
            "created": 1677610602,
            "owned_by": model_data.get("provider", "unknown"),
            "permission": [],
            "root": client_model_id,
            "parent": None
        })
    
    return {
        "object": "list",
        "data": models_list
    }
```

**Format de réponse** (OpenAI-compatible) :
```json
{
    "object": "list",
    "data": [
        {
            "id": "nvidia/kimi-k2-thinking",
            "object": "model",
            "created": 1677610602,
            "owned_by": "nvidia",
            "root": "nvidia/kimi-k2-thinking"
        }
    ]
}
```

### 2. Correction de la Logique de Mapping

**Fichier** : `main.py` (dans `proxy_chat()`)

**Avant** (bug) :
```python
model_name = body_json.get('model', '')
if '/' in model_name:
    clean_model = model_name.split('/', 1)[1]  # → "kimi-k2-thinking" ❌
    body_json['model'] = clean_model
```

**Après** (corrigé) :
```python
model_name = body_json.get('model', '')
original_model = model_name

# Utilise le modèle mappé depuis la config si disponible
if model_name in MODELS:
    mapped_model = MODELS[model_name].get('model', model_name)
    body_json['model'] = mapped_model
    print(f"📝 Modèle mappé: {original_model} → {mapped_model}")
elif '/' in model_name:
    # Fallback: retire le préfixe provider (ancien comportement)
    clean_model = model_name.split('/', 1)[1]
    body_json['model'] = clean_model
    print(f"📝 Modèle nettoyé (fallback): {original_model} → {clean_model}")
```

**Mapping des modèles** (dans `config.toml`) :
```toml
[models."nvidia/kimi-k2-thinking"]
provider = "nvidia"
model = "moonshotai/kimi-k2-thinking"  # ← Nom attendu par l'API NVIDIA
max_context_size = 262144
```

---

## 🧪 Tests de Validation

### Test 1 : Endpoint /models

```bash
curl -s http://localhost:8000/models | python3 -m json.tool
```

**Résultat** :
```json
{
    "object": "list",
    "data": [
        {"id": "kimi-code/kimi-for-coding", "owned_by": "managed:kimi-code"},
        {"id": "nvidia/kimi-k2.5", "owned_by": "nvidia"},
        {"id": "nvidia/kimi-k2-thinking", "owned_by": "nvidia"},
        {"id": "mistral/codestral-2501", "owned_by": "mistral"}
        // ... 16 autres modèles
    ]
}
```

✅ **20 modèles exposés** au format OpenAI-compatible

### Test 2 : Requête Proxy avec Mapping

```bash
curl -s -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy-key" \
  -d '{
    "model": "nvidia/kimi-k2-thinking",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10,
    "stream": false
  }' | python3 -m json.tool | grep model
```

**Résultat** :
```json
"model": "moonshotai/kimi-k2-thinking"
```

✅ **Mapping correct** : `nvidia/kimi-k2-thinking` → `moonshotai/kimi-k2-thinking`

### Test 3 : Logs du Serveur

```
📝 Modèle mappé: nvidia/kimi-k2-thinking → moonshotai/kimi-k2-thinking
🔑 Clé API nvidia injectée: nvapi-5kNTmO...
🌐 Header Host mis à jour: integrate.api.nvidia.com
🔄 Proxy vers nvidia (openai): https://integrate.api.nvidia.com/v1
✅ Vrais tokens reçus (non-stream): {'prompt_tokens': 8, 'completion_tokens': 10}
```

✅ **Requête transmise correctement** à l'API NVIDIA

---

## 📋 Cohérence des Configurations

| Fichier | Modèle NVIDIA K2 Thinking | Usage |
|---------|---------------------------|-------|
| `config.toml` (proxy) | `model = "moonshotai/kimi-k2-thinking"` | API destination |
| `config.yaml` (proxy) | `model: nvidia/kimi-k2-thinking` | Routing via proxy |
| `config_continue_optimisé.yaml` | `model: moonshotai/kimi-k2-thinking` | Direct NVIDIA (sans proxy) |

---

## 🔧 Détails Techniques

### Pourquoi le Mapping est Nécessaire

Les providers utilisent différents formats de noms de modèles :

| Provider | Format Client | Format API |
|----------|---------------|------------|
| NVIDIA | `nvidia/kimi-k2-thinking` | `moonshotai/kimi-k2-thinking` |
| NVIDIA | `nvidia/kimi-k2.5` | `moonshotai/kimi-k2.5` |
| SiliconFlow | `siliconflow/qwen3-32b` | `Qwen/Qwen3-32B` |
| SiliconFlow | `siliconflow/deepseek-v3.2` | `deepseek-ai/DeepSeek-V3.2` |
| Groq | `groq/gpt-oss-120b` | `openai/gpt-oss-120b` |

Le dictionnaire `MODELS` dans `main.py` sert de table de correspondance entre :
- **Clé** : identifiant client (ce que Continue envoie)
- **Valeur `model`** : nom réel attendu par l'API provider

### Fallback Sécurisé

Si un modèle n'est pas trouvé dans `MODELS`, le proxy utilise le fallback `split('/')` pour compatibilité descendante. Cela permet de supporter des modèles non configurés tout en privilégiant les mappings explicites.

---

## 📁 Fichiers Modifiés

| Fichier | Changements |
|---------|-------------|
| `main.py` | Ajout endpoint `GET /models`, correction logique mapping dans `proxy_chat()` |

---

## ✅ Checklist

- [x] Endpoint `GET /models` OpenAI-compatible ajouté
- [x] Mapping des modèles corrigé (utilise `MODELS[client_model]["model"]`)
- [x] Fallback `split('/')` conservé pour compatibilité
- [x] Tests de validation passés (endpoint + proxy)
- [x] Cohérence des configurations vérifiée
- [x] Documentation mise à jour (AGENTS.md, README.md)

---

**Date** : 2026-02-14  
**Auteur** : Kimi Code CLI  
**Version** : 3.0.1 Fix Model Routing
