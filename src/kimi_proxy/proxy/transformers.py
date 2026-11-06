"""
Transformations de format entre OpenAI et autres APIs (Gemini, etc.).
"""
from typing import Dict, Any


def build_gemini_endpoint(base_url: str, model: str, stream: bool = False) -> str:
    """Construit l'endpoint Gemini sans clé API en query param.

    La clé est passée via le header ``x-goog-api-key``.
    """
    action = "streamGenerateContent" if stream else "generateContent"
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


