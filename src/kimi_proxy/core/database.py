"""
Gestion de la base de données SQLite avec migrations.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, List, Dict, Any

from .constants import DATABASE_FILE
from .exceptions import DatabaseError


@contextmanager
def get_db() -> Generator[sqlite3.Row, None, None]:
    """
    Context manager pour les connexions DB.
    
    Yields:
        Connection SQLite avec row_factory=sqlite3.Row
    """
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_db_connection() -> sqlite3.Connection:
    """
    Crée une connexion DB simple (sans context manager).
    
    Returns:
        Connection SQLite
    """
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """
    Initialise la base de données SQLite avec toutes les tables et migrations.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Table providers (cache configuration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            base_url TEXT NOT NULL,
            api_key TEXT
        )
    """)
    
    # Table sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider TEXT DEFAULT 'managed:kimi-code',
            model TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 0
        )
    """)
    
    # Table metrics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estimated_tokens INTEGER NOT NULL,
            percentage REAL NOT NULL,
            content_preview TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            is_estimated BOOLEAN DEFAULT 1,
            source TEXT DEFAULT 'proxy',
            memory_tokens INTEGER DEFAULT 0,
            chat_tokens INTEGER DEFAULT 0,
            memory_ratio REAL DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Table masked_content (Sanitizer Phase 1)
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
    
    # Table memory_metrics (MCP Phase 2)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            memory_tokens INTEGER DEFAULT 0,
            chat_tokens INTEGER DEFAULT 0,
            memory_ratio REAL DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Table memory_segments (détail MCP Phase 2)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            metric_id INTEGER,
            segment_type TEXT,
            content_preview TEXT,
            token_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Table compression_log (Phase 3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compression_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            original_tokens INTEGER NOT NULL,
            compressed_tokens INTEGER NOT NULL,
            compression_ratio REAL NOT NULL,
            summary_preview TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Table compaction_history (Phase 1 Context Compaction)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tokens_before INTEGER NOT NULL,
            tokens_after INTEGER NOT NULL,
            tokens_saved INTEGER NOT NULL,
            preserved_messages INTEGER NOT NULL,
            summarized_messages INTEGER NOT NULL,
            compaction_ratio REAL NOT NULL,
            trigger_reason TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Table mcp_memory_entries (Phase 3 MCP Memory Standardisée)
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
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Index pour performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_type ON mcp_memory_entries(memory_type)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_session ON mcp_memory_entries(session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_hash ON mcp_memory_entries(content_hash)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_access ON mcp_memory_entries(access_count)
    """)
    
    # Table mcp_compression_results (Phase 3 Compression MCP)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mcp_compression_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            original_tokens INTEGER NOT NULL,
            compressed_tokens INTEGER NOT NULL,
            compression_ratio REAL NOT NULL,
            algorithm TEXT DEFAULT 'zlib',
            compressed_content TEXT,
            decompression_time_ms REAL DEFAULT 0.0,
            quality_score REAL DEFAULT 0.0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Table mcp_routing_decisions (Phase 3 Routage Optimisé)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mcp_routing_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            original_provider TEXT NOT NULL,
            selected_provider TEXT NOT NULL,
            original_model TEXT,
            selected_model TEXT,
            required_context INTEGER NOT NULL,
            available_context INTEGER NOT NULL,
            context_remaining INTEGER NOT NULL,
            confidence_score REAL NOT NULL,
            reason TEXT,
            fallback_triggered BOOLEAN DEFAULT 0,
            estimated_cost REAL DEFAULT 0.0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    conn.commit()
    
    # Migrations (ajout de colonnes si elles n'existent pas)
    _run_migrations(cursor, conn)
    
    conn.close()
    print("✅ Base de données initialisée")


def _run_migrations(cursor: sqlite3.Cursor, conn: sqlite3.Connection):
    """Exécute les migrations de schéma."""
    
    # Migration: ajoute la colonne source dans metrics
    try:
        cursor.execute("ALTER TABLE metrics ADD COLUMN source TEXT DEFAULT 'proxy'")
        conn.commit()
        print("   Migration: colonne 'source' ajoutée à metrics")
    except sqlite3.OperationalError:
        pass  # Colonne existe déjà
    
    # Migration: ajoute la colonne model dans sessions
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN model TEXT")
        conn.commit()
        print("   Migration: colonne 'model' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass
    
    # Migration: ajoute les colonnes tags et token_count dans masked_content
    try:
        cursor.execute("ALTER TABLE masked_content ADD COLUMN tags TEXT")
        conn.commit()
        print("   Migration: colonne 'tags' ajoutée à masked_content")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE masked_content ADD COLUMN token_count INTEGER DEFAULT 0")
        conn.commit()
        print("   Migration: colonne 'token_count' ajoutée à masked_content")
    except sqlite3.OperationalError:
        pass
    
    # Migration: ajoute les colonnes mémoire dans metrics (Phase 2 MCP)
    try:
        cursor.execute("ALTER TABLE metrics ADD COLUMN memory_tokens INTEGER DEFAULT 0")
        conn.commit()
        print("   Migration: colonne 'memory_tokens' ajoutée à metrics")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE metrics ADD COLUMN chat_tokens INTEGER DEFAULT 0")
        conn.commit()
        print("   Migration: colonne 'chat_tokens' ajoutée à metrics")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE metrics ADD COLUMN memory_ratio REAL DEFAULT 0")
        conn.commit()
        print("   Migration: colonne 'memory_ratio' ajoutée à metrics")
    except sqlite3.OperationalError:
        pass
    
    # Migrations Phase 1 Context Compaction
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN reserved_tokens INTEGER DEFAULT 0")
        conn.commit()
        print("   Migration: colonne 'reserved_tokens' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN compaction_count INTEGER DEFAULT 0")
        conn.commit()
        print("   Migration: colonne 'compaction_count' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN last_compaction_at TIMESTAMP")
        conn.commit()
        print("   Migration: colonne 'last_compaction_at' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass
    
    # Migrations Phase 2 - Auto-compaction par session
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN auto_compaction_enabled BOOLEAN DEFAULT 1")
        conn.commit()
        print("   Migration: colonne 'auto_compaction_enabled' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN auto_compaction_threshold REAL DEFAULT 0.85")
        conn.commit()
        print("   Migration: colonne 'auto_compaction_threshold' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN consecutive_auto_compactions INTEGER DEFAULT 0")
        conn.commit()
        print("   Migration: colonne 'consecutive_auto_compactions' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass


# ============================================================================
# Opérations CRUD pour Sessions
# ============================================================================

def get_active_session() -> Optional[Dict[str, Any]]:
    """Récupère la session active."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    """Récupère une session par son ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_sessions() -> List[Dict[str, Any]]:
    """Récupère toutes les sessions."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]


def create_session(name: str, provider: str = "managed:kimi-code", model: str = None) -> Dict[str, Any]:
    """Crée une nouvelle session et la rend active."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Désactive toutes les sessions
        cursor.execute("UPDATE sessions SET is_active = 0")
        
        # Insère la nouvelle session
        if model:
            cursor.execute(
                "INSERT INTO sessions (name, provider, model, is_active) VALUES (?, ?, ?, 1)",
                (name, provider, model)
            )
        else:
            cursor.execute(
                "INSERT INTO sessions (name, provider, is_active) VALUES (?, ?, 1)",
                (name, provider)
            )
        
        session_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        return dict(cursor.fetchone())


def update_session_model(session_id: int, model: str) -> bool:
    """Met à jour le modèle d'une session."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sessions SET model = ? WHERE id = ?",
                (model, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"⚠️ Erreur mise à jour modèle session: {e}")
            return False


def update_session_first_prompt(session_id: int, prompt: str):
    """Met à jour le nom de la session avec le premier prompt si c'est un nom générique."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        
        if row and (row[0].startswith("Session") or row[0] == "Session par défaut"):
            short_name = prompt[:50] + "..." if len(prompt) > 50 else prompt
            cursor.execute(
                "UPDATE sessions SET name = ? WHERE id = ?",
                (short_name, session_id)
            )
            conn.commit()


def set_active_session(session_id: int) -> bool:
    """Active une session spécifique."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE sessions SET is_active = 0")
        cursor.execute(
            "UPDATE sessions SET is_active = 1 WHERE id = ?",
            (session_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


# ============================================================================
# Opérations pour Metrics
# ============================================================================

def save_metric(
    session_id: int,
    tokens: int,
    percentage: float,
    preview: str,
    is_estimated: bool = True,
    source: str = 'proxy',
    memory_tokens: int = 0,
    chat_tokens: int = 0,
    memory_ratio: float = 0
) -> int:
    """Sauvegarde une métrique et retourne son ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO metrics 
                (session_id, estimated_tokens, percentage, content_preview, 
                 is_estimated, source, memory_tokens, chat_tokens, memory_ratio)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, tokens, percentage, preview[:200], 
             is_estimated, source, memory_tokens, chat_tokens, memory_ratio)
        )
        conn.commit()
        return cursor.lastrowid


