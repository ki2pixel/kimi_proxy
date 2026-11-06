"""
Stockage du contenu masqué par le sanitizer.
"""
import os
import hashlib
import base64
from typing import Optional, List, Dict, Any

from ...core.database import get_db


def decrypt_content(encrypted_b64: str, key_str: str) -> str:
    """Déchiffre un contenu historique stocké par l'ancien sanitizer."""
    payload = base64.b64decode(encrypted_b64.encode('utf-8'))
    salt = payload[:16]
    encrypted = payload[16:]
    
    key = hashlib.pbkdf2_hmac('sha256', key_str.encode('utf-8'), salt, 10000)
    
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(encrypted):
        block = hashlib.sha256(key + counter.to_bytes(4, 'big')).digest()
        keystream.extend(block)
        counter += 1
        
    decrypted = bytearray(b1 ^ b2 for b1, b2 in zip(encrypted, keystream))
    return decrypted.decode('utf-8')


def get_masked_content(content_hash: str) -> Optional[Dict[str, Any]]:
    """Récupère le contenu masqué depuis la DB."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM masked_content WHERE content_hash = ?",
            (content_hash,)
        )
        row = cursor.fetchone()
        if not row:
            return None
            
        row_dict = dict(row)
        encrypted_content = row_dict.get("original_content")
        
        if encrypted_content:
            secret_key = os.getenv("KIMI_SANITIZER_SECRET_KEY", "").strip()
            if secret_key:
                try:
                    row_dict["original_content"] = decrypt_content(encrypted_content, secret_key)
                except Exception as dec_err:
                    print(f"⚠️ Erreur déchiffrement: {dec_err}")
                    row_dict["original_content"] = "[Erreur de déchiffrement : clé invalide]"
            else:
                row_dict["original_content"] = "[Contenu chiffré - KIMI_SANITIZER_SECRET_KEY non fournie]"
        else:
            row_dict["original_content"] = "[Non stocké selon la politique de sécurité]"
            
        return row_dict


def list_masked_contents(limit: int = 50) -> List[Dict[str, Any]]:
    """Liste les contenus masqués récents."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT content_hash, preview, tags, token_count, created_at 
               FROM masked_content 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        
        return [{
            "hash": row[0],
            "preview": row[1][:200] if row[1] else "",
            "tags": row[2].split(",") if row[2] else [],
            "token_count": row[3],
            "created_at": row[4]
        } for row in rows]


def get_sanitizer_stats() -> Dict[str, Any]:
    """Récupère les statistiques du sanitizer."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM masked_content")
        total_masked = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(token_count) FROM masked_content")
        total_tokens_masked = cursor.fetchone()[0] or 0
        
        cursor.execute(
            """SELECT COUNT(*) FROM masked_content 
               WHERE created_at > datetime('now', '-1 day')"""
        )
        recent_masked = cursor.fetchone()[0]
        
        return {
            "total_masked": total_masked,
            "total_tokens_masked": total_tokens_masked,
            "recent_24h": recent_masked
        }
