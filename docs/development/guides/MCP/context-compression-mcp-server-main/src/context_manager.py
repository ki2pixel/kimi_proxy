"""
Context Manager for Context Compression MCP Server.

This module provides the main business logic for managing context data,
coordinating between compression and database operations.
"""

import uuid
import json
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from .database import DatabaseManager
from .compression import CompressionEngine, CompressionResult

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Main business logic coordinator for context operations.
    
    Handles context storage, retrieval, search, and management operations
    by coordinating between the compression engine and database manager.
    """
    
    def __init__(self, 
                 db_path: Optional[str] = None,
                 compression_engine: Optional[CompressionEngine] = None):
        """
        Initialize context manager.
        
        Args:
            db_path: Path to SQLite database file (defaults to CONTEXT_DB_PATH env var or "context_data.db")
            compression_engine: Optional compression engine instance
        """
        # Use environment variable if db_path not provided
        if db_path is None:
            db_path = os.environ.get("CONTEXT_DB_PATH", "context_data.db")
        
        self.db = DatabaseManager(db_path)
        self.compression = compression_engine or CompressionEngine()
        
        logger.info(f"Context manager initialized with database path: {db_path}")
    
    def _generate_context_id(self) -> str:
        """
        Generate a unique context ID.
        
        Returns:
            Unique context identifier with 'ctx_' prefix
        """
        return f"ctx_{uuid.uuid4().hex[:12]}"
    
    def _serialize_tags(self, tags: Optional[List[str]]) -> str:
        """
        Serialize tags list to JSON string.
        
        Args:
            tags: List of tag strings or None
            
        Returns:
            JSON string (empty list if tags is None or empty)
        """
        if tags is None:
            tags = []
        
        try:
            return json.dumps(tags)
        except Exception as e:
            logger.warning(f"Failed to serialize tags {tags}: {e}")
            return "[]"
    
    def _deserialize_tags(self, tags_json: Optional[str]) -> List[str]:
        """
        Deserialize tags from JSON string.
        
        Args:
            tags_json: JSON string of tags
            
        Returns:
            List of tag strings (empty list if None or invalid)
        """
        if not tags_json:
            return []
        
        try:
            tags = json.loads(tags_json)
            return tags if isinstance(tags, list) else []
        except Exception as e:
            logger.warning(f"Failed to deserialize tags '{tags_json}': {e}")
            return []
    
    def store_context(self, 
                     data: str, 
                     title: Optional[str] = None, 
                     tags: Optional[List[str]] = None) -> str:
        """
        Store context data with compression and metadata.
        
        Args:
            data: Context data to store
            title: Optional title for the context
            tags: Optional list of tags
            
        Returns:
            Generated context ID
            
        Raises:
            ValueError: If data is empty or invalid
            RuntimeError: If storage operation fails
        """
        if not data or not data.strip():
            raise ValueError("Context data cannot be empty")
        
        # Generate unique ID
        context_id = self._generate_context_id()
        
        try:
            # Compress the data
            compression_result = self.compression.compress(data)
            
            # Serialize tags
            tags_json = self._serialize_tags(tags)
            
            # Store in database
            success = self.db.insert_context(
                context_id=context_id,
                title=title,
                original_size=compression_result.original_size,
                compressed_size=compression_result.compressed_size,
                compression_method=compression_result.compression_method,
                data=compression_result.compressed_data,
                tags=tags_json
            )
            
            if not success:
                raise RuntimeError(f"Failed to store context in database")
            
            logger.info(f"Stored context {context_id} (compression: {compression_result.compression_method}, "
                       f"ratio: {compression_result.compression_ratio:.2f})")
            
            return context_id
            
        except Exception as e:
            logger.error(f"Failed to store context: {e}")
            raise RuntimeError(f"Context storage failed: {str(e)}")
    
    def retrieve_context(self, context_id: str) -> Dict[str, Any]:
        """
        Retrieve and decompress context data by ID.
        
        Args:
            context_id: Unique context identifier
            
        Returns:
            Dictionary with context data and metadata
            
        Raises:
            ValueError: If context_id is invalid
            RuntimeError: If retrieval or decompression fails
        """
        if not context_id or not context_id.strip():
            raise ValueError("Context ID cannot be empty")
        
        try:
            # Retrieve from database
            record = self.db.select_context(context_id)
            
            if not record:
                raise RuntimeError(f"Context '{context_id}' not found")
            
            # Decompress data
            decompressed_data = self.compression.decompress(
                record['data'], 
                record['compression_method']
            )
            
            # Deserialize tags
            tags = self._deserialize_tags(record['tags'])
            
            # Build response
            result = {
                'id': record['id'],
                'title': record['title'],
                'data': decompressed_data,
                'tags': tags,
                'metadata': {
                    'original_size': record['original_size'],
                    'compressed_size': record['compressed_size'],
                    'compression_method': record['compression_method'],
                    'created_at': record['created_at'],
                    'updated_at': record['updated_at']
                }
            }
            
            logger.info(f"Retrieved context {context_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve context {context_id}: {e}")
            if "not found" in str(e).lower():
                raise RuntimeError(f"Context '{context_id}' not found")
            else:
                raise RuntimeError(f"Context retrieval failed: {str(e)}")  
  
    def search_contexts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for contexts matching the query.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of matching context summaries
            
        Raises:
            ValueError: If query is invalid
            RuntimeError: If search operation fails
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
        
        if limit <= 0:
            raise ValueError("Limit must be positive")
        
        try:
            # Search in database
            records = self.db.search_contexts(query.strip(), limit=limit)
            
            # Format results
            results = []
            for record in records:
                tags = self._deserialize_tags(record['tags'])
                
                result = {
                    'id': record['id'],
                    'title': record['title'],
                    'tags': tags,
                    'metadata': {
                        'original_size': record['original_size'],
                        'compressed_size': record['compressed_size'],
                        'compression_method': record['compression_method'],
                        'created_at': record['created_at'],
                        'updated_at': record['updated_at']
                    }
                }
                results.append(result)
            
            logger.info(f"Search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search contexts with query '{query}': {e}")
            raise RuntimeError(f"Context search failed: {str(e)}")
    
    def list_contexts(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List contexts with pagination support.
        
        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            List of context summaries
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If list operation fails
        """
        if limit <= 0:
            raise ValueError("Limit must be positive")
        
        if offset < 0:
            raise ValueError("Offset cannot be negative")
        
        try:
            # Get contexts from database
            records = self.db.list_contexts(limit=limit, offset=offset)
            
            # Format results
            results = []
            for record in records:
                tags = self._deserialize_tags(record['tags'])
                
                result = {
                    'id': record['id'],
                    'title': record['title'],
                    'tags': tags,
                    'metadata': {
                        'original_size': record['original_size'],
                        'compressed_size': record['compressed_size'],
                        'compression_method': record['compression_method'],
                        'created_at': record['created_at'],
                        'updated_at': record['updated_at']
                    }
                }
                results.append(result)
            
            logger.info(f"Listed {len(results)} contexts (limit: {limit}, offset: {offset})")
            return results
            
        except Exception as e:
            logger.error(f"Failed to list contexts: {e}")
            raise RuntimeError(f"Context listing failed: {str(e)}")
    
    def delete_context(self, context_id: str) -> bool:
        """
        Delete a context by ID.
        
        Args:
            context_id: Unique context identifier
            
        Returns:
            True if deletion was successful
            
        Raises:
            ValueError: If context_id is invalid
            RuntimeError: If deletion fails or context not found
        """
        if not context_id or not context_id.strip():
            raise ValueError("Context ID cannot be empty")
        
        try:
            # Check if context exists first
            if not self.db.context_exists(context_id):
                raise RuntimeError(f"Context '{context_id}' not found")
            
            # Delete from database
            success = self.db.delete_context(context_id)
            
            if not success:
                raise RuntimeError(f"Failed to delete context '{context_id}'")
            
            logger.info(f"Deleted context {context_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete context {context_id}: {e}")
            if "not found" in str(e).lower():
                raise RuntimeError(f"Context '{context_id}' not found")
            else:
                raise RuntimeError(f"Context deletion failed: {str(e)}")
    
    def update_context(self, 
                      context_id: str,
                      data: Optional[str] = None,
                      title: Optional[str] = None,
                      tags: Optional[List[str]] = None) -> bool:
        """
        Update an existing context.
        
        Args:
            context_id: Unique context identifier
            data: New context data (if provided, will be recompressed)
            title: New title (if provided)
            tags: New tags list (if provided)
            
        Returns:
            True if update was successful
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If update fails or context not found
        """
        if not context_id or not context_id.strip():
            raise ValueError("Context ID cannot be empty")
        
        # Note: We allow tags=None as a valid update (clears tags)
        # The server layer handles validation of whether at least one field should be updated
        
        try:
            # Check if context exists
            if not self.db.context_exists(context_id):
                raise RuntimeError(f"Context '{context_id}' not found")
            
            # Prepare update parameters
            update_params = {}
            
            if title is not None:
                update_params['title'] = title
            
            if tags is not None:
                # Always serialize tags when provided, even if None (converts to empty list)
                serialized_tags = self._serialize_tags(tags)
                update_params['tags'] = serialized_tags
                logger.debug(f"Serialized tags {tags} to {serialized_tags}")
            
            if data is not None:
                if not data.strip():
                    raise ValueError("Context data cannot be empty")
                
                # Recompress the data
                compression_result = self.compression.compress(data)
                update_params.update({
                    'data': compression_result.compressed_data,
                    'original_size': compression_result.original_size,
                    'compressed_size': compression_result.compressed_size,
                    'compression_method': compression_result.compression_method
                })
            
            # Update in database
            success = self.db.update_context(context_id, **update_params)
            
            if not success:
                raise RuntimeError(f"Failed to update context '{context_id}'")
            
            logger.info(f"Updated context {context_id}")
            return True
            
        except ValueError:
            # Re-raise ValueError directly (validation errors)
            raise
        except Exception as e:
            logger.error(f"Failed to update context {context_id}: {e}")
            if "not found" in str(e).lower():
                raise RuntimeError(f"Context '{context_id}' not found")
            else:
                raise RuntimeError(f"Context update failed: {str(e)}")
    
    def get_context_summary(self, context_id: str) -> Dict[str, Any]:
        """
        Get context metadata without retrieving the actual data.
        
        Args:
            context_id: Unique context identifier
            
        Returns:
            Dictionary with context metadata
            
        Raises:
            ValueError: If context_id is invalid
            RuntimeError: If context not found or operation fails
        """
        if not context_id or not context_id.strip():
            raise ValueError("Context ID cannot be empty")
        
        try:
            # Retrieve from database
            record = self.db.select_context(context_id)
            
            if not record:
                raise RuntimeError(f"Context '{context_id}' not found")
            
            # Deserialize tags
            tags = self._deserialize_tags(record['tags'])
            
            # Build summary (without data)
            result = {
                'id': record['id'],
                'title': record['title'],
                'tags': tags,
                'metadata': {
                    'original_size': record['original_size'],
                    'compressed_size': record['compressed_size'],
                    'compression_method': record['compression_method'],
                    'created_at': record['created_at'],
                    'updated_at': record['updated_at']
                }
            }
            
            logger.info(f"Retrieved summary for context {context_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get context summary {context_id}: {e}")
            if "not found" in str(e).lower():
                raise RuntimeError(f"Context '{context_id}' not found")
            else:
                raise RuntimeError(f"Context summary retrieval failed: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get context manager statistics.
        
        Returns:
            Dictionary with statistics and database info
        """
        try:
            db_info = self.db.get_database_info()
            context_count = self.db.get_context_count()
            
            return {
                'total_contexts': context_count,
                'database_info': db_info,
                'compression_config': {
                    'min_size_threshold': self.compression.min_size_threshold,
                    'min_compression_ratio': self.compression.min_compression_ratio,
                    'compression_level': self.compression.compression_level
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                'error': str(e)
            }
    
    def close(self):
        """Close database connections and cleanup resources."""
        try:
            self.db.close_connections()
            logger.info("Context manager closed")
        except Exception as e:
            logger.error(f"Error closing context manager: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()