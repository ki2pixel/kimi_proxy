# Session 2026-02-14 : Extension Multi-Provider & Corrections de Calculs

## Résumé

Extension du Kimi Proxy Dashboard pour supporter **8 providers** et **20+ modèles**, avec corrections des incohérences de calcul de tokens et de contexte max.

---

## 🎯 Objectifs

1. Étendre le support à tous les modèles utilisés par l'extension Continue
2. Corriger les incohérences de contexte max (ex: Mistral affichait 262K au lieu de 131K)
3. Corriger les calculs cumulatifs de tokens
4. Améliorer l'UI du dashboard avec sélection granulaire des modèles

---

## ✅ Providers Ajoutés

| Provider | Type | Modèles | Contexte |
|----------|------|---------|----------|
| 🌙 **Kimi Code** | kimi | 1 | 256K |
| 🟢 **NVIDIA** | openai | 2 | 256K |
| 🔷 **Mistral** | openai | 4 | 32K-256K |
| 🔀 **OpenRouter** | openai | 1 | 128K |
| 💧 **SiliconFlow** | openai | 2 | 131K-164K |
| ⚡ **Groq** | openai | 3 | 131K |
| 🧠 **Cerebras** | openai | 3 | 64K-65K |
| 💎 **Gemini** | gemini | 4 | 1M |

---

## 🔧 Changements Techniques

### Backend (`main.py`)

#### 1. Nouvelle colonne `model` dans la base de données
```python
# Migration ajoutée dans init_database()
try:
    cursor.execute("ALTER TABLE sessions ADD COLUMN model TEXT")
    conn.commit()
    print("   Migration: colonne 'model' ajoutée à sessions")
except sqlite3.OperationalError:
    pass  # Colonne existe déjà
```

#### 2. Correction de `get_max_context_for_session()`
```python
def get_max_context_for_session(session: dict) -> int:
    """Récupère le contexte max pour une session basé sur son provider.
    
    Si un modèle spécifique est stocké dans la session, utilise son contexte.
    Sinon, utilise le contexte le plus petit parmi les modèles du provider.
    """
    if not session:
        return DEFAULT_MAX_CONTEXT
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    model_key = session.get("model")  # Modèle spécifique si disponible
    
    # Si un modèle spécifique est stocké, utilise son contexte
    if model_key and model_key in MODELS:
        return MODELS[model_key].get("max_context_size", DEFAULT_MAX_CONTEXT)
    
    # Sinon, trouve le contexte le plus petit parmi les modèles du provider
    min_context = None
    for mk, model in MODELS.items():
        if model.get("provider") == provider_key:
            ctx = model.get("max_context_size", DEFAULT_MAX_CONTEXT)
            if min_context is None or ctx < min_context:
                min_context = ctx
    
    return min_context if min_context else DEFAULT_MAX_CONTEXT
```

#### 3. Correction de `get_session_total_tokens()`
```python
def get_session_total_tokens(session_id: int) -> dict:
    """Calcule le total cumulé des tokens pour une session.
    
    Logique:
    - Input: Somme des prompt_tokens (réels) sinon estimated_tokens
    - Output: Somme des completion_tokens (réels)
    - Total: Input + Output
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT estimated_tokens, prompt_tokens, completion_tokens, is_estimated
        FROM metrics WHERE session_id = ? ORDER BY timestamp ASC
    """, (session_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    total_input = 0
    total_output = 0
    
    for row in rows:
        estimated = row[0] or 0
        prompt = row[1] or 0
        completion = row[2] or 0
        
        # Pour l'input: utilise prompt_tokens si disponible, sinon estimated_tokens
        if prompt > 0:
            total_input += prompt
        else:
            total_input += estimated
        
        # Pour l'output: toujours completion_tokens
        total_output += completion
    
    return {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output
    }
```

#### 4. Support Non-Streaming
Ajout d'une branche spécifique dans `proxy_chat()` pour traiter les réponses JSON complètes (sans SSE) et extraire les vrais tokens.

#### 5. Nouveaux Endpoints
- `GET /api/models` : Liste tous les modèles avec métadonnées
- `POST /api/sessions` : Accepte maintenant un paramètre `model` optionnel

---

### Configuration (`config.toml`)

Ajout de tous les providers et modèles :

```toml
# === Kimi Code Officiel ===
[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
max_context_size = 262144

# === NVIDIA ===
[models."nvidia/kimi-k2.5"]
provider = "nvidia"
model = "moonshotai/kimi-k2.5"
max_context_size = 262144

[models."nvidia/kimi-k2-thinking"]
provider = "nvidia"
model = "moonshotai/kimi-k2-thinking"
max_context_size = 262144

# === Mistral ===
[models."mistral/codestral-2501"]
provider = "mistral"
model = "codestral-2501"
max_context_size = 262144

[models."mistral/mistral-large-2411"]
provider = "mistral"
model = "mistral-large-2411"
max_context_size = 131072

[models."mistral/pixtral-large-2411"]
provider = "mistral"
model = "pixtral-large-2411"
max_context_size = 131072

[models."mistral/ministral-8b-2410"]
provider = "mistral"
model = "ministral-8b-2410"
max_context_size = 32768

# ... (autres providers)

# === Providers Configuration ===
[providers.mistral]
type = "openai"
base_url = "https://api.mistral.ai/v1"
api_key = "..."

[providers.openrouter]
type = "openai"
base_url = "https://openrouter.ai/api/v1"
api_key = "..."

[providers.siliconflow]
type = "openai"
base_url = "https://api.siliconflow.cn/v1"
api_key = "..."

[providers.groq]
type = "openai"
base_url = "https://api.groq.com/openai/v1"
api_key = "..."

[providers.cerebras]
type = "openai"
base_url = "https://api.cerebras.ai/v1"
api_key = "..."

[providers.gemini]
type = "gemini"
base_url = "https://generativelanguage.googleapis.com/v1beta"
api_key = "..."
```

---

### Frontend (`static/index.html`)

#### Nouveau Modal de Création de Session
- **Filtre de recherche** en temps réel
- **Affichage groupé** par provider avec icônes colorées
- **Grille de modèles** avec indicateurs de capacités
- **Format du contexte** affiché en K/M
- **Bouton désactivé** tant qu'aucun modèle n'est sélectionné

#### Indicateurs de Capacités
- 🔧 `tool_use` - Support des outils (MCP)
- 🧠 `thinking` - Mode réflexion
- 👁️ `vision` - Support vision
- 🖼️ `multimodal` - Support multimodal
- ⚡ `autocomplete` - Autocomplétion
- 💡 `reasoning` - Raisonnement avancé
- 💻 `coding` - Optimisé codage
- 🚀 `ultra_fast` - Ultra rapide

#### Couleurs des Providers
- 🌙 Kimi Code: `purple`
- 🟢 NVIDIA: `green`
- 🔷 Mistral: `blue`
- 🔀 OpenRouter: `orange`
- 💧 SiliconFlow: `cyan`
- ⚡ Groq: `yellow`
- 🧠 Cerebras: `red`
- 💎 Gemini: `indigo`

---

## 🐛 Corrections de Bugs

### Bug 1: Contexte Max Incorrect
**Symptôme**: La jauge affichait 262144 pour Mistral Large (devrait être 131072)

**Cause**: `get_max_context_for_session()` prenait le premier modèle du provider

**Solution**: 
- Stockage du modèle spécifique dans la session
- Si pas de modèle stocké, utilise le plus petit contexte (approche conservatrice)

### Bug 2: Calculs Cumulatifs Incorrects
**Symptôme**: Total affiché 146217 au lieu du vrai total (~67062)

**Cause**: `get_session_total_tokens()` utilisait `estimated_tokens` au lieu de `prompt_tokens`

**Solution**: Refonte complète de la logique:
- Input: somme des `prompt_tokens` (réels) ou `estimated_tokens`
- Output: somme des `completion_tokens`
- Total: input + output

### Bug 3: Tokens Réels Non Extraits (Non-Streaming)
**Symptôme**: Les métriques restaient en mode "ESTIMÉ" même après réponse

**Cause**: Le code ne gérait que le format SSE (streaming)

**Solution**: Ajout d'une branche pour traiter les réponses JSON complètes

---

## 🧪 Tests Effectués

### Test 1: Création Session Mistral
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","provider":"mistral","model":"mistral/mistral-large-2411"}'

# Résultat:
# Max Context: 131072  ✅
```

### Test 2: Calculs de Tokens
```bash
# Après 2 requêtes:
# Input: 16  ✅ (prompt_tokens cumulés)
# Output: 342  ✅ (completion_tokens)
# Total: 358  ✅ (input + output)
```

### Test 3: Extraction Tokens Réels
```bash
curl -X POST http://localhost:8000/chat/completions \
  -d '{"model":"mistral/mistral-large-2411","messages":[...],"stream":false}'

# La métrique passe bien de "ESTIMÉ" à "RÉEL"
```

---

## 📁 Fichiers Modifiés

| Fichier | Changements |
|---------|-------------|
| `main.py` | Corrections calculs, support multi-provider, endpoints `/api/models`, gestion non-streaming |
| `config.toml` | 8 providers, 20 modèles |
| `config.yaml` | Configuration Continue synchronisée |
| `static/index.html` | Nouveau modal, filtres, indicateurs de capacités |
| `AGENTS.md` | Documentation agent mise à jour |
| `README.md` | Documentation utilisateur mise à jour |

---

## 📝 Notes pour le Développement Futur

### Rate Limiting par Provider
Actuellement, le rate limiting est global (40 RPM par défaut). À terme, on pourrait implémenter des limites spécifiques par provider :

```python
RATE_LIMITS = {
    "nvidia": 40,
    "mistral": 60,
    "groq": 100,
    # ...
}
```

### Support Gemini Natif
Le support Gemini est partiel (conversion OpenAI→Gemini basique). Pour une meilleure compatibilité, envisager :
- Mapping complet des paramètres
- Gestion des formats de réponse différenciés
- Support des fonctionnalités spécifiques Gemini (tools, etc.)

### Historique des Sessions
Actuellement, le max_context est stocké à la création. Si un utilisateur change de modèle dans Continue sans créer une nouvelle session, le contexte max reste celui du modèle initial.

---

## ✅ Checklist

- [x] Tous les providers configurés dans `config.toml`
- [x] Tous les modèles avec contexte correct
- [x] Endpoint `/api/models` fonctionnel
- [x] Endpoint `/api/providers` enrichi (icônes, couleurs)
- [x] Modal UI avec sélection granulaire
- [x] Filtre de recherche fonctionnel
- [x] Indicateurs de capacités affichés
- [x] Calculs cumulatifs corrigés
- [x] Extraction tokens réels (streaming + non-streaming)
- [x] Contexte max correct par modèle
- [x] Tests de validation passés

---

**Date**: 2026-02-14
**Auteur**: Kimi Code CLI
**Version**: 3.0.0 Multi-Provider
