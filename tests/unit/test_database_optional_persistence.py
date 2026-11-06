"""Tests de la persistance optionnelle et du schéma SQLite réduit."""
import os
from unittest.mock import patch

import pytest

import kimi_proxy.core.database as db_mod


def _reset_memory_db() -> None:
    if db_mod._mem_conn is not None:
        try:
            db_mod._mem_conn.close()
        except Exception:
            pass
        db_mod._mem_conn = None


@pytest.fixture(autouse=True)
def clean_memory_state():
    _reset_memory_db()
    yield
    _reset_memory_db()


class TestShouldPersist:
    def test_env_true_overrides_config(self):
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "true"}):
            assert db_mod._should_persist() is True

    def test_env_false_overrides_config(self):
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "false"}):
            assert db_mod._should_persist() is False

    def test_env_case_insensitive(self):
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "TRUE"}):
            assert db_mod._should_persist() is True
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "False"}):
            assert db_mod._should_persist() is False

    def test_default_without_env(self):
        env = os.environ.copy()
        env.pop("KIMI_PERSIST_SESSIONS", None)
        with patch.dict(os.environ, env, clear=True):
            assert isinstance(db_mod._should_persist(), bool)


class TestSchema:
    def test_in_memory_schema_contains_only_middleware_tables(self):
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "false"}):
            db_mod.init_database()
            with db_mod.get_db() as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }

        assert "mcp_memory_entries" in tables
        assert "masked_content" in tables
        assert "sessions" not in tables
        assert "metrics" not in tables

    def test_persistent_mode_creates_file(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"KIMI_PERSIST_SESSIONS": "true"}):
            with patch.object(db_mod, "DATABASE_FILE", db_file):
                db_mod.init_database()
                assert os.path.exists(db_file)
