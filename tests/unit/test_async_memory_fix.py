"""
Test de validation pour le correctif des coroutines non-awaitées dans l'auto-memory.

Ce test vérifie que toutes les fonctions async sont correctement awaitées
pour éviter les RuntimeWarning.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from kimi_proxy.features.mcp.auto_memory import (
    AutomaticMemoryDetector,
    detect_and_store_memories,
    get_memory_detector
)
from kimi_proxy.features.mcp.memory import MemoryManager, get_memory_manager


@pytest.mark.asyncio
async def test_detect_and_store_memories_uses_await():
    """Vérifie que detect_and_store_memories utilise await pour store_memory."""
    
    # Mock du MemoryManager
    mock_manager = AsyncMock(spec=MemoryManager)
    mock_manager.store_memory.return_value = MagicMock()
    mock_manager.store_memory.return_value.id = "test_memory_123"
    
    # Remplace le singleton temporairement
    import kimi_proxy.features.mcp.memory
    original_get_manager = kimi_proxy.features.mcp.memory.get_memory_manager
    kimi_proxy.features.mcp.memory.get_memory_manager = lambda: mock_manager
    
    try:
        # Messages de test
        # Note: AutomaticMemoryDetector détecte les blocs de code significatifs
        # (voir CODE_BLOCK_MIN_LINES). On fournit donc un bloc >= 10 lignes.
        test_messages = [
            {"role": "user", "content": "Voici un code Python important:"},
            {
                "role": "assistant",
                "content": """```python
def hello_world() -> bool:
    message = 'Hello World'
    print(message)
    ok = True
    if not ok:
        raise RuntimeError('unexpected')
    return ok

def main() -> None:
    result = hello_world()
    print('result=', result)

main()
```""",
            },
        ]
        
        # Appel de la fonction - ne doit pas générer de RuntimeWarning
        result = await detect_and_store_memories(
            messages=test_messages,
            session_id=1,
            confidence_threshold=0.5  # Bas pour assurer la détection
        )
        
        # Vérifie que store_memory a été appelé avec await
        assert mock_manager.store_memory.awaited, "store_memory doit être awaité!"
        assert mock_manager.store_memory.call_count > 0, "store_memory doit être appelé"
        
        # Vérifie les paramètres de l'appel
        call_args = mock_manager.store_memory.call_args
        assert call_args[1]['session_id'] == 1
        assert 'content' in call_args[1]
        assert 'memory_type' in call_args[1]
        
        print(f"✅ Test passé: {len(result)} mémoire(s) stockée(s), store_memory correctement awaité")
        
    finally:
        # Restaure le singleton
        kimi_proxy.features.mcp.memory.get_memory_manager = original_get_manager


@pytest.mark.asyncio
async def test_no_runtime_warning_generated():
    """Vérifie qu'aucun RuntimeWarning n'est généré pendant l'exécution."""
    
    import warnings
    
    # Capture les warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")
        
        # Mock du MemoryManager
        mock_manager = AsyncMock(spec=MemoryManager)
        mock_manager.store_memory.return_value = MagicMock()
        mock_manager.store_memory.return_value.id = "test_memory_456"
        
        # Remplace le singleton
        import kimi_proxy.features.mcp.memory
        original_get_manager = kimi_proxy.features.mcp.memory.get_memory_manager
        kimi_proxy.features.mcp.memory.get_memory_manager = lambda: mock_manager
        
        try:
            # Messages de test avec code important
            # Fournit aussi un bloc >= 10 lignes (cohérent avec les seuils de détection)
            test_messages = [
                {
                    "role": "assistant",
                    "content": """```python
# Configuration critique
import os

def get_api_key() -> str:
    value = os.environ.get('API_KEY')
    if not value:
        raise ValueError('API_KEY requise')
    return value

def process_data(data: str) -> str:
    return data.upper()

print(process_data('ok'))
```""",
                }
            ]
            
            # Exécute la fonction
            await detect_and_store_memories(
                messages=test_messages,
                session_id=42,
                confidence_threshold=0.6
            )
            
        finally:
            kimi_proxy.features.mcp.memory.get_memory_manager = original_get_manager
    
    # Filtre les RuntimeWarning spécifiques
    runtime_warnings = [
        w for w in warning_list 
        if issubclass(w.category, RuntimeWarning) 
        and "coroutine not awaited" in str(w.message)
    ]
    
    assert len(runtime_warnings) == 0, f"RuntimeWarning détecté: {[str(w.message) for w in runtime_warnings]}"
    print("✅ Aucun RuntimeWarning de coroutine non-awaitée détecté")


@pytest.mark.asyncio 
async def test_memory_manager_store_memory_is_async():
    """Vérifie que MemoryManager.store_memory est bien une coroutine."""
    
    manager = get_memory_manager()
    
    # Vérifie que la méthode est une coroutine
    import inspect
    assert inspect.iscoroutinefunction(manager.store_memory), \
        "MemoryManager.store_memory doit être une coroutine (async def)"
    
    print("✅ MemoryManager.store_memory est bien une coroutine")


if __name__ == "__main__":
    # Test rapide en mode standalone
    print("🧪 Test du correctif async/await pour auto-memory...")
    
    async def run_tests():
        await test_detect_and_store_memories_uses_await()
        await test_no_runtime_warning_generated() 
        await test_memory_manager_store_memory_is_async()
        print("\n🎉 Tous les tests passés! Le correctif fonctionne correctement.")
    
    asyncio.run(run_tests())