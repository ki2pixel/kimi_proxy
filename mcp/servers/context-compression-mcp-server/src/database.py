"""
Database manager for Context Compression MCP Server.
Handles SQLite database operations with thread-safe connection management.
"""

import sqlite3
import threading
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe SQLite database manager with connection pooling."""
    
    def __init__(self, db_path: str = "context_data.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._initialized = False
        
        # Initialize database on first use
        self._ensure_initialized()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            # Enable foreign keys and WAL mode for better concurrency
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            self._local.connection.execute("PRAGMA journal_mode = WAL")
            self._local.connection.row_factory = sqlite3.Row
        
        return self._local.connection
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database operations with automatic transaction handling."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            cursor.close()
    
    def _ensure_initialized(self):
        """Ensure database is initialized with proper schema."""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            try:
                self._create_schema()
                self._initialized = True
                logger.info(f"Database initialized at {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                # Don't raise here to allow graceful degradation
                self._initialized = False
    
    def _create_schema(self):
        """Create database schema if it doesn't exist."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS contexts (
            id TEXT PRIMARY KEY,
            title TEXT,
            original_size INTEGER NOT NULL,
            compressed_size INTEGER NOT NULL,
            compression_method TEXT NOT NULL,
            data BLOB NOT NULL,
            tags TEXT, -- JSON array of tags
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_contexts_title ON contexts(title);
        CREATE INDEX IF NOT EXISTS idx_contexts_created_at ON contexts(created_at);
        CREATE INDEX IF NOT EXISTS idx_contexts_tags ON contexts(tags);
        
        -- Create trigger to update updated_at timestamp
        CREATE TRIGGER IF NOT EXISTS update_contexts_timestamp 
        AFTER UPDATE ON contexts
        BEGIN
            UPDATE contexts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        """
        
        with self.get_cursor() as cursor:
            cursor.executescript(schema_sql)
    
    def verify_schema(self) -> bool:
        """
        Verify that the database schema is correct.
        
        Returns:
            True if schema is valid, False otherwise
        """
        try:
            with self.get_cursor() as cursor:
                # Check if contexts table exists with correct columns
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='contexts'
                """)
                
                if not cursor.fetchone():
                    return False
                
                # Check table structure
                cursor.execute("PRAGMA table_info(contexts)")
                columns = {row['name']: row['type'] for row in cursor.fetchall()}
                
                expected_columns = {
                    'id': 'TEXT',
                    'title': 'TEXT',
                    'original_size': 'INTEGER',
                    'compressed_size': 'INTEGER',
                    'compression_method': 'TEXT',
                    'data': 'BLOB',
                    'tags': 'TEXT',
                    'created_at': 'TIMESTAMP',
                    'updated_at': 'TIMESTAMP'
                }
                
                for col_name, col_type in expected_columns.items():
                    if col_name not in columns:
                        logger.error(f"Missing column: {col_name}")
                        return False
                
                return True
                
        except Exception as e:
            logger.error(f"Schema verification failed: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get database information and statistics.
        
        Returns:
            Dictionary with database info
        """
        try:
            with self.get_cursor() as cursor:
                # Get table count
                cursor.execute("SELECT COUNT(*) as count FROM contexts")
                context_count = cursor.fetchone()['count']
                
                # Get database file size
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                # Get database version info
                cursor.execute("PRAGMA user_version")
                user_version = cursor.fetchone()[0]
                
                return {
                    'db_path': self.db_path,
                    'context_count': context_count,
                    'db_size_bytes': db_size,
                    'user_version': user_version,
                    'schema_valid': self.verify_schema()
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                'db_path': self.db_path,
                'error': str(e)
            }
    
    def close_connections(self):
        """Close all thread-local connections."""
        if hasattr(self._local, 'connection'):
            try:
                self._local.connection.close()
                delattr(self._local, 'connection')
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
    
    def __del__(self):
        """Cleanup connections on deletion."""
        self.close_connections()
  
  # CRUD Operations
    
    def insert_context(self, context_id: str, title: Optional[str], original_size: int,
                      compressed_size: int, compression_method: str, data: bytes,
                      tags: Optional[str] = None) -> bool:
        """
        Insert a new context record.
        
        Args:
            context_id: Unique identifier for the context
            title: Optional title for the context
            original_size: Size of original data in bytes
            compressed_size: Size of compressed data in bytes
            compression_method: Method used for compression
            data: Compressed data as bytes
            tags: JSON string of tags
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO contexts 
                    (id, title, original_size, compressed_size, compression_method, data, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (context_id, title, original_size, compressed_size, 
                     compression_method, data, tags))
                
                logger.info(f"Inserted context {context_id}")
                return True
                
        except sqlite3.IntegrityError as e:
            logger.error(f"Context {context_id} already exists: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to insert context {context_id}: {e}")
            return False
    
    def select_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a context record by ID.
        
        Args:
            context_id: Unique identifier for the context
            
        Returns:
            Dictionary with context data or None if not found
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, title, original_size, compressed_size, 
                           compression_method, data, tags, created_at, updated_at
                    FROM contexts WHERE id = ?
                """, (context_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to select context {context_id}: {e}")
            return None
    
    def update_context(self, context_id: str, title: Optional[str] = None,
                      data: Optional[bytes] = None, original_size: Optional[int] = None,
                      compressed_size: Optional[int] = None, 
                      compression_method: Optional[str] = None,
                      tags: Optional[str] = None) -> bool:
        """
        Update an existing context record.
        
        Args:
            context_id: Unique identifier for the context
            title: New title (if provided)
            data: New compressed data (if provided)
            original_size: New original size (if provided)
            compressed_size: New compressed size (if provided)
            compression_method: New compression method (if provided)
            tags: New tags JSON string (if provided)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build dynamic update query
            update_fields = []
            params = []
            
            if title is not None:
                update_fields.append("title = ?")
                params.append(title)
            if data is not None:
                update_fields.append("data = ?")
                params.append(data)
            if original_size is not None:
                update_fields.append("original_size = ?")
                params.append(original_size)
            if compressed_size is not None:
                update_fields.append("compressed_size = ?")
                params.append(compressed_size)
            if compression_method is not None:
                update_fields.append("compression_method = ?")
                params.append(compression_method)
            if tags is not None:
                update_fields.append("tags = ?")
                params.append(tags)
            
            if not update_fields:
                logger.warning(f"No fields to update for context {context_id}")
                return False
            
            # Debug logging
            logger.debug(f"Updating context {context_id} with fields: {update_fields}, params: {params}")
            
            params.append(context_id)
            
            with self.get_cursor() as cursor:
                cursor.execute(f"""
                    UPDATE contexts 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Context {context_id} not found for update")
                    return False
                
                logger.info(f"Updated context {context_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update context {context_id}: {e}")
            return False
    
    def delete_context(self, context_id: str) -> bool:
        """
        Delete a context record by ID.
        
        Args:
            context_id: Unique identifier for the context
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("DELETE FROM contexts WHERE id = ?", (context_id,))
                
                if cursor.rowcount == 0:
                    logger.warning(f"Context {context_id} not found for deletion")
                    return False
                
                logger.info(f"Deleted context {context_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete context {context_id}: {e}")
            return False
    
    def search_contexts(self, query: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search contexts by title, tags, or content metadata.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of matching context records (without data field)
        """
        try:
            with self.get_cursor() as cursor:
                # Search in title and tags fields
                search_sql = """
                    SELECT id, title, original_size, compressed_size, 
                           compression_method, tags, created_at, updated_at
                    FROM contexts 
                    WHERE (title LIKE ? OR tags LIKE ?)
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                
                search_term = f"%{query}%"
                cursor.execute(search_sql, (search_term, search_term, limit, offset))
                
                results = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Search for '{query}' returned {len(results)} results")
                return results
                
        except Exception as e:
            logger.error(f"Failed to search contexts with query '{query}': {e}")
            return []
    
    def list_contexts(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List all contexts with pagination.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of context records (without data field)
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, title, original_size, compressed_size, 
                           compression_method, tags, created_at, updated_at
                    FROM contexts 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                results = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Listed {len(results)} contexts")
                return results
                
        except Exception as e:
            logger.error(f"Failed to list contexts: {e}")
            return []
    
    def get_context_count(self) -> int:
        """
        Get total number of contexts in database.
        
        Returns:
            Total count of contexts
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM contexts")
                return cursor.fetchone()['count']
                
        except Exception as e:
            logger.error(f"Failed to get context count: {e}")
            return 0
    
    def context_exists(self, context_id: str) -> bool:
        """
        Check if a context exists by ID.
        
        Args:
            context_id: Unique identifier for the context
            
        Returns:
            True if context exists, False otherwise
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1 FROM contexts WHERE id = ? LIMIT 1", (context_id,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Failed to check if context {context_id} exists: {e}")
            return False