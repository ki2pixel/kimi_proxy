"""
Résumé LLM pour la compression.
"""
import json
from typing import List, Dict, Any, Optional

import httpx

from ...core.tokens import count_tokens_tiktoken
from ...core.constants import DEFAULT_COMPRESSION_CONFIG
from ...config.loader import get_config


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
    
    from ...config.display import get_max_context_for_session
    from ...proxy.router import get_target_url_for_session, get_provider_host_header
    
    # Construit le prompt de résumé
    conversation_text = "\n\n".join([
        f"{msg.get('role', 'user').upper()}: {msg.get('content', '')[:500]}"
        for msg in messages
    ])
    
    summary_prompt = f"""Résume brièvement la conversation suivante en conservant les points clés, décisions importantes et contexte technique pertinent. Sois concis (max 300 mots):

{conversation_text}

RÉSUMÉ:"""
    
    # Prépare la requête au provider
    config = get_config()
    provider_key = session.get("provider", "managed:kimi-code")
    providers = config.get("providers", {})
    provider = providers.get(provider_key, {})
    provider_api_key = provider.get("api_key", "")
    provider_type = provider.get("type", "openai")
    target_url = get_target_url_for_session(session, providers)
    
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
        "max_tokens": DEFAULT_COMPRESSION_CONFIG["summary_max_tokens"],
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
