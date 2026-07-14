"""
Stockage du contenu masqué par le sanitizer.
"""
import os
import json
import hashlib
import base64
from datetime import datetime
from typing import Tuple, Optional, List, Dict, Any

from ...core.tokens import count_tokens_text
from ...core.database import get_db


def encrypt_content(content: str, key_str: str) -> str:
    """Chiffre le contenu avec une clé via SHA-256 CTR (keystream pure Python)."""
    data = content.encode('utf-8')
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', key_str.encode('utf-8'), salt, 10000)
    
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(data):
        block = hashlib.sha256(key + counter.to_bytes(4, 'big')).digest()
        keystream.extend(block)
        counter += 1
        
    encrypted = bytearray(b1 ^ b2 for b1, b2 in zip(data, keystream))
    payload = salt + encrypted
    return base64.b64encode(payload).decode('utf-8')


def decrypt_content(encrypted_b64: str, key_str: str) -> str:
    """Déchiffre le contenu chiffré par encrypt_content."""
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


def generate_content_hash(content: str) -> str:
    """Génère un hash unique pour le contenu."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def extract_tags_from_content(content: str) -> List[str]:
    """Extrait les tags XML (@file, @codebase, etc.) du contenu."""
    tags = ["@file", "@codebase", "@tool", "@console", "@output"]
    found_tags = []
    
    for tag in tags:
        if tag in content or f"<{tag}>" in content or f"[{tag}]" in content:
            found_tags.append(tag)
    
    # Détection heuristique de type de contenu
    if '"path"' in content or '"file"' in content:
        found_tags.append("@file")
    if 'stdout' in content or 'stderr' in content:
        found_tags.append("@console")
    if len(content) > 5000 and ('{' in content or '[' in content):
        found_tags.append("@json_large")
    
    return list(set(found_tags))


def create_preview(content: str, max_length: int = 200) -> str:
    """Crée un aperçu du contenu."""
    if len(content) <= max_length:
        return content
    
    preview = content[:max_length]
    last_newline = preview.rfind('\n')
    
    if last_newline > max_length * 0.7:
        preview = preview[:last_newline]
    
    return preview.strip() + "\n\n[... Contenu masqué - utilisez le hash pour récupérer la version complète ...]"


def save_masked_content(
    content: str,
    tags: Optional[List[str]] = None,
    config: Optional[dict] = None
) -> Tuple[str, str, int]:
    """
    Sauvegarde le contenu masqué sur disque et en DB.
    
    Args:
        content: Contenu à masquer
        tags: Tags associés (optionnel)
        config: Configuration (optionnel)
        
    Returns:
        Tuple (content_hash, preview, token_count)
    """
    from ...config.loader import get_config
    global_config = get_config()
    sanitizer_cfg = global_config.get("sanitizer", {})
    
    store_original = sanitizer_cfg.get("store_original_content", False)
    
    if config is None:
        config = {
            "threshold_tokens": sanitizer_cfg.get("threshold_tokens", 1000),
            "preview_length": sanitizer_cfg.get("preview_length", 200),
            "tmp_dir": sanitizer_cfg.get("tmp_dir", os.path.join(os.path.expanduser("~"), ".kimi", "tmp", "kimi_proxy_masked"))
        }
    
    content_hash = generate_content_hash(content)
    token_count = count_tokens_text(content)
    preview = create_preview(content, config.get("preview_length", 200))
    tags = tags or extract_tags_from_content(content)
    tags_str = ",".join(tags) if tags else ""
    
    stored_content = None
    if store_original:
        secret_key = os.getenv("KIMI_SANITIZER_SECRET_KEY", "").strip()
        if secret_key:
            stored_content = encrypt_content(content, secret_key)
        else:
            print("⚠️ WARNING: store_original_content is True but KIMI_SANITIZER_SECRET_KEY is empty. Skipping storage of original content.")
            stored_content = None
            
    file_path = ""
    if stored_content is not None:
        tmp_dir = config.get("tmp_dir", os.path.join(os.path.expanduser("~"), ".kimi", "tmp", "kimi_proxy_masked"))
        os.makedirs(tmp_dir, exist_ok=True)
        
        file_path = os.path.join(tmp_dir, f"{content_hash}.json")
        file_data = {
            "hash": content_hash,
            "tags": tags,
            "token_count": token_count,
            "preview": preview,
            "original_content": stored_content,
            "encrypted": True,
            "created_at": datetime.now().isoformat()
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde fichier masqué: {e}")
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO masked_content 
                (content_hash, original_content, preview, file_path, tags, token_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (content_hash, stored_content, preview, file_path, tags_str, token_count, datetime.now().isoformat()))
            conn.commit()
        except Exception as e:
            print(f"⚠️ Erreur DB masked_content: {e}")
    
    return content_hash, preview, token_count


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
