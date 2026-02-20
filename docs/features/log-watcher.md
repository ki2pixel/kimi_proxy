# Log Watcher : Monitoring Temps Réel PyCharm

**TL;DR**: Le log watcher parse les logs PyCharm en temps réel, extrait métriques compilation/execution, et met à jour le dashboard via WebSocket. Complexité D justifiée par parsing robuste blocs CompileChat.

## Le Problème des Logs Développeur

Vous codez. PyCharm génère des logs verbeux. Vous voulez métriques utiles sans parsing manuel.

## ❌ Parsing Regex Simpliste (Avant)

```python
# Regex fragile
metrics = re.findall(r"(\d+)ms", log_line)
if metrics:
    return int(metrics[0])
return 0  # Erreur silencieuse
```

## ✅ Parser Structuré (Actuel)

```python
class LogParser:
    def _extract_standard_metrics(self, block: str) -> dict:
        """Extrait métriques standard avec validation"""
        return {
            "compile_time": self._parse_time(block),
            "memory_usage": self._parse_memory(block),
            "error_count": len(self._find_errors(block))
        }
    
    def _parse_compile_chat_block(self, block: str) -> CompileMetrics:
        """Parse blocs CompileChat avec patterns connus"""
        # Logique robuste avec fallbacks
```

## Architecture Technique

### Flux de Parsing

```
PyCharm Logs → FileWatcher → LogParser
                              ↓
                         _extract_standard_metrics()
                              ↓
                         _parse_compile_chat_block()
                              ↓
                         WebSocketManager
                              ↓
                         Dashboard (temps réel)
```

### Patterns de Logs Supportés

| Type Log | Pattern | Métriques Extraites |
| -------- | ------- | ------------------- |
| Compilation | `CompileChat: 1500ms` | temps, fichiers |
| Execution | `Run: 200ms` | durée, statut |
| Erreurs | `ERROR: line 42` | compte, sévérité |
| Tests | `pytest: 45s` | durée, succès/échec |

## Parsing Métriques Log (Pattern 6)

**TL;DR**: Le parser analyse les blocs CompileChat avec complexité D pour extraire métriques précises sans perdre de données.

### Défis Parsing
Les logs PyCharm mélangent métriques standard et blocs CompileChat. Une erreur de parsing peut invalider toute la session.

### ✅ Logique Interne
```python
# Dans parser.py:_extract_standard_metrics
def _extract_standard_metrics(self, log_line: str) -> dict:
    # Pattern matching hiérarchique
    if 'tokens:' in log_line:
        # Validation numérique
        tokens = int(re.search(r'tokens:(\d+)', log_line).group(1))
        # Bounds checking
        if tokens > 0 and tokens < 100000:
            return {'tokens': tokens}
    return {}
```

### Gestion Erreurs Parsing
- **Validation stricte** : rejet automatique des valeurs invalides
- **Fallback partiel** : extraction des métriques valides même si une ligne échoue
- **Logging détaillé** : traçabilité des rejets pour debug

### Règle d'Or : Validation Plutôt Que Silence
Préférer rejeter une métrique invalide que de corrompre les statistiques globales.

### Extraction Métriques

```python
def _extract_standard_metrics(self, block: str) -> dict:
    """Extrait métriques avec validation et fallbacks"""
    metrics = {
        "compile_time": self._safe_extract_time(block),
        "memory_peak": self._safe_extract_memory(block),
        "file_count": self._count_files(block),
        "error_count": len(self._find_errors(block))
    }
    
    # Validation cohérence
    if metrics["compile_time"] > 30000:  # 30s+
        metrics["compile_time"] = None  # Anomalie
    
    return metrics
```

### Parsing Blocs CompileChat

```python
def _parse_compile_chat_block(self, block: str) -> CompileMetrics:
    """Parse spécialisé pour blocs PyCharm"""
    lines = block.split('\n')
    
    # Pattern: "CompileChat: 1500ms, 42 files"
    compile_match = re.search(r'CompileChat:\s*(\d+)ms', block)
    files_match = re.search(r'(\d+)\s+files', block)
    
    return CompileMetrics(
        compile_time=int(compile_match.group(1)) if compile_match else 0,
        files_processed=int(files_match.group(1)) if files_match else 0,
        timestamp=datetime.now(),
        success=self._check_success_indicators(block)
    )
```

## Patterns Système Appliqués

- **Pattern 2** : Injection dépendances parser
- **Pattern 6** : Gestion erreurs parsing avec fallbacks
- **Pattern 15** : Mise à jour temps réel dashboard via WebSocket

## Points Chauds Complexité

### _extract_standard_metrics() - Score D
- **Raison** : 57 LOC de parsing robuste avec validation
- **Solution** : Décomposition en extracteurs spécialisés

### _parse_compile_chat_block() - Score C
- **Raison** : 142 LOC de parsing complexe PyCharm
- **Solution** : Séparation patterns regex par type

## Performance Optimisation

### File Watching Efficace

```python
class LogWatcher:
    def __init__(self):
        self.observer = Observer()
        self.parser = LogParser()
        self.last_position = 0
        
    def on_modified(self, event):
        """Lit uniquement les nouvelles lignes"""
        with open(event.src_path, 'r') as f:
            f.seek(self.last_position)
            new_content = f.read()
            self.last_position = f.tell()
            
        if new_content.strip():
            self.process_new_content(new_content)
```

### Batch Processing

```python
def process_batch(self, lines: List[str]) -> List[Metrics]:
    """Traite les logs par batch pour éviter surcharge"""
    batch_size = 100
    results = []
    
    for i in range(0, len(lines), batch_size):
        batch = lines[i:i+batch_size]
        block = '\n'.join(batch)
        metrics = self.parser._extract_standard_metrics(block)
        results.append(metrics)
        
    return results
```

## Integration Dashboard

### WebSocket Updates

```python
async def send_metrics_update(self, metrics: dict):
    """Envoie métriques au dashboard en temps réel"""
    await self.websocket_manager.broadcast({
        "type": "log_metrics",
        "data": {
            "compile_time": metrics["compile_time"],
            "memory_usage": metrics["memory_peak"],
            "timestamp": datetime.now().isoformat(),
            "errors": metrics["error_count"]
        }
    })
```

## Golden Rule : Parse Avec Contexte, Jamais Ligne par Ligne

Le parsing doit considérer le bloc complet pour la cohérence des métriques; le parsing ligne par ligne perd le contexte temporel et structural des logs PyCharm.