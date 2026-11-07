# Validation et Correction des Arguments Tool

## TL;DR
`fix_malformed_json_arguments()` applique un pipeline de stratégies pures pour réparer les arguments JSON des tool calls. Aucune évaluation dynamique de code n'est effectuée. Les échecs sont bornés dans une `deque(maxlen=100)` et le budget de réparation est limité à 100 ms par appel.

## Le problème
Les modèles génèrent parfois des arguments JSON légèrement corrompus :

```json
{"query":"abc" "limit":3}
```

Rejeter la requête avec un 400 casse la conversation. Exécuter la chaîne comme du code Python serait une faille critique. Il faut donc corriger la syntaxe de manière conservatrice, sans jamais évaluer le contenu.

## Architecture du pipeline

### ❌ Ancienne approche monolithique
- Une fonction de plusieurs centaines de lignes.
- Validation après certaines étapes seulement.
- Fallback `ast.literal_eval` sur une chaîne issue du modèle.
- Liste `failure_reasons` non bornée.
- Compteur global d'essais qui désactivait la réparation après dix tentatives dans tout le processus.

### ✅ Approche actuelle
```python
for strategy in strategies:
    if budget_depasse:
        break
    candidate = strategy.apply(cleaned)
    if json_valide(candidate):
        return candidate
    cleaned = candidate
```

Chaque stratégie est une fonction pure `str -> str`. Le pipeline valide le résultat après chaque groupe et conserve les transformations intermédiaires.

### Stratégies appliquées

| Ordre | Stratégie | Rôle |
|---|---|---|
| 1 | Fusion JSON concaténé | Fusionne `{"a":1}{"b":2}` |
| 2 | Corrections directes | Patterns connus, tableaux, virgules finales, virgules de propriétés |
| 3 | Virgule numérique | Corrige `123"clé":` |
| 4 | Virgule booléenne | Corrige `true"clé":`, `false"clé":`, `null"clé":` |
| 5 | Corrections avancées | Tableaux vides, éléments vides, guillemets, doublons, positions |
| 6 | Reconstruction basique | Extrait les paires `"clé": valeur` |
| 7 | Reconstruction complexe | Regex de propriétés puis reconstruction par tokens |

## Métriques

```python
JSON_FIX_METRICS = {
    "total_attempts": 0,
    "success_by_strategy": {
        "direct_fix": 0,
        "reconstruct_basic": 0,
        "reconstruct_complex": 0,
        "all_failed": 0,
    },
    "failure_reasons": deque(maxlen=100),
}
```

`failure_reasons` ne dépasse jamais 100 entrées. Les motifs sont écrits en français.

## Budget de temps

`CIRCUIT_BREAKER_CONFIG["max_time_ms"]` vaut 100 ms. Le budget s'applique à chaque appel de `run_repair_pipeline()`. Il n'existe plus de plafond global qui désactiverait la réparation pour tout le processus.

## Exemples

### Virgule manquante
```python
# Entrée
'{"query":"abc" "limit":3}'

# Sortie
'{"query":"abc","limit":3}'
```

### Tableau malformé
```python
# Entrée
'{"rules": [""]cursor{"enabled": true}'

# Sortie
'{"rules": ["cursor"], "enabled": true}'
```

### Budget dépassé
```text
⚠️ Réparation JSON interrompue : délai maximal dépassé
❌ Réparation JSON impossible après toutes les stratégies
```

La fonction retourne la chaîne originale. L'appelant décide de conserver ou de rejeter l'argument.

## Trade-offs

| Aspect | Choix | Avantage | Limite |
|---|---|---|---|
| Multi-stratégies | Fonctions pures séquentielles | Complexité maîtrisée et testable | Couverture dépendante de l'ordre |
| Budget de temps | 100 ms par appel | Protège la boucle de requête | Certains JSON volumineux ne sont pas réparés |
| Métriques | Compteurs par stratégie | Diagnostic des erreurs fréquentes | Overhead minimal |
| Aucune évaluation dynamique | Reconstruction syntaxique uniquement | Pas d'exécution de code | Les littéraux Python ne sont plus convertis |

## Common Misconceptions

### « La reconstruction agressive exécute le contenu »
Non. Le pipeline manipule uniquement des chaînes et `json.loads()`. Aucune fonction d'évaluation Python n'est appelée.

### « Toutes les erreurs JSON doivent être réparées »
Non. Le pipeline est best-effort. Si aucune stratégie ne produit un JSON valide, la chaîne originale est retournée sans exécution.

### « Les métriques sont illimitées »
Non. `failure_reasons` est une `deque(maxlen=100)`.

## Golden Rule
**Corriger la syntaxe plutôt que rejeter, sans jamais évaluer le contenu.**

---
*Dernière mise à jour : 2026-11-06*
*Implémentation : `src/kimi_proxy/proxy/tool_utils.py`.*
