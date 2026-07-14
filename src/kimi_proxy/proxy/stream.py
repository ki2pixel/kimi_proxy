"""
Gestion du streaming et extraction des tokens avec gestion d'erreurs robuste.

Pourquoi cette complexité:
- Les providers peuvent interrompre le stream (ReadError)
- Le réseau peut être instable
- Les timeouts doivent être gérés gracieusement
- Les tokens partiels doivent être extraits même en cas d'erreur
"""
import json
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

import httpx

from ..core.database import update_metric_with_real_tokens, get_session_total_tokens
from ..services.websocket_manager import ConnectionManager
from ..services.alerts import check_threshold_alert
from ..config.display import get_max_context_for_session


# Types d'erreurs streaming connus
STREAMING_ERROR_TYPES = {
    "read_error": "Connexion interrompue par le provider",
    "connect_error": "Impossible de se connecter au provider",
    "timeout_error": "Timeout lors de la lecture du stream",
    "decode_error": "Erreur de décodage des données",
    "unknown": "Erreur streaming inconnue"
}


async def stream_generator(
    response: httpx.Response,
    session_id: int,
    metric_id: int,
    provider_type: str = "openai",
    models: Optional[dict] = None,
    manager: Optional[ConnectionManager] = None
) -> AsyncGenerator[bytes, None]:
    buffer = b""
    first_chunk = True
    chunk_count = 0
    error_occurred = None
    stream_start_time = datetime.now()
    
    try:
        async for chunk in _iter_stream_with_error_handling(response, provider_type):
            chunk_count += 1
            if first_chunk and response.status_code >= 400:
                _log_error_response(chunk, response.status_code)
            first_chunk = False
            
            # Limite le buffer aux derniers 256 Ko pour éviter une consommation mémoire non bornée
            buffer = (buffer + chunk)[-256 * 1024:]
            yield chunk
            
    except Exception as e:
        error_occurred = _handle_stream_exception(e, provider_type, session_id, metric_id, chunk_count, stream_start_time)
    finally:
        await _finalize_stream(buffer, session_id, metric_id, provider_type, models, manager, error_occurred)  # type: ignore

def _handle_stream_exception(e: Exception, provider_type: str, session_id: int, metric_id: int, chunk_count: int, start_time: datetime) -> tuple[str, str]:
    if isinstance(e, httpx.ReadError):
        error_type = "read_error"
    elif isinstance(e, httpx.ConnectError):
        error_type = "connect_error"
    elif isinstance(e, httpx.TimeoutException):
        error_type = "timeout_error"
    else:
        error_type = "unknown"
        
    _log_streaming_error(
        error_type=error_type,
        provider=provider_type,
        session_id=session_id,
        metric_id=metric_id,
        chunks_received=chunk_count,
        error=str(e),
        start_time=start_time
    )
    return (error_type, str(e))

async def _finalize_stream(buffer: bytes, session_id: int, metric_id: int, provider_type: str, models: dict, manager: Optional[ConnectionManager], error_occurred: tuple[str, str] | None):
    if not (metric_id and session_id):
        return
        
    try:
        usage_data = extract_usage_from_stream(buffer, provider_type)
        if usage_data and models and manager:
            await _broadcast_token_update(
                session_id, metric_id, usage_data, models, manager
            )
            
            if error_occurred:
                await _broadcast_streaming_error(
                    session_id, metric_id, error_occurred[0], 
                    manager
                )
    except Exception as e:
        print(f"⚠️  [STREAM] Erreur extraction usage après stream: {e}")


async def _iter_stream_with_error_handling(
    response: httpx.Response,
    provider_type: str
) -> AsyncGenerator[bytes, None]:
    """
    Itère sur le stream avec timeout et gestion d'erreurs.
    
    Pourquoi un timeout de chunk: certains providers peuvent 
    "geler" sans fermer la connexion.
    """
    # Timeout par provider (certains sont plus lents)
    chunk_timeout = {
        "gemini": 60.0,      # Gemini peut être lent
        "kimi": 30.0,        # Kimi est généralement rapide
        "default": 30.0
    }.get(provider_type, 30.0)
    
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    except httpx.ReadTimeout:
        # Timeout spécifique pendant la lecture
        raise httpx.TimeoutException(
            f"Timeout lecture chunk après {chunk_timeout}s"
        )


