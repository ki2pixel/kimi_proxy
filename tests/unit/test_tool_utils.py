#!/usr/bin/env python3
"""
Test pour la validation et génération d'IDs de tool calls.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from kimi_proxy.proxy.tool_utils import generate_tool_call_id


def test_generate_tool_call_id():
    """Test la génération d'IDs."""
    print("🧪 Test génération d'IDs...")
    
    # Test génération standard
    for i in range(5):
        tool_id = generate_tool_call_id()
        print(f"   ID généré: {tool_id} (longueur: {len(tool_id)})")
        assert len(tool_id) == 9, f"Longueur incorrecte: {len(tool_id)}"
        assert tool_id.isalnum(), f"ID non alphanumérique: {tool_id}"
    
    # Test longueur personnalisée
    custom_id = generate_tool_call_id(12)
    print(f"   ID personnalisé (12): {custom_id}")
    assert len(custom_id) == 12, f"Longueur personnalisée incorrecte: {len(custom_id)}"
    assert custom_id.isalnum(), f"ID non alphanumérique: {custom_id}"
    
    print("✅ Génération d'IDs: OK")


def main():
    """Exécute tous les tests."""
    print("🚀 Lancement des tests pour tool_utils.py")
    
    try:
        test_generate_tool_call_id()
        
        print("\n🎉 TOUS LES TESTS SONT OK!")
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
