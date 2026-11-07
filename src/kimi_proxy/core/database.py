"""Gestion de la base de données SQLite du middleware."""
import asyncio
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Callable, Generator, Optional, TypeVar

from .constants import DATABASE_FILE

_mem_conn: Optional[sqlite3.Connection] = None
_mem_conn_lock = threading.Lock()
_persist_sessions: bool = False

T = TypeVar("T")


def configure_database(*, persist_sessions: bool) -> None:
    """Injecte la politique de persistance depuis l'appelant (couche API)."""
    global _persist_sessions
    _persist_sessions = bool(persist_sessions)


async def run_db_in_thread(fn: Callable[..., T], *args: object, **kwargs: object) -> T:
    """Exécute une opération SQLite synchrone hors de la boucle asyncio."""
    return await asyncio.to_thread(fn, *args, **kwargs)


def _should_persist() -> bool:
    env_val = os.environ.get("KIMI_PERSIST_SESSIONS")
    if env_val is not None:
        return env_val.strip().lower() == "true"
    return _persist_sessions


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

    with _mem_conn_lock:
        if _mem_conn is None:
            _mem_conn = sqlite3.connect(
                "file:kimi_mem?mode=memory&cache=shared",
                uri=True,
                check_same_thread=False,
            )
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
