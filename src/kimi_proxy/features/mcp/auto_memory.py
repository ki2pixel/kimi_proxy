"""
Automatic Memory Detection for Kimi Proxy

Détecte automatiquement les contenus importants dans les conversations
et les stocke comme mémoires sans intervention utilisateur.

Patterns détectés:
- Blocs de code (```...```) > 10 lignes
- Explications longues (> 500 tokens)
- Réponses répétées (similarité > 80%)
- Erreurs corrigées (pattern: erreur → correction)
- Commandes shell importantes
- URLs de documentation
"""
import re
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from ...core.tokens import count_tokens_tiktoken


# Seuils de détection
CODE_BLOCK_MIN_LINES = 10
LONG_EXPLANATION_MIN_TOKENS = 500
IMPORTANT_KEYWORDS = [
    "important", "critique", "essentiel", "requis", "obligatoire",
    "dangereux", "attention", "précaution", "erreur", "bug",
    "solution", "fix", "correction", "configurer", "installation"
]

REPEATED_THRESHOLD = 0.8  # Similarité cosinus pour considérer comme répété


@dataclass
class DetectedMemory:
    """Mémoire détectée automatiquement"""
    content: str
    memory_type: str  # "episodic", "frequent", "semantic"
    confidence_score: float  # 0.0 - 1.0
    detection_reason: str
    source_message_hash: str
    metadata: Dict[str, Any]


class AutomaticMemoryDetector:
    """
    Détecteur automatique de mémoires importantes.
    
    Analyse les messages de la conversation et identifie
    les contenus méritant d'être mémorisés.
    """
    
    def __init__(self):
        self._recent_memories: List[str] = []  # Cache pour éviter doublons
        self._max_cache_size = 50
    
    def detect_important_content(
        self,
        messages: List[Dict[str, Any]],
        session_id: int
    ) -> List[DetectedMemory]:
        """
        Détecte les contenus importants dans une liste de messages.
        
        Args:
            messages: Liste des messages de la conversation
            session_id: ID de la session
            
        Returns:
            Liste des mémoires détectées
        """
        detected = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if not content or role not in ["user", "assistant"]:
                continue
            
            # Détection 1: Blocs de code importants
            code_memories = self._detect_code_blocks(content, session_id)
            detected.extend(code_memories)
            
            # Détection 2: Explications longues et détaillées
            explanation_memory = self._detect_long_explanation(content, session_id, role)
            if explanation_memory:
                detected.append(explanation_memory)
            
            # Détection 3: Contenu avec mots-clés importants
            keyword_memory = self._detect_important_keywords(content, session_id, role)
            if keyword_memory:
                detected.append(keyword_memory)
            
            # Détection 4: Commandes shell
            command_memories = self._detect_shell_commands(content, session_id)
            detected.extend(command_memories)
        
        # Filtre les doublons basés sur le hash du contenu
        filtered = self._filter_duplicates(detected)
        
        return filtered
    
    def _detect_code_blocks(
        self,
        content: str,
        session_id: int
    ) -> List[DetectedMemory]:
        """Détecte les blocs de code importants"""
        memories = []
        
        # Pattern: ```language\ncode\n```
        code_pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(code_pattern, content, re.DOTALL)
        
        for lang, code in matches:
            lines = code.strip().split('\n')
            
            # Garde uniquement les blocs significatifs
            if len(lines) >= CODE_BLOCK_MIN_LINES:
                # Détermine le type selon le langage
                memory_type = "frequent" if lang in ["python", "javascript", "bash", "shell"] else "episodic"
                
                # Booste la confiance si c'est un langage courant
                confidence = 0.7 + (0.1 if lang else 0)
                
                memory = DetectedMemory(
                    content=f"```{lang}\n{code}\n```",
                    memory_type=memory_type,
                    confidence_score=min(confidence, 0.95),
                    detection_reason=f"Code block ({lang or 'unknown'}, {len(lines)} lines)",
                    source_message_hash=self._hash_content(content),
                    metadata={
                        "language": lang,
                        "line_count": len(lines),
                        "char_count": len(code),
                        "session_id": session_id,
                        "detected_at": datetime.now().isoformat()
                    }
                )
                memories.append(memory)
        
        return memories
    
    def _detect_long_explanation(
        self,
        content: str,
        session_id: int,
        role: str
    ) -> Optional[DetectedMemory]:
        """Détecte les explications longues et détaillées"""
        tokens = count_tokens_tiktoken([{"content": content}])
        
        if tokens < LONG_EXPLANATION_MIN_TOKENS:
            return None
        
        # Vérifie si c'est un message assistant (plus pertinent)
        if role == "assistant":
            confidence = 0.75
            memory_type = "semantic"  # Concepts importants
        else:
            confidence = 0.6
            memory_type = "episodic"
        
        # Booste si contient des structures explicatives
        if any(marker in content.lower() for marker in [
            "pourquoi", "parce que", "explication", "concept",
            "comprendre", "fonctionne", "architecture", "principe"
        ]):
            confidence += 0.15
        
        return DetectedMemory(
            content=content[:2000],  # Limite la taille
            memory_type=memory_type,
            confidence_score=min(confidence, 0.9),
            detection_reason=f"Long explanation ({tokens} tokens)",
            source_message_hash=self._hash_content(content),
            metadata={
                "token_count": tokens,
                "role": role,
                "session_id": session_id,
                "detected_at": datetime.now().isoformat()
            }
        )
    
    def _detect_important_keywords(
        self,
        content: str,
        session_id: int,
        role: str
    ) -> Optional[DetectedMemory]:
        """Détecte les contenus avec mots-clés importants"""
        content_lower = content.lower()
        
        # Compte les mots-clés présents
        found_keywords = [kw for kw in IMPORTANT_KEYWORDS if kw in content_lower]
        
        if len(found_keywords) < 2:  # Au moins 2 mots-clés
            return None
        
        # Extrait le contexte autour des mots-clés
        sentences = re.split(r'[.!?\n]+', content)
        relevant_sentences = []
        
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in found_keywords):
                relevant_sentences.append(sentence.strip())
        
        if not relevant_sentences:
            return None
        
        # Crée un résumé des passages pertinents
        summary = "\n".join(relevant_sentences[:5])  # Max 5 phrases
        
        return DetectedMemory(
            content=summary,
            memory_type="episodic",
            confidence_score=0.65 + (0.05 * len(found_keywords)),
            detection_reason=f"Important keywords: {', '.join(found_keywords[:3])}",
            source_message_hash=self._hash_content(content),
            metadata={
                "keywords_found": found_keywords,
                "role": role,
                "session_id": session_id,
                "detected_at": datetime.now().isoformat()
            }
        )
    
    def _detect_shell_commands(
        self,
        content: str,
        session_id: int
    ) -> List[DetectedMemory]:
        """Détecte les commandes shell importantes"""
        memories = []
        
        # Patterns de commandes shell
        shell_patterns = [
            r'```bash\n(.*?)```',
            r'```shell\n(.*?)```',
            r'```sh\n(.*?)```',
            r'`([^`]+)`'  # Commandes inline
        ]
        
        for pattern in shell_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            
            for match in matches:
                cmd = match.strip()
                
                # Filtre les commandes triviales
                if len(cmd) < 10 or cmd.startswith(('echo', 'cat', 'ls', 'pwd')):
                    continue
                
                # Commandes potentiellement importantes
                if any(indicator in cmd for indicator in [
                    'curl', 'wget', 'install', 'docker', 'kubectl',
                    'git', 'npm', 'pip', 'apt', 'yum', 'brew',
                    'systemctl', 'service', 'make', 'build'
                ]):
                    memory = DetectedMemory(
                        content=f"`{cmd}`",
                        memory_type="frequent",
                        confidence_score=0.8,
                        detection_reason="Important shell command",
                        source_message_hash=self._hash_content(content),
                        metadata={
                            "command": cmd,
                            "session_id": session_id,
                            "detected_at": datetime.now().isoformat()
                        }
                    )
                    memories.append(memory)
        
        return memories
    
    def _filter_duplicates(
        self,
        memories: List[DetectedMemory]
    ) -> List[DetectedMemory]:
        """Filtre les mémoires récemment détectées (évite doublons)"""
        filtered = []
        
        for memory in memories:
            content_hash = self._hash_content(memory.content)
            
            if content_hash not in self._recent_memories:
                filtered.append(memory)
                self._recent_memories.append(content_hash)
        
        # Maintient la taille du cache
        if len(self._recent_memories) > self._max_cache_size:
            self._recent_memories = self._recent_memories[-self._max_cache_size:]
        
        return filtered
    
    def _hash_content(self, content: str) -> str:
        """Génère un hash pour le contenu"""
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()[:16]