def update_metric_with_real_tokens(
    metric_id: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    max_context: int
) -> Dict[str, Any]:
    """Met à jour une métrique avec les vrais tokens de l'API."""
    percentage = (total_tokens / max_context) * 100 if max_context > 0 else 0
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE metrics 
               SET estimated_tokens = ?, 
                   prompt_tokens = ?, 
                   completion_tokens = ?,
                   percentage = ?,
                   is_estimated = 0
               WHERE id = ?""",
            (total_tokens, prompt_tokens, completion_tokens, percentage, metric_id)
        )
        conn.commit()
    
    return {
        "total": total_tokens,
        "prompt": prompt_tokens,
        "completion": completion_tokens,
        "percentage": percentage
    }


def get_session_total_tokens(session_id: int) -> Dict[str, int]:
    """
    Récupère les tokens de la DERNIÈRE requête uniquement.
    
    Logique pour la JAUGE de contexte (stateless):
    - Le contexte LLM est recalculé à chaque requête
    - On prend les tokens de la dernière métrique uniquement
    - Cela représente le remplissage réel de la fenêtre de contexte
    
    Pour le cumul (facturation), utiliser get_session_cumulative_tokens().
    """
    with get_db() as conn:
        cursor = conn.cursor()
        # Prend UNIQUEMENT la dernière métrique (plus récente)
        cursor.execute("""
            SELECT 
                estimated_tokens,
                prompt_tokens,
                completion_tokens,
                is_estimated
            FROM metrics 
            WHERE session_id = ? 
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
        """, (session_id,))
        
        row = cursor.fetchone()
    
    if not row:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        }
    
    estimated = row[0] or 0
    prompt = row[1] or 0
    completion = row[2] or 0
    
    # Pour l'input: utilise prompt_tokens si disponible (réel), sinon estimated_tokens
    input_tokens = prompt if prompt > 0 else estimated
    
    return {
        "input_tokens": input_tokens,
        "output_tokens": completion,
        "total_tokens": input_tokens + completion
    }


def get_session_cumulative_tokens(session_id: int) -> Dict[str, int]:
    """
    Calcule le CUMUL réel des tokens pour la facturation.
    
    Logique pour les STATS:
    - Input: Somme des prompt_tokens (réels) sinon estimated_tokens
    - Output: Somme des completion_tokens (réels)
    - Total: Input + Output (total facturé)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                estimated_tokens,
                prompt_tokens,
                completion_tokens,
                is_estimated
            FROM metrics 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,))
        
        rows = cursor.fetchall()
    
    total_input = 0
    total_output = 0
    
    for row in rows:
        estimated = row[0] or 0
        prompt = row[1] or 0
        completion = row[2] or 0
        
        # Pour l'input: utilise prompt_tokens si disponible, sinon estimated_tokens
        if prompt > 0:
            total_input += prompt
        else:
            total_input += estimated
        
        # Pour l'output: toujours completion_tokens
        total_output += completion
    
    return {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output
    }


def get_session_stats(session_id: int) -> Dict[str, Any]:
    """Récupère les statistiques d'une session."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT 
                COUNT(*) as total_requests,
                MAX(estimated_tokens) as max_tokens,
                AVG(estimated_tokens) as avg_tokens
               FROM metrics WHERE session_id = ?""",
            (session_id,)
        )
        stats = dict(cursor.fetchone())
        
        # Pour la jauge: tokens de la dernière requête (contexte actuel)
        current_totals = get_session_total_tokens(session_id)
        stats["current_input_tokens"] = current_totals["input_tokens"]
        stats["current_output_tokens"] = current_totals["output_tokens"]
        stats["current_total_tokens"] = current_totals["total_tokens"]
        
        # Pour les stats cumulées: total facturé
        cumulative_totals = get_session_cumulative_tokens(session_id)
        stats["cumulative_input_tokens"] = cumulative_totals["input_tokens"]
        stats["cumulative_output_tokens"] = cumulative_totals["output_tokens"]
        stats["cumulative_total_tokens"] = cumulative_totals["total_tokens"]
        
        cursor.execute(
            """SELECT * FROM metrics 
               WHERE session_id = ? 
               ORDER BY timestamp DESC LIMIT 50""",
            (session_id,)
        )
        recent_metrics = [dict(row) for row in cursor.fetchall()]
        
        return {
            "stats": stats,
            "recent_metrics": recent_metrics
        }


def get_recent_metrics(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Récupère les métriques récentes d'une session."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM metrics 
               WHERE session_id = ? 
               ORDER BY timestamp DESC LIMIT ?""",
            (session_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# Utilitaires
# ============================================================================

def is_system_message(content: str) -> bool:
    """Détecte si un message est un message système."""
    return (
        "You are Kimi Code CLI" in content or 
        "interactive general AI agent" in content
    )


def check_threshold_alert(percentage: float) -> Optional[Dict[str, Any]]:
    """Vérifie si un seuil d'alerte est atteint."""
    if percentage >= 95:
        return {
            "level": "critical",
            "color": "#ef4444",
            "message": "⚠️ CONTEXTE CRITIQUE (95%)"
        }
    elif percentage >= 90:
        return {
            "level": "warning",
            "color": "#f97316",
            "message": "⚠️ CONTEXTE ÉLEVÉ (90%)"
        }
    elif percentage >= 80:
        return {
            "level": "caution",
            "color": "#eab308",
            "message": "⚡ Attention (80%)"
        }
    return None


# ============================================================================
# Opérations pour Compaction History (Phase 1 Context Compaction)
# ============================================================================

def save_compaction_history(
    session_id: int,
    tokens_before: int,
    tokens_after: int,
    preserved_messages: int,
    summarized_messages: int,
    trigger_reason: str = "manual"
) -> int:
    """
    Sauvegarde un historique de compaction.
    
    Args:
        session_id: ID de la session
        tokens_before: Nombre de tokens avant compaction
        tokens_after: Nombre de tokens après compaction
        preserved_messages: Nombre de messages préservés
        summarized_messages: Nombre de messages résumés
        trigger_reason: Raison du déclenchement (manual, auto, threshold)
        
    Returns:
        ID de l'entrée créée
    """
    tokens_saved = tokens_before - tokens_after
    compaction_ratio = (tokens_saved / tokens_before * 100) if tokens_before > 0 else 0
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Insère l'historique
        cursor.execute(
            """INSERT INTO compaction_history 
                (session_id, tokens_before, tokens_after, tokens_saved,
                 preserved_messages, summarized_messages, compaction_ratio, trigger_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, tokens_before, tokens_after, tokens_saved,
             preserved_messages, summarized_messages, compaction_ratio, trigger_reason)
        )
        history_id = cursor.lastrowid
        
        # Met à jour les compteurs de la session
        cursor.execute(
            """UPDATE sessions 
               SET compaction_count = COALESCE(compaction_count, 0) + 1,
                   last_compaction_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (session_id,)
        )
        
        conn.commit()
        return history_id


def get_compaction_history(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Récupère l'historique de compaction d'une session.
    
    Args:
        session_id: ID de la session
        limit: Nombre maximum d'entrées
        
    Returns:
        Liste des entrées d'historique
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM compaction_history 
               WHERE session_id = ? 
               ORDER BY timestamp DESC LIMIT ?""",
            (session_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_global_compaction_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques globales de compaction.
    
    Returns:
        Statistiques globales
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_compactions,
                SUM(tokens_saved) as total_tokens_saved,
                AVG(compaction_ratio) as avg_compaction_ratio,
                MAX(timestamp) as last_compaction_at
            FROM compaction_history
        """)
        stats = dict(cursor.fetchone())
        
        cursor.execute("""
            SELECT 
                session_id,
                COUNT(*) as compaction_count,
                SUM(tokens_saved) as session_tokens_saved
            FROM compaction_history
            GROUP BY session_id
        """)
        sessions = [dict(row) for row in cursor.fetchall()]
        
        return {
            "global": stats,
            "sessions": sessions
        }


def update_session_reserved_tokens(session_id: int, reserved_tokens: int) -> bool:
    """
    Met à jour le nombre de tokens réservés pour une session.
    
    Args:
        session_id: ID de la session
        reserved_tokens: Nombre de tokens à réserver
        
    Returns:
        True si mis à jour avec succès
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sessions SET reserved_tokens = ? WHERE id = ?",
                (reserved_tokens, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"⚠️ Erreur mise à jour tokens réservés: {e}")
            return False


def get_session_compaction_state(session_id: int) -> Dict[str, Any]:
    """
    Récupère l'état complet de compaction d'une session.
    
    Args:
        session_id: ID de la session
        
    Returns:
        État de compaction incluant compteurs et historique
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Récupère les infos de la session
        cursor.execute(
            """SELECT reserved_tokens, compaction_count, last_compaction_at,
                      auto_compaction_enabled, auto_compaction_threshold, consecutive_auto_compactions
               FROM sessions WHERE id = ?""",
            (session_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return {
                "session_id": session_id,
                "reserved_tokens": 0,
                "compaction_count": 0,
                "last_compaction_at": None,
                "auto_compaction_enabled": True,
                "auto_compaction_threshold": 0.85,
                "consecutive_auto_compactions": 0,
                "history": [],
                "total_tokens_saved": 0
            }
        
        # Récupère l'historique
        history = get_compaction_history(session_id, limit=10)
        
        # Calcule le total économisé
        cursor.execute(
            """SELECT COALESCE(SUM(tokens_saved), 0) as total_saved
               FROM compaction_history WHERE session_id = ?""",
            (session_id,)
        )
        total_saved = cursor.fetchone()[0] or 0
        
        return {
            "session_id": session_id,
            "reserved_tokens": row[0] or 0,
            "compaction_count": row[1] or 0,
            "last_compaction_at": row[2],
            "auto_compaction_enabled": row[3] if row[3] is not None else True,
            "auto_compaction_threshold": row[4] if row[4] is not None else 0.85,
            "consecutive_auto_compactions": row[5] or 0,
            "history": history,
            "total_tokens_saved": total_saved
        }


def update_session_auto_compaction(session_id: int, enabled: bool) -> bool:
    """
    Active ou désactive l'auto-compaction pour une session.
    
    Args:
        session_id: ID de la session
        enabled: True pour activer, False pour désactiver
        
    Returns:
        True si mis à jour avec succès
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sessions SET auto_compaction_enabled = ? WHERE id = ?",
                (enabled, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"⚠️ Erreur mise à jour auto-compaction: {e}")
            return False


def update_session_auto_threshold(session_id: int, threshold: float) -> bool:
    """
    Met à jour le seuil d'auto-compaction pour une session.
    
    Args:
        session_id: ID de la session
        threshold: Seuil entre 0.0 et 1.0
        
    Returns:
        True si mis à jour avec succès
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sessions SET auto_compaction_threshold = ? WHERE id = ?",
                (threshold, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"⚠️ Erreur mise à jour seuil auto-compaction: {e}")
            return False


def increment_consecutive_auto_compactions(session_id: int) -> int:
    """
    Incrémente le compteur de compactions automatiques consécutives.
    
    Args:
        session_id: ID de la session
        
    Returns:
        Nouvelle valeur du compteur
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE sessions 
               SET consecutive_auto_compactions = COALESCE(consecutive_auto_compactions, 0) + 1
               WHERE id = ?""",
            (session_id,)
        )
        conn.commit()
        
        cursor.execute(
            "SELECT consecutive_auto_compactions FROM sessions WHERE id = ?",
            (session_id,)
        )
        return cursor.fetchone()[0] or 0


def reset_consecutive_auto_compactions(session_id: int) -> bool:
    """
    Réinitialise le compteur de compactions automatiques consécutives.
    
    Args:
        session_id: ID de la session
        
    Returns:
        True si mis à jour avec succès
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sessions SET consecutive_auto_compactions = 0 WHERE id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"⚠️ Erreur réinitialisation compteur: {e}")
            return False
