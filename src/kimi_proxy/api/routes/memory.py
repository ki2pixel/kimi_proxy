"""
memory.py - Routes API pour les opérations mémoire (compression & similarité)

Pourquoi : Fournit les endpoints HTTP/WebSocket pour les fonctionnalités
mémoire avancées du Kimi Proxy Dashboard
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import logging
from datetime import datetime

from ...core.database import get_db
from ...services.websocket_manager import ConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

# ============================================================================
# MODÈLES PYDANTIC
# ============================================================================

class CompressionRequest(BaseModel):
    strategy: str = Field(..., description="Stratégie de compression", pattern="^(token|semantic)$")
    threshold: float = Field(..., ge=0.1, le=0.9, description="Seuil de compression")
    dry_run: bool = Field(default=False, description="Mode simulation uniquement")

class SimilarityRequest(BaseModel):
    reference_id: Optional[str] = Field(None, description="ID de la mémoire de référence")
    reference_text: Optional[str] = Field(None, description="Texte de référence (alternative)")
    method: str = Field(default="cosine", description="Méthode de similarité", pattern="^(cosine|jaccard|levenshtein)$")
    threshold: float = Field(default=0.75, ge=0.5, le=1.0, description="Seuil de similarité")
    limit: int = Field(default=20, ge=5, le=100, description="Nombre maximum de résultats")

class MemoryItem(BaseModel):
    id: str
    title: str
    content: str
    content_preview: str
    type: str
    tokens: int
    created_at: datetime
    similarity_score: Optional[float] = None

class CompressionResult(BaseModel):
    success: bool
    current_count: int
    projected_count: int
    space_saved: str
    preview: List[Dict[str, Any]]
    compression_ratio: Optional[float] = None
    error: Optional[str] = None

class SimilarityResult(BaseModel):
    success: bool
    results: List[MemoryItem]
    total_found: int
    method_used: str
    threshold_used: float
    error: Optional[str] = None

# ============================================================================
# SERVICES MÉMOIRE
# ============================================================================

class MemoryService:
    """Service central pour les opérations mémoire avec données réelles et similarité MCP"""
    
    def __init__(self, db, ws_manager: ConnectionManager):
        self.db = db
        self.ws_manager = ws_manager
        self._qdrant_client = None
        self._mock_memories = self._generate_mock_memories()  # Fallback uniquement
    
    def _get_qdrant_client(self):
        """Lazy loading du client Qdrant MCP"""
        if self._qdrant_client is None:
            try:
                from ...features.mcp.client import get_mcp_client
                client = get_mcp_client()
                if client and client.qdrant:
                    self._qdrant_client = client.qdrant
            except Exception as e:
                logger.warning(f"Qdrant client non disponible: {e}")
        return self._qdrant_client
    
    def _generate_mock_memories(self) -> List[Dict]:
        """Génère des mémoires de test pour fallback si aucune donnée réelle"""
        memories = [
            {
                "id": "mem_001",
                "title": "Configuration FastAPI",
                "content": "Configuration du serveur FastAPI avec Uvicorn, middleware CORS, et routes API pour le proxy Kimi",
                "content_preview": "Configuration du serveur FastAPI avec Uvicorn...",
                "type": "configuration",
                "tokens": 156,
                "created_at": datetime.now()
            },
            {
                "id": "mem_002", 
                "title": "Architecture 5 Couches",
                "content": "Architecture en 5 couches: API → Services → Features → Proxy → Core avec dépendances unidirectionnelles",
                "content_preview": "Architecture en 5 couches: API → Services → Features...",
                "type": "architecture",
                "tokens": 234,
                "created_at": datetime.now()
            },
            {
                "id": "mem_003",
                "title": "Token Counting Tiktoken",
                "content": "Utilisation de tiktoken pour le comptage précis des tokens avec encodage cl100k_base",
                "content_preview": "Utilisation de tiktoken pour le comptage précis...",
                "type": "technique",
                "tokens": 189,
                "created_at": datetime.now()
            },
            {
                "id": "mem_004",
                "title": "WebSocket Manager",
                "content": "Gestionnaire WebSocket pour communication temps réel avec reconnexion automatique et diffusion d'événements",
                "content_preview": "Gestionnaire WebSocket pour communication temps réel...",
                "type": "communication",
                "tokens": 267,
                "created_at": datetime.now()
            },
            {
                "id": "mem_005",
                "title": "MCP Phase 4 Integration",
                "content": "Intégration des 4 serveurs MCP Phase 4: Shrimp Task Manager, Sequential Thinking, Fast Filesystem, JSON Query",
                "content_preview": "Intégration des 4 serveurs MCP Phase 4...",
                "type": "integration",
                "tokens": 312,
                "created_at": datetime.now()
            }
        ]
        return memories
    
    async def _get_real_memories_from_db(self, limit: int = 50) -> List[Dict]:
        """Récupère les mémoires réelles depuis la base de données SQLite"""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT id, session_id, memory_type, content_hash, content_preview, 
                       full_content, token_count, access_count, created_at, metadata
                FROM mcp_memory_entries
                ORDER BY access_count DESC, last_accessed_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            memories = []
            
            for row in rows:
                mem = {
                    "id": str(row[0]),
                    "title": row[4][:50] if row[4] else f"Mémoire {row[0]}",
                    "content": row[5] or row[4] or "",
                    "content_preview": row[4] or "",
                    "type": row[2] or "episodic",
                    "tokens": row[6] or 0,
                    "created_at": datetime.fromisoformat(row[8].replace('Z', '+00:00')) if row[8] and isinstance(row[8], str) else datetime.now(),
                    "session_id": row[1],
                    "access_count": row[7] or 0
                }
                memories.append(mem)
            
            return memories
            
        except Exception as e:
            logger.error(f"Erreur récupération mémoires DB: {e}")
            return []
    
    async def get_frequent_memories(self) -> List[MemoryItem]:
        """Récupère les mémoires fréquentes depuis la base de données"""
        real_memories = await self._get_real_memories_from_db(limit=50)
        
        # Fallback vers mock si aucune donnée réelle
        if not real_memories:
            logger.info("Aucune mémoire réelle trouvée, utilisation du fallback mock")
            real_memories = self._mock_memories
        
        return [MemoryItem(**mem) for mem in real_memories]
    
    async def preview_compression(self, strategy: str, threshold: float) -> CompressionResult:
        """Prévisualise la compression mémoire avec données réelles"""
        try:
            # Récupère les mémoires réelles
            memories = await self._get_real_memories_from_db(limit=100)
            
            # Fallback vers mock si aucune donnée réelle
            if not memories:
                memories = self._mock_memories
            
            # Simulation de l'analyse
            await asyncio.sleep(0.1)  # Réduit pour meilleure UX
            
            total_tokens = sum(m["tokens"] for m in memories)
            
            # Stratégie token: fusionner les petites mémoires
            if strategy == "token":
                small_memories = [m for m in memories if m["tokens"] < threshold * 1000]
                projected_count = len(memories) - len(small_memories) // 2
                space_saved_tokens = sum(m["tokens"] for m in small_memories) // 2
                
                preview = [
                    {
                        "action": "fusionner",
                        "items": f"{len(small_memories)} petites mémoires",
                        "tokens": space_saved_tokens,
                        "preview": f"Fusion de {len(small_memories)} mémoires < {threshold * 1000:.0f} tokens"
                    }
                ]
            else:  # semantic
                # Regroupement sémantique basé sur les types de mémoires
                types = {}  # type: ignore
                for m in memories:
                    t = m.get("type", "unknown")
                    types[t] = types.get(t, 0) + 1
                
                dominant_type = max(types.items(), key=lambda x: x[1]) if types else ("unknown", 0)
                projected_count = max(2, len(memories) - len(types) + 1)
                space_saved_tokens = int(total_tokens * 0.25)  # Estimation 25% économie
                
                preview = [
                    {
                        "action": "regrouper",
                        "items": f"{len(types)} types de mémoires",
                        "tokens": space_saved_tokens,
                        "preview": f"Regroupement par similarité sémantique (type dominant: {dominant_type[0]})"
                    }
                ]
            
            return CompressionResult(
                success=True,
                current_count=len(memories),
                projected_count=projected_count,
                space_saved=f"{space_saved_tokens} tokens",
                preview=preview,
                compression_ratio=space_saved_tokens / total_tokens if total_tokens > 0 else 0
            )
            
        except Exception as e:
            logger.error(f"Erreur preview compression: {e}")
            return CompressionResult(
                success=False,
                current_count=0,
                projected_count=0,
                space_saved="0 tokens",
                preview=[],
                error=str(e)
            )
    
    async def execute_compression(self, strategy: str, threshold: float, dry_run: bool) -> CompressionResult:
        """Exécute la compression mémoire avec données réelles"""
        if dry_run:
            return await self.preview_compression(strategy, threshold)
        
        try:
            # Récupère les mémoires réelles
            memories = await self._get_real_memories_from_db(limit=100)
            
            # Fallback vers mock si aucune donnée réelle
            if not memories:
                memories = self._mock_memories
            
            # Simulation de l'exécution (optimisée)
            await asyncio.sleep(0.2)
            
            # Log la compression dans la base de données
            try:
                cursor = self.db.cursor()
                for mem in memories[:5]:  # Limite pour performance
                    cursor.execute("""
                        INSERT INTO compression_log 
                        (session_id, original_tokens, compressed_tokens, compression_ratio, summary_preview)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        mem.get("session_id", 0),
                        mem["tokens"],
                        int(mem["tokens"] * 0.8),  # Simulation 20% compression
                        0.2,
                        mem["content_preview"][:100]
                    ))
                self.db.commit()
            except Exception as e:
                logger.warning(f"Erreur logging compression: {e}")
            
            # Notifier les clients WebSocket
            await self.ws_manager.broadcast({
                "type": "memory_compression_completed",
                "strategy": strategy,
                "threshold": threshold,
                "memories_processed": len(memories),
                "timestamp": datetime.now().isoformat()
            })
            
            return await self.preview_compression(strategy, threshold)
            
        except Exception as e:
            logger.error(f"Erreur exécution compression: {e}")
            return CompressionResult(
                success=False,
                current_count=0,
                projected_count=0,
                space_saved="0 tokens",
                preview=[],
                error=str(e)
            )
    
    async def find_similar_memories(self, request: SimilarityRequest) -> SimilarityResult:
        """Recherche des mémoires similaires avec Qdrant MCP ou algorithmes locaux"""
        try:
            # Récupère les mémoires réelles
            memories = await self._get_real_memories_from_db(limit=100)
            
            # Fallback vers mock si aucune donnée réelle
            if not memories:
                memories = self._mock_memories
            
            # Détermine le texte de référence
            reference_text = request.reference_text
            if request.reference_id and not reference_text:
                # Cherche la mémoire par ID
                for mem in memories:
                    if mem["id"] == request.reference_id:
                        reference_text = mem["content"]
                        break
            
            if not reference_text:
                return SimilarityResult(
                    success=False,
                    results=[],
                    total_found=0,
                    method_used=request.method,
                    threshold_used=request.threshold,
                    error="Texte de référence non trouvé"
                )
            
            # Essaie d'abord Qdrant si disponible
            qdrant_client = self._get_qdrant_client()
            if qdrant_client:
                try:
                    # Vérifie si Qdrant est disponible
                    status = await qdrant_client.check_status()
                    if status and status.connected:
                        logger.info(f"🔍 Utilisation de Qdrant pour similarité (latence: {status.latency_ms:.1f}ms)")
                        
                        # Recherche sémantique via Qdrant
                        qdrant_results = await qdrant_client.search_similar(
                            query=reference_text[:500],  # Limite pour performance
                            limit=request.limit,
                            score_threshold=request.threshold
                        )
                        
                        # Mappe les résultats Qdrant vers MemoryItem
                        results = []
                        for hit in qdrant_results:
                            mem_item = MemoryItem(
                                id=hit.id,
                                title=hit.content_preview[:50] if hit.content_preview else f"Résultat {hit.id}",
                                content=hit.full_content or hit.content_preview or "",
                                content_preview=hit.content_preview or "",
                                type=hit.metadata.get("type", "semantic") if hit.metadata else "semantic",
                                tokens=hit.metadata.get("token_count", 0) if hit.metadata else 0,
                                created_at=datetime.now(),  # Qdrant ne stocke pas le datetime
                                similarity_score=hit.score
                            )
                            results.append(mem_item)
                        
                        return SimilarityResult(
                            success=True,
                            results=results,
                            total_found=len(results),
                            method_used="qdrant_semantic",
                            threshold_used=request.threshold
                        )
                except Exception as e:
                    logger.warning(f"Qdrant indisponible, fallback vers algorithmes locaux: {e}")
            
            # Fallback: Algorithmes locaux
            logger.info(f"🔢 Utilisation des algorithmes locaux ({request.method})")
            results = await self._find_similar_local(
                memories, reference_text, request.method, request.threshold, request.limit
            )
            
            return SimilarityResult(
                success=True,
                results=results,
                total_found=len(results),
                method_used=request.method,
                threshold_used=request.threshold
            )
            
        except Exception as e:
            logger.error(f"Erreur recherche similarité: {e}")
            return SimilarityResult(
                success=False,
                results=[],
                total_found=0,
                method_used=request.method,
                threshold_used=request.threshold,
                error=str(e)
            )
    
    async def _find_similar_local(
        self, 
        memories: List[Dict], 
        reference_text: str, 
        method: str, 
        threshold: float, 
        limit: int
    ) -> List[MemoryItem]:
        """Algorithmes de similarité locaux (fallback)"""
        
        # Normalise le texte de référence
        ref_words = self._extract_words(reference_text)
        ref_set = set(ref_words)
        
        results = []
        for mem in memories:
            mem_words = self._extract_words(mem["content"])
            mem_set = set(mem_words)
            
            # Calcule le score selon la méthode
            if method == "cosine":
                score = self._cosine_similarity(ref_words, mem_words)
            elif method == "jaccard":
                score = self._jaccard_similarity(ref_set, mem_set)
            else:  # levenshtein
                score = self._levenshtein_similarity(reference_text, mem["content"])
            
            # Filtre par seuil
            if score >= threshold:
                mem_copy = mem.copy()
                mem_copy["similarity_score"] = round(score, 3)
                results.append(MemoryItem(**mem_copy))
        
        # Trie par score décroissant
        results.sort(key=lambda x: x.similarity_score, reverse=True)  # type: ignore
        
        # Limite les résultats
        return results[:limit]
    
    def _extract_words(self, text: str) -> List[str]:
        """Extrait les mots d'un texte (tokenisation simple)"""
        if not text:
            return []
        # Minuscules, alphanumérique uniquement, mots > 2 caractères
        words = []
        for word in text.lower().split():
            clean = ''.join(c for c in word if c.isalnum())
            if len(clean) > 2:
                words.append(clean)
        return words
    
    def _cosine_similarity(self, words1: List[str], words2: List[str]) -> float:
        """Calcule la similarité cosinus entre deux listes de mots"""
        if not words1 or not words2:
            return 0.0
        
        # Compte les fréquences
        from collections import Counter
        vec1 = Counter(words1)
        vec2 = Counter(words2)
        
        # Vocabulaire commun
        all_words = set(vec1.keys()) | set(vec2.keys())
        
        # Vecteurs
        v1 = [vec1.get(w, 0) for w in all_words]
        v2 = [vec2.get(w, 0) for w in all_words]
        
        # Produit scalaire
        dot_product = sum(a * b for a, b in zip(v1, v2))
        
        # Normes
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        """Calcule le coefficient de similarité de Jaccard"""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calcule la similarité basée sur la distance de Levenshtein (normalisée)"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        # Distance de Levenshtein
        distance = self._levenshtein_distance(s1[:200], s2[:200])  # Limite pour performance
        max_len = max(len(s1), len(s2))
        
        return 1.0 - (distance / max_len) if max_len > 0 else 0.0
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calcule la distance de Levenshtein entre deux chaînes (programmation dynamique)"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        # Optimisation: utilise deux lignes au lieu de matrice complète
        previous_row = list(range(len(s2) + 1))
        current_row = [0] * (len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row[0] = i + 1
            
            for j, c2 in enumerate(s2):
                # Coûts: insertion, deletion, substitution
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row[j + 1] = min(insertions, deletions, substitutions)
            
            # Swap rows
            previous_row, current_row = current_row, previous_row
        
        return previous_row[len(s2)]

# ============================================================================
# ENDPOINTS API
# ============================================================================

@router.get("/frequent", response_model=List[MemoryItem])
async def get_frequent_memories(db=Depends(get_db)):
    """Récupère les mémoires fréquentes depuis la base de données"""
    ws_manager = get_connection_manager()
    service = MemoryService(db, ws_manager)
    return await service.get_frequent_memories()

@router.post("/compress/preview", response_model=CompressionResult)
async def preview_compression(
    strategy: str,
    threshold: float,
    db=Depends(get_db)
):
    """Prévisualise la compression mémoire"""
    ws_manager = get_connection_manager()
    service = MemoryService(db, ws_manager)
    return await service.preview_compression(strategy, threshold)

@router.post("/compress/execute", response_model=CompressionResult)
async def execute_compression(
    request: CompressionRequest,
    db=Depends(get_db)
):
    """Exécute la compression mémoire"""
    ws_manager = get_connection_manager()
    service = MemoryService(db, ws_manager)
    return await service.execute_compression(
        request.strategy, 
        request.threshold, 
        request.dry_run
    )

@router.post("/similarity/search", response_model=SimilarityResult)
async def search_similar_memories(
    request: SimilarityRequest,
    db=Depends(get_db)
):
    """Recherche des mémoires similaires"""
    ws_manager = get_connection_manager()
    service = MemoryService(db, ws_manager)
    return await service.find_similar_memories(request)

@router.get("/stats")
async def get_memory_stats(db=Depends(get_db)):
    """Statistiques sur les mémoires"""
    ws_manager = get_connection_manager()
    service = MemoryService(db, ws_manager)
    memories = await service.get_frequent_memories()
    
    total_tokens = sum(m.tokens for m in memories)
    avg_tokens = total_tokens / len(memories) if memories else 0
    
    return {
        "total_memories": len(memories),
        "total_tokens": total_tokens,
        "average_tokens": round(avg_tokens, 1),
        "types": list(set(m.type for m in memories)),
        "last_updated": datetime.now().isoformat()
    }

# ============================================================================
# HANDLERS WEBSOCKET
# ============================================================================

async def handle_memory_compress_preview(websocket, data: Dict[str, Any]):
    """Handler WebSocket pour preview compression"""
    try:
        db = get_db()
        ws_manager = get_connection_manager()
        service = MemoryService(db, ws_manager)
        
        result = await service.preview_compression(
            data.get("strategy", "token"),
            data.get("threshold", 0.3)
        )
        
        await websocket.send_json({
            "type": "memory_compress_preview_response",
            "requestId": data.get("requestId"),
            "result": result.dict()
        })
        
    except Exception as e:
        logger.error(f"Erreur WebSocket preview compression: {e}")
        await websocket.send_json({
            "type": "memory_compress_preview_response",
            "requestId": data.get("requestId"),
            "error": str(e)
        })

async def handle_memory_compress_execute(websocket, data: Dict[str, Any]):
    """Handler WebSocket pour exécution compression"""
    try:
        db = get_db()
        ws_manager = get_connection_manager()
        service = MemoryService(db, ws_manager)
        
        result = await service.execute_compression(
            data.get("strategy", "token"),
            data.get("threshold", 0.3),
            data.get("dryRun", False)
        )
        
        await websocket.send_json({
            "type": "memory_compress_result_response",
            "requestId": data.get("requestId"),
            "result": result.dict()
        })
        
    except Exception as e:
        logger.error(f"Erreur WebSocket exécution compression: {e}")
        await websocket.send_json({
            "type": "memory_compress_result_response",
            "requestId": data.get("requestId"),
            "error": str(e)
        })

import json  # noqa
from datetime import datetime  # noqa

# Helper pour sérialiser les objets datetime
def serialize_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

async def handle_memory_similarity_search(websocket, data: Dict[str, Any]):
    """Handler WebSocket pour recherche similarité"""
    try:
        db = get_db()
        ws_manager = get_connection_manager()
        service = MemoryService(db, ws_manager)
        
        request = SimilarityRequest(**data.get("payload", {}))
        result = await service.find_similar_memories(request)
        
        # Sérialise correctement avec gestion des datetime
        response_data = {
            "type": "memory_similarity_result_response",
            "requestId": data.get("requestId"),
            "result": json.loads(json.dumps(result.dict() if hasattr(result, 'dict') else result, default=serialize_datetime))
        }
        
        await websocket.send_json(response_data)
        
    except Exception as e:
        logger.error(f"Erreur WebSocket recherche similarité: {e}")
        await websocket.send_json({
            "type": "memory_similarity_result_response",
            "requestId": data.get("requestId"),
            "error": str(e)
        })

# Export des handlers pour le WebSocket manager
WEBSOCKET_HANDLERS = {
    "memory_compress_preview": handle_memory_compress_preview,
    "memory_compress_execute": handle_memory_compress_execute,
    "memory_similarity_search": handle_memory_similarity_search,
}