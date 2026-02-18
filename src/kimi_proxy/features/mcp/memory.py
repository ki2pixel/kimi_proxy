"""
Gestion de la mémoire standardisée MCP (Phase 3).

Types de mémoire:
- Frequent: Contextes fréquemment utilisés (patterns, snippets)
- Episodic: Conversations et événements spécifiques
- Semantic: Concepts et relations sémantiques (stockés dans Qdrant)

Stockage:
- SQLite: Méta-données et contenu fréquent/épisodique
- Qdrant: Vecteurs sémantiques
"""
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

from ...core.database import get_db
from ...core.tokens import count_tokens_text
from kimi_proxy.core.models import MCPMemoryEntry
from .client import get_mcp_client, MCPExternalClient


# Seuils de configuration
FREQUENT_ACCESS_THRESHOLD = 3  # Nombre d'accès pour considérer comme fréquent
FREQUENT_MEMORY_MIN_TOKENS = 100  # Tokens minimum pour mémoire fréquente
EPISODIC_MEMORY_MAX_AGE_DAYS = 30  # Âge max mémoire épisodique


class MemoryManager:
    """
    Gestionnaire de mémoire standardisée MCP.
    
    Responsabilités:
    - Stocker et récupérer les mémoires fréquentes/épisodiques
    - Décider du type de mémoire selon l'usage
    - Maintenir la cohérence avec Qdrant
    """
    
    def __init__(self, mcp_client: Optional[MCPExternalClient] = None):
        self.mcp_client = mcp_client or get_mcp_client()
        self._local_cache: Dict[str, MCPMemoryEntry] = {}
    
    def _generate_content_hash(self, content: str) -> str:
        """Génère un hash unique pour le contenu."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _get_db_memory_by_hash(self, content_hash: str) -> Optional[MCPMemoryEntry]:
        """Récupère une mémoire par son hash."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, session_id, memory_type, content_hash, content_preview,
                       full_content, token_count, access_count, last_accessed_at,
                       created_at, embedding_id, metadata
                FROM mcp_memory_entries
                WHERE content_hash = ?
            """, (content_hash,))
            row = cursor.fetchone()
            
            if row:
                return MCPMemoryEntry(
                    id=row[0],
                    session_id=row[1],
                    memory_type=row[2],
                    content_hash=row[3],
                    content_preview=row[4],
                    full_content=row[5],
                    token_count=row[6] or 0,
                    access_count=row[7] or 0,
                    last_accessed_at=row[8],
                    created_at=row[9],
                    embedding_id=row[10],
                    metadata=json.loads(row[11]) if row[11] else {}
                )
            return None
    
    async def store_memory(
        self,
        session_id: int,
        content: str,
        memory_type: str = "episodic",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[MCPMemoryEntry]:
        """
        Stocke une nouvelle mémoire.
        
        Args:
            session_id: ID de la session
            content: Contenu à mémoriser
            memory_type: "frequent", "episodic", ou "semantic"
            metadata: Métadonnées additionnelles
            
        Returns:
            Entrée mémoire créée ou None
        """
        if not content or len(content.strip()) < 10:
            return None
        
        token_count = count_tokens_text(content)
        content_hash = self._generate_content_hash(content)
        
        # Vérifie si existe déjà
        existing = self._get_db_memory_by_hash(content_hash)
        if existing:
            # Incrémente le compteur d'accès
            await self._increment_access(existing.id)
            return existing
        
        # Stocke dans Qdrant si disponible et type sémantique
        embedding_id = None
        if memory_type == "semantic" and self.mcp_client.is_qdrant_available():
            embedding_id = await self.mcp_client.store_memory_vector(
                content=content,
                memory_type=memory_type,
                metadata={**metadata, "session_id": session_id} if metadata else {"session_id": session_id}
            )
        
        # Crée l'entrée
        entry = MCPMemoryEntry(
            session_id=session_id,
            memory_type=memory_type,
            content_hash=content_hash,
            content_preview=content[:200],
            full_content=content,
            token_count=token_count,
            access_count=1,
            last_accessed_at=datetime.now().isoformat(),
            created_at=datetime.now().isoformat(),
            embedding_id=embedding_id,
            metadata=metadata or {}
        )
        
        # Persiste dans SQLite
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mcp_memory_entries
                (session_id, memory_type, content_hash, content_preview, full_content,
                 token_count, access_count, last_accessed_at, created_at, embedding_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.session_id, entry.memory_type, entry.content_hash,
                entry.content_preview, entry.full_content, entry.token_count,
                entry.access_count, entry.last_accessed_at, entry.created_at,
                entry.embedding_id, json.dumps(entry.metadata)
            ))
            conn.commit()
            entry.id = cursor.lastrowid
        
        self._local_cache[content_hash] = entry
        return entry
    
    async def _increment_access(self, memory_id: int) -> bool:
        """Incrémente le compteur d'accès d'une mémoire."""
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE mcp_memory_entries
                    SET access_count = access_count + 1,
                        last_accessed_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), memory_id))
                conn.commit()
                return cursor.rowcount > 0
            except Exception:
                return False
    
    async def find_similar_memories(
        self,
        query: str,
        session_id: Optional[int] = None,
        limit: int = 5
    ) -> List[MCPMemoryEntry]:
        """
        Recherche des mémoires similaires.
        
        Args:
            query: Texte de recherche
            session_id: Filtrer par session (optionnel)
            limit: Nombre max de résultats
            
        Returns:
            Liste des mémoires similaires
        """
        results = []
        
        # 1. Recherche sémantique via Qdrant si disponible
        if self.mcp_client.is_qdrant_available():
            qdrant_results = await self.mcp_client.search_similar(query, limit=limit)
            for qr in qdrant_results:
                # Récupère la mémoire complète depuis SQLite
                entry = self._get_db_memory_by_hash(qr.id.split("_")[-1])
                if entry:
                    entry.similarity_score = qr.score
                    results.append(entry)
        
        # 2. Fallback: recherche textuelle simple
        if not results:
            results = await self._search_textual(query, session_id, limit)
        
        # Tri par score de similarité
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:limit]
    
    async def _search_textual(
        self,
        query: str,
        session_id: Optional[int] = None,
        limit: int = 5
    ) -> List[MCPMemoryEntry]:
        """Recherche textuelle simple dans SQLite."""
        with get_db() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT id, session_id, memory_type, content_hash, content_preview,
                           full_content, token_count, access_count, last_accessed_at,
                           created_at, embedding_id, metadata
                    FROM mcp_memory_entries
                    WHERE session_id = ? AND (full_content LIKE ? OR content_preview LIKE ?)
                    ORDER BY access_count DESC, last_accessed_at DESC
                    LIMIT ?
                """, (session_id, f"%{query}%", f"%{query}%", limit))
            else:
                cursor.execute("""
                    SELECT id, session_id, memory_type, content_hash, content_preview,
                           full_content, token_count, access_count, last_accessed_at,
                           created_at, embedding_id, metadata
                    FROM mcp_memory_entries
                    WHERE full_content LIKE ? OR content_preview LIKE ?
                    ORDER BY access_count DESC, last_accessed_at DESC
                    LIMIT ?
                """, (f"%{query}%", f"%{query}%", limit))
            
            rows = cursor.fetchall()
            results = []
            for row in rows:
                entry = MCPMemoryEntry(
                    id=row[0], session_id=row[1], memory_type=row[2],
                    content_hash=row[3], content_preview=row[4],
                    full_content=row[5], token_count=row[6] or 0,
                    access_count=row[7] or 0, last_accessed_at=row[8],
                    created_at=row[9], embedding_id=row[10],
                    metadata=json.loads(row[11]) if row[11] else {}
                )
                # Score basique basé sur fréquence
                entry.similarity_score = min(entry.access_count / 10.0, 1.0)
                results.append(entry)
            
            return results
    
    async def get_frequent_memories(
        self,
        session_id: Optional[int] = None,
        min_access_count: int = FREQUENT_ACCESS_THRESHOLD,
        limit: int = 10
    ) -> List[MCPMemoryEntry]:
        """
        Récupère les mémoires fréquemment utilisées.
        
        Args:
            session_id: Filtrer par session
            min_access_count: Nombre minimum d'accès
            limit: Nombre max de résultats
            
        Returns:
            Liste des mémoires fréquentes
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT id, session_id, memory_type, content_hash, content_preview,
                           full_content, token_count, access_count, last_accessed_at,
                           created_at, embedding_id, metadata
                    FROM mcp_memory_entries
                    WHERE session_id = ? AND access_count >= ?
                    ORDER BY access_count DESC, last_accessed_at DESC
                    LIMIT ?
                """, (session_id, min_access_count, limit))
            else:
                cursor.execute("""
                    SELECT id, session_id, memory_type, content_hash, content_preview,
                           full_content, token_count, access_count, last_accessed_at,
                           created_at, embedding_id, metadata
                    FROM mcp_memory_entries
                    WHERE access_count >= ?
                    ORDER BY access_count DESC, last_accessed_at DESC
                    LIMIT ?
                """, (min_access_count, limit))
            
            rows = cursor.fetchall()
            return [
                MCPMemoryEntry(
                    id=row[0], session_id=row[1], memory_type=row[2],
                    content_hash=row[3], content_preview=row[4],
                    full_content=row[5], token_count=row[6] or 0,
                    access_count=row[7] or 0, last_accessed_at=row[8],
                    created_at=row[9], embedding_id=row[10],
                    metadata=json.loads(row[11]) if row[11] else {}
                )
                for row in rows
            ]
    
    async def detect_and_promote_frequent_patterns(self, session_id: int) -> int:
        """
        Détecte et promeut les patterns fréquents en mémoire fréquente.
        
        Args:
            session_id: ID de la session à analyser
            
        Returns:
            Nombre de mémoires promues
        """
        promoted = 0
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Cherche les mémoires épisodiques avec beaucoup d'accès
            cursor.execute("""
                SELECT id, access_count
                FROM mcp_memory_entries
                WHERE session_id = ? AND memory_type = 'episodic' AND access_count >= ?
            """, (session_id, FREQUENT_ACCESS_THRESHOLD))
            
            candidates = cursor.fetchall()
            
            for memory_id, access_count in candidates:
                cursor.execute("""
                    UPDATE mcp_memory_entries
                    SET memory_type = 'frequent',
                        metadata = json_set(COALESCE(metadata, '{}'), '$.promoted_at', ?)
                    WHERE id = ?
                """, (datetime.now().isoformat(), memory_id))
                promoted += 1
            
            conn.commit()
        
        return promoted
    
    async def get_memory_stats(self, session_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Récupère les statistiques de mémoire.
        
        Args:
            session_id: Filtrer par session (optionnel)
            
        Returns:
            Statistiques détaillées
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN memory_type = 'frequent' THEN 1 ELSE 0 END) as frequent,
                        SUM(CASE WHEN memory_type = 'episodic' THEN 1 ELSE 0 END) as episodic,
                        SUM(CASE WHEN memory_type = 'semantic' THEN 1 ELSE 0 END) as semantic,
                        SUM(token_count) as total_tokens,
                        AVG(access_count) as avg_access
                    FROM mcp_memory_entries
                    WHERE session_id = ?
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN memory_type = 'frequent' THEN 1 ELSE 0 END) as frequent,
                        SUM(CASE WHEN memory_type = 'episodic' THEN 1 ELSE 0 END) as episodic,
                        SUM(CASE WHEN memory_type = 'semantic' THEN 1 ELSE 0 END) as semantic,
                        SUM(token_count) as total_tokens,
                        AVG(access_count) as avg_access
                    FROM mcp_memory_entries
                """)
            
            row = cursor.fetchone()
            
            return {
                "total_memories": row[0] or 0,
                "frequent_memories": row[1] or 0,
                "episodic_memories": row[2] or 0,
                "semantic_memories": row[3] or 0,
                "total_tokens": row[4] or 0,
                "average_access_count": round(row[5] or 0, 2),
                "qdrant_connected": self.mcp_client.is_qdrant_available()
            }
    
    async def cleanup_old_episodic_memories(self, max_age_days: int = EPISODIC_MEMORY_MAX_AGE_DAYS) -> int:
        """
        Nettoie les mémoires épisodiques anciennes.
        
        Args:
            max_age_days: Âge maximum en jours
            
        Returns:
            Nombre de mémoires supprimées
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM mcp_memory_entries
                WHERE memory_type = 'episodic'
                AND datetime(created_at) < datetime('now', '-{} days')
                AND access_count < ?
            """.format(max_age_days), (FREQUENT_ACCESS_THRESHOLD,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted
    
    async def compress_memory_if_beneficial(
        self,
        memory_id: int,
        min_token_threshold: int = 500
    ) -> Optional[MCPMemoryEntry]:
        """
        Compresse une mémoire si c'est bénéfique.
        
        Args:
            memory_id: ID de la mémoire
            min_token_threshold: Tokens minimum pour considérer la compression
            
        Returns:
            Mémoire compressée ou None
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT full_content, token_count, memory_type
                FROM mcp_memory_entries
                WHERE id = ?
            """, (memory_id,))
            row = cursor.fetchone()
            
            if not row or row[1] < min_token_threshold:
                return None
            
            content, original_tokens, mem_type = row
            
            # Compression via MCP
            compression_result = await self.mcp_client.compress_content(
                content=content,
                algorithm="context_aware",
                target_ratio=0.5
            )
            
            if compression_result.compression_ratio < 0.2:
                # Pas assez de gain, abandonne
                return None
            
            # Met à jour la mémoire avec le contenu compressé
            compressed_content = compression_result.compressed_content
            new_token_count = compression_result.compressed_tokens
            
            cursor.execute("""
                UPDATE mcp_memory_entries
                SET full_content = ?,
                    token_count = ?,
                    metadata = json_set(COALESCE(metadata, '{}'), '$.compressed', 'true')
                WHERE id = ?
            """, (compressed_content, new_token_count, memory_id))
            conn.commit()
            
            # Retourne l'entrée mise à jour
            return self._get_db_memory_by_hash(self._generate_content_hash(compressed_content))


import json  # Import manquant


# Singleton
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(mcp_client: Optional[MCPExternalClient] = None) -> MemoryManager:
    """Récupère le gestionnaire de mémoire global."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager(mcp_client)
    return _memory_manager


def reset_memory_manager():
    """Réinitialise le gestionnaire de mémoire (pour tests)."""
    global _memory_manager
    _memory_manager = None
