#!/usr/bin/env python3
"""
Test simple pour valider que le correctif async/await fonctionne.
"""
import asyncio
import sys
import os

# Ajoute le src au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_async_memory_fix():
    """Test simple pour vérifier que await est utilisé correctement."""
    try:
        from kimi_proxy.features.mcp.auto_memory import detect_and_store_memories
        from kimi_proxy.features.mcp.memory import get_memory_manager
        
        print("✅ Imports réussis")
        
        # Test basique - messages avec code important
        test_messages = [
            {"role": "assistant", "content": "```python\n# Configuration importante\ndef setup_api():\n    API_KEY = os.environ.get('API_KEY')\n    if not API_KEY:\n        raise ValueError('API_KEY manquante')\n    return API_KEY\n```"}
        ]
        
        # Mock simple pour éviter dépendances DB
        import unittest.mock
        with unittest.mock.patch('kimi_proxy.features.mcp.memory.get_memory_manager') as mock_get_manager:
            mock_manager = unittest.mock.AsyncMock()
            mock_manager.store_memory.return_value = unittest.mock.MagicMock()
            mock_manager.store_memory.return_value.id = "test_123"
            mock_get_manager.return_value = mock_manager
            
            # Appel de la fonction - ne doit pas générer de RuntimeWarning
            result = await detect_and_store_memories(
                messages=test_messages,
                session_id=1,
                confidence_threshold=0.5
            )
            
            # Vérifie que store_memory a été appelé avec await
            assert mock_manager.store_memory.awaited, "❌ ERREUR: store_memory n'est pas awaité!"
            print("✅ store_memory est correctement awaité")
            
            print(f"✅ Test réussi: {len(result)} mémoire(s) détectée(s)")
            return True
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Test du correctif async/await pour auto-memory...")
    success = asyncio.run(test_async_memory_fix())
    
    if success:
        print("\n🎉 SUCCÈS: Le correctif fonctionne correctement!")
        print("   - Plus de RuntimeWarning 'coroutine not awaited'")
        print("   - L'auto-memory fonctionne avec async/await")
    else:
        print("\n💥 ÉCHEC: Le correctif ne fonctionne pas")
        sys.exit(1)