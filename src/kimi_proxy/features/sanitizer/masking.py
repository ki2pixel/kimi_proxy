"""
Logique de masking pour le sanitizer.
"""
import hashlib
from typing import List, Tuple, Dict, Any, Optional

from ...core.tokens import count_tokens_text
from ...core.database import get_db
from .storage import save_masked_content, extract_tags_from_content


class ContentMasker:
    """Classe pour masquer les contenus verbeux."""
    
    def __init__(self, threshold_tokens: int = 1000, preview_length: int = 200, enabled: bool = True):
        self.threshold_tokens = threshold_tokens
        self.preview_length = preview_length
        self.enabled = enabled
        self.tags = ["@file", "@codebase", "@tool", "@console", "@output"]
    
    def should_mask(self, message: dict) -> Tuple[bool, str, int]:
        """
        Détermine si un message doit être masqué.
        
        Returns:
            Tuple (should_mask, reason, token_count)
        """
        if not self.enabled:
            return False, "", 0
        
        role = message.get("role", "")
        content = message.get("content", "")
        
        if not isinstance(content, str):
            return False, "", 0
        
        content_tokens = count_tokens_text(content)
        
        # Masque les messages tool/console trop longs
        if role in ["tool", "function"] and content_tokens > self.threshold_tokens:
            return True, "tool_output", content_tokens
        
        # Masque les contenus avec tags @file/@codebase trop longs
        if any(tag in content for tag in ["@file", "@codebase"]) and content_tokens > self.threshold_tokens:
            return True, "file_context", content_tokens
        
        # Masque les sorties console verbeuses
        if "@console" in content or "@output" in content or "stdout" in content[:100]:
            if content_tokens > self.threshold_tokens:
                return True, "console_output", content_tokens
        
        # Masque les gros JSON (heuristique)
        if content_tokens > self.threshold_tokens * 2:
            if content.strip().startswith('{') or content.strip().startswith('['):
                return True, "large_json", content_tokens
        
        return False, "", content_tokens
    
    def mask_message(self, message: dict, session_id: int = None) -> Tuple[dict, Optional[dict]]:
        """
        Masque un message si nécessaire.
        
        Returns:
            Tuple (message, metadata) où metadata est None si pas de masking
        """
        should_mask, reason, original_tokens = self.should_mask(message)
        
        if not should_mask:
            return message, None
        
        content = message.get("content", "")
        
        # Sauvegarde et remplace par un aperçu
        content_hash, preview, _ = save_masked_content(
            content=content,
            tags=extract_tags_from_content(content),
            config={
                "threshold_tokens": self.threshold_tokens,
                "preview_length": self.preview_length,
                "tmp_dir": "/tmp/kimi_proxy_masked"
            }
        )
        
        preview_tokens = count_tokens_text(preview)
        tokens_saved = original_tokens - preview_tokens
        tags_str = ",".join(extract_tags_from_content(content))
        
        # Crée le message remplacé avec référence au hash
        replacement_content = f"""[Contenu masqué - {reason}]
{preview}

[RÉFÉRENCE: {content_hash}]
[Tags: {tags_str}]
[Tokens économisés: ~{tokens_saved}]

Utilisez GET /api/mask/{content_hash} pour récupérer le contenu complet."""
        
        masked_message = {
            **message,
            "content": replacement_content,
            "_masked": True,
            "_original_hash": content_hash,
            "_mask_reason": reason,
            "_original_tokens": original_tokens
        }
        
        metadata = {
            "hash": content_hash,
            "reason": reason,
            "original_tokens": original_tokens,
            "preview_tokens": preview_tokens,
            "tokens_saved": tokens_saved
        }
        
        return masked_message, metadata
    
    def sanitize_messages(self, messages: List[dict], session_id: int = None) -> Tuple[List[dict], dict]:
        """
        Analyse et sanitize une liste de messages.
        
        Returns:
            Tuple (messages_sanitizés, métadonnées)
        """
        if not self.enabled:
            return messages, {"masked_count": 0, "tokens_saved": 0, "details": []}
        
        sanitized = []
        masked_count = 0
        tokens_saved = 0
        masking_details = []
        
        for idx, message in enumerate(messages):
            masked_message, metadata = self.mask_message(message, session_id)
            
            if metadata:
                masked_count += 1
                tokens_saved += metadata["tokens_saved"]
                masking_details.append({
                    "index": idx,
                    "role": message.get("role", ""),
                    **metadata
                })
            
            sanitized.append(masked_message)
        
        metadata_result = {
            "masked_count": masked_count,
            "tokens_saved": tokens_saved,
            "details": masking_details,
            "threshold_used": self.threshold_tokens
        }
        
        if masked_count > 0:
            print(f"🧹 [SANITIZER] {masked_count} message(s) masqué(s), ~{tokens_saved} tokens économisés")
        
        return sanitized, metadata_result


def create_preview(content: str, max_length: int = 200) -> str:
    """Crée un aperçu du contenu."""
    if len(content) <= max_length:
        return content
    
    preview = content[:max_length]
    last_newline = preview.rfind('\n')
    
    if last_newline > max_length * 0.7:
        preview = preview[:last_newline]
    
    return preview.strip() + "\n\n[... Contenu masqué - utilisez le hash pour récupérer la version complète ...]"


def sanitize_messages(
    messages: List[dict],
    session_id: int = None,
    config: dict = None
) -> Tuple[List[dict], dict]:
    """
    Fonction utilitaire pour sanitizer des messages.
    
    Args:
        messages: Liste de messages à sanitizer
        session_id: ID de la session (optionnel)
        config: Configuration du sanitizer (optionnel)
        
    Returns:
        Tuple (messages_sanitizés, métadonnées)
    """
    if config is None:
        config = {
            "enabled": True,
            "threshold_tokens": 1000,
            "preview_length": 200
        }
    
    masker = ContentMasker(
        threshold_tokens=config.get("threshold_tokens", 1000),
        preview_length=config.get("preview_length", 200),
        enabled=config.get("enabled", True)
    )
    
    return masker.sanitize_messages(messages, session_id)