def _log_error_response(chunk: bytes, status_code: int) -> None:
    """Log une réponse d'erreur API."""
    try:
        error_text = chunk.decode('utf-8', errors='ignore')[:500]
        print(f"❌ [STREAM] Erreur API {status_code}: {error_text}")
    except Exception:
        pass  # nosec B110


def _log_streaming_error(
    error_type: str,
    provider: str,
    session_id: int,
    metric_id: int,
    chunks_received: int,
    error: str,
    start_time: datetime
) -> None:
    """
    Log structuré d'une erreur streaming.
    
    Pourquoi cette structure: permet de parser les logs
    pour des dashboards de monitoring provider.
    """
    duration = (datetime.now() - start_time).total_seconds()
    error_msg = STREAMING_ERROR_TYPES.get(error_type, STREAMING_ERROR_TYPES["unknown"])
    
    print(
        f"🔴 [STREAM_ERROR] {error_msg}\n"
        f"   Provider: {provider}\n"
        f"   Session: {session_id}, Metric: {metric_id}\n"
        f"   Chunks reçus: {chunks_received}\n"
        f"   Durée: {duration:.2f}s\n"
        f"   Détail: {error[:200]}"
    )


async def _broadcast_streaming_error(
    session_id: int,
    metric_id: int,
    error_type: str,
    
    manager: ConnectionManager
) -> None:
    """Diffuse une erreur streaming via WebSocket."""
    try:
        await manager.broadcast({
            "type": "streaming_error",
            "session_id": session_id,
            "metric_id": metric_id,
            "error_type": error_type,
            "error_message": STREAMING_ERROR_TYPES.get(
                error_type, STREAMING_ERROR_TYPES["unknown"]
            ),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        # Ne jamais laisser le broadcast casser le flux
        print(f"⚠️  [STREAM] Erreur broadcast WebSocket: {e}")


async def _broadcast_token_update(
    session_id: int,
    metric_id: int,
    usage_data: Dict[str, int],
    models: dict,
    manager: ConnectionManager
):
    """Diffuse la mise à jour des tokens via WebSocket."""
    from ..core.database import get_session_by_id
    
    session = get_session_by_id(session_id)
    max_context = get_max_context_for_session(session, models)  # type: ignore
    
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


def extract_usage_from_stream(buffer: bytes, provider_type: str = "openai") -> Optional[Dict[str, int]]:
    """
    Extrait les usage tokens du stream SSE.
    
    Pourquoi on cherche dans les lignes inversées:
    - Les tokens d'usage sont généralement dans le dernier chunk
    - Format SSE: data: {...} par ligne
    - [DONE] marque la fin du stream
    
    Args:
        buffer: Buffer contenant tout le stream (même partiel)
        provider_type: Type de provider
        
    Returns:
        Dictionnaire avec prompt_tokens, completion_tokens, total_tokens
        ou None si pas trouvé
    """
    if not buffer:
        return None
        
    text = buffer.decode('utf-8', errors='ignore')
    lines = text.strip().split('\n')
    
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
                
                # Format Gemini
                if provider_type == "gemini":
                    if 'usageMetadata' in data:
                        meta = data['usageMetadata']
                        return {
                            "prompt_tokens": meta.get("promptTokenCount", 0),
                            "completion_tokens": meta.get("candidatesTokenCount", 0),
                            "total_tokens": meta.get("totalTokenCount", 0)
                        }
                        
            except json.JSONDecodeError:
                # Ligne malformée - on continue
                continue
            except Exception:
                # Autre erreur - on continue
                continue  # nosec B112
    
    return None


def extract_usage_from_response(response_data: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """
    Extrait les usage tokens d'une réponse complète (non-streaming).
    
    Args:
        response_data: Données JSON de la réponse (dict ou list pour Gemini)
        
    Returns:
        Dictionnaire avec prompt_tokens, completion_tokens, total_tokens
    """
    # Gemini peut retourner une liste au lieu d'un dict
    if isinstance(response_data, list) and len(response_data) > 0:
        response_data = response_data[0]
    
    if not isinstance(response_data, dict):
        return None
    
    usage = response_data.get('usage', {})
    if usage:
        return {
            "prompt_tokens": usage.get('prompt_tokens', 0),
            "completion_tokens": usage.get('completion_tokens', 0),
            "total_tokens": usage.get('total_tokens', 0)
        }
    return None
