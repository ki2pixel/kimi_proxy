"""
Tests unitaires pour le service SimpleCompaction.
"""
import pytest
from typing import List, Dict, Any

from src.kimi_proxy.features.compaction.simple_compaction import (
    SimpleCompaction,
    CompactionResult,
    CompactionConfig,
    get_compactor,
    create_compactor,
)
from src.kimi_proxy.core.tokens import count_tokens_tiktoken


class TestCompactionConfig:
    """Tests pour la configuration de compaction."""
    
    def test_default_config(self):
        """Vérifie les valeurs par défaut de la configuration."""
        config = CompactionConfig()
        
        assert config.max_preserved_messages == 2
        assert config.preserve_system_messages is True
        assert config.create_summary is True
        assert config.summary_max_length == 1000
        assert config.min_messages_to_compact == 6
        assert config.min_tokens_to_compact == 500
        assert config.target_reduction_ratio == 0.60
    
    def test_custom_config(self):
        """Vérifie la configuration personnalisée."""
        config = CompactionConfig(
            max_preserved_messages=5,
            preserve_system_messages=False,
            min_tokens_to_compact=1000
        )
        
        assert config.max_preserved_messages == 5
        assert config.preserve_system_messages is False
        assert config.min_tokens_to_compact == 1000
    
    def test_config_to_dict(self):
        """Vérifie la sérialisation de la configuration."""
        config = CompactionConfig()
        data = config.to_dict()
        
        assert "max_preserved_messages" in data
        assert "preserve_system_messages" in data
        assert data["max_preserved_messages"] == 2


class TestCompactionResult:
    """Tests pour le résultat de compaction."""
    
    def test_result_creation(self):
        """Vérifie la création d'un résultat."""
        result = CompactionResult(
            compacted=True,
            session_id=1,
            original_tokens=1000,
            compacted_tokens=600,
            tokens_saved=400,
            compaction_ratio=40.0,
            messages_before=10,
            messages_after=5
        )
        
        assert result.compacted is True
        assert result.tokens_saved == 400
        assert result.compaction_ratio == 40.0
    
    def test_result_to_dict(self):
        """Vérifie la sérialisation du résultat."""
        result = CompactionResult(
            compacted=True,
            session_id=1,
            original_tokens=1000,
            compacted_tokens=600,
            tokens_saved=400,
            compaction_ratio=40.0,
            messages_before=10,
            messages_after=5
        )
        
        data = result.to_dict()
        
        assert data["compacted"] is True
        assert data["tokens_saved"] == 400
        assert data["compaction_ratio"] == 40.0
        assert "timestamp" in data


class TestSimpleCompaction:
    """Tests pour le service SimpleCompaction."""
    
    def create_test_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """Crée des messages de test avec suffisamment de tokens."""
        messages = []
        
        # Ajoute un message système
        messages.append({
            "role": "system",
            "content": "You are a helpful assistant with expertise in software development."
        })
        
        # Ajoute des échanges user/assistant avec contenu long pour atteindre 500+ tokens
        for i in range(count):
            messages.append({
                "role": "user",
                "content": f"Question {i + 1}: Comment implémenter une architecture modulaire scalable en Python avec gestion d'erreurs robuste et monitoring? Voici le contexte: " + "y" * 200
            })
            messages.append({
                "role": "assistant",
                "content": f"Réponse {i + 1}: Pour implémenter une architecture modulaire scalable, vous devriez considérer plusieurs patterns de conception incluant l'injection de dépendances, le pattern factory, et l'utilisation d'interfaces claires. Voici une approche détaillée: " + "x" * 300
            })
        
        return messages
    
    def test_should_compact_empty_list(self):
        """Vérifie qu'une liste vide ne déclenche pas de compaction."""
        compactor = SimpleCompaction()
        should, reason = compactor.should_compact([])
        
        assert should is False
        assert reason == "no_messages"
    
    def test_should_compact_insufficient_messages(self):
        """Vérifie que peu de messages ne déclenchent pas de compaction."""
        compactor = SimpleCompaction()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        should, reason = compactor.should_compact(messages)
        
        assert should is False
        assert reason == "insufficient_messages"
    
    def test_should_compact_sufficient_messages(self):
        """Vérifie que suffisamment de messages déclenchent la compaction."""
        compactor = SimpleCompaction()
        messages = self.create_test_messages(count=5)  # 1 system + 10 messages
        
        should, reason = compactor.should_compact(messages)
        
        assert should is True
        assert reason == "threshold_reached"
    
    def test_compact_empty_list(self):
        """Vérifie la compaction d'une liste vide."""
        compactor = SimpleCompaction()
        result = compactor.compact([], session_id=1)
        
        assert result.compacted is False
        assert result.reason == "no_messages"
    
    def test_compact_not_enough_messages(self):
        """Vérifie la compaction avec peu de messages."""
        compactor = SimpleCompaction()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        result = compactor.compact(messages, session_id=1)
        
        assert result.compacted is False
        assert result.messages_before == 2
        assert result.messages_after == 2
    
    def test_compact_successful(self):
        """Vérifie une compaction réussie."""
        compactor = SimpleCompaction()
        messages = self.create_test_messages(count=5)  # 11 messages
        
        original_tokens = count_tokens_tiktoken(messages)
        
        result = compactor.compact(messages, session_id=1)
        
        # Vérifie le résultat
        assert result.compacted is True
        assert result.session_id == 1
        assert result.messages_before == 11
        assert result.system_preserved == 1  # Message système préservé
        assert result.recent_preserved == 4  # 2 échanges récents (max_preserved=2)
        assert result.summarized_count == 6  # Le reste résumé
        
        # Vérifie les tokens
        assert result.original_tokens == original_tokens
        assert result.tokens_saved > 0
        assert result.compaction_ratio > 0
        
        # Vérifie le résumé
        assert result.summary_text is not None
        assert "Historique" in result.summary_text
    
    def test_compact_preserves_system_messages(self):
        """Vérifie que les messages système sont préservés."""
        compactor = SimpleCompaction()
        
        # Il faut au moins 6 messages non-système (min_messages_to_compact) + 2 système = 8 minimum
        # Plus 4 messages pour avoir assez à résumer (après préservation de 4 récents)
        # Donc 2 système + 10 non-système = 12 messages minimum
        messages = [
            {"role": "system", "content": "System prompt 1 with detailed configuration instructions for the assistant behavior and constraints"},
            {"role": "system", "content": "System prompt 2 with additional settings and constraints that must be preserved during compaction"},
            # Échanges à résumer (6 messages)
            {"role": "user", "content": "Hello, I need help with a complex problem involving software architecture and design patterns " + "y" * 120},
            {"role": "assistant", "content": "Hi! I can help you with that. Let me provide a detailed explanation of how to approach this complex architectural problem with practical examples. " + "x" * 180},
            {"role": "user", "content": "Question about implementation details and specific code examples? " + "z" * 120},
            {"role": "assistant", "content": "Answer with comprehensive details including code samples and best practices for implementation! " + "a" * 180},
            {"role": "user", "content": "Another question regarding best practices for testing and deployment strategies? " + "b" * 120},
            {"role": "assistant", "content": "Another detailed answer with examples showing how to properly test and deploy your application! " + "c" * 180},
            # Échanges récents à préserver (4 messages)
            {"role": "user", "content": "Recent question about testing strategy and quality assurance processes? " + "d" * 120},
            {"role": "assistant", "content": "Recent answer about testing best practices and how to implement comprehensive test coverage! " + "e" * 180},
            {"role": "user", "content": "Final question about deployment and continuous integration workflows? " + "f" * 120},
            {"role": "assistant", "content": "Final answer about deployment strategies and CI/CD pipeline configuration best practices! " + "g" * 180},
        ]
        
        result = compactor.compact(messages, session_id=1)
        
        assert result.compacted is True
        assert result.system_preserved == 2
    
    def test_compact_without_summary(self):
        """Vérifie la compaction sans création de résumé."""
        config = CompactionConfig(create_summary=False)
        compactor = SimpleCompaction(config)
        messages = self.create_test_messages(count=5)
        
        result = compactor.compact(messages, session_id=1)
        
        assert result.compacted is True
        assert result.summary_text is None
    
    def test_custom_preserve_count(self):
        """Vérifie la configuration personnalisée du nombre de messages préservés."""
        config = CompactionConfig(max_preserved_messages=3)
        compactor = SimpleCompaction(config)
        messages = self.create_test_messages(count=5)
        
        result = compactor.compact(messages, session_id=1)
        
        assert result.recent_preserved == 6  # 3 échanges = 6 messages
    
    def test_create_summary(self):
        """Vérifie la création de résumé."""
        compactor = SimpleCompaction()
        
        messages = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
            {"role": "assistant", "content": "Answer 2"},
        ]
        
        summary = compactor._create_summary(messages)
        
        assert "Historique" in summary
        assert "messages" in summary
        assert "tokens" in summary
    
    def test_get_context_with_reserved_fits(self):
        """Vérifie le contexte qui rentre sans compaction."""
        compactor = SimpleCompaction()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        filtered, meta = compactor.get_context_with_reserved(
            messages,
            max_context_size=100000,
            reserved_tokens=5000
        )
        
        assert meta["compacted"] is False
        assert meta["reason"] == "fits_in_context"
        assert meta["reserved_tokens"] == 5000


class TestCompactionSingleton:
    """Tests pour les fonctions utilitaires de compaction."""
    
    def test_get_compactor_singleton(self):
        """Vérifie que get_compactor retourne une instance singleton."""
        compactor1 = get_compactor()
        compactor2 = get_compactor()
        
        assert compactor1 is compactor2
    
    def test_create_compactor_new_instance(self):
        """Vérifie que create_compactor crée une nouvelle instance."""
        compactor1 = create_compactor()
        compactor2 = create_compactor()
        
        assert compactor1 is not compactor2
    
    def test_create_compactor_with_config(self):
        """Vérifie la création avec configuration personnalisée."""
        config = CompactionConfig(max_preserved_messages=5)
        compactor = create_compactor(config)
        
        assert compactor.config.max_preserved_messages == 5


class TestCompactionEdgeCases:
    """Tests pour les cas limites."""
    
    def test_all_system_messages(self):
        """Vérifie avec uniquement des messages système."""
        compactor = SimpleCompaction()
        messages = [
            {"role": "system", "content": "System 1"},
            {"role": "system", "content": "System 2"},
            {"role": "system", "content": "System 3"},
        ]
        
        result = compactor.compact(messages, session_id=1)
        
        # Ne devrait pas compacter car pas de messages non-système
        assert result.compacted is False
    
    def test_large_content(self):
        """Vérifie avec du contenu très long."""
        compactor = SimpleCompaction()
        
        # Crée un message très long
        long_content = "x" * 10000
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": "Response"},
        ]
        
        result = compactor.compact(messages, session_id=1)
        
        # Devrait calculer correctement les tokens
        assert result.original_tokens > 0
    
    def test_multilingual_content(self):
        """Vérifie avec du contenu multilingue."""
        compactor = SimpleCompaction()
        
        messages = [
            {"role": "system", "content": "Système en français"},
            {"role": "user", "content": "日本語の内容"},
            {"role": "assistant", "content": "Réponse en français"},
            {"role": "user", "content": "English content here"},
            {"role": "assistant", "content": "Mixed: 中文 и русский"},
        ]
        
        result = compactor.compact(messages, session_id=1)
        
        # Devrait gérer le contenu multilingue
        assert result.original_tokens > 0
    
    def test_token_calculation_accuracy(self):
        """Vérifie la précision du calcul des tokens."""
        compactor = SimpleCompaction()
        
        # Message simple avec nombre de tokens connu
        messages = [
            {"role": "user", "content": "Hello world"}
        ]
        
        result = compactor.compact(messages, session_id=1)
        
        # Vérifie que les tokens sont cohérents
        assert result.original_tokens >= 3  # Au moins les tokens de structure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
