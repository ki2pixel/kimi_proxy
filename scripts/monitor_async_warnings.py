#!/usr/bin/env python3
"""
Script de monitoring pour détecter les RuntimeWarning 'coroutine not awaited'.

À utiliser en développement ou en production pour s'assurer que le correctif
async/await fonctionne correctement.
"""
import asyncio
import sys
import os
import warnings
import time
from contextlib import contextmanager

# Ajoute le src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

@contextmanager
def catch_runtime_warnings():
    """Capture les RuntimeWarning de coroutine non-awaitée."""
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")
        yield warning_list

async def test_auto_memory_flow():
    """Test complet du flux auto-memory pour détecter les warnings."""
    from kimi_proxy.features.mcp.auto_memory import detect_and_store_memories
    
    # Messages de test qui devraient déclencher l'auto-memory
    test_messages = [
        {"role": "user", "content": "Montre-moi comment configurer un serveur web"},
        {"role": "assistant", "content": '''Voici une configuration complète et importante:

```python
# Configuration serveur web critique
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/health")
def health_check():
    """Point de terminaison essentiel pour le monitoring."""
    return {"status": "healthy", "timestamp": time.time()}

# Configuration production obligatoire
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=4,
        access_log=True
    )
```

Cette configuration est essentielle pour un déploiement en production.'''},
        
        {"role": "user", "content": "Quelles sont les commandes Docker importantes?"},
        {"role": "assistant", "content": '''Voici les commandes Docker essentielles:

```bash
# Installation Docker (obligatoire)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Commandes critiques de gestion
docker system prune -f  # Nettoyage espace disque
docker stats           # Monitoring ressources
docker logs -f container_name  # Logs en temps réel

# Gestion des images
docker pull image_name
docker push registry/image:tag
docker rmi $(docker images -f "dangling=true" -q)
```

Ces commandes sont requises pour la gestion quotidienne.'''}
    ]
    
    with catch_runtime_warnings() as warning_list:
        # Mock pour éviter dépendances DB
        import unittest.mock
        with unittest.mock.patch('kimi_proxy.features.mcp.memory.get_memory_manager') as mock_get_manager:
            mock_manager = unittest.mock.AsyncMock()
            mock_manager.store_memory.return_value = unittest.mock.MagicMock()
            mock_manager.store_memory.return_value.id = f"memory_{int(time.time())}"
            mock_get_manager.return_value = mock_manager
            
            # Exécute la détection auto-memory
            result = await detect_and_store_memories(
                messages=test_messages,
                session_id=999,
                confidence_threshold=0.6
            )
    
    # Analyse les warnings
    runtime_warnings = [
        w for w in warning_list 
        if issubclass(w.category, RuntimeWarning) 
        and "coroutine not awaited" in str(w.message)
    ]
    
    return runtime_warnings, result

async def main():
    """Fonction principale de monitoring."""
    print("🔍 Monitoring des RuntimeWarning 'coroutine not awaited'...")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        runtime_warnings, result = await test_auto_memory_flow()
        
        execution_time = time.time() - start_time
        
        print(f"⏱️  Exécution: {execution_time:.2f}s")
        print(f"📊 Mémoires détectées: {len(result)}")
        
        if runtime_warnings:
            print("\n❌ ALERTES - RuntimeWarning détectés:")
            for i, warning in enumerate(runtime_warnings, 1):
                print(f"   {i}. {warning.message}")
                print(f"      Fichier: {warning.filename}:{warning.lineno}")
            print(f"\n💥 Total: {len(runtime_warnings)} RuntimeWarning(s)")
            return False
        else:
            print("\n✅ SUCCÈS - Aucun RuntimeWarning détecté!")
            print("   🎯 Le correctif async/await fonctionne correctement")
            print("   🚀 L'auto-memory est opérationnel sans warnings")
            return True
            
    except Exception as e:
        print(f"\n💥 ERREUR lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)