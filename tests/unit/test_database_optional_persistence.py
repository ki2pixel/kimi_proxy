"""
Tests unitaires pour la persistance optionnelle des sessions.

Valide que les opérations CRUD de session fonctionnent correctement
en mode in-memory (persist_sessions=false) et en mode SQLite fichier.
"""
import os
import sqlite3
import time
from unittest.mock import patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────

def _reset_memory_db():
    """Réinitialise la DB en mémoire partagée entre chaque test."""
    import kimi_proxy.core.database as db_mod
    # Ferme la connexion globale en mémoire si elle existe
    if db_mod._mem_conn is not None:
        try:
            db_mod._mem_conn.close()
        except Exception:
            pass
        db_mod._mem_conn = None
    db_mod._invalidate_session_cache()


@pytest.fixture(autouse=True)
def clean_memory_state():
    """Nettoie l'état global du module database entre chaque test."""
    _reset_memory_db()
    yield
    _reset_memory_db()


# ── Tests _should_persist ────────────────────────────────────────────────────

class TestShouldPersist:
    """Vérifie la logique de détermination du mode de persistance."""

    def test_env_true_overrides_config(self):
        """KIMI_PERSIST_SESSIONS=true force la persistance."""
        from kimi_proxy.core.database import _should_persist
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "true"}):
            assert _should_persist() is True

    def test_env_false_overrides_config(self):
        """KIMI_PERSIST_SESSIONS=false désactive la persistance."""
        from kimi_proxy.core.database import _should_persist
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "false"}):
            assert _should_persist() is False

    def test_env_case_insensitive(self):
        """La variable d'environnement est insensible à la casse."""
        from kimi_proxy.core.database import _should_persist
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "TRUE"}):
            assert _should_persist() is True
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "False"}):
            assert _should_persist() is False

    def test_default_without_env(self):
        """Sans variable d'env, utilise la config TOML (false par défaut)."""
        from kimi_proxy.core.database import _should_persist
        env = os.environ.copy()
        env.pop("KIMI_PERSIST_SESSIONS", None)
        with patch.dict(os.environ, env, clear=True):
            # La config TOML par défaut a persist_sessions=false
            result = _should_persist()
            assert isinstance(result, bool)


# ── Tests Session CRUD en mode in-memory ─────────────────────────────────────