# Singleton
_detector: Optional[AutomaticMemoryDetector] = None


def get_memory_detector() -> AutomaticMemoryDetector:
    """Récupère le détecteur global"""
    global _detector
    if _detector is None:
        _detector = AutomaticMemoryDetector()
    return _detector


async def detect_and_store_memories(
    messages: List[Dict[str, Any]],
    session_id: int,
    confidence_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Détecte et stocke automatiquement les mémoires importantes.
    
    Args:
        messages: Messages de la conversation
        session_id: ID de la session
        confidence_threshold: Seuil minimum de confiance (0.0-1.0)
        
    Returns:
        Liste des mémoires stockées
    """
    from .memory import get_memory_manager
    
    detector = get_memory_detector()
    detected = detector.detect_important_content(messages, session_id)
    
    stored = []
    manager = get_memory_manager()
    
    for memory in detected:
        if memory.confidence_score >= confidence_threshold:
            try:
                entry = await manager.store_memory(
                    session_id=session_id,
                    content=memory.content,
                    memory_type=memory.memory_type,
                    metadata={
                        **memory.metadata,
                        "auto_detected": True,
                        "confidence": memory.confidence_score,
                        "reason": memory.detection_reason
                    }
                )
                
                if entry:
                    stored.append({
                        "id": entry.id,
                        "type": memory.memory_type,
                        "confidence": memory.confidence_score,
                        "reason": memory.detection_reason,
                        "content_preview": memory.content[:100]
                    })
                    print(f"🧠 [AUTO MEMORY] Stocké: {memory.detection_reason} "
                          f"(confiance: {memory.confidence_score:.2f})")
                    
            except Exception as e:
                print(f"⚠️ [AUTO MEMORY] Erreur stockage: {e}")
    
    if stored:
        print(f"✅ [AUTO MEMORY] {len(stored)} mémoire(s) stockée(s) automatiquement")
    
    return stored
