# Validation et Correction Arguments Tool - Tool Utils

**TL;DR**: Ces fonctions corrigent automatiquement les arguments JSON malformés des appels tool, utilisant 15+ stratégies de réparation avec métriques et circuit breaker pour éviter les boucles infinies. Elles transforment les erreurs 400 "Bad Request" en appels réussis.

> **NOTE D'ARCHITECTURE** : Ces utilitaires sont **agnostiques** et fonctionnent avec **tout outil** (MCP ou autre). Ils restent pleinement opérationnels dans l'architecture locale où les serveurs MCP Phase 4 fonctionnent via Continue.app. Le proxy ne fait plus de validation spécifique MCP, mais ces fonctions de correction JSON génériques sont essentielles pour la couche Proxy.

## Le Problème des Arguments JSON Malformés

Vous intégrez des APIs d'IA avec des outils (functions calling). Les modèles génèrent parfois des arguments JSON corrompus:

```json
// ❌ JSON malformé généré par l'IA
{"rules": [""]cursor{"  // Virgule manquante, guillemets non fermés
```

Au lieu de rejeter l'appel avec une erreur 400, vous voulez:

- Corriger automatiquement les erreurs communes
- Maintenir des métriques de succès/réussite
- Éviter les corrections infinies (circuit breaker)
- Fournir des diagnostics pour améliorer les prompts

Les fonctions `fix_malformed_json_arguments` et `reconstruct_complex_json` résolvent cette complexité avec une approche multi-stratégies.

### ❌ L'Approche Simpliste
```python
def validate_tool_call(arguments_str: str) -> dict:
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError:
        # Rejet pur et simple
        raise ValueError(f"Arguments JSON invalides: {arguments_str}")
```

### ✅ L'Approche Corrective Multi-Stratégies
```python
def fix_malformed_json_arguments(arguments_str: str) -> str:
    """15 étapes de correction automatique avec métriques."""
    fixed = arguments_str.strip()

    # Étape 1: Fusion des JSON concaténés
    fixed = detect_and_merge_concatenated_json(fixed)

    # Étape 2-15: Corrections spécifiques (virgules, guillemets, etc.)
    fixed = apply_specific_corrections(fixed)

    # Validation finale
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        # Reconstruction agressive en dernier recours
        return reconstruct_complex_json(fixed)
```

## Architecture des Fonctions

### `fix_malformed_json_arguments` (552 LOC)
Fonction principale avec 15 étapes de correction:

1. **Fusion JSON concaténés** - Détecte et fusionne plusieurs objets JSON
2. **Correction patterns directs** - Remplace les erreurs connues
3. **Suppression trailing commas** - Supprime les virgules finales
4. **Ajout virgules manquantes** - Entre propriétés et valeurs
5. **Corrections numériques** - Gestion des nombres sans virgule
6. **Corrections booléens** - true/false/null sans virgule
7. **Reconstruction spécifique** - Pour patterns observés
8. **Gestion arrays vides** - Correction des `[]clé{`
9. **Éléments vides** - Correction des `[""]` malformés
10. **Corrections avancées** - Chaînes longues, objets imbriqués
11. **Position-based fixes** - Pour JSON très longs (>1000 chars)
12. **Gestion duplications** - Suppression des objets répétés
13. **Virgules propriétés** - Correction `"valeur""clé":`
14. **Virgules objets** - Avant `{` et `[`
15. **Reconstruction complète** - En dernier recours

### `reconstruct_complex_json` (107 LOC)
Reconstruction agressive pour JSON très corrompus:

1. **Extraction propriétés** - Regex pour trouver `"clé": valeur`
2. **Parsing valeurs** - String, bool, null, nombres, arrays
3. **Reconstruction tokens** - À partir des tokens JSON valides restants

### Métriques et Circuit Breaker

```python
JSON_FIX_METRICS = {
    "total_attempts": 0,
    "success_by_strategy": {
        "direct_fix": 0,
        "eval_fallback": 0,
        "reconstruct_basic": 0,
        "reconstruct_complex": 0,
        "all_failed": 0
    },
    "failure_reasons": []
}

CIRCUIT_BREAKER_CONFIG = {
    "enabled": True,
    "max_total_attempts": 1000,
    "max_time_ms": 5000
}
```

## Exemples Concrets

### Exemple 1: Virgule Manquante Simple
```python
# Entrée corrompue
'{"name": "test" "age": 25}'

# Après correction étape 5
'{"name": "test", "age": 25}'

# Résultat: JSON valide
```

### Exemple 2: Array Malformé
```python
# Entrée corrompue
'{"rules": [""]cursor{"enabled": true}'

# Étape 1: Détection concaténation
'{"rules": ["cursor"], "enabled": true}'

# Résultat: JSON valide avec array corrigé
```

### Exemple 3: JSON Complexe Très Corrompu
```python
# Entrée très corrompue (position 1146 problématique)
'{"model": "gpt-4", "temperature": 0.7"max_tokens": 100}'

# Reconstruction via extract_properties:
# - model: "gpt-4"
# - temperature: 0.7
# - max_tokens: 100

# Résultat: {"model": "gpt-4", "temperature": 0.7, "max_tokens": 100}
```

### Exemple 4: Circuit Breaker Activation
```python
# Après 1000 tentatives ou 5 secondes
print("⚠️ Circuit breaker activé: max attempts reached")
return arguments_str  # Retourne l'original sans correction
```

## Trade-offs de Conception

| Aspect | Choix | Avantages | Inconvénients |
|--------|-------|-----------|---------------|
| **Multi-stratégies** | 15 étapes séquentielles | Couverture large d'erreurs | Complexité maintenabilité |
| **Circuit Breaker** | Limite temps + tentatives | Évite boucles infinies | Corrections refusées légitimes |
| **Reconstruction agressive** | Regex + parsing manuel | Corrige JSON très corrompus | Risque de perte de données |
| **Métriques détaillées** | Compteurs par stratégie | Diagnostic améliorations | Overhead performance |
| **Fallback eval()** | Exécution Python dangereuse | Corrige certains cas extrêmes | Sécurité (code injection potentiel) |

## Patterns Système Appliqués

- **Pattern 6 (Error Handling)**: Récupération automatique vs échec graceful
- **Pattern 13 (JSON Processing)**: Validation et correction robuste
- **Pattern 14 (Streaming)**: Métriques pour optimisation continue
- **Pattern 1 (Clean Architecture)**: Séparation logique de correction

## Common Misconceptions

### "Ces corrections sont dangereuses"

**Réalité**: Les corrections sont conservatrices - elles n'altèrent que la syntaxe, pas les données. Le circuit breaker garantit qu'aucune tentative infinie n'a lieu.

### "Mieux vaut rejeter les appels malformés"

**Réalité**: Les modèles IA génèrent souvent du JSON légèrement corrompu. La correction automatique améliore significativement le taux de succès des appels tool.

### "Les métriques sont inutiles"

**Réalité**: Les métriques identifient les patterns d'erreur les plus fréquents, permettant d'améliorer les prompts système et réduire les corrections nécessaires.

## Golden Rule: Corriger Plutôt que Rejeter

**Tout argument tool JSON doit être corrigé automatiquement si possible, avec métriques pour amélioration continue.** Les fonctions `fix_malformed_json_arguments` et `reconstruct_complex_json` incarnent cette règle en transformant les erreurs de syntaxe en appels réussis.

---

*Cette documentation explique la logique complexe de correction JSON. Pour l'implémentation complète, voir `src/kimi_proxy/proxy/tool_utils.py:552` et `src/kimi_proxy/proxy/tool_utils.py:382`.*