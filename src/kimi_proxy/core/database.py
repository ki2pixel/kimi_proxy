"""Gestion de la base de données SQLite du middleware."""
import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

from .constants import DATABASE_FILE

_mem_conn: Optional[sqlite3.Connection] = None


def _should_persist() -> bool:
    try:
        from ..config.loader import get_config, get_database_config
        cfg = get_database_config(get_config())
        env_val = os.environ.get("KIMI_PERSIST_SESSIONS")
        if env_val is not None:
            return env_val.lower() == "true"
        return cfg.persist_sessions
    except Exception:
        return False


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager pour les connexions DB."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_db_connection() -> sqlite3.Connection:
    """Crée une connexion DB simple (sans context manager)."""
    global _mem_conn
    if _should_persist():
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        return conn

    if _mem_conn is None:
        _mem_conn = sqlite3.connect("file:kimi_mem?mode=memory&cache=shared", uri=True)
        _mem_conn.row_factory = sqlite3.Row
        _init_database_conn(_mem_conn)
    conn = sqlite3.connect("file:kimi_mem?mode=memory&cache=shared", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialise la base de données SQLite."""
    if not _should_persist():
        get_db_connection()
        return

    conn = sqlite3.connect(DATABASE_FILE)
    _init_database_conn(conn)
    conn.close()
    print("✅ Base de données SQLite initialisée")


def _init_database_conn(conn: sqlite3.Connection):
    """Initialise le schéma SQLite du middleware."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS masked_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE NOT NULL,
            original_content TEXT NOT NULL,
            preview TEXT NOT NULL,
            file_path TEXT NOT NULL,
            tags TEXT,
            token_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mcp_memory_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            memory_type TEXT DEFAULT 'episodic',
            content_hash TEXT UNIQUE NOT NULL,
            content_preview TEXT NOT NULL,
            full_content TEXT NOT NULL,
            token_count INTEGER DEFAULT 0,
            access_count INTEGER DEFAULT 0,
            last_accessed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            embedding_id TEXT,
            metadata TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_type ON mcp_memory_entries(memory_type)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_session ON mcp_memory_entries(session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_access ON mcp_memory_entries(access_count)
    """)

    conn.commit()
