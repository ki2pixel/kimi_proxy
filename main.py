"""
Kimi Proxy Dashboard - Backend FastAPI
Proxy streaming + SQLite + WebSockets pour monitoring temps réel
Intégration Log Watcher pour PyCharm/Continue
"""

import uvicorn
import json
import sqlite3
import asyncio
import time
import os
import re
import aiofiles
import hashlib
from datetime import datetime
from collections import deque
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Set, Tuple

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx
import tiktoken

# ============================================================================
# TOKENIZATION PRÉCISE
# ============================================================================
ENCODING = tiktoken.get_encoding("cl100k_base")

def count_tokens_tiktoken(messages: list) -> int:
    """
    Compte précisément les tokens d'une liste de messages.
    Format compatible OpenAI/Kimi.
    """
    if not messages:
        return 0
    
    token_count = 0
    
    for message in messages:
        token_count += 3
        role = message.get("role", "")
        content = message.get("content", "")
        
        token_count += len(ENCODING.encode(role))
        
        if isinstance(content, str):
            token_count += len(ENCODING.encode(content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text = part.get("text", "")
                        token_count += len(ENCODING.encode(text))
                    elif part.get("type") == "image_url":
                        token_count += 512
    
    token_count += 3
    return token_count


def count_tokens_text(text: str) -> int:
    """Compte les tokens d'un texte simple."""
    if not text:
        return 0
    return len(ENCODING.encode(text))


# ============================================================================
# MCP MEMORY - DÉTECTION ET COMPTAGE MÉMOIRE LONG TERME (Phase 2)
# ============================================================================

# Patterns de détection des balises MCP et contenus mémoire
MCP_PATTERNS = {
    # Balises explicites de mémoire MCP
    'memory_tag': re.compile(r'<mcp-memory>.*?</mcp-memory>', re.DOTALL | re.IGNORECASE),
    'memory_ref': re.compile(r'@memory\[[^\]]+\]', re.IGNORECASE),
    'memory_block': re.compile(r'\[MEMORY\].*?\[/MEMORY\]', re.DOTALL | re.IGNORECASE),
    # Contenu MCP injecté par Continue (structure standard)
    'mcp_result': re.compile(r'<mcp-result[^>]*>.*?</mcp-result>', re.DOTALL | re.IGNORECASE),
    'mcp_tool': re.compile(r'<mcp-tool[^>]*>.*?</mcp-tool>', re.DOTALL | re.IGNORECASE),
    # Détection contexte mémoire
    'context_memory': re.compile(r'Contexte\s+précédent|Mémoire\s+de\s+la\s+session|Memory\s+from\s+previous', re.IGNORECASE),
    'recall_tag': re.compile(r'@recall\([^)]+\)', re.IGNORECASE),
    'remember_tag': re.compile(r'@remember\([^)]+\)', re.IGNORECASE),
}

# Seuil minimum pour considérer du contenu comme mémoire (vs simple instruction)
MCP_MIN_MEMORY_TOKENS = 50


def extract_mcp_memory_content(content: str) -> List[dict]:
    """
    Extrait le contenu MCP mémoire d'un message.
    
    Returns:
        Liste des segments mémoire détectés avec métadonnées
    """
    memory_segments = []
    
    if not content or not isinstance(content, str):
        return memory_segments
    
    for pattern_name, pattern in MCP_PATTERNS.items():
        matches = pattern.finditer(content)
        for match in matches:
            segment = match.group(0)
            token_count = count_tokens_text(segment)
            
            if token_count >= MCP_MIN_MEMORY_TOKENS:
                memory_segments.append({
                    'type': pattern_name,
                    'content': segment,
                    'tokens': token_count,
                    'position': (match.start(), match.end())
                })
    
    return memory_segments


def analyze_mcp_memory_in_messages(messages: List[dict]) -> dict:
    """
    Analyse une liste de messages pour détecter et compter les tokens mémoire MCP.
    
    Returns:
        {
            'memory_tokens': int,
            'chat_tokens': int,
            'memory_ratio': float,
            'segments': List[dict],
            'has_memory': bool
        }
    """
    total_tokens = 0
    memory_tokens = 0
    all_segments = []
    
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')
        
        if not isinstance(content, str):
            continue
        
        msg_tokens = count_tokens_text(content)
        total_tokens += msg_tokens
        
        # Extrait les segments mémoire
        segments = extract_mcp_memory_content(content)
        msg_memory_tokens = sum(s['tokens'] for s in segments)
        memory_tokens += msg_memory_tokens
        all_segments.extend(segments)
    
    chat_tokens = total_tokens - memory_tokens
    memory_ratio = (memory_tokens / total_tokens * 100) if total_tokens > 0 else 0
    
    return {
        'memory_tokens': memory_tokens,
        'chat_tokens': chat_tokens,
        'total_tokens': total_tokens,
        'memory_ratio': round(memory_ratio, 2),
        'segments': all_segments,
        'has_memory': memory_tokens > 0,
        'segment_count': len(all_segments)
    }


def save_memory_metrics(session_id: int, memory_tokens: int, chat_tokens: int, memory_ratio: float):
    """Sauvegarde les métriques mémoire pour une session."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO memory_metrics 
            (session_id, timestamp, memory_tokens, chat_tokens, memory_ratio)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), memory_tokens, chat_tokens, memory_ratio))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde mémoire metrics: {e}")
    finally:
        conn.close()


# ============================================================================
# PHASE 3: COMPRESSION DE DERNIER RECOURS (Last Resort Compression)
# ============================================================================

# Configuration de la compression
COMPRESSION_CONFIG = {
    "enabled": True,
    "threshold_percentage": 85,  # Seuil pour activer le bouton de compression
    "preserve_recent_exchanges": 5,  # Nombre d'échanges à préserver (user+assistant)
    "summary_max_tokens": 500,  # Taille max du résumé
}

async def summarize_with_llm(messages: List[dict], session: dict) -> str:
    """
    Génère un résumé des messages avec un appel LLM au provider actif.
    
    Args:
        messages: Liste des messages à résumer
        session: Session active pour déterminer le provider
    
    Returns:
        Texte résumé
    """
    if not messages:
        return "[Historique précédent réservé]"
    
    # Construit le prompt de résumé
    conversation_text = "\n\n".join([
        f"{msg.get('role', 'user').upper()}: {msg.get('content', '')[:500]}"
        for msg in messages
    ])
    
    summary_prompt = f"""Résume brièvement la conversation suivante en conservant les points clés, décisions importantes et contexte technique pertinent. Sois concis (max 300 mots):

{conversation_text}

RÉSUMÉ:"""

    # Prépare la requête au provider
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    provider = PROVIDERS.get(provider_key, {})
    provider_api_key = provider.get("api_key", "")
    provider_type = provider.get("type", "openai")
    target_url = get_target_url_for_session(session)
    
    if not provider_api_key:
        print(f"⚠️ [COMPRESSION] Pas de clé API pour {provider_key}, résumé basique")
        return f"[Résumé basique: {len(messages)} messages échangés précédemment]"
    
    # Construit le body pour le résumé
    summary_body = {
        "model": session.get("model", "gpt-3.5-turbo"),
        "messages": [
            {"role": "system", "content": "Tu es un assistant qui résume des conversations techniques de manière concise."},
            {"role": "user", "content": summary_prompt}
        ],
        "max_tokens": COMPRESSION_CONFIG["summary_max_tokens"],
        "temperature": 0.3
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            proxy_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider_api_key}"
            }
            
            # Mise à jour du Host header
            host_header = get_provider_host_header(target_url)
            if host_header:
                proxy_headers["Host"] = host_header
            
            response = await client.post(
                f"{target_url}/chat/completions",
                headers=proxy_headers,
                json=summary_body
            )
            
            if response.status_code == 200:
                data = response.json()
                summary = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if summary:
                    print(f"✅ [COMPRESSION] Résumé généré: {len(summary)} caractères")
                    return summary.strip()
            else:
                print(f"⚠️ [COMPRESSION] Erreur API résumé: {response.status_code}")
                
    except Exception as e:
        print(f"⚠️ [COMPRESSION] Exception résumé LLM: {e}")
    
    # Fallback si échec
    return f"[Résumé: {len(messages)} messages précédents sur {count_tokens_tiktoken(messages)} tokens]"


def compress_history_heuristic(messages: List[dict]) -> Tuple[List[dict], dict]:
    """
    Algorithme heuristique de compression:
    1. Préserve tous les messages système
    2. Garde les 5 derniers échanges (user + assistant)
    3. Résume le milieu avec LLM
    
    Args:
        messages: Liste complète des messages
    
    Returns:
        Tuple (messages compressés, métadonnées)
    """
    if not messages:
        return messages, {"compressed": False, "reason": "no_messages"}
    
    original_tokens = count_tokens_tiktoken(messages)
    
    # Sépare les messages par type
    system_messages = [m for m in messages if m.get("role") == "system"]
    non_system_messages = [m for m in messages if m.get("role") != "system"]
    
    if len(non_system_messages) <= COMPRESSION_CONFIG["preserve_recent_exchanges"] * 2:
        # Pas assez de messages pour justifier la compression
        return messages, {
            "compressed": False, 
            "reason": "insufficient_messages",
            "original_tokens": original_tokens
        }
    
    # Garde les N derniers échanges
    preserve_count = COMPRESSION_CONFIG["preserve_recent_exchanges"] * 2
    recent_messages = non_system_messages[-preserve_count:]
    messages_to_summarize = non_system_messages[:-preserve_count]
    
    metadata = {
        "compressed": True,
        "original_count": len(messages),
        "original_tokens": original_tokens,
        "system_count": len(system_messages),
        "preserved_recent_count": len(recent_messages),
        "summarized_count": len(messages_to_summarize),
        "messages_to_summarize": messages_to_summarize
    }
    
    return system_messages + recent_messages, metadata


async def compress_session_history(session_id: int) -> dict:
    """
    Compression complète de l'historique d'une session.
    
    Returns:
        Résultat de la compression avec ratio, tokens économisés, etc.
    """
    session = get_session_by_id(session_id)
    if not session:
        return {"error": "Session non trouvée", "session_id": session_id}
    
    # Récupère les métriques de la session pour reconstruire l'historique
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content_preview, prompt_tokens, completion_tokens, timestamp
        FROM metrics 
        WHERE session_id = ? 
        ORDER BY timestamp ASC
    """, (session_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"error": "Aucune métrique trouvée pour cette session", "session_id": session_id}
    
    # Reconstruit les messages à partir des métriques
    # Note: C'est une approximation, idéalement on stockerait l'historique complet
    messages = []
    for row in rows:
        preview = row[0] or ""
        if preview:
            messages.append({
                "role": "user",
                "content": preview
            })
    
    # Applique l'heuristique de compression
    compressed_messages, metadata = compress_history_heuristic(messages)
    
    if not metadata.get("compressed"):
        return {
            "compressed": False,
            "reason": metadata.get("reason"),
            "session_id": session_id,
            "original_tokens": metadata.get("original_tokens", 0)
        }
    
    # Génère le résumé pour les messages du milieu
    messages_to_summarize = metadata.get("messages_to_summarize", [])
    if messages_to_summarize:
        summary = await summarize_with_llm(messages_to_summarize, session)
        
        # Insère le résumé comme message assistant
        summary_message = {
            "role": "assistant",
            "content": f"[📋 RÉSUMÉ DE L'HISTORIQUE PRÉCÉDENT]\n\n{summary}\n\n[Fin du résumé - Conversation continue]"
        }
        
        # Structure finale: système + résumé + récents
        final_messages = []
        
        # Ajoute les messages système
        system_count = metadata.get("system_count", 0)
        if system_count > 0:
            final_messages.extend(compressed_messages[:system_count])
        
        # Ajoute le résumé
        final_messages.append(summary_message)
        
        # Ajoute les messages récents
        preserved_count = metadata.get("preserved_recent_count", 0)
        if preserved_count > 0:
            final_messages.extend(compressed_messages[-preserved_count:])
    else:
        final_messages = compressed_messages
    
    # Calcule les statistiques
    compressed_tokens = count_tokens_tiktoken(final_messages)
    original_tokens = metadata.get("original_tokens", 0)
    tokens_saved = original_tokens - compressed_tokens
    compression_ratio = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0
    
    # Sauvegarde dans le log de compression
    summary_preview = final_messages[metadata.get("system_count", 0)].get("content", "")[:200] if len(final_messages) > metadata.get("system_count", 0) else ""
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO compression_log 
            (session_id, timestamp, original_tokens, compressed_tokens, compression_ratio, summary_preview)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), original_tokens, compressed_tokens, 
              compression_ratio, summary_preview))
        conn.commit()
        log_id = cursor.lastrowid
    except Exception as e:
        print(f"⚠️ [COMPRESSION] Erreur sauvegarde log: {e}")
        log_id = None
    finally:
        conn.close()
    
    result = {
        "compressed": True,
        "session_id": session_id,
        "log_id": log_id,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "tokens_saved": tokens_saved,
        "compression_ratio": round(compression_ratio, 2),
        "messages_before": metadata.get("original_count", 0),
        "messages_after": len(final_messages),
        "system_preserved": metadata.get("system_count", 0),
        "recent_preserved": metadata.get("preserved_recent_count", 0),
        "summary": summary if messages_to_summarize else None
    }
    
    print(f"🗜️ [COMPRESSION] Session {session_id}: {original_tokens} → {compressed_tokens} tokens "
          f"({compression_ratio:.1f}% économisés)")
    
    return result


def get_compression_stats(session_id: int = None) -> dict:
    """Récupère les statistiques de compression."""
    conn = get_db()
    cursor = conn.cursor()
    
    if session_id:
        cursor.execute("""
            SELECT COUNT(*), SUM(original_tokens), SUM(compressed_tokens), AVG(compression_ratio)
            FROM compression_log 
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        stats = {
            "total_compressions": row[0] or 0,
            "total_original_tokens": row[1] or 0,
            "total_compressed_tokens": row[2] or 0,
            "avg_compression_ratio": round(row[3] or 0, 2)
        }
    else:
        cursor.execute("""
            SELECT COUNT(*), SUM(original_tokens), SUM(compressed_tokens), AVG(compression_ratio)
            FROM compression_log
        """)
        row = cursor.fetchone()
        stats = {
            "total_compressions": row[0] or 0,
            "total_original_tokens": row[1] or 0,
            "total_compressed_tokens": row[2] or 0,
            "avg_compression_ratio": round(row[3] or 0, 2)
        }
    
    conn.close()
    return stats


def get_session_memory_stats(session_id: int) -> dict:
    """Récupère les statistiques mémoire d'une session."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Dernière métrique mémoire
    cursor.execute("""
        SELECT memory_tokens, chat_tokens, memory_ratio 
        FROM memory_metrics 
        WHERE session_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    """, (session_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'memory_tokens': row[0] or 0,
            'chat_tokens': row[1] or 0,
            'memory_ratio': row[2] or 0
        }
    
    return {'memory_tokens': 0, 'chat_tokens': 0, 'memory_ratio': 0}


# ============================================================================
# SANITIZER - MASKING DE CONTENU VERBEUX (Phase 1)
# ============================================================================

# Configuration du masking (sera surchargée par config.toml)
MASKING_CONFIG = {
    "enabled": True,
    "threshold_tokens": 1000,  # Seuil pour masquer un message
    "preview_length": 200,     # Longueur de l'aperçu conservé
    "tmp_dir": "/tmp/kimi_proxy_masked",
    "tags": ["@file", "@codebase", "@tool", "@console", "@output"]
}

def generate_content_hash(content: str) -> str:
    """Génère un hash unique pour le contenu."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

def extract_tags_from_content(content: str) -> List[str]:
    """Extrait les tags XML (@file, @codebase, etc.) du contenu."""
    found_tags = []
    for tag in MASKING_CONFIG["tags"]:
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
    # Essaie de couper à la fin d'une ligne
    preview = content[:max_length]
    last_newline = preview.rfind('\n')
    if last_newline > max_length * 0.7:
        preview = preview[:last_newline]
    return preview.strip() + "\n\n[... Contenu masqué - utilisez le hash pour récupérer la version complète ...]"

def save_masked_content(content: str, tags: List[str] = None) -> Tuple[str, str, int]:
    """
    Sauvegarde le contenu masqué sur disque et en DB.
    
    Returns:
        Tuple (content_hash, preview, token_count)
    """
    content_hash = generate_content_hash(content)
    token_count = count_tokens_text(content)
    preview = create_preview(content, MASKING_CONFIG["preview_length"])
    tags = tags or extract_tags_from_content(content)
    tags_str = ",".join(tags) if tags else ""
    
    # Crée le répertoire temporaire si nécessaire
    tmp_dir = MASKING_CONFIG["tmp_dir"]
    os.makedirs(tmp_dir, exist_ok=True)
    
    # Sauvegarde sur disque
    file_path = os.path.join(tmp_dir, f"{content_hash}.json")
    file_data = {
        "hash": content_hash,
        "tags": tags,
        "token_count": token_count,
        "preview": preview,
        "original_content": content,
        "created_at": datetime.now().isoformat()
    }
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(file_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  Erreur sauvegarde fichier masqué: {e}")
    
    # Sauvegarde en DB
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO masked_content 
            (content_hash, original_content, preview, file_path, tags, token_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (content_hash, content, preview, file_path, tags_str, token_count, datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        print(f"⚠️  Erreur DB masked_content: {e}")
    finally:
        conn.close()
    
    return content_hash, preview, token_count

def get_masked_content(content_hash: str) -> Optional[dict]:
    """Récupère le contenu masqué depuis la DB."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM masked_content WHERE content_hash = ?",
        (content_hash,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def sanitize_messages(messages: List[dict], session_id: int = None) -> Tuple[List[dict], dict]:
    """
    Analyse et sanitize les messages pour réduire la consommation de tokens.
    
    Retourne:
        - Liste des messages sanitizés
        - Métadonnées du masking (nombre de messages masqués, tokens économisés, etc.)
    """
    if not MASKING_CONFIG["enabled"]:
        return messages, {"masked_count": 0, "tokens_saved": 0}
    
    sanitized = []
    masked_count = 0
    tokens_saved = 0
    masking_details = []
    
    for idx, message in enumerate(messages):
        role = message.get("role", "")
        content = message.get("content", "")
        
        # Détermine si ce message doit être masqué
        should_mask = False
        mask_reason = ""
        
        if isinstance(content, str):
            content_tokens = count_tokens_text(content)
            
            # Masque les messages tool/console trop longs
            if role in ["tool", "function"] and content_tokens > MASKING_CONFIG["threshold_tokens"]:
                should_mask = True
                mask_reason = "tool_output"
            
            # Masque les contenus avec tags @file/@codebase trop longs
            elif any(tag in content for tag in ["@file", "@codebase"]) and content_tokens > MASKING_CONFIG["threshold_tokens"]:
                should_mask = True
                mask_reason = "file_context"
            
            # Masque les sorties console verbeuses
            elif "@console" in content or "@output" in content or "stdout" in content[:100]:
                if content_tokens > MASKING_CONFIG["threshold_tokens"]:
                    should_mask = True
                    mask_reason = "console_output"
            
            # Masque les gros JSON (heuristique)
            elif content_tokens > MASKING_CONFIG["threshold_tokens"] * 2:
                if content.strip().startswith('{') or content.strip().startswith('['):
                    should_mask = True
                    mask_reason = "large_json"
        
        if should_mask and isinstance(content, str):
            # Sauvegarde et remplace par un aperçu
            content_hash, preview, original_tokens = save_masked_content(content)
            tokens_saved += (original_tokens - count_tokens_text(preview))
            masked_count += 1
            
            # Crée le message remplacé avec référence au hash
            tags_str = ",".join(extract_tags_from_content(content))
            replacement_content = f"""[Contenu masqué - {mask_reason}]
{preview}

[RÉFÉRENCE: {content_hash}]
[Tags: {tags_str}]
[Tokens économisés: ~{original_tokens - count_tokens_text(preview)}]

Utilisez GET /api/mask/{content_hash} pour récupérer le contenu complet."""
            
            sanitized.append({
                **message,
                "content": replacement_content,
                "_masked": True,
                "_original_hash": content_hash,
                "_mask_reason": mask_reason,
                "_original_tokens": original_tokens
            })
            
            masking_details.append({
                "index": idx,
                "role": role,
                "reason": mask_reason,
                "hash": content_hash,
                "tokens_original": original_tokens,
                "tokens_preview": count_tokens_text(preview)
            })
        else:
            sanitized.append(message)
    
    metadata = {
        "masked_count": masked_count,
        "tokens_saved": tokens_saved,
        "details": masking_details,
        "threshold_used": MASKING_CONFIG["threshold_tokens"]
    }
    
    if masked_count > 0:
        print(f"🧹 [SANITIZER] {masked_count} message(s) masqué(s), ~{tokens_saved} tokens économisés")
    
    return sanitized, metadata


# ============================================================================
# ROUTING DYNAMIQUE - CONTEXT WINDOW FALLBACK (Phase 1)
# ============================================================================

# Seuil pour le fallback (90% du contexte max)
CONTEXT_FALLBACK_THRESHOLD = 0.90

def find_heavy_duty_model(provider_key: str, current_model: str, required_context: int) -> Optional[str]:
    """
    Trouve un modèle "Heavy Duty" (plus grand contexte) dans le même provider.
    
    Args:
        provider_key: Clé du provider
        current_model: Modèle actuel
        required_context: Contexte minimum requis
    
    Returns:
        Clé du modèle fallback ou None si aucun trouvé
    """
    current_model_data = MODELS.get(current_model, {})
    current_context = current_model_data.get("max_context_size", DEFAULT_MAX_CONTEXT)
    
    # Cherche les modèles du même provider avec plus de contexte
    candidates = []
    for model_key, model_data in MODELS.items():
        if model_data.get("provider") == provider_key:
            model_context = model_data.get("max_context_size", DEFAULT_MAX_CONTEXT)
            if model_context > current_context and model_context >= required_context:
                candidates.append((model_key, model_context))
    
    if not candidates:
        return None
    
    # Trie par contexte croissant pour prendre le plus petit suffisant
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]

async def route_dynamic_model(session: dict, prompt_tokens: int) -> Tuple[dict, Optional[dict]]:
    """
    Route dynamiquement vers un modèle plus grand si nécessaire.
    
    Args:
        session: Session active
        prompt_tokens: Nombre de tokens dans le prompt
    
    Returns:
        Tuple (session_mise_à_jour, notification_webSocket)
    """
    if not session:
        return session, None
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    current_model = session.get("model")
    max_context = get_max_context_for_session(session)
    
    # Vérifie si on dépasse le seuil de fallback
    usage_ratio = prompt_tokens / max_context if max_context > 0 else 0
    
    if usage_ratio < CONTEXT_FALLBACK_THRESHOLD:
        return session, None
    
    # Cherche un modèle plus grand
    fallback_model = find_heavy_duty_model(provider_key, current_model, prompt_tokens)
    
    if not fallback_model:
        # Aucun modèle plus grand disponible
        notification = {
            "type": "context_warning",
            "level": "critical",
            "message": f"⚠️ Contexte critique ({usage_ratio*100:.1f}%) - Aucun modèle plus grand disponible",
            "current_model": current_model,
            "prompt_tokens": prompt_tokens,
            "max_context": max_context
        }
        return session, notification
    
    # Effectue le fallback
    old_model = current_model
    session["model"] = fallback_model
    new_max_context = MODELS.get(fallback_model, {}).get("max_context_size", DEFAULT_MAX_CONTEXT)
    
    # Met à jour en DB
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE sessions SET model = ? WHERE id = ?",
            (fallback_model, session["id"])
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️  Erreur mise à jour modèle session: {e}")
    finally:
        conn.close()
    
    print(f"🔄 [ROUTING] Fallback: {old_model} → {fallback_model} "
          f"({max_context/1024:.0f}K → {new_max_context/1024:.0f}K contexte)")
    
    notification = {
        "type": "model_fallback",
        "level": "warning",
        "message": f"Basculement automatique vers {get_model_display_name(fallback_model)}",
        "old_model": old_model,
        "new_model": fallback_model,
        "old_context": max_context,
        "new_context": new_max_context,
        "prompt_tokens": prompt_tokens,
        "reason": f"Contexte dépassé ({usage_ratio*100:.1f}%)"
    }
    
    return session, notification

def get_session_total_tokens(session_id: int) -> dict:
    """Calcule le total cumulé des tokens pour une session.
    
    Logique:
    - Input: Somme des prompt_tokens (réels) sinon estimated_tokens
    - Output: Somme des completion_tokens (réels)
    - Total: Input + Output (pourcentage calculé sur input seul pour le contexte)
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupère toutes les métriques de la session
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
    conn.close()
    
    total_input = 0
    total_output = 0
    
    for row in rows:
        estimated = row[0] or 0
        prompt = row[1] or 0
        completion = row[2] or 0
        is_estimated = row[3]
        
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

# ============================================================================
# CHARGEMENT DE LA CONFIGURATION
# ============================================================================
def load_config():
    """Charge la configuration depuis config.toml"""
    config_path = os.path.join(os.path.dirname(__file__), "config.toml")
    if not os.path.exists(config_path):
        return {}
    
    try:
        import tomllib
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        try:
            import tomli
            with open(config_path, "rb") as f:
                return tomli.load(f)
        except ImportError:
            print("⚠️  tomllib/tomli non disponible, utilisation config par défaut")
            return {}

CONFIG = load_config()

# Charge la configuration du sanitizer depuis config.toml
_sanitizer_config = CONFIG.get("sanitizer", {})
MASKING_CONFIG["enabled"] = _sanitizer_config.get("enabled", True)
MASKING_CONFIG["threshold_tokens"] = _sanitizer_config.get("threshold_tokens", 1000)
MASKING_CONFIG["preview_length"] = _sanitizer_config.get("preview_length", 200)
MASKING_CONFIG["tmp_dir"] = _sanitizer_config.get("tmp_dir", "/tmp/kimi_proxy_masked")

# ============================================================================
# CONFIGURATION DES PROVIDERS
# ============================================================================
DEFAULT_MAX_CONTEXT = 262144
DATABASE_FILE = "sessions.db"

PROVIDERS = {}
MODELS = {}

def init_providers():
    """Initialise les providers depuis la config"""
    global PROVIDERS, MODELS
    
    providers_config = CONFIG.get("providers", {})
    models_config = CONFIG.get("models", {})
    
    for provider_key, provider_data in providers_config.items():
        PROVIDERS[provider_key] = {
            "key": provider_key,
            "type": provider_data.get("type", "openai"),
            "base_url": provider_data.get("base_url", ""),
            "api_key": provider_data.get("api_key", "")
        }
    
    for model_key, model_data in models_config.items():
        provider = model_data.get("provider", "nvidia")
        MODELS[model_key] = {
            "key": model_key,
            "model": model_data.get("model", model_key),
            "provider": provider,
            "max_context_size": model_data.get("max_context_size", DEFAULT_MAX_CONTEXT),
            "capabilities": model_data.get("capabilities", [])
        }
    
    print(f"✅ {len(PROVIDERS)} provider(s) chargé(s)")
    print(f"✅ {len(MODELS)} modèle(s) chargé(s)")
    
    # Affiche les providers et modèles pour debug
    for key in PROVIDERS:
        models = [m["key"] for m in MODELS.values() if m["provider"] == key]
        print(f"   📦 {key}: {len(models)} modèle(s)")

init_providers()

DEFAULT_PROVIDER = "managed:kimi-code"

# Rate Limiting par provider
RATE_LIMITS = {
    "nvidia": 40,
    "mistral": 60,
    "openrouter": 30,
    "siliconflow": 100,
    "groq": 100,
    "cerebras": 100,
    "gemini": 60,
    "managed:kimi-code": 40
}

MAX_RPM = 40  # Default
RATE_LIMIT_WARNING_THRESHOLD = 0.875
RATE_LIMIT_CRITICAL_THRESHOLD = 0.95

# ============================================================================
# LOG WATCHER - SURVEILLANCE DES LOGS CONTINUE (PYCHARM)
# ============================================================================
class LogWatcher:
    """
    Surveille en temps réel le fichier core.log de Continue
    pour extraire les métriques de tokens avec parsing avancé.
    
    Supporte:
    - Symboles ~ (tilde) pour les estimations
    - Bloc de diagnostic "CompileChat" (contextLength, tools, system message)
    - Erreurs API (429/quota)
    - Mise à jour dynamique du contexte max
    """
    
    def __init__(self):
        self.log_path = os.path.expanduser("~/.continue/logs/core.log")
        self.running = False
        self.last_position = 0
        self.task = None
        
        # Contexte max dynamique (peut être mis à jour par les logs)
        self.dynamic_max_context = None
        
        # Accumulateur pour le bloc CompileChat multi-lignes
        self._compile_chat_buffer = []
        self._in_compile_chat_block = False
        
        # Regex pour capturer les métriques de tokens (avec support du tilde ~)
        self.token_patterns = [
            # Pattern: "prompt tokens: 1234, completion tokens: 567" (avec ~ optionnel)
            re.compile(r'prompt\s*tokens?[\s:]+~?(\d+)', re.IGNORECASE),
            re.compile(r'completion\s*tokens?[\s:]+~?(\d+)', re.IGNORECASE),
            # Pattern: "tokens: 1234" ou "token count: 1234" (avec ~ optionnel)
            re.compile(r'(?:total\s+)?tokens?[\s:]+~?(\d+)', re.IGNORECASE),
            # Pattern: contextLength: 262144 ou context_length: 262144
            re.compile(r'context[_\s]?[Ll]ength[\s:]+(\d+)', re.IGNORECASE),
            # Pattern JSON-like: "prompt_tokens":1234
            re.compile(r'"prompt_tokens"\s*:\s*(\d+)', re.IGNORECASE),
            re.compile(r'"completion_tokens"\s*:\s*(\d+)', re.IGNORECASE),
            re.compile(r'"total_tokens"\s*:\s*(\d+)', re.IGNORECASE),
        ]
        
        # Patterns spécifiques au bloc CompileChat de Continue
        self.compile_chat_patterns = {
            'context_length': re.compile(r'context[Ll]ength[\s:]+(\d+)', re.IGNORECASE),
            'tools': re.compile(r'tools?[\s:]+~?(\d+)', re.IGNORECASE),
            'system_message': re.compile(r'system\s+message[\s:]+~?(\d+)', re.IGNORECASE),
        }
        
        # Patterns pour les erreurs API (429/quota)
        self.api_error_patterns = [
            # Pattern: input_token_count, limit: 12345
            re.compile(r'input_token_count,\s+limit:\s*(\d+)', re.IGNORECASE),
            # Pattern: "limit": 12345 dans JSON d'erreur
            re.compile(r'"limit"\s*:\s*(\d+)', re.IGNORECASE),
            # Pattern: rate limit exceeded, current: 12345
            re.compile(r'rate\s+limit.*current[:\s]+(\d+)', re.IGNORECASE),
        ]
        
        # Pattern pour détecter le début/fin du bloc CompileChat
        self.compile_chat_start = re.compile(r'Request\s+had\s+the\s+following\s+token\s+counts', re.IGNORECASE)
        self.compile_chat_end = re.compile(r'^[\s]*$', re.IGNORECASE)  # Ligne vide = fin du bloc
        
        # Pattern pour détecter les lignes pertinentes
        self.relevant_keywords = [
            'token', 'context', 'prompt', 'completion', 
            'usage', 'metrics', 'llm', 'request', 'system message',
            'tools', 'compile', 'limit', 'rate', 'quota', 'error'
        ]
    
    def _is_relevant_line(self, line: str) -> bool:
        """Vérifie si une ligne contient des métriques de tokens."""
        line_lower = line.lower()
        return any(kw in line_lower for kw in self.relevant_keywords)
    
    def _extract_token_metrics(self, line: str) -> Optional[dict]:
        """
        Extrait les métriques de tokens d'une ligne de log.
        Supporte les formats spécifiques de Continue.
        """
        # Détection du bloc CompileChat multi-lignes
        if self.compile_chat_start.search(line):
            self._in_compile_chat_block = True
            self._compile_chat_buffer = [line]
            return None  # Attend la fin du bloc
        
        if self._in_compile_chat_block:
            self._compile_chat_buffer.append(line)
            
            # Fin du bloc si ligne vide ou nouvelle section
            if line.strip() == '' or not line.startswith('-') and not line.startswith(' '):
                self._in_compile_chat_block = False
                return self._parse_compile_chat_block()
            
            # Continue d'accumuler
            if len(self._compile_chat_buffer) < 10:  # Limite de sécurité
                return None
            else:
                self._in_compile_chat_block = False
                return self._parse_compile_chat_block()
        
        if not self._is_relevant_line(line):
            return None
        
        metrics = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "context_length": 0,
            "tools_tokens": 0,
            "system_message_tokens": 0,
            "source": "logs",
            "raw_line": line[:200],
            "is_compile_chat": False,
            "is_api_error": False
        }
        
        found = False
        
        # === 1. Extraction des patterns standards (avec support ~) ===
        for pattern in self.token_patterns:
            matches = pattern.findall(line)
            for match in matches:
                try:
                    value = int(match)
                    pattern_str = pattern.pattern.lower()
                    
                    if 'prompt' in pattern_str:
                        metrics["prompt_tokens"] = value
                        found = True
                    elif 'completion' in pattern_str:
                        metrics["completion_tokens"] = value
                        found = True
                    elif 'context' in pattern_str:
                        metrics["context_length"] = value
                        # Mise à jour dynamique du contexte max
                        self.dynamic_max_context = value
                        found = True
                    elif 'total' in pattern_str or pattern_str.startswith(r'"total_tokens"'):
                        metrics["total_tokens"] = value
                        found = True
                    else:
                        if metrics["total_tokens"] == 0:
                            metrics["total_tokens"] = value
                            found = True
                except (ValueError, IndexError):
                    continue
        
        # === 2. Extraction des erreurs API (429/quota) ===
        for pattern in self.api_error_patterns:
            match = pattern.search(line)
            if match:
                try:
                    value = int(match.group(1))
                    metrics["total_tokens"] = value
                    metrics["is_api_error"] = True
                    found = True
                except (ValueError, IndexError):
                    continue
        
        # === 3. Extraction des patterns CompileChat individuels ===
        for key, pattern in self.compile_chat_patterns.items():
            match = pattern.search(line)
            if match:
                try:
                    value = int(match.group(1))
                    if key == 'tools':
                        metrics["tools_tokens"] = value
                    elif key == 'system_message':
                        metrics["system_message_tokens"] = value
                    elif key == 'context_length':
                        metrics["context_length"] = value
                        self.dynamic_max_context = value
                    found = True
                except (ValueError, IndexError):
                    continue
        
        # === 4. Calcul du total si on a des composants séparés ===
        components = [
            metrics["prompt_tokens"],
            metrics["completion_tokens"],
            metrics["tools_tokens"],
            metrics["system_message_tokens"]
        ]
        
        if any(components):
            calculated_total = sum(c for c in components if c > 0)
            if calculated_total > 0:
                # Si on a déjà un total détecté, prend le plus grand
                if metrics["total_tokens"] > 0:
                    metrics["total_tokens"] = max(metrics["total_tokens"], calculated_total)
                else:
                    metrics["total_tokens"] = calculated_total
                found = True
        
        return metrics if found else None
    
    def _parse_compile_chat_block(self) -> Optional[dict]:
        """
        Parse le bloc CompileChat accumulé et retourne les métriques complètes.
        """
        if not self._compile_chat_buffer:
            return None
        
        block_text = '\n'.join(self._compile_chat_buffer)
        
        metrics = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "context_length": 0,
            "tools_tokens": 0,
            "system_message_tokens": 0,
            "source": "logs",
            "raw_line": block_text[:300],
            "is_compile_chat": True,
            "is_api_error": False
        }
        
        found = False
        
        # Parse chaque ligne du bloc
        for line in self._compile_chat_buffer:
            for key, pattern in self.compile_chat_patterns.items():
                match = pattern.search(line)
                if match:
                    try:
                        value = int(match.group(1))
                        if key == 'tools':
                            metrics["tools_tokens"] = value
                        elif key == 'system_message':
                            metrics["system_message_tokens"] = value
                        elif key == 'context_length':
                            metrics["context_length"] = value
                            self.dynamic_max_context = value
                        found = True
                    except (ValueError, IndexError):
                        continue
        
        # Calcule le total à partir des composants
        if found:
            total = (metrics["tools_tokens"] + 
                    metrics["system_message_tokens"] +
                    metrics["prompt_tokens"])
            
            # Si context_length est présent, c'est notre référence max
            if metrics["context_length"] > 0:
                # Le total ne devrait pas dépasser context_length
                metrics["total_tokens"] = min(total, metrics["context_length"])
            else:
                metrics["total_tokens"] = total
        
        self._compile_chat_buffer = []
        return metrics if found else None
    
    def get_max_context(self, default_context: int = DEFAULT_MAX_CONTEXT) -> int:
        """
        Retourne le contexte max à utiliser.
        Priorité: contexte dynamique des logs > contexte de session > défaut
        """
        if self.dynamic_max_context and self.dynamic_max_context > 0:
            return self.dynamic_max_context
        return default_context
    
    async def start(self):
        """Démarre la surveillance des logs."""
        if not os.path.exists(self.log_path):
            print(f"⚠️  Fichier log non trouvé: {self.log_path}")
            print("   Le Log Watcher démarrera automatiquement quand le fichier sera créé.")
        
        self.running = True
        self.task = asyncio.create_task(self._watch_loop())
        print(f"📁 Log Watcher démarré (surveillance: ~/.continue/logs/core.log)")
        print(f"   Patterns actifs: CompileChat, API errors, Token metrics")
    
    async def stop(self):
        """Arrête la surveillance."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        print("📁 Log Watcher arrêté")
    
    async def _watch_loop(self):
        """Boucle principale de surveillance."""
        while self.running and not os.path.exists(self.log_path):
            await asyncio.sleep(5)
        
        if not self.running:
            return
        
        try:
            async with aiofiles.open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                await f.seek(0, 2)
                self.last_position = await f.tell()
        except Exception as e:
            print(f"⚠️  Erreur initialisation log watcher: {e}")
            return
        
        print(f"   Position initiale: {self.last_position} bytes")
        
        while self.running:
            try:
                await self._check_for_updates()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️  Erreur log watcher: {e}")
                await asyncio.sleep(2)
    
    async def _check_for_updates(self):
        """Vérifie les nouvelles lignes dans le fichier log."""
        try:
            current_size = os.path.getsize(self.log_path)
            
            if current_size < self.last_position:
                self.last_position = 0
            
            if current_size == self.last_position:
                return
            
            async with aiofiles.open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                await f.seek(self.last_position)
                new_content = await f.read()
                self.last_position = await f.tell()
            
            if new_content:
                lines = new_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        metrics = self._extract_token_metrics(line)
                        if metrics:
                            await self._broadcast_metrics(metrics)
                            
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"⚠️  Erreur lecture log: {e}")
    
    async def _broadcast_metrics(self, metrics: dict):
        """Diffuse les métriques extraites via WebSocket."""
        global manager
        
        session = get_active_session()
        if not session:
            return
        
        # Utilise le contexte max dynamique si disponible
        max_context = self.get_max_context(get_max_context_for_session(session))
        total_tokens = metrics.get("total_tokens", 0)
        percentage = (total_tokens / max_context) * 100 if max_context > 0 else 0
        
        # Détermine le type de source pour l'affichage
        source_type = "logs"
        if metrics.get("is_compile_chat"):
            source_type = "compile_chat"
        elif metrics.get("is_api_error"):
            source_type = "api_error"
        
        message = {
            "type": "log_metric",
            "source": source_type,
            "metrics": {
                "prompt_tokens": metrics.get("prompt_tokens", 0),
                "completion_tokens": metrics.get("completion_tokens", 0),
                "tools_tokens": metrics.get("tools_tokens", 0),
                "system_message_tokens": metrics.get("system_message_tokens", 0),
                "total_tokens": total_tokens,
                "context_length": metrics.get("context_length", max_context),
                "max_context": max_context,
                "percentage": percentage
            },
            "session_id": session["id"],
            "timestamp": datetime.now().isoformat()
        }
        
        await manager.broadcast(message)
        
        # Log détaillé selon le type
        if metrics.get("is_compile_chat"):
            print(f"📊 [COMPILE] Context: {metrics.get('context_length', 0)}, "
                  f"Tools: {metrics.get('tools_tokens', 0)}, "
                  f"System: {metrics.get('system_message_tokens', 0)} "
                  f"= {total_tokens} ({percentage:.1f}%)")
        elif metrics.get("is_api_error"):
            print(f"⚠️  [API ERROR] Tokens: {total_tokens} (limite atteinte)")
        elif total_tokens > 100:
            print(f"📊 [LOGS] Tokens: {total_tokens} ({percentage:.1f}%)")

# Instance globale du Log Watcher
log_watcher = LogWatcher()

# ============================================================================
# RATE LIMITER
# ============================================================================
class RateLimiter:
    def __init__(self, max_rpm: int = 40):
        self.max_rpm = max_rpm
        self.warning_threshold = int(max_rpm * RATE_LIMIT_WARNING_THRESHOLD)
        self.critical_threshold = int(max_rpm * RATE_LIMIT_CRITICAL_THRESHOLD)
        self.requests: deque = deque()
        self.lock = asyncio.Lock()
        self.total_throttled = 0
        
    def _clean_old_requests(self):
        now = time.time()
        cutoff = now - 60
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    def get_current_rpm(self) -> float:
        self._clean_old_requests()
        return len(self.requests)
    
    def get_rpm_percentage(self) -> float:
        return (self.get_current_rpm() / self.max_rpm) * 100
    
    async def acquire(self, wait_if_needed: bool = True) -> dict:
        async with self.lock:
            self._clean_old_requests()
            current_rpm = len(self.requests)
            
            status = {
                "allowed": True,
                "current_rpm": current_rpm,
                "max_rpm": self.max_rpm,
                "percentage": (current_rpm / self.max_rpm) * 100,
                "throttled": False,
                "wait_time": 0
            }
            
            if current_rpm >= self.critical_threshold:
                if wait_if_needed:
                    oldest_request = self.requests[0]
                    wait_time = 60 - (time.time() - oldest_request) + 0.1
                    status["wait_time"] = max(0.1, wait_time)
                    status["throttled"] = True
                    self.total_throttled += 1
                else:
                    status["allowed"] = False
                    return status
            
            self.requests.append(time.time())
            return status
    
    async def throttle_if_needed(self) -> dict:
        status = await self.acquire(wait_if_needed=True)
        
        if status["throttled"] and status["wait_time"] > 0:
            print(f"⏱️  Rate limit critique ({status['current_rpm']:.0f} RPM) - Attente {status['wait_time']:.1f}s...")
            await asyncio.sleep(status["wait_time"])
            async with self.lock:
                self._clean_old_requests()
                self.requests.append(time.time())
                status["current_rpm"] = len(self.requests)
                status["throttled"] = False
        
        return status
    
    def check_alert(self) -> Optional[str]:
        rpm = self.get_current_rpm()
        percentage = self.get_rpm_percentage()
        
        if rpm >= self.critical_threshold:
            return f"🚨 RATE LIMIT CRITIQUE: {rpm:.0f}/{self.max_rpm} RPM ({percentage:.1f}%)"
        elif rpm >= self.warning_threshold:
            return f"⚠️  Rate limit élevé: {rpm:.0f}/{self.max_rpm} RPM ({percentage:.1f}%)"
        return None

rate_limiter = RateLimiter(max_rpm=MAX_RPM)

# ============================================================================
# GESTION WEBSOCKET
# ============================================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        for conn in disconnected:
            self.active_connections.discard(conn)

manager = ConnectionManager()

# ============================================================================
# BASE DE DONNÉES
# ============================================================================
def init_database():
    """Initialise la base de données SQLite"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            base_url TEXT NOT NULL,
            api_key TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider TEXT DEFAULT 'nvidia',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 0
        )
    """)
    
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
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    
    # Table pour le contenu masqué (Sanitizer Phase 1)
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
    
    # Table pour les métriques mémoire MCP (Phase 2)
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
    
    # Table pour tracker les segments mémoire individuels
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
    
    # Migration: ajoute la colonne source si elle n'existe pas
    try:
        cursor.execute("ALTER TABLE metrics ADD COLUMN source TEXT DEFAULT 'proxy'")
        conn.commit()
        print("   Migration: colonne 'source' ajoutée à metrics")
    except sqlite3.OperationalError:
        pass  # Colonne existe déjà
    
    # Migration: ajoute la colonne model dans sessions si elle n'existe pas
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN model TEXT")
        conn.commit()
        print("   Migration: colonne 'model' ajoutée à sessions")
    except sqlite3.OperationalError:
        pass  # Colonne existe déjà
    
    # Migration: ajoute les colonnes tags et token_count dans masked_content si elles n'existent pas
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
    
    # Table pour le log de compression (Phase 3)
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
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_active_session() -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_session(name: str, provider: str = "nvidia", model: str = None) -> dict:
    """Crée une nouvelle session avec provider et modèle optionnel."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE sessions SET is_active = 0")
    
    # Si un modèle est fourni, stocke-le aussi
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
    row = cursor.fetchone()
    conn.close()
    
    return dict(row)

def save_metric(session_id: int, tokens: int, percentage: float, preview: str, 
                is_estimated: bool = True, source: str = 'proxy',
                memory_tokens: int = 0, chat_tokens: int = 0, memory_ratio: float = 0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO metrics (session_id, estimated_tokens, percentage, content_preview, is_estimated, source,
                                memory_tokens, chat_tokens, memory_ratio)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, tokens, percentage, preview[:200], is_estimated, source,
         memory_tokens, chat_tokens, memory_ratio)
    )
    conn.commit()
    metric_id = cursor.lastrowid
    conn.close()
    return metric_id

def update_metric_with_real_tokens(metric_id: int, prompt_tokens: int, completion_tokens: int, 
                                   total_tokens: int, max_context: int = DEFAULT_MAX_CONTEXT):
    conn = get_db()
    cursor = conn.cursor()
    percentage = (total_tokens / max_context) * 100
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
    conn.close()
    return {"total": total_tokens, "prompt": prompt_tokens, "completion": completion_tokens, "percentage": percentage}

def is_system_message(content: str) -> bool:
    is_sys = "You are Kimi Code CLI" in content or "interactive general AI agent" in content
    return is_sys

def update_session_first_prompt(session_id: int, prompt: str):
    conn = get_db()
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
    
    conn.close()

def get_session_stats(session_id: int) -> dict:
    conn = get_db()
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
    
    totals = get_session_total_tokens(session_id)
    stats["cumulative_input_tokens"] = totals["input_tokens"]
    stats["cumulative_output_tokens"] = totals["output_tokens"]
    stats["cumulative_total_tokens"] = totals["total_tokens"]
    
    cursor.execute(
        """SELECT * FROM metrics 
           WHERE session_id = ? 
           ORDER BY timestamp DESC LIMIT 50""",
        (session_id,)
    )
    recent_metrics = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "stats": stats,
        "recent_metrics": recent_metrics
    }

def get_all_sessions() -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sessions

# ============================================================================
# LIFESPAN - Démarrage/Arrêt
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    init_database()
    
    if not get_active_session():
        provider_key = "managed:kimi-code"
        create_session("Session par défaut", provider_key)
        print(f"✅ Session par défaut créée (provider: {provider_key})")
    
    # Démarre le Log Watcher
    await log_watcher.start()
    
    print("🚀 Serveur démarré - Dashboard disponible sur http://localhost:8000")
    yield
    
    # Shutdown
    await log_watcher.stop()
    print("👋 Serveur arrêté")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(title="Kimi Proxy Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# FICHIERS STATIQUES
# ============================================================================
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ============================================================================
# ROUTES FRONTEND
# ============================================================================
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    html_file = os.path.join(static_dir, "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>Dashboard non trouvé</h1>", status_code=404)

# ============================================================================
# API - SESSIONS & PROVIDERS
# ============================================================================
@app.post("/api/sessions")
async def api_create_session(request: Request):
    data = await request.json()
    name = data.get("name", f"Session {datetime.now().strftime('%H:%M:%S')}")
    provider = data.get("provider", DEFAULT_PROVIDER)
    model = data.get("model")  # Modèle spécifique optionnel
    
    session = create_session(name, provider, model)
    
    # Ajoute max_context à la réponse
    max_context = get_max_context_for_session(session)
    session_with_context = dict(session)
    session_with_context["max_context"] = max_context
    
    await manager.broadcast({
        "type": "new_session",
        "session": session_with_context
    })
    
    return session_with_context

@app.get("/api/sessions")
async def api_get_sessions():
    return get_all_sessions()

@app.get("/api/sessions/active")
async def api_get_active_session():
    session = get_active_session()
    if not session:
        return {"error": "Aucune session active"}
    
    stats = get_session_stats(session["id"])
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    provider_info = PROVIDERS.get(provider_key, {})
    max_context = get_max_context_for_session(session)
    
    # Récupère les stats mémoire MCP (Phase 2)
    memory_stats = get_session_memory_stats(session["id"])
    
    # Ajoute max_context à la session pour le frontend
    session_with_context = dict(session)
    session_with_context["max_context"] = max_context
    
    return {
        "session": session_with_context,
        "provider": {
            "key": provider_key,
            "name": get_provider_display_name(provider_key),
            "info": provider_info,
            "color": get_provider_color(provider_key),
            "icon": get_provider_icon(provider_key)
        },
        "memory": memory_stats,
        **stats
    }

@app.get("/api/providers")
async def api_get_providers():
    """Retourne tous les providers avec leurs modèles groupés"""
    result = []
    for key, provider in PROVIDERS.items():
        safe_provider = {
            "key": key,
            "type": provider.get("type", "openai"),
            "name": get_provider_display_name(key),
            "has_api_key": bool(provider.get("api_key")),
            "icon": get_provider_icon(key),
            "color": get_provider_color(key),
            "models": []
        }
        for model_key, model in MODELS.items():
            if model.get("provider") == key:
                safe_provider["models"].append({
                    "key": model_key,
                    "model": model.get("model"),
                    "name": get_model_display_name(model_key),
                    "max_context_size": model.get("max_context_size", DEFAULT_MAX_CONTEXT),
                    "capabilities": model.get("capabilities", [])
                })
        # Trie les modèles par nom
        safe_provider["models"].sort(key=lambda x: x["name"])
        result.append(safe_provider)
    
    # Trie les providers: Kimi d'abord, puis alphabétique
    result.sort(key=lambda x: (0 if "kimi" in x["key"] else 1, x["name"]))
    return result


@app.get("/api/models")
async def api_get_models():
    """Retourne tous les modèles disponibles depuis la config"""
    result = []
    for model_key, model in MODELS.items():
        result.append({
            "key": model_key,
            "model": model.get("model"),
            "name": get_model_display_name(model_key),
            "provider": model.get("provider"),
            "provider_name": get_provider_display_name(model.get("provider")),
            "max_context_size": model.get("max_context_size", DEFAULT_MAX_CONTEXT),
            "capabilities": model.get("capabilities", []),
            "icon": get_provider_icon(model.get("provider")),
            "color": get_provider_color(model.get("provider"))
        })
    # Trie par provider puis par nom
    result.sort(key=lambda x: (x["provider_name"], x["name"]))
    return result


# ============================================================================
# API - MCP MEMORY (Phase 2)
# ============================================================================
@app.get("/api/sessions/{session_id}/memory")
async def api_get_session_memory(session_id: int):
    """Retourne les statistiques mémoire d'une session."""
    memory_stats = get_session_memory_stats(session_id)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupère l'historique des métriques mémoire
    cursor.execute("""
        SELECT timestamp, memory_tokens, chat_tokens, memory_ratio
        FROM memory_metrics
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT 50
    """, (session_id,))
    
    history = [{
        'timestamp': row[0],
        'memory_tokens': row[1],
        'chat_tokens': row[2],
        'memory_ratio': row[3]
    } for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "session_id": session_id,
        "current": memory_stats,
        "history": history
    }


@app.get("/api/memory/stats")
async def api_get_memory_stats():
    """Retourne les statistiques globales de mémoire MCP."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Total de tokens mémoire utilisés
    cursor.execute("SELECT SUM(memory_tokens) FROM memory_metrics")
    total_memory_tokens = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(chat_tokens) FROM memory_metrics")
    total_chat_tokens = cursor.fetchone()[0] or 0
    
    # Nombre de sessions avec mémoire
    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM memory_metrics WHERE memory_tokens > 0")
    sessions_with_memory = cursor.fetchone()[0]
    
    # Ratio moyen
    cursor.execute("SELECT AVG(memory_ratio) FROM memory_metrics WHERE memory_tokens > 0")
    avg_ratio = cursor.fetchone()[0] or 0
    
    conn.close()
    
    total_tokens = total_memory_tokens + total_chat_tokens
    global_ratio = (total_memory_tokens / total_tokens * 100) if total_tokens > 0 else 0
    
    return {
        "total_memory_tokens": total_memory_tokens,
        "total_chat_tokens": total_chat_tokens,
        "total_tokens": total_tokens,
        "global_memory_ratio": round(global_ratio, 2),
        "average_session_ratio": round(avg_ratio, 2),
        "sessions_with_memory": sessions_with_memory
    }


# ============================================================================
# API - COMPRESSION (Phase 3)
# ============================================================================
@app.post("/api/compress/{session_id}")
async def api_compress_session(session_id: int, request: Request):
    """
    Endpoint pour compresser manuellement l'historique d'une session.
    Filet de sécurité ultime contre les crashes de contexte.
    """
    data = await request.json() if await request.body() else {}
    force = data.get("force", False)  # Force la compression même si < 85%
    
    # Vérifie la session
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    # Vérifie le seuil de contexte (sauf si force=True)
    if not force:
        session_totals = get_session_total_tokens(session_id)
        max_context = get_max_context_for_session(session)
        current_percentage = (session_totals["total_tokens"] / max_context * 100) if max_context > 0 else 0
        
        if current_percentage < COMPRESSION_CONFIG["threshold_percentage"]:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"Contexte trop faible pour compression ({current_percentage:.1f}% < {COMPRESSION_CONFIG['threshold_percentage']}%)",
                    "current_percentage": round(current_percentage, 2),
                    "threshold": COMPRESSION_CONFIG["threshold_percentage"],
                    "hint": "Utilisez force=true pour forcer la compression"
                }
            )
    
    # Exécute la compression
    try:
        result = await compress_session_history(session_id)
        
        if result.get("error"):
            return JSONResponse(
                status_code=400,
                content=result
            )
        
        # Notifie via WebSocket
        await manager.broadcast({
            "type": "compression_event",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "compression": {
                "compressed": result.get("compressed"),
                "original_tokens": result.get("original_tokens"),
                "compressed_tokens": result.get("compressed_tokens"),
                "tokens_saved": result.get("tokens_saved"),
                "compression_ratio": result.get("compression_ratio"),
                "messages_before": result.get("messages_before"),
                "messages_after": result.get("messages_after")
            }
        })
        
        return result
        
    except Exception as e:
        print(f"❌ [COMPRESSION] Erreur: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Erreur lors de la compression: {str(e)}"}
        )


@app.get("/api/compress/{session_id}/stats")
async def api_get_compression_stats(session_id: int):
    """Retourne les statistiques de compression d'une session."""
    stats = get_compression_stats(session_id)
    
    # Ajoute l'état actuel de la session
    session = get_session_by_id(session_id)
    session_totals = get_session_total_tokens(session_id) if session else {"total_tokens": 0}
    max_context = get_max_context_for_session(session) if session else DEFAULT_MAX_CONTEXT
    current_percentage = (session_totals["total_tokens"] / max_context * 100) if max_context > 0 else 0
    
    return {
        "session_id": session_id,
        "compression_stats": stats,
        "current_context": {
            "total_tokens": session_totals["total_tokens"],
            "max_context": max_context,
            "percentage": round(current_percentage, 2),
            "can_compress": current_percentage >= COMPRESSION_CONFIG["threshold_percentage"]
        },
        "config": {
            "threshold_percentage": COMPRESSION_CONFIG["threshold_percentage"],
            "preserve_recent_exchanges": COMPRESSION_CONFIG["preserve_recent_exchanges"]
        }
    }


@app.get("/api/compress/stats")
async def api_get_global_compression_stats():
    """Retourne les statistiques globales de compression."""
    stats = get_compression_stats()
    return {
        "global": stats,
        "config": COMPRESSION_CONFIG
    }


@app.get("/models")
async def openai_models():
    """
    Endpoint OpenAI-compatible GET /models pour validation Continue.dev.
    Retourne la liste des modèles au format OpenAI standard.
    """
    models_list = []
    
    for model_key, model_data in MODELS.items():
        # Le nom exposé est le model_key client (ex: "nvidia/kimi-k2-thinking")
        # car Continue envoie ce nom dans les requêtes
        client_model_id = model_key
        
        models_list.append({
            "id": client_model_id,
            "object": "model",
            "created": 1677610602,  # Timestamp fixe pour compatibilité
            "owned_by": model_data.get("provider", "unknown"),
            "permission": [],
            "root": client_model_id,
            "parent": None
        })
    
    return {
        "object": "list",
        "data": models_list
    }


def get_provider_display_name(provider_key: str) -> str:
    """Retourne le nom d'affichage d'un provider"""
    names = {
        "managed:kimi-code": "🌙 Kimi Code",
        "nvidia": "🟢 NVIDIA",
        "mistral": "🔷 Mistral",
        "openrouter": "🔀 OpenRouter",
        "siliconflow": "💧 SiliconFlow",
        "groq": "⚡ Groq",
        "cerebras": "🧠 Cerebras",
        "gemini": "💎 Gemini"
    }
    return names.get(provider_key, provider_key.replace("managed:", "").replace("-", " ").title())


def get_provider_icon(provider_key: str) -> str:
    """Retourne l'icône Lucide pour un provider"""
    icons = {
        "managed:kimi-code": "bot",
        "nvidia": "gpu",
        "mistral": "wind",
        "openrouter": "git-branch",
        "siliconflow": "droplets",
        "groq": "zap",
        "cerebras": "brain",
        "gemini": "sparkles"
    }
    return icons.get(provider_key, "cpu")


def get_provider_color(provider_key: str) -> str:
    """Retourne la couleur Tailwind pour un provider"""
    colors = {
        "managed:kimi-code": "purple",
        "nvidia": "green",
        "mistral": "blue",
        "openrouter": "orange",
        "siliconflow": "cyan",
        "groq": "yellow",
        "cerebras": "red",
        "gemini": "indigo"
    }
    return colors.get(provider_key, "slate")


def get_model_display_name(model_key: str) -> str:
    """Retourne le nom d'affichage d'un modèle"""
    # Mapping des noms d'affichage
    names = {
        "kimi-code/kimi-for-coding": "Kimi for Coding",
        "nvidia/kimi-k2.5": "Kimi K2.5",
        "nvidia/kimi-k2-thinking": "Kimi K2 Thinking",
        "mistral/codestral-2501": "Codestral 2501",
        "mistral/mistral-large-2411": "Mistral Large",
        "mistral/pixtral-large-2411": "Pixtral Large",
        "mistral/ministral-8b-2410": "Ministral 8B",
        "openrouter/aurora-alpha": "Aurora Alpha",
        "siliconflow/qwen3-32b": "Qwen 3 32B",
        "siliconflow/deepseek-v3.2": "DeepSeek V3.2",
        "groq/compound": "Compound",
        "groq/qwen3-32b": "Qwen 3 32B",
        "groq/gpt-oss-120b": "GPT-OSS 120B",
        "cerebras/qwen3-235b": "Qwen 3 235B",
        "cerebras/gpt-oss-120b": "GPT-OSS 120B",
        "cerebras/glm-4.7": "GLM-4.7",
        "gemini/gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite",
        "gemini/gemini-3-flash-preview": "Gemini 3 Flash Preview",
        "gemini/gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini/gemini-2.5-pro": "Gemini 2.5 Pro"
    }
    if model_key in names:
        return names[model_key]
    
    # Fallback: nettoie le nom
    parts = model_key.split("/")
    if len(parts) > 1:
        return parts[-1].replace("-", " ").title()
    return model_key.replace("-", " ").title()

# ============================================================================
# WEBSOCKET
# ============================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        session = get_active_session()
        if session:
            stats = get_session_stats(session["id"])
            await websocket.send_json({
                "type": "init",
                "session": session,
                **stats
            })
        
        while True:
            data = await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ============================================================================
# PROXY - CŒUR DE L'APPLICATION
# ============================================================================
def get_max_context_for_session(session: dict) -> int:
    """Récupère le contexte max pour une session basé sur son provider.
    
    Si un modèle spécifique est stocké dans la session, utilise son contexte.
    Sinon, utilise le contexte le plus petit parmi les modèles du provider (conservateur).
    """
    if not session:
        return DEFAULT_MAX_CONTEXT
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    model_key = session.get("model")  # Modèle spécifique si disponible
    
    # Si un modèle spécifique est stocké, utilise son contexte
    if model_key and model_key in MODELS:
        return MODELS[model_key].get("max_context_size", DEFAULT_MAX_CONTEXT)
    
    # Sinon, trouve le contexte le plus petit parmi les modèles du provider
    # (approche conservatrice pour éviter de dépasser)
    min_context = None
    for mk, model in MODELS.items():
        if model.get("provider") == provider_key:
            ctx = model.get("max_context_size", DEFAULT_MAX_CONTEXT)
            if min_context is None or ctx < min_context:
                min_context = ctx
    
    return min_context if min_context else DEFAULT_MAX_CONTEXT


def build_gemini_endpoint(base_url: str, model: str, api_key: str, stream: bool = False) -> str:
    """Construit l'endpoint Gemini avec la clé API en query param."""
    action = "streamGenerateContent" if stream else "generateContent"
    return f"{base_url}/models/{model}:{action}?key={api_key}"


def convert_to_gemini_format(openai_body: dict) -> dict:
    """Convertit un body OpenAI au format Gemini."""
    gemini_body = {}
    
    # Convertit les messages
    if "messages" in openai_body:
        contents = []
        for msg in openai_body["messages"]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Mapping des roles
            gemini_role = "user" if role in ["user", "system"] else "model"
            
            gemini_content = {"role": gemini_role, "parts": [{"text": content}]}
            contents.append(gemini_content)
        
        gemini_body["contents"] = contents
    
    # Génération config
    generation_config = {}
    if "temperature" in openai_body:
        generation_config["temperature"] = openai_body["temperature"]
    if "max_tokens" in openai_body:
        generation_config["maxOutputTokens"] = openai_body["max_tokens"]
    
    if generation_config:
        gemini_body["generationConfig"] = generation_config
    
    return gemini_body

def get_target_url_for_session(session: dict) -> str:
    """Récupère l'URL cible pour la session en fonction du provider."""
    if not session:
        return "https://api.kimi.com/coding/v1"
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    provider = PROVIDERS.get(provider_key, {})
    
    base_url = provider.get("base_url", "")
    
    # Protection contre la boucle infinie
    if base_url and "127.0.0.1:8000" not in base_url and "localhost:8000" not in base_url:
        return base_url.rstrip("/")
    
    return "https://api.kimi.com/coding/v1"

def get_provider_host_header(target_url: str) -> str:
    """Extrait le header Host approprié pour l'URL cible."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(target_url)
        return parsed.netloc
    except:
        return None

async def stream_generator(response: httpx.Response, session_id: int, metric_id: int, body: bytes = None, headers: dict = None, provider_type: str = "openai"):
    """Générateur de streaming + extraction des vrais tokens.
    
    Supporte différents formats de réponse selon le provider.
    """
    buffer = b""
    usage_data = None
    first_chunk = True
    
    async for chunk in response.aiter_bytes():
        if first_chunk and response.status_code >= 400:
            try:
                error_text = chunk.decode('utf-8', errors='ignore')[:500]
                print(f"❌ Erreur API {response.status_code}: {error_text}")
            except:
                pass
        first_chunk = False
        
        buffer += chunk
        yield chunk
    
    if metric_id and session_id:
        try:
            usage_data = extract_usage_from_stream(buffer, provider_type)
            if usage_data:
                print(f"✅ Vrais tokens reçus: {usage_data}")
                session = get_session_by_id(session_id)
                max_context = get_max_context_for_session(session)
                
                prompt_tokens = usage_data.get("prompt_tokens", 0)
                completion_tokens = usage_data.get("completion_tokens", 0)
                total_tokens = usage_data.get("total_tokens", 0) or (prompt_tokens + completion_tokens)
                
                real_data = update_metric_with_real_tokens(
                    metric_id,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    max_context
                )
                
                new_totals = get_session_total_tokens(session_id)
                cumulative_total = new_totals["total_tokens"]
                cumulative_percentage = (cumulative_total / max_context) * 100
                
                alert = check_threshold_alert(cumulative_percentage)
                
                await manager.broadcast({
                    "type": "metric_updated",
                    "metric_id": metric_id,
                    "session_id": session_id,
                    "real_tokens": real_data,
                    "cumulative_tokens": cumulative_total,
                    "cumulative_percentage": cumulative_percentage,
                    "alert": alert,
                    "source": "proxy"
                })
        except Exception as e:
            print(f"⚠️  Erreur extraction usage: {e}")

def get_session_by_id(session_id: int) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def extract_usage_from_stream(buffer: bytes, provider_type: str = "openai") -> dict:
    """Extrait les usage tokens du stream SSE.
    
    Supporte différents formats selon le provider.
    """
    text = buffer.decode('utf-8', errors='ignore')
    lines = text.strip().split('\n')
    
    # Format OpenAI standard et compatibles (Mistral, NVIDIA, Groq, etc.)
    for line in reversed(lines):
        if line.startswith('data: '):
            data_str = line[6:]
            if data_str == '[DONE]':
                continue
            try:
                data = json.loads(data_str)
                # Format OpenAI standard
                if 'usage' in data and data['usage']:
                    usage = data['usage']
                    return {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    }
                # Format Gemini (peut avoir une structure différente)
                if provider_type == "gemini":
                    if 'usageMetadata' in data:
                        meta = data['usageMetadata']
                        return {
                            "prompt_tokens": meta.get("promptTokenCount", 0),
                            "completion_tokens": meta.get("candidatesTokenCount", 0),
                            "total_tokens": meta.get("totalTokenCount", 0)
                        }
            except json.JSONDecodeError:
                continue
    return None

@app.post("/chat/completions")
async def proxy_chat(request: Request):
    """
    Proxy vers l'API provider avec:
    - Injection robuste de la clé API
    - Mise à jour correcte du header Host
    - Calcul des tokens
    - SANITIZER: Masking des contenus verbeux
    - ROUTING: Fallback dynamique vers modèle plus grand
    - Broadcast WebSocket
    - Support multi-provider (OpenAI-compatible + Gemini)
    """
    body = await request.body()
    headers = dict(request.headers)
    
    # ============================================================================
    # PHASE 1: SANITIZER - Analyse et masking des messages
    # ============================================================================
    sanitized_body = body
    masking_metadata = {"masked_count": 0, "tokens_saved": 0}
    
    # ============================================================================
    # PHASE 2: MCP MEMORY - Analyse mémoire long terme
    # ============================================================================
    mcp_memory_analysis = {
        'memory_tokens': 0,
        'chat_tokens': 0,
        'memory_ratio': 0,
        'has_memory': False,
        'segments': []
    }
    original_messages = []
    
    try:
        body_json = json.loads(body)
        original_messages = body_json.get("messages", [])
        
        # Analyse MCP mémoire (Phase 2)
        if original_messages:
            mcp_memory_analysis = analyze_mcp_memory_in_messages(original_messages)
            if mcp_memory_analysis['has_memory']:
                print(f"🧠 [MCP MEMORY] Détecté: {mcp_memory_analysis['memory_tokens']} tokens mémoire "
                      f"({mcp_memory_analysis['memory_ratio']:.1f}%) - "
                      f"{mcp_memory_analysis['segment_count']} segment(s)")
        
        if original_messages and MASKING_CONFIG["enabled"]:
            sanitized_messages, masking_metadata = sanitize_messages(original_messages)
            
            if masking_metadata["masked_count"] > 0:
                body_json["messages"] = sanitized_messages
                sanitized_body = json.dumps(body_json).encode('utf-8')
                print(f"🧹 [SANITIZER] {masking_metadata['masked_count']} message(s) nettoyé(s), "
                      f"~{masking_metadata['tokens_saved']} tokens économisés")
        
        body = sanitized_body
    except Exception as e:
        print(f"⚠️  [SANITIZER/MCP] Erreur lors de l'analyse: {e}")
        # Continue avec le body original en cas d'erreur
    
    # Récupère la session active
    session = get_active_session()
    
    max_context = get_max_context_for_session(session)
    target_url = get_target_url_for_session(session)
    provider_key = session.get("provider", DEFAULT_PROVIDER) if session else DEFAULT_PROVIDER
    
    # ============================================================================
    # PHASE 1: ROUTING DYNAMIQUE - Fallback vers modèle plus grand si nécessaire
    # ============================================================================
    
    # Calcul des tokens
    estimated_tokens = 0
    percentage = 0
    content_preview = ""
    request_tokens = 0
    
    try:
        json_body = json.loads(body)
        messages = json_body.get("messages", [])
        
        request_tokens = count_tokens_tiktoken(messages)
        
        # Vérifie si on doit faire un fallback de modèle
        if session and request_tokens > 0:
            updated_session, routing_notification = await route_dynamic_model(session, request_tokens)
            if routing_notification:
                session = updated_session
                # Met à jour max_context après fallback
                max_context = get_max_context_for_session(session)
                # Notifie via WebSocket
                await manager.broadcast({
                    "type": "sanitizer_event",
                    "event": routing_notification,
                    "session_id": session["id"],
                    "timestamp": datetime.now().isoformat()
                })
                print(f"🔄 [ROUTING] Notification envoyée: {routing_notification['message']}")
        
        session_totals = get_session_total_tokens(session["id"]) if session else {"total_tokens": 0}
        cumulative_tokens = session_totals["total_tokens"]
        
        total_current = cumulative_tokens + request_tokens
        percentage = (total_current / max_context) * 100
        
        content_preview = ""
        # Utilise les messages originaux pour le preview (pas les messages sanitizés)
        preview_messages = original_messages if masking_metadata.get("masked_count", 0) > 0 else messages
        for msg in preview_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user" and content:
                if isinstance(content, str):
                    content_preview = content[:100]
                elif isinstance(content, list) and len(content) > 0:
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    content_preview = (text_parts[0] if text_parts else str(content[0]))[:100]
                break
    except Exception as e:
        request_tokens = 0
        total_current = 0
        percentage = 0
        content_preview = f"Erreur parsing: {str(e)[:50]}"
    
    # Sauvegarde en DB si session active ET ce n'est pas un message système
    metric_id = None
    if session and content_preview and not is_system_message(content_preview):
        print(f"📊 [PROXY] Tokens: +{request_tokens} (cumul: {total_current}) = {percentage:.1f}% - {content_preview[:50]}...")
        
        update_session_first_prompt(session["id"], content_preview)
        
        # Sauvegarde aussi les métriques mémoire si présentes
        if mcp_memory_analysis['has_memory']:
            save_memory_metrics(
                session_id=session["id"],
                memory_tokens=mcp_memory_analysis['memory_tokens'],
                chat_tokens=mcp_memory_analysis['chat_tokens'],
                memory_ratio=mcp_memory_analysis['memory_ratio']
            )
        
        metric_id = save_metric(
            session_id=session["id"],
            tokens=request_tokens,
            percentage=percentage,
            preview=content_preview,
            is_estimated=True,
            source='proxy',
            memory_tokens=mcp_memory_analysis['memory_tokens'],
            chat_tokens=mcp_memory_analysis['chat_tokens'],
            memory_ratio=mcp_memory_analysis['memory_ratio']
        )
        
        alert = check_threshold_alert(percentage)
        await manager.broadcast({
            "type": "metric",
            "metric": {
                "id": metric_id,
                "timestamp": datetime.now().isoformat(),
                "estimated_tokens": request_tokens,
                "cumulative_tokens": total_current,
                "percentage": percentage,
                "content_preview": content_preview,
                "is_estimated": True,
                "source": "proxy"
            },
            "session_id": session["id"],
            "session_updated": True,
            "alert": alert,
            "sanitizer": masking_metadata if masking_metadata.get("masked_count", 0) > 0 else None,
            "mcp_memory": mcp_memory_analysis if mcp_memory_analysis['has_memory'] else None
        })
        
        # WebSocket event spécifique pour métriques mémoire (Phase 2)
        if mcp_memory_analysis['has_memory']:
            await manager.broadcast({
                "type": "memory_metrics_update",
                "session_id": session["id"],
                "timestamp": datetime.now().isoformat(),
                "memory": {
                    "memory_tokens": mcp_memory_analysis['memory_tokens'],
                    "chat_tokens": mcp_memory_analysis['chat_tokens'],
                    "total_tokens": mcp_memory_analysis['total_tokens'],
                    "memory_ratio": mcp_memory_analysis['memory_ratio'],
                    "segment_count": mcp_memory_analysis['segment_count']
                }
            })
    
    # Rate Limiting
    rate_status = await rate_limiter.throttle_if_needed()
    
    if provider_key in ["nvidia", "mistral", "openrouter"]:
        rate_alert = rate_limiter.check_alert()
        if rate_alert:
            print(f"{rate_alert}")
        
        if rate_status["percentage"] >= 50:
            print(f"ℹ️  Rate limit: {rate_status['current_rpm']:.0f}/{MAX_RPM} RPM ({rate_status['percentage']:.1f}%)")
    
    # ============================================================================
    # PROXY VERS LE PROVIDER (avec injection robuste de la clé API)
    # ============================================================================
    client = httpx.AsyncClient(timeout=120.0)
    try:
        provider_config = PROVIDERS.get(provider_key, {})
        provider_api_key = provider_config.get("api_key", "")
        provider_type = provider_config.get("type", "openai")
        
        # Construction des headers pour l'API distante
        proxy_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Kimi-Proxy-Dashboard/1.0"
        }
        
        # 🔑 INJECTION ROBUSTE DE LA CLÉ API
        if provider_api_key:
            if provider_type == "gemini":
                # Gemini utilise un format différent pour l'auth (clé en query param)
                pass  # Géré dans l'URL
            else:
                proxy_headers["Authorization"] = f"Bearer {provider_api_key}"
            # Masque la clé pour le log
            masked_key = provider_api_key[:10] + "..." if len(provider_api_key) > 10 else "***"
            print(f"🔑 Clé API {provider_key} injectée: {masked_key}")
        else:
            print(f"⚠️  ATTENTION: Aucune clé API trouvée pour {provider_key}")
        
        # 🌐 MISE À JOUR DU HEADER HOST
        host_header = get_provider_host_header(target_url)
        if host_header:
            proxy_headers["Host"] = host_header
            print(f"🌐 Header Host mis à jour: {host_header}")
        
        # Headers additionnels optionnels
        if "x-request-id" in headers:
            proxy_headers["x-request-id"] = headers["x-request-id"]
        
        print(f"🔄 Proxy vers {provider_key} ({provider_type}): {target_url}")
        
        # Parse et nettoie le body
        try:
            body_json = json.loads(body)
            
            # Nettoie le nom du modèle en utilisant le mapping MODELS
            model_name = body_json.get('model', '')
            original_model = model_name
            
            # Utilise le modèle mappé depuis la config si disponible
            if model_name in MODELS:
                mapped_model = MODELS[model_name].get('model', model_name)
                body_json['model'] = mapped_model
                print(f"📝 Modèle mappé: {original_model} → {mapped_model}")
            elif '/' in model_name:
                # Fallback: retire le préfixe provider (ancien comportement)
                clean_model = model_name.split('/', 1)[1]
                body_json['model'] = clean_model
                print(f"📝 Modèle nettoyé (fallback): {original_model} → {clean_model}")
            
            print(f"📤 Requête: model={body_json.get('model')}, stream={body_json.get('stream', False)}")
            
            # Construction de l'URL cible selon le type de provider
            if provider_type == "gemini":
                # Gemini utilise un format d'URL différent
                target_endpoint = build_gemini_endpoint(target_url, body_json.get('model'), provider_api_key, body_json.get('stream', False))
                clean_body = json.dumps(convert_to_gemini_format(body_json))
            else:
                target_endpoint = f"{target_url}/chat/completions"
                clean_body = json.dumps(body_json)
                
        except Exception as e:
            print(f"⚠️  Erreur parsing body: {e}")
            clean_body = body
            target_endpoint = f"{target_url}/chat/completions"
        
        req = client.build_request(
            "POST",
            target_endpoint,
            headers=proxy_headers,
            content=clean_body
        )
        
        # Détecte si la requête demande du streaming
        is_streaming = body_json.get('stream', False)
        
        if is_streaming:
            # Mode streaming: utilise stream_generator
            response = await client.send(req, stream=True)
            
            # Log si erreur
            if response.status_code >= 400:
                error_text = ""
                try:
                    error_body = await response.aread()
                    error_text = error_body.decode('utf-8', errors='ignore')[:500]
                    print(f"❌ Erreur {response.status_code}: {error_text}")
                    
                    if response.status_code == 401:
                        print(f"🔒 Erreur 401 - Vérifiez la clé API dans config.toml pour {provider_key}")
                        print(f"   URL appelée: {target_endpoint}")
                        
                except Exception as e:
                    print(f"❌ Erreur {response.status_code} (impossible de lire le corps): {e}")
                
                response = await client.send(req, stream=True)
            
            return StreamingResponse(
                stream_generator(response, session["id"] if session else 0, metric_id, provider_type=provider_type),
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json")
            )
        else:
            # Mode non-streaming: réponse complète
            response = await client.send(req, stream=False)
            
            if response.status_code >= 400:
                error_text = ""
                try:
                    error_text = response.text[:500]
                    print(f"❌ Erreur {response.status_code}: {error_text}")
                except Exception as e:
                    print(f"❌ Erreur {response.status_code}: {e}")
            
            # Extrait les tokens de la réponse complète
            if metric_id and session:
                try:
                    response_data = response.json()
                    usage = response_data.get('usage', {})
                    if usage:
                        prompt_tokens = usage.get('prompt_tokens', 0)
                        completion_tokens = usage.get('completion_tokens', 0)
                        total_tokens = usage.get('total_tokens', 0) or (prompt_tokens + completion_tokens)
                        
                        print(f"✅ Vrais tokens reçus (non-stream): {usage}")
                        
                        real_data = update_metric_with_real_tokens(
                            metric_id,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                            max_context
                        )
                        
                        new_totals = get_session_total_tokens(session["id"])
                        cumulative_total = new_totals["total_tokens"]
                        cumulative_percentage = (cumulative_total / max_context) * 100
                        
                        alert = check_threshold_alert(cumulative_percentage)
                        
                        await manager.broadcast({
                            "type": "metric_updated",
                            "metric_id": metric_id,
                            "session_id": session["id"],
                            "real_tokens": real_data,
                            "cumulative_tokens": cumulative_total,
                            "cumulative_percentage": cumulative_percentage,
                            "alert": alert,
                            "source": "proxy"
                        })
                except Exception as e:
                    print(f"⚠️  Erreur extraction usage (non-stream): {e}")
            
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
                headers=dict(response.headers)
            )
    except Exception as e:
        print(f"❌ Exception proxy: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Proxy error: {str(e)}", "provider": provider_key}
        )

# ============================================================================
# HEALTH & EXPORT
# ============================================================================
@app.get("/health")
async def health_check():
    session = get_active_session()
    max_context = get_max_context_for_session(session)
    
    # Vérifie si le log watcher est actif
    log_watcher_status = "running" if log_watcher.running else "stopped"
    log_file_exists = os.path.exists(log_watcher.log_path)
    
    return {
        "status": "ok",
        "max_context": max_context,
        "active_session": session,
        "log_watcher": {
            "status": log_watcher_status,
            "log_file_exists": log_file_exists,
            "log_path": log_watcher.log_path
        },
        "rate_limit": {
            "current_rpm": rate_limiter.get_current_rpm(),
            "max_rpm": MAX_RPM,
            "percentage": round(rate_limiter.get_rpm_percentage(), 1)
        }
    }

@app.get("/api/rate-limit")
async def get_rate_limit_status():
    rpm = rate_limiter.get_current_rpm()
    percentage = rate_limiter.get_rpm_percentage()
    
    status = "normal"
    if rpm >= rate_limiter.critical_threshold:
        status = "critical"
    elif rpm >= rate_limiter.warning_threshold:
        status = "warning"
    elif rpm >= MAX_RPM * 0.5:
        status = "elevated"
    
    return {
        "status": status,
        "current_rpm": rpm,
        "max_rpm": MAX_RPM,
        "percentage": round(percentage, 1)
    }

@app.get("/api/export/csv")
async def export_csv():
    session = get_active_session()
    if not session:
        return {"error": "Aucune session active"}
    
    import csv
    import io
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT timestamp, estimated_tokens, percentage, content_preview, 
                  prompt_tokens, completion_tokens, is_estimated, source
           FROM metrics 
           WHERE session_id = ? 
           ORDER BY timestamp DESC""",
        (session["id"],)
    )
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Tokens Total", "Pourcentage", "Aperçu", 
                     "Prompt Tokens", "Completion Tokens", "Type", "Source"])
    
    for row in rows:
        writer.writerow([
            row[0],
            row[1],
            f"{row[2]:.2f}%",
            row[3],
            row[4] or 0,
            row[5] or 0,
            "Estimé" if row[6] else "Réel",
            row[7] or "proxy"
        ])
    
    output.seek(0)
    filename = f"session_{session['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/export/json")
async def export_json():
    session = get_active_session()
    if not session:
        return {"error": "Aucune session active"}
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM metrics WHERE session_id = ? ORDER BY timestamp DESC""",
        (session["id"],)
    )
    metrics = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        "session": session,
        "metrics": metrics,
        "exported_at": datetime.now().isoformat()
    }


# ============================================================================
# API - SANITIZER (Phase 1)
# ============================================================================
@app.get("/api/mask/{content_hash}")
async def get_masked_content_endpoint(content_hash: str):
    """
    Récupère le contenu masqué par son hash.
    """
    content = get_masked_content(content_hash)
    if not content:
        return JSONResponse(
            status_code=404,
            content={"error": "Contenu masqué non trouvé", "hash": content_hash}
        )
    
    return {
        "hash": content["content_hash"],
        "preview": content["preview"],
        "tags": content["tags"].split(",") if content["tags"] else [],
        "token_count": content["token_count"],
        "created_at": content["created_at"],
        "file_path": content["file_path"],
        "original_content": content["original_content"]
    }

@app.get("/api/mask")
async def list_masked_content(limit: int = 50):
    """
    Liste les contenus masqués récents.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT content_hash, preview, tags, token_count, created_at 
           FROM masked_content 
           ORDER BY created_at DESC 
           LIMIT ?""",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return {
        "items": [{
            "hash": row[0],
            "preview": row[1][:200] if row[1] else "",
            "tags": row[2].split(",") if row[2] else [],
            "token_count": row[3],
            "created_at": row[4]
        } for row in rows],
        "total": len(rows)
    }

@app.get("/api/sanitizer/stats")
async def get_sanitizer_stats():
    """
    Retourne les statistiques du sanitizer.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Nombre total de contenus masqués
    cursor.execute("SELECT COUNT(*) FROM masked_content")
    total_masked = cursor.fetchone()[0]
    
    # Total de tokens économisés (approximation)
    cursor.execute("SELECT SUM(token_count) FROM masked_content")
    total_tokens_masked = cursor.fetchone()[0] or 0
    
    # Contenus récents (24h)
    cursor.execute(
        """SELECT COUNT(*) FROM masked_content 
           WHERE created_at > datetime('now', '-1 day')"""
    )
    recent_masked = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "enabled": MASKING_CONFIG["enabled"],
        "threshold_tokens": MASKING_CONFIG["threshold_tokens"],
        "preview_length": MASKING_CONFIG["preview_length"],
        "tmp_dir": MASKING_CONFIG["tmp_dir"],
        "stats": {
            "total_masked": total_masked,
            "total_tokens_masked": total_tokens_masked,
            "recent_24h": recent_masked
        }
    }

@app.post("/api/sanitizer/toggle")
async def toggle_sanitizer(request: Request):
    """
    Active/désactive le sanitizer.
    """
    global MASKING_CONFIG
    data = await request.json()
    enabled = data.get("enabled", True)
    
    MASKING_CONFIG["enabled"] = enabled
    
    return {
        "enabled": enabled,
        "message": f"Sanitizer {'activé' if enabled else 'désactivé'}"
    }

# ============================================================================
# ALERTES ET SEUILS
# ============================================================================
def check_threshold_alert(percentage: float) -> dict:
    if percentage >= 95:
        return {"level": "critical", "color": "#ef4444", "message": "⚠️ CONTEXTE CRITIQUE (95%)"}
    elif percentage >= 90:
        return {"level": "warning", "color": "#f97316", "message": "⚠️ CONTEXTE ÉLEVÉ (90%)"}
    elif percentage >= 80:
        return {"level": "caution", "color": "#eab308", "message": "⚡ Attention (80%)"}
    return None

# ============================================================================
# DÉMARRAGE
# ============================================================================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