class TestInMemorySessionCRUD:
    """Teste les opérations CRUD de session avec la DB en mémoire."""

    @pytest.fixture(autouse=True)
    def force_in_memory(self):
        """Force le mode in-memory pour tous les tests de cette classe."""
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "false"}):
            from kimi_proxy.core.database import init_database
            init_database()
            yield

    def test_create_session_in_memory(self):
        """Crée une session en mémoire et vérifie ses attributs."""
        from kimi_proxy.core.database import create_session
        session = create_session("Test Session", provider="test:provider", model="test-model")
        assert session is not None
        assert session["name"] == "Test Session"
        assert session["provider"] == "test:provider"
        assert session["model"] == "test-model"
        assert session["is_active"] == 1

    def test_get_active_session_in_memory(self):
        """Récupère la session active après création."""
        from kimi_proxy.core.database import create_session, get_active_session
        create_session("Active Test", provider="p1")
        active = get_active_session()
        assert active is not None
        assert active["name"] == "Active Test"

    def test_multiple_sessions_only_one_active(self):
        """Seule la dernière session créée est active."""
        from kimi_proxy.core.database import create_session, get_active_session
        create_session("Session 1", provider="p1")
        create_session("Session 2", provider="p2")
        active = get_active_session()
        assert active["name"] == "Session 2"

    def test_get_session_by_id(self):
        """Récupère une session par son ID."""
        from kimi_proxy.core.database import create_session, get_session_by_id
        session = create_session("By ID", provider="p1")
        found = get_session_by_id(session["id"])
        assert found is not None
        assert found["name"] == "By ID"

    def test_get_all_sessions(self):
        """Liste toutes les sessions en mémoire."""
        from kimi_proxy.core.database import create_session, get_all_sessions
        create_session("S1", provider="p1")
        create_session("S2", provider="p2")
        all_sessions = get_all_sessions()
        assert len(all_sessions) >= 2

    def test_update_session_model(self):
        """Met à jour le modèle d'une session."""
        from kimi_proxy.core.database import create_session, update_session_model, get_session_by_id
        session = create_session("Model Update", provider="p1", model="old-model")
        update_session_model(session["id"], "new-model")
        updated = get_session_by_id(session["id"])
        assert updated["model"] == "new-model"

    def test_update_session_external_id(self):
        """Met à jour l'external_session_id."""
        from kimi_proxy.core.database import (
            create_session, update_session_external_id, get_session_by_id
        )
        session = create_session("Ext ID", provider="p1")
        update_session_external_id(session["id"], "ext-abc-123")
        updated = get_session_by_id(session["id"])
        assert updated["external_session_id"] == "ext-abc-123"

    def test_update_session_first_prompt(self):
        """Renomme la session avec le premier prompt si nom générique."""
        from kimi_proxy.core.database import (
            create_session, update_session_first_prompt, get_session_by_id
        )
        session = create_session("Session par défaut", provider="p1")
        update_session_first_prompt(session["id"], "Mon premier prompt ici")
        updated = get_session_by_id(session["id"])
        assert updated["name"] == "Mon premier prompt ici"

    def test_set_active_session(self):
        """Active une session spécifique."""
        from kimi_proxy.core.database import (
            create_session, set_active_session, get_active_session
        )
        s1 = create_session("S1", provider="p1")
        s2 = create_session("S2", provider="p2")
        # s2 est active, activons s1
        set_active_session(s1["id"])
        active = get_active_session()
        assert active["id"] == s1["id"]

    def test_delete_session(self):
        """Supprime une session en mémoire."""
        from kimi_proxy.core.database import (
            create_session, delete_session, get_session_by_id
        )
        session = create_session("To Delete", provider="p1")
        result = delete_session(session["id"])
        assert result is True
        assert get_session_by_id(session["id"]) is None


# ── Tests Cache TTL ──────────────────────────────────────────────────────────

class TestActiveSessionCache:
    """Vérifie le comportement du cache TTL de la session active."""

    @pytest.fixture(autouse=True)
    def force_in_memory(self):
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "false"}):
            from kimi_proxy.core.database import init_database
            init_database()
            yield

    def test_cache_returns_same_object(self):
        """Deux appels rapprochés retournent le même objet (cache hit)."""
        from kimi_proxy.core.database import create_session, get_active_session
        create_session("Cached", provider="p1")
        first = get_active_session()
        second = get_active_session()
        # Même référence en mémoire (cache hit)
        assert first is second

    def test_cache_invalidated_on_create(self):
        """Le cache est invalidé quand on crée une nouvelle session."""
        from kimi_proxy.core.database import create_session, get_active_session
        create_session("First", provider="p1")
        first = get_active_session()
        assert first["name"] == "First"
        
        create_session("Second", provider="p2")
        second = get_active_session()
        assert second["name"] == "Second"
        assert first is not second


# ── Tests init_database mode selection ───────────────────────────────────────

class TestInitDatabaseMode:
    """Vérifie que init_database choisit le bon mode."""

    def test_in_memory_no_file_created(self, tmp_path):
        """En mode in-memory, aucun fichier sessions.db n'est créé."""
        db_file = str(tmp_path / "sessions.db")
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "false"}):
            with patch("kimi_proxy.core.database.DATABASE_FILE", db_file):
                from kimi_proxy.core.database import init_database
                init_database()
                assert not os.path.exists(db_file)

    def test_persist_creates_file(self, tmp_path):
        """En mode persistant, le fichier sessions.db est créé."""
        db_file = str(tmp_path / "sessions.db")
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "true"}):
            with patch("kimi_proxy.core.database.DATABASE_FILE", db_file):
                from kimi_proxy.core.database import init_database
                init_database()
                assert os.path.exists(db_file)
