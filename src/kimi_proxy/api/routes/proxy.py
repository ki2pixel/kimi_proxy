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
from ...features.sanitizer import sanitize_messages
from ...features.mcp import (
    analyze_mcp_memory_in_messages, 
    save_memory_metrics,
    detect_and_store_memories,
)
from ...features.sanitizer.routing import route_dynamic_model
from ...proxy.router import get_target_url_for_session, get_provider_host_header, map_model_name
from ...proxy.transformers import convert_to_gemini_format, build_gemini_endpoint
from ...proxy.stream import stream_generator, extract_usage_from_response
from ...proxy.tool_utils import validate_and_fix_tool_calls
from ...core.auto_session import process_auto_session

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
    
    # Récupère la configuration
    config = get_config()
    providers = config.get("providers", {})
    models = config.get("models", {})
    sanitizer_config = config.get("sanitizer", {})
    
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
            mcp_result = analyze_mcp_memory_in_messages(original_messages)
            mcp_memory_analysis = mcp_result.to_dict()
            if mcp_memory_analysis['has_memory']:
                print(f"🧠 [MCP MEMORY] Détecté: {mcp_memory_analysis['memory_tokens']} tokens mémoire "
                      f"({mcp_memory_analysis['memory_ratio']:.1f}%) - "
                      f"{mcp_memory_analysis['segment_count']} segment(s)")
        
        # Sanitizer (Phase 1)
        if original_messages and sanitizer_config.get("enabled", True):
            sanitized_messages, masking_metadata = sanitize_messages(
                original_messages,
                config={
                    "enabled": True,
                    "threshold_tokens": sanitizer_config.get("threshold_tokens", 1000),
                    "preview_length": sanitizer_config.get("preview_length", 200)
                }
            )
            
            if masking_metadata["masked_count"] > 0:
                body_json["messages"] = sanitized_messages
                sanitized_body = json.dumps(body_json).encode('utf-8')
                print(f"🧹 [SANITIZER] {masking_metadata['masked_count']} message(s) nettoyé(s), "
                      f"~{masking_metadata['tokens_saved']} tokens économisés")
        
        body = sanitized_body
    except Exception as e:
        print(f"⚠️ [SANITIZER/MCP] Erreur lors de l'analyse: {e}")
    
    # ============================================================================
    # AUTO SESSION: Détection et création automatique de session
    # ============================================================================
    session_created = False
    try:
        if 'body_json' in locals() and body_json:
            session, session_created = process_auto_session(body_json, get_active_session())
            if session_created:
                # Notifie le frontend via WebSocket
                manager = get_connection_manager()
                await manager.broadcast({
                    "type": "auto_session_created",
                    "session": session,
                    "message": f"Nouvelle session auto créée: {session.get('name')}"
                })
    except Exception as e:
        print(f"⚠️ [AUTO SESSION] Erreur: {e}")
        session = get_active_session()
        session_created = False
    
    if not session:
        session = get_active_session()
    
    max_context = get_max_context_for_session(session, models, DEFAULT_MAX_CONTEXT)
    target_url = get_target_url_for_session(session, providers)
    provider_key = session.get("provider", "managed:kimi-code") if session else "managed:kimi-code"
    
    # ============================================================================
    # Calcul des tokens
    # ============================================================================
    estimated_tokens = 0
    percentage = 0
    content_preview = ""
    request_tokens = 0
    
    try:
        json_body = json.loads(body)
        messages = json_body.get("messages", [])
        
        # ============================================================================
        # IDENTIFICATION DU "CONTEXTE FANTÔME"
        # ============================================================================
        # Calcule la taille du message système vs l'historique
        system_message_tokens = 0
        history_tokens = 0
        user_message_tokens = 0
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            msg_tokens = count_tokens_tiktoken([msg])
            
            if role == "system":
                system_message_tokens += msg_tokens
            elif role == "user":
                user_message_tokens += msg_tokens
                # Le dernier message utilisateur est le "nouveau" contenu
            else:  # assistant, etc.
                history_tokens += msg_tokens
        
        history_tokens += user_message_tokens  # Tous les messages sauf système = historique
        
        # Log console pour identifier le contexte fantôme
        print(f"\n📊 [CONTEXT BREAKDOWN] Session: {session['id'] if session else 'N/A'}")
        print(f"   ├─ Message Système: {system_message_tokens:,} tokens ({system_message_tokens/max(request_tokens, 1)*100:.1f}%)")
        print(f"   ├─ Historique:      {history_tokens:,} tokens ({history_tokens/max(request_tokens, 1)*100:.1f}%)")
        print(f"   └─ Total Requête:   {request_tokens:,} tokens")
        
        if system_message_tokens > 5000:
            print(f"   ⚠️  [GHOST CONTEXT] Système > 5k tokens! Vérifiez le prompt système.")
        if len(messages) > 20:
            print(f"   ⚠️  [LONG HISTORY] {len(messages)} messages dans l'historique")
        
        
        # Vérifie si on doit faire un fallback de modèle
        if session and request_tokens > 0:
            updated_session, routing_notification = await route_dynamic_model(
                session, request_tokens, models
            )
            if routing_notification:
                session = updated_session
                max_context = get_max_context_for_session(session, models)
                manager = get_connection_manager()
                await manager.broadcast({
                    "type": "sanitizer_event",
                    "event": routing_notification,
                    "session_id": session["id"]
                })
                print(f"🔄 [ROUTING] Notification envoyée: {routing_notification['message']}")
        
        # Récupère les tokens cumulés pour les stats (facturation)
        cumulative_totals = get_session_cumulative_tokens(session["id"]) if session else {"total_tokens": 0}
        cumulative_tokens = cumulative_totals["total_tokens"]
        
        # La JAUGE montre uniquement les tokens de la requête ACTUELLE
        # (Le contexte LLM est stateless - chaque requête contient tout le contexte)
        # C'est request_tokens qui représente le remplissage réel de la fenêtre
        total_current = request_tokens  # PAS cumulative + request
        percentage = (total_current / max_context) * 100
        
        # Extrait un aperçu du contenu
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
    
    # ============================================================================
    # Sauvegarde en DB et broadcast
    # ============================================================================
    metric_id = None
    if session and content_preview and not is_system_message(content_preview):
        print(f"📊 [PROXY] Contexte actuel: {request_tokens:,} tokens ({percentage:.1f}%) - Cumul facturé: {cumulative_tokens:,} - {content_preview[:50]}...")
        
        update_session_first_prompt(session["id"], content_preview)
        
        # Sauvegarde aussi les métriques mémoire si présentes
        if mcp_memory_analysis.get('has_memory'):
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
            memory_tokens=mcp_memory_analysis.get('memory_tokens', 0),
            chat_tokens=mcp_memory_analysis.get('chat_tokens', 0),
            memory_ratio=mcp_memory_analysis.get('memory_ratio', 0)
        )
        
        alert = check_threshold_alert(percentage)
        manager = get_connection_manager()
        
        # Calcule le delta (nouveau contenu ajouté = dernier message utilisateur)
        delta_tokens = user_message_tokens if 'user_message_tokens' in locals() else 0
        
        await manager.broadcast({
            "type": "metric",
            "metric": {
                "id": metric_id,
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "estimated_tokens": request_tokens,  # Taille totale de la requête (contexte)
                "cumulative_tokens": total_current,   # Pour compatibilité (même que estimated)
                "cumulative_billing": cumulative_tokens,  # Total facturé (cumul)
                "delta_tokens": delta_tokens,         # Nouveau contenu réel ajouté
                "system_tokens": system_message_tokens if 'system_message_tokens' in locals() else 0,
                "history_tokens": history_tokens if 'history_tokens' in locals() else 0,
                "percentage": percentage,
                "content_preview": content_preview,
                "is_estimated": True,
                "source": "proxy"
            },
            "session_id": session["id"],
            "session_updated": True,
            "alert": alert,
            "sanitizer": masking_metadata if masking_metadata.get("masked_count", 0) > 0 else None,
            "mcp_memory": mcp_memory_analysis if mcp_memory_analysis.get('has_memory') else None
        })
        
        # WebSocket event spécifique pour métriques mémoire
        if mcp_memory_analysis.get('has_memory'):
            await manager.broadcast({
                "type": "memory_metrics_update",
                "session_id": session["id"],
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "memory": {
                    "memory_tokens": mcp_memory_analysis['memory_tokens'],
                    "chat_tokens": mcp_memory_analysis['chat_tokens'],
                    "total_tokens": mcp_memory_analysis['total_tokens'],
                    "memory_ratio": mcp_memory_analysis['memory_ratio'],
                    "segment_count": mcp_memory_analysis['segment_count']
                }
            })
    
    # ============================================================================
    # VÉRIFICATION PROACTIVE DE LIMITE DE CONTEXTE
    # ============================================================================
    context_violation = check_context_limit_violation(
        request_tokens, max_context, session["id"] if session else None
    )
    
    if context_violation:
        print(f"🚫 [CONTEXT LIMIT] Requête rejetée: {request_tokens:,} tokens > {max_context:,} limite")
        print(f"   Ratio violation: {context_violation['violation_ratio']:.2f}")
        print(f"   Recommandations: {', '.join(context_violation['recommendations'])}")
        
        # Notifie via WebSocket
        manager = get_connection_manager()
        await manager.broadcast({
            "type": "context_limit_violation",
            "session_id": session["id"] if session else None,
            "violation": context_violation,
            "message": f"Requête trop volumineuse ({request_tokens:,} tokens) - {context_violation['recommendations'][0]}"
        })
        
        # Retourne une erreur explicite
        return JSONResponse(
            content={
                "error": "Context limit exceeded",
                "details": context_violation,
                "message": f"Requête de {request_tokens:,} tokens dépasse la limite de {max_context:,} tokens",
                "recommendations": context_violation["recommendations"]
            },
            status_code=413  # Payload Too Large
        )
    
    print(f"✅ [CONTEXT CHECK] Requête validée: {request_tokens:,} tokens ({percentage:.1f}%)")

    # ============================================================================
    # MONITORING DE PERFORMANCE CONTEXTE
    # ============================================================================
    try:
        # Calcule les métriques de contexte pour monitoring
        context_metrics = {
            "session_id": session["id"] if session else None,
            "estimated_tokens": request_tokens,
            "max_context": max_context,
            "usage_percentage": percentage,
            "system_tokens": system_message_tokens if 'system_message_tokens' in locals() else 0,
            "history_tokens": history_tokens if 'history_tokens' in locals() else 0,
            "user_tokens": user_message_tokens if 'user_message_tokens' in locals() else 0,
            "mcp_memory_tokens": mcp_memory_analysis.get('memory_tokens', 0) if 'mcp_memory_analysis' in locals() else 0,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
        # Vérifie les seuils d'alerte personnalisés pour le contexte
        context_alert = create_context_limit_alert(context_metrics)
        if context_alert:
            manager = get_connection_manager()
            await manager.broadcast({
                "type": "context_performance_alert",
                "alert": context_alert,
                "metrics": context_metrics,
                "session_id": session["id"] if session else None,
                "message": f"Alerte contexte: {context_alert['level']} - {context_alert['message']}"
            })
            print(f"⚠️ [CONTEXT MONITOR] {context_alert['level']}: {context_alert['message']}")
            
    except Exception as e:
        print(f"⚠️ [CONTEXT MONITOR] Erreur monitoring: {e}")

    # ============================================================================
    # Rate Limiting
    # ============================================================================
    rate_limiter = get_rate_limiter()
    rate_status = await rate_limiter.throttle_if_needed()
    
    if provider_key in ["nvidia", "mistral", "openrouter"]:
        rate_alert = rate_limiter.check_alert()
        if rate_alert:
            print(f"{rate_alert}")
    
    # ============================================================================
    # PROXY VERS LE PROVIDER
    # ============================================================================
    return await _proxy_to_provider(
        body=body,
        headers=headers,
        provider_key=provider_key,
        providers=providers,
        models=models,
        target_url=target_url,
        session=session,
        metric_id=metric_id,
        max_context=max_context
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
    max_context: int
):
    """Effectue le proxy vers le provider."""
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
        
        # Nettoyage des messages pour compatibilité API stricte (Mistral, etc.)
        # Supprime les clés internes commençant par underscore (_masked, _original_hash, etc.)
        for msg in body_json.get('messages', []):
            keys_to_remove = [k for k in msg.keys() if k.startswith('_')]
            for k in keys_to_remove:
                del msg[k]
        
        # Validation et correction des tool calls (NVIDIA, etc.)
        body_json, tool_stats = validate_and_fix_tool_calls(body_json)
        if tool_stats["fixed_ids"] > 0:
            print(f"🔧 [TOOL CALLS] {tool_stats['fixed_ids']} ID(s) corrigé(s) sur {tool_stats['total_tool_calls']} tool calls")
            if tool_stats["invalid_ids"]:
                print(f"   IDs invalides détectés: {tool_stats['invalid_ids']}")
        
        # Validation des tools pour Groq (limite 128 outils maximum)
        if provider_key == "groq":
            tools = body_json.get('tools', [])
            if len(tools) > 128:
                print(f"⚠️ [GROQ TOOLS LIMIT] {len(tools)} outils détectés, limite à 128 (troncature)")
                body_json['tools'] = tools[:128]
        
        print(f"📤 Requête: model={body_json.get('model')}, stream={body_json.get('stream', False)}")
        
        # Construction de l'URL cible
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
                print(f"🔴 [PROXY] ReadError: {e}")
                return JSONResponse(
                    content={
                        "error": "Erreur de lecture",
                        "detail": str(e)
                    },
                    status_code=502
                )
                
            except httpx.TimeoutException as e:
                print(f"🔴 [PROXY] Timeout: {e}")
                return JSONResponse(
                    content={
                        "error": "Timeout",
                        "detail": str(e)
                    },
                    status_code=504
                )
            
            # Extrait les tokens de la réponse
            if metric_id and session:
                try:
                    response_data = response.json()
                    usage = extract_usage_from_response(response_data)
                    if usage:
                        print(f"✅ Vrais tokens reçus (non-stream): {usage}")
                        
                        real_data = update_metric_with_real_tokens(
                            metric_id,
                            usage["prompt_tokens"],
                            usage["completion_tokens"],
                            usage["total_tokens"],
                            max_context
                        )
                        
                        new_totals = get_session_total_tokens(session["id"])
                        cumulative_total = new_totals["total_tokens"]
                        cumulative_percentage = (cumulative_total / max_context) * 100
                        
                        alert = check_threshold_alert(cumulative_percentage)
                        manager = get_connection_manager()
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
                    print(f"⚠️ Erreur extraction usage (non-stream): {e}")
            
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
                headers=_filter_response_headers(dict(response.headers))
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
