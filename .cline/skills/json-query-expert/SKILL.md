---
name: json-query-expert
description: Expert en manipulation de données JSON massives via le pattern "Sniper". Stratégie | Ne jamais charger un fichier > 1000 lignes. Inspection via json_query_jsonpath. Édition via edit_file.
---

# JSON Query Expert

> **Expertise** : Manipulation chirurgicale de JSON massifs, extraction précise via JSONPath, optimisation token pour fichiers de configuration.

## Quick Start

### Mental Model

JSON Query Expert utilise le pattern "Sniper" pour les fichiers JSON :
- Jamais de chargement complet de fichiers > 1000 lignes
- Extraction ciblée avec `json_query_jsonpath`
- Localisation précise avant édition
- Modification chirurgicale avec `edit_file`

### Workflow obligatoire

1. **Inspection** : `json_query_jsonpath` pour localiser les données
2. **Localisation** : Trouver les lignes exactes dans le fichier
3. **Édition** : `edit_file` pour modification ciblée
4. **Validation** : Vérification minimale du résultat

### Patterns d'utilisation

#### Pour modification de configuration

```bash
# 1. Localiser la configuration cible
json_query_jsonpath package.json "$.scripts.dev"

# 2. Trouver les lignes correspondantes
json_query_search_keys package.json "scripts.dev"

# 3. Éditer chirurgicalement
edit_file package.json --line 15 --replacement '"dev": "vite --port 3000",'
```

#### Pour manipulation de i18n

```bash
# 1. Extraire uniquement les traductions nécessaires
json_query_jsonpath locales/fr.json "$.pages.home.title"

# 2. Localiser les clés manquantes
json_query_search_keys locales/fr.json "pages.home"

# 3. Ajouter les traductions manquantes
edit_file locales/fr.json --line 45 --replacement '"title": "Page d''accueil",'
```

## Production-safe patterns

### Pattern "Sniper" pour fichiers massifs

```bash
# ❌ JAMAIS charger un gros fichier entièrement
read_file massive_manifest.json  # 5000+ lignes = PROHIBÉ

# ✅ Pattern "Sniper" obligatoire
# 1. Inspection ciblée
json_query_jsonpath massive_manifest.json "$.compo
<truncated 21134 bytes>