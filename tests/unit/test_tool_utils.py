#!/usr/bin/env python3
"""
Test pour la validation et génération d'IDs de tool calls.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from kimi_proxy.proxy.tool_utils import (
    generate_tool_call_id,
    validate_tool_call_id,
    validate_and_fix_tool_calls
)


def test_generate_tool_call_id():
    """Test la génération d'IDs."""
    print("🧪 Test génération d'IDs...")
    
    # Test génération standard
    for i in range(5):
        tool_id = generate_tool_call_id()
        print(f"   ID généré: {tool_id} (longueur: {len(tool_id)})")
        assert len(tool_id) == 9, f"Longueur incorrecte: {len(tool_id)}"
        assert validate_tool_call_id(tool_id), f"ID invalide: {tool_id}"
    
    # Test longueur personnalisée
    custom_id = generate_tool_call_id(12)
    print(f"   ID personnalisé (12): {custom_id}")
    assert len(custom_id) == 12, f"Longueur personnalisée incorrecte: {len(custom_id)}"
    
    print("✅ Génération d'IDs: OK")


def test_validate_tool_call_id():
    """Test la validation d'IDs."""
    print("\n🧪 Test validation d'IDs...")
    
    # IDs valides
    valid_ids = ["abc123XYZ", "A1B2C3D4E", "123456789", "abcdefghi"]
    for tool_id in valid_ids:
        assert validate_tool_call_id(tool_id), f"ID devrait être valide: {tool_id}"
    
    # IDs invalides
    invalid_ids = ["", "abc", "abc-123", "abc_123", "123!@#$%", "1234567890"]
    for tool_id in invalid_ids:
        assert not validate_tool_call_id(tool_id), f"ID devrait être invalide: {tool_id}"
    
    print("✅ Validation d'IDs: OK")


def test_validate_and_fix_tool_calls():
    """Test la correction des tool calls dans une requête."""
    print("\n🧪 Test correction des tool calls...")
    
    # Test avec tool calls valides
    body_valid = {
        "messages": [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "abc123XYZ", "type": "function", "function": {"name": "test"}},
                    {"id": "DEF456GHI", "type": "function", "function": {"name": "test2"}}
                ]
            }
        ]
    }
    
    fixed_body, stats = validate_and_fix_tool_calls(body_valid)
    assert stats["fixed_ids"] == 0, f"Aucune correction attendue: {stats}"
    assert stats["total_tool_calls"] == 2, f"2 tool calls attendus: {stats}"
    
    # Test avec tool calls invalides
    body_invalid = {
        "messages": [
            {
                "role": "assistant", 
                "content": None,
                "tool_calls": [
                    {"id": "", "type": "function", "function": {"name": "test"}},
                    {"id": "invalid-id", "type": "function", "function": {"name": "test2"}},
                    {"type": "function", "function": {"name": "test3"}}  # Pas d'ID
                ]
            }
        ]
    }
    
    fixed_body, stats = validate_and_fix_tool_calls(body_invalid)
    assert stats["fixed_ids"] == 3, f"3 corrections attendues: {stats}"
    assert stats["total_tool_calls"] == 3, f"3 tool calls attendus: {stats}"
    assert len(stats["invalid_ids"]) == 1, f"1 ID invalide attendu: {stats['invalid_ids']}"
    
    # Vérifie que tous les IDs sont maintenant valides
    for tool_call in fixed_body["messages"][0]["tool_calls"]:
        assert validate_tool_call_id(tool_call["id"]), f"ID devrait être valide: {tool_call['id']}"
    
    print("✅ Correction des tool calls: OK")


def test_validate_and_fix_tool_results():
    """Test la correction des tool results dans une requête."""
    print("\n🧪 Test correction des tool results...")
    
    # Test avec tool results invalides
    body_with_tool_results = {
        "messages": [
            {
                "role": "tool",
                "content": "Résultat du tool",
                "tool_call_id": ""  # ID vide
            },
            {
                "role": "tool", 
                "content": "Autre résultat",
                "tool_call_id": "invalid-id"  # ID invalide
            },
            {
                "role": "tool",
                "content": "Résultat valide",
                "tool_call_id": "abc123XYZ"  # ID valide
            }
        ]
    }
    
    fixed_body, stats = validate_and_fix_tool_calls(body_with_tool_results)
    assert stats["fixed_ids"] == 2, f"2 corrections attendues pour tool results: {stats}"
    assert stats["total_tool_results"] == 3, f"3 tool results attendus: {stats}"
    
    # Vérifie que tous les tool_call_id sont maintenant valides
    for message in fixed_body["messages"]:
        if message.get("role") == "tool":
            tool_call_id = message.get("tool_call_id")
            assert validate_tool_call_id(tool_call_id), f"tool_call_id devrait être valide: {tool_call_id}"
    
    print("✅ Correction des tool results: OK")


def test_edge_cases():
    """Test des cas limites."""
    print("\n🧪 Test cas limites...")
    
    # Body vide
    empty_body, stats = validate_and_fix_tool_calls({})
    assert stats["total_tool_calls"] == 0, "Aucun tool call attendu"
    
    # Body None
    none_body, stats = validate_and_fix_tool_calls(None)
    assert none_body is None, "Body None devrait rester None"
    
    # Messages sans tool_calls
    no_tools_body = {"messages": [{"role": "user", "content": "Hello"}]}
    fixed_body, stats = validate_and_fix_tool_calls(no_tools_body)
    assert stats["total_tool_calls"] == 0, "Aucun tool call attendu"
    
    # Tool calls avec types incorrects
    weird_body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": "not_a_list"  # Type incorrect
            }
        ]
    }
    
    fixed_body, stats = validate_and_fix_tool_calls(weird_body)
    assert stats["total_tool_calls"] == 0, "Aucun tool call traitable"
    
    print("✅ Cas limites: OK")


def main():
    """Exécute tous les tests."""
    print("🚀 Lancement des tests pour tool_utils.py")
    
    try:
        test_generate_tool_call_id()
        test_validate_tool_call_id()
        test_validate_and_fix_tool_calls()
        test_validate_and_fix_tool_results()
        test_edge_cases()
        
        print("\n🎉 TOUS LES TESTS SONT OK!")
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST ÉCHOUÉ: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
