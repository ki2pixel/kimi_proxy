"""
Transformations de format entre OpenAI et autres APIs (Gemini, etc.).
"""
from typing import Dict, Any, Optional


def build_gemini_endpoint(
    base_url: str,
    model: str,
    api_key_or_stream: Optional[Any] = None,
    stream: bool = False
) -> str:
    """
    Construit l'endpoint Gemini (sans clé API en query param pour la sécurité).
    La clé doit être passée via le header 'x-goog-api-key'.
    
    Args:
        base_url: URL de base de l'API
        model: Nom du modèle
        api_key_or_stream: Clé API (legacy) ou booléen pour le stream
        stream: Si True, utilise streamGenerateContent
        
    Returns:
        URL complète
    """
    actual_stream = stream
    if isinstance(api_key_or_stream, bool):
        actual_stream = api_key_or_stream
        
    action = "streamGenerateContent" if actual_stream else "generateContent"
    return f"{base_url.rstrip('/')}/models/{model}:{action}"


def convert_to_gemini_format(openai_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit un body OpenAI au format Gemini.
    
    Args:
        openai_body: Body de requête au format OpenAI
        
    Returns:
        Body au format Gemini
    """
    gemini_body = {}
    
    # Convertit les messages
    if "messages" in openai_body:
        contents = []
        for msg in openai_body["messages"]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Mapping des roles
            gemini_role = "user" if role in ["user", "system"] else "model"
            
            gemini_content = {
                "role": gemini_role,
                "parts": [{"text": content}]
            }
            contents.append(gemini_content)
        
        gemini_body["contents"] = contents
    
    # Génération config
    generation_config = {}
    if "temperature" in openai_body:
        generation_config["temperature"] = openai_body["temperature"]
    if "max_tokens" in openai_body:
        generation_config["maxOutputTokens"] = openai_body["max_tokens"]
    
    if generation_config:
        gemini_body["generationConfig"] = generation_config  # type: ignore
    
    return gemini_body


def convert_from_gemini_response(gemini_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit une réponse Gemini au format OpenAI.
    
    Args:
        gemini_response: Réponse de l'API Gemini
        
    Returns:
        Réponse au format OpenAI
    """
    openai_response = {
        "id": "gemini-" + str(hash(str(gemini_response))),
        "object": "chat.completion",
        "created": 0,
        "model": "gemini",
        "choices": [],
        "usage": {}
    }
    
    # Extrait le contenu
    candidates = gemini_response.get("candidates", [])
    if candidates:
        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        
        text = ""
        for part in parts:
            if "text" in part:
                text += part["text"]
        
        openai_response["choices"].append({  # type: ignore
            "index": 0,
            "message": {
                "role": "assistant",
                "content": text
            },
            "finish_reason": "stop"
        })
    
    # Extrait les métriques d'usage
    usage = gemini_response.get("usageMetadata", {})
    openai_response["usage"] = {
        "prompt_tokens": usage.get("promptTokenCount", 0),
        "completion_tokens": usage.get("candidatesTokenCount", 0),
        "total_tokens": usage.get("totalTokenCount", 0)
    }
    
    return openai_response


def convert_stream_chunk(
    chunk: bytes,
    provider_type: str = "openai"
) -> Optional[Dict[str, Any]]:
    """
    Convertit un chunk de stream selon le provider.
    
    Args:
        chunk: Données binaires du chunk
        provider_type: Type de provider
        
    Returns:
        Chunk parsé ou None
    """
    text = chunk.decode('utf-8', errors='ignore')
    
    for line in text.split('\n'):
        if line.startswith('data: '):
            data_str = line[6:]
            if data_str == '[DONE]':
                return {"done": True}
            
            try:
                import json
                return json.loads(data_str)
            except json.JSONDecodeError:
                continue
    
    return None
