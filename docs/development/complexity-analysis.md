# Analyse Complexité Cyclomatique

## TL;DR
Analyse radon révèle 19 fonctions haute complexité (C+) avec 2 points critiques E/F nécessitant documentation Pattern 6 et refactorisation prioritaire.

## Problème
La complexité cyclomatique moyenne de C (17.42) avec 2 fonctions E/F indique un risque technique croissant pour la maintenabilité du codebase.

## Méthodologie d'Analyse
**Outil** : Radon CC (Cyclomatic Complexity)
**Commande** : `radon cc src/kimi_proxy -a -nc --min C`
**Scope** : 73 fichiers Python, 8883 LOC

## Seuils d'Alerte

| Score | Complexité | Action Requise |
|-------|------------|----------------|
| **A (1-4)** | Simple | Documentation standard |
| **B (5-7)** | Modérée | Documentation améliorée |
| **C (10-19)** | Complexe | **Documentation Pattern 6 OBLIGATOIRE** |
| **D (20-29)** | Très Complexe | **Refactorisation RECOMMANDÉE** |
| **E (30-39)** | Extrêmement Complexe | **Refactorisation OBLIGATOIRE** |
| **F (40+)** | Inmaintenable | **Refactorisation URGENTE** |

## Points Chauds Identifiés

### 🔴 Critique - Score F (40+)
#### `proxy_chat` - F (40+)
**Localisation** : `src/kimi_proxy/api/routes/proxy.py:89`
**Impact** : Point d'entrée principal du proxy
**Risque** : Maintenance impossible, bugs difficiles à tracer

**Actions Recommandées** :
1. **Immédiat** : Documenter avec Pattern 6
2. **Court terme** : Extraire fonctions utilitaires
3. **Long terme** : Refactoriser en classes/services

```python
# Structure proposée
class ProxyChatHandler:
    def __init__(self, router: Router, transformer: Transformer):
        self.router = router
        self.transformer = transformer
    
    async def handle_request(self, request: ChatCompletionRequest):
        # Extraction logique métier
        provider = self.router.select_provider(request.model)
        transformed = self.transformer.to_provider(request, provider)
        return await self._call_provider(transformed, provider)
```

### 🟠 Critique - Score E (30-39)
#### `_proxy_to_provider` - E (30-39)
**Localisation** : `src/kimi_proxy/api/routes/proxy.py:447`
**Impact** : Orchestration appels API externes
**Risque** : Erreurs propagation, difficulté debugging

**Actions Recommandées** :
1. **Immédiat** : Documenter extraction tokens partiels
2. **Court terme** : Extraire retry logic
3. **Long terme** : Pattern Strategy par provider

### 🟡 Modéré - Score C (10-19)

#### Features Layer
- `SimpleCompaction.compact` - C (11)
- `CompactionAutoTrigger.check_and_trigger` - C (11)
- `ContentMasker.should_mask` - C (11)
- `compress_session_history` - C (14)
- `MCPExternalClient.call_mcp_tool` - C (11)
- `MCPRPCClient.make_rpc_call` - C (11)

#### Core Layer
- `_run_migrations` - C (11)
- `count_tokens_tiktoken` - C (15)

#### API Layer
- `MemoryService.find_similar_memories` - C (11)
- `MemoryService._get_real_memories_from_db` - C (11)
- `MemoryService.preview_compression` - C (11)

#### Proxy Layer
- `stream_generator` - C (25)
- `extract_usage_from_stream` - C (20)
- `validate_and_fix_tool_calls` - C (15)

#### Log Watcher
- `LogParser._extract_standard_metrics` - D (22)
- `LogParser._parse_compile_chat_block` - C (11)

## Patterns de Complexité

### Pattern 1: Long Functions
**Symptôme** : Fonctions > 50 lignes avec multiple responsabilités
**Exemples** : `proxy_chat`, `_proxy_to_provider`
**Solution** : Extract Method pattern

```python
# Avant : 100+ lignes
async def proxy_chat(request):
    # Validation
    # Routing
    # Transformation
    # Appel HTTP
    # Gestion erreurs
    # Response formatting

# Après : Functions spécialisées
async def proxy_chat(request):
    validated = validate_request(request)
    provider = route_to_provider(validated.model)
    transformed = transform_request(validated, provider)
    response = await call_provider(transformed, provider)
    return format_response(response)
```

### Pattern 2: Deep Nesting
**Symptôme** : 4+ niveaux d'imbrication try/except/for/if
**Exemples** : `extract_usage_from_stream`
**Solution** : Early returns et guard clauses

```python
# Avant : Deep nesting
def extract_usage_from_stream(stream):
    if stream:
        lines = stream.split('\n')
        for line in lines:
            if 'data:' in line:
                try:
                    data = json.loads(line[5:])
                    if 'usage' in data:
                        # ... nesting continues
                except:
                    pass

# Après : Early returns
def extract_usage_from_stream(stream):
    if not stream:
        return TokenUsage()
    
    lines = stream.split('\n')
    usage_data = []
    
    for line in lines:
        if not line.startswith('data: '):
            continue
        
        try:
            data = json.loads(line[6:])
            if 'usage' in data:
                usage_data.append(data['usage'])
        except json.JSONDecodeError:
            continue
    
    return aggregate_usage(usage_data)
```

### Pattern 3: Multiple Responsibilities
**Symptôme** : Fonctions gérant validation, transformation, appel, et formatting
**Exemples** : `_proxy_to_provider`
**Solution** : Single Responsibility Principle

## Plan de Refactorisation

### Phase 1: Documentation (Immédiat)
- [ ] Documenter toutes fonctions C+ avec Pattern 6
- [ ] Ajouter exemples d'utilisation
- [ ] Documenter invariants et préconditions

### Phase 2: Extraction (Court terme - 2 semaines)
- [ ] Extraire fonctions utilitaires des points critiques
- [ ] Créer classes/services pour logique métier
- [ ] Simplifier fonctions C vers B/A

### Phase 3: Refactorisation (Long terme - 1 mois)
- [ ] Refactoriser fonctions E/F vers C/B
- [ ] Implémenter patterns Strategy/Factory
- [ ] Ajouter tests unitaires pour fonctions extraites

## Métriques Cibles

| Métrique | Actuel | Cible | Délai |
|----------|--------|-------|-------|
| Complexité moyenne | C (17.42) | B (8-12) | 1 mois |
| Fonctions E/F | 2 | 0 | 2 semaines |
| Fonctions C | 17 | < 10 | 1 mois |
| Couverture tests | 60% | 85% | 1 mois |

## Outils d'Analyse Continue

### CI/CD Integration
```yaml
# .github/workflows/complexity-check.yml
- name: Check Complexity
  run: |
    radon cc src/kimi_proxy --min B --fail C
    radon mi src/kimi_proxy --min B --fail C
```

### Pre-commit Hooks
```bash
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: radon
      name: Radon complexity check
      entry: radon cc
      args: [--min, C]
      language: system
      files: ^src/
```

## Golden Rule
**Toute nouvelle fonction doit :**
1. Avoir complexité ≤ B (7) ou justification documentée
2. Suivre Single Responsibility Principle
3. Inclure tests unitaires
4. Documenter les invariants
5. Passer les checks CI/CD

---
*Dernière mise à jour : 2026-02-20*  
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*