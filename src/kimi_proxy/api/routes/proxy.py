"""
Route proxy principale /chat/completions.
"""
import json
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

import httpx

from ...core.database import (
    get_active_session,
    save_metric,
    update_metric_with_real_tokens,
    get_session_total_tokens,
    get_session_cumulative_tokens,
    get_session_by_id,
    is_system_message,
    update_session_first_prompt,
)
from ...core.tokens import count_tokens_tiktoken
from ...core.constants import DEFAULT_MAX_CONTEXT, MCP_MAX_RESPONSE_TOKENS
from ...config.loader import get_config
from ...config.display import get_max_context_for_session
from ...services.websocket_manager import get_connection_manager
from ...services.rate_limiter import get_rate_limiter
from ...services.alerts import check_threshold_alert, create_context_limit_alert
from ...proxy.router import get_target_url_for_session, get_provider_host_header, map_model_name
from ...proxy.stream import stream_generator, extract_usage_from_response
from ...proxy.client import create_proxy_client

router = APIRouter()


def check_context_limit_violation(
    estimated_tokens: int, 
    max_context: int, 
    session_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Vérifie si une requête dépasserait les limites de contexte.
    
    Args:
        estimated_tokens: Nombre de tokens estimé
        max_context: Limite maximale de contexte
        session_id: ID de session pour le logging
        
    Returns:
        Dict avec détails de violation si dépassement, None sinon
    """
    # Laisse une marge de sécurité (5% du contexte max)
    safety_margin = int(max_context * 0.05)
    effective_limit = max_context - safety_margin
    
    if estimated_tokens > effective_limit:
        violation_ratio = estimated_tokens / max_context
        return {
            "violation": True,
            "estimated_tokens": estimated_tokens,
            "max_context": max_context,
            "effective_limit": effective_limit,
            "violation_ratio": violation_ratio,
            "excess_tokens": estimated_tokens - max_context,
            "recommendations": [
                "Utiliser le sanitizer pour réduire la verbosité",
                "Compresser le contexte historique",
                "Diviser la requête en parties plus petites",
                f"Limiter à {effective_limit:,} tokens maximum"
            ] if violation_ratio > 1.1 else [
                "Optimiser le prompt système",
                "Réduire la longueur des messages utilisateur"
            ]
        }
    
    return None


@router.post("/chat/completions")
async def proxy_chat(request: Request):
    """
    Proxy simple vers l'API provider.
    Plus de traitement MCP - les serveurs locaux gèrent tout.
    """
    body = await request.body()
    headers = dict(request.headers)
    
    # Configuration basique
    config = get_config()
    providers = config.get("providers", {})
    models = config.get("models", {})
    
    # Session - Vérifier si on doit créer une nouvelle session automatiquement
    from ...core.auto_session import process_auto_session
    
    current_session = get_active_session()
    json_body = json.loads(body) if body else {}
    
    # Traiter la logique d'auto-session
    session, new_session_created = process_auto_session(json_body, current_session)
    
    if new_session_created:
        print(f"🔄 [AUTO SESSION] Nouvelle session créée: #{session['id']}")
    
    max_context = get_max_context_for_session(session, models, DEFAULT_MAX_CONTEXT)
    target_url = get_target_url_for_session(session, providers)
    provider_key = session.get("provider", "managed:kimi-code") if session else "managed:kimi-code"
    
    # Calcul tokens simple
    estimated_tokens = 0
    try:
        json_body = json.loads(body)
        messages = json_body.get("messages", [])
        for msg in messages:
            estimated_tokens += count_tokens_tiktoken([msg])
    except:
        estimated_tokens = 0
    
    # Vérification limite contexte
    if estimated_tokens > max_context:
        return JSONResponse(
            content={
                "error": "Context limit exceeded",
                "message": f"Request of {estimated_tokens:,} tokens exceeds limit of {max_context:,} tokens"
            },
            status_code=413
        )
    
    # Métriques basiques
    if session:
        content_preview = ""
        try:
            messages = json_body.get("messages", [])
            for msg in messages:
                if msg.get("role") == "user" and msg.get("content"):
                    content_preview = str(msg.get("content"))[:100]
                    break
        except:
            content_preview = "Parse error"
        
        metric_id = save_metric(
            session_id=session["id"],
            tokens=estimated_tokens,
            percentage=(estimated_tokens / max_context) * 100,
            preview=content_preview,
            is_estimated=True,
            source='proxy'
        )
        
        # Vérifier auto-compaction après sauvegarde des métriques
        from ...core.database import get_session_cumulative_tokens
        from ...features.compaction.auto_trigger import get_auto_trigger
        
        cumulative_tokens = get_session_cumulative_tokens(session["id"])["total_tokens"]
        auto_trigger = get_auto_trigger()
        
        # Vérifier si auto-compaction doit être déclenchée
        compaction_result = await auto_trigger.check_and_trigger(
            session_id=session["id"],
            current_tokens=cumulative_tokens,  # Utiliser les tokens cumulés
            max_context=max_context,
            messages=json_body.get("messages", []),  # Messages de la requête
            trigger_callback=lambda result, info: print(f"🗜️ [AUTO-COMPACTION] Déclenchée: {info}")
        )
        
        if compaction_result:
            print(f"✅ [AUTO-COMPACTION] Exécutée pour session {session['id']}: {compaction_result.tokens_saved} tokens économisés")
    
    print(f"📊 [PROXY] {estimated_tokens:,} tokens → {provider_key}")
    
    # Proxy direct
    return await _proxy_to_provider(
        body=body,
        headers=headers,
        provider_key=provider_key,
        providers=providers,
        models=models,
        target_url=target_url,
        session=session,
        metric_id=metric_id if 'metric_id' in locals() else None,
        max_context=max_context,
        request_tokens=estimated_tokens
    )


async def _proxy_to_provider(
    body: bytes,
    headers: dict,
    provider_key: str,
    providers: dict,
    models: dict,
    target_url: str,
    session: dict,
    metric_id: int,
    max_context: int,
    request_tokens: int
):
    """
    Effectue le proxy vers le provider IA avec gestion d'erreurs robuste et métriques temps réel.
    """
    provider_config = providers.get(provider_key, {})
    provider_api_key = provider_config.get("api_key", "")
    provider_type = provider_config.get("type", "openai")
    
    # Construction des headers
    proxy_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Kimi-Proxy-Dashboard/1.0"
    }
    
    # Injection de la clé API
    if provider_api_key:
        if provider_type != "gemini":
            proxy_headers["Authorization"] = f"Bearer {provider_api_key}"
        masked_key = provider_api_key[:10] + "..." if len(provider_api_key) > 10 else "***"
        print(f"🔑 Clé API {provider_key} injectée: {masked_key}")
    else:
        print(f"⚠️ ATTENTION: Aucune clé API trouvée pour {provider_key}")
    
    # Mise à jour du Host header
    host_header = get_provider_host_header(target_url)
    if host_header:
        proxy_headers["Host"] = host_header
        print(f"🌐 Header Host mis à jour: {host_header}")
    
    if "x-request-id" in headers:
        proxy_headers["x-request-id"] = headers["x-request-id"]
    
    print(f"🔄 Proxy vers {provider_key} ({provider_type}): {target_url}")
    
    # Parse et nettoie le body
    try:
        body_json = json.loads(body)
        model_name = body_json.get('model', '')
        original_model = model_name
        
        # Mappe le modèle
        mapped_model = map_model_name(model_name, models)
        if mapped_model != model_name:
            body_json['model'] = mapped_model
            print(f"📝 Modèle mappé: {original_model} → {mapped_model}")
        
        # Nettoyage basique des messages
        for msg in body_json.get('messages', []):
            keys_to_remove = [k for k in msg.keys() if k.startswith('_')]
            for k in keys_to_remove:
                del msg[k]
        
        # Mapping modèle simple
        mapped_model = map_model_name(model_name, models)
        if mapped_model != model_name:
            body_json['model'] = mapped_model
            print(f"📝 Modèle mappé: {original_model} → {mapped_model}")
        
        print(f"📤 Requête: model={body_json.get('model')}, stream={body_json.get('stream', False)}")
        
        # Construction URL et body
        if provider_type == "gemini":
            target_endpoint = build_gemini_endpoint(
                target_url, body_json.get('model'), provider_api_key, body_json.get('stream', False)
            )
            clean_body = json.dumps(convert_to_gemini_format(body_json))
        else:
            target_endpoint = f"{target_url}/chat/completions"
            clean_body = json.dumps(body_json)
    except Exception as e:
        print(f"⚠️ Erreur parsing body: {e}")
        clean_body = body
        target_endpoint = f"{target_url}/chat/completions"
    
    # Envoie la requête
    async with httpx.AsyncClient(timeout=120.0) as client:
        req = client.build_request(
            "POST",
            target_endpoint,
            headers=proxy_headers,
            content=clean_body
        )
        
        body_json = json.loads(clean_body) if isinstance(clean_body, str) else {"stream": False}
        is_streaming = body_json.get('stream', False)
        
        if is_streaming:
            # Streaming avec gestion d'erreurs robuste
            from ...proxy.client import create_proxy_client
            
            proxy_client = create_proxy_client(timeout=120.0, max_retries=2)
            
            try:
                response = await proxy_client.send_streaming(req, provider_type=provider_type)
                
                # Si erreur 4xx/5xx, on log et on retourne l'erreur
                if response.status_code >= 400:
                    try:
                        error_body = await response.aread()
                        error_text = error_body.decode('utf-8', errors='ignore')[:500]
                        print(f"❌ [PROXY] Erreur {response.status_code}: {error_text}")
                        
                        # Gestion spécifique de l'erreur "Message exceeds context limit"
                        if "message exceeds context limit" in error_text.lower() or "context length" in error_text.lower():
                            print(f"🚫 [CONTEXT LIMIT] Erreur provider détectée: {error_text[:100]}...")
                            
                            # Notifie via WebSocket
                            manager = get_connection_manager()
                            await manager.broadcast({
                                "type": "provider_context_limit_error",
                                "session_id": session["id"] if session else None,
                                "error": error_text,
                                "provider": provider_key,
                                "model": body_json.get('model', 'unknown'),
                                "estimated_tokens": request_tokens,
                                "max_context": max_context,
                                "message": "Le provider a rejeté la requête pour dépassement de limite de contexte"
                            })
                            
                            return JSONResponse(
                                content={
                                    "error": "Provider context limit exceeded",
                                    "details": {
                                        "provider": provider_key,
                                        "error_message": error_text,
                                        "estimated_tokens": request_tokens,
                                        "max_context": max_context,
                                        "recommendations": [
                                            "Réduire la taille du contexte historique",
                                            "Utiliser le sanitizer pour nettoyer les messages verbeux",
                                            "Compresser la conversation avec le bouton 'Compresser'",
                                            "Diviser la requête en parties plus petites"
                                        ]
                                    },
                                    "message": f"Le provider {provider_key} a rejeté la requête: limite de contexte dépassée"
                                },
                                status_code=413
                            )
                        
                        return JSONResponse(
                            content={"error": error_text, "code": response.status_code},
                            status_code=response.status_code
                        )
                    except Exception as e:
                        print(f"❌ [PROXY] Erreur {response.status_code}: {e}")
                
                manager = get_connection_manager()
                
                # Pourquoi ces headers: certains clients ont besoin de ces headers SSE
                headers = {
                    "Content-Type": response.headers.get("content-type", "text/event-stream"),
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # Désactive buffering nginx
                }
                
                return StreamingResponse(
                    stream_generator(
                        response, 
                        session["id"] if session else 0, 
                        metric_id,
                        provider_type=provider_type, 
                        models=models, 
                        manager=manager,
                        max_retries=0,  # Retry déjà géré dans send_streaming
                        retry_delay=1.0
                    ),
                    status_code=response.status_code,
                    headers=headers,
                    media_type="text/event-stream"
                )
                
            except httpx.ReadError as e:
                print(f"🔴 [PROXY] ReadError streaming: {e}")
                return JSONResponse(
                    content={
                        "error": "Connexion interrompue par le provider",
                        "detail": str(e),
                        "type": "streaming_error"
                    },
                    status_code=502
                )
                
            except httpx.TimeoutException as e:
                print(f"🔴 [PROXY] Timeout streaming: {e}")
                return JSONResponse(
                    content={
                        "error": "Timeout lors du streaming",
                        "detail": str(e),
                        "type": "timeout_error"
                    },
                    status_code=504
                )
                
            except Exception as e:
                print(f"🔴 [PROXY] Erreur streaming inattendue: {e}")
                return JSONResponse(
                    content={
                        "error": "Erreur streaming",
                        "detail": str(e),
                        "type": "unknown_error"
                    },
                    status_code=500
                )
        else:
            # Non-streaming avec retry
            from ...proxy.client import create_proxy_client
            
            proxy_client = create_proxy_client(timeout=120.0, max_retries=2)
            
            try:
                response = await proxy_client.send(req, provider_type=provider_type)
                
                if response.status_code >= 400:
                    print(f"❌ [PROXY] Erreur {response.status_code}: {response.text[:500]}")
                    
                    # Gestion spécifique de l'erreur "Message exceeds context limit"
                    if "message exceeds context limit" in response.text.lower() or "context length" in response.text.lower():
                        print(f"🚫 [CONTEXT LIMIT] Erreur provider détectée: {response.text[:100]}...")
                        
                        # Notifie via WebSocket
                        manager = get_connection_manager()
                        await manager.broadcast({
                            "type": "provider_context_limit_error",
                            "session_id": session["id"] if session else None,
                            "error": response.text,
                            "provider": provider_key,
                            "model": body_json.get('model', 'unknown'),
                            "estimated_tokens": request_tokens,
                            "max_context": max_context,
                            "message": "Le provider a rejeté la requête pour dépassement de limite de contexte"
                        })
                        
                        return JSONResponse(
                            content={
                                "error": "Provider context limit exceeded",
                                "details": {
                                    "provider": provider_key,
                                    "error_message": response.text,
                                    "estimated_tokens": request_tokens,
                                    "max_context": max_context,
                                    "recommendations": [
                                        "Réduire la taille du contexte historique",
                                        "Utiliser le sanitizer pour nettoyer les messages verbeux",
                                        "Compresser la conversation avec le bouton 'Compresser'",
                                        "Diviser la requête en parties plus petites"
                                    ]
                                },
                                "message": f"Le provider {provider_key} a rejeté la requête: limite de contexte dépassée"
                            },
                            status_code=413
                        )
                    
            except httpx.ReadError as e:
                print(f"🔴 [PROXY] ReadError streaming: {e}")
                return JSONResponse(
                    content={
                        "error": "Connexion interrompue par le provider",
                        "detail": str(e),
                        "type": "streaming_error"
                    },
                    status_code=502
                )
                
            except httpx.TimeoutException as e:
                print(f"🔴 [PROXY] Timeout streaming: {e}")
                return JSONResponse(
                    content={
                        "error": "Timeout lors du streaming",
                        "detail": str(e),
                        "type": "timeout_error"
                    },
                    status_code=504
                )
                
            except Exception as e:
                print(f"🔴 [PROXY] Erreur streaming inattendue: {e}")
                return JSONResponse(
                    content={
                        "error": "Erreur streaming",
                        "detail": str(e),
                        "type": "unknown_error"
                    },
                    status_code=500
                )


# ============================================================================
# RESPONSE HEADERS FILTER
# ============================================================================

def _filter_response_headers(headers: dict) -> dict:
    """
    Filtre les headers de réponse pour éviter les problèmes côté client.
    
    Pourquoi: httpx décompresse automatiquement le corps, mais garde
    les headers content-encoding. Le client essaie alors de décompresser
    un corps déjà décompressé → erreur "incorrect header check".
    """
    filtered = {}
    skip_headers = {
        'content-encoding',  # Déjà décompressé par httpx
        'transfer-encoding',  # Chunked n'a plus de sens
        'content-length',     # La longueur change après décompression
    }
    
    for key, value in headers.items():
        if key.lower() not in skip_headers:
            filtered[key] = value
    
    return filtered


# ============================================================================
# AUTO MEMORY DETECTION HELPER
# ============================================================================

async def _detect_auto_memories(messages: list, session_id: int):
    """
    Helper function pour détecter et stocker les mémoires automatiquement.
    S'exécute en arrière-plan sans bloquer le proxy.
    """
    try:
        stored = await detect_and_store_memories(
            messages=messages,
            session_id=session_id,
            confidence_threshold=0.75  # Seuil élevé pour éviter faux positifs
        )
        
        if stored:
            print(f"🧠 [AUTO MEMORY] {len(stored)} mémoire(s) détectée(s) et stockée(s)")
            # Notifie via WebSocket
            from ...services.websocket_manager import get_connection_manager
            manager = get_connection_manager()
            await manager.broadcast({
                "type": "auto_memory_stored",
                "session_id": session_id,
                "count": len(stored),
                "memories": [
                    {
                        "id": m["id"],
                        "type": m["type"],
                        "confidence": m["confidence"],
                        "reason": m["reason"]
                    }
                    for m in stored
                ]
            })
    except Exception as e:
        print(f"⚠️ [AUTO MEMORY] Erreur: {e}")
