"""
Kimi Proxy Dashboard - Application FastAPI Factory.
Proxy streaming + SQLite + WebSockets pour monitoring temps réel.
Intégration Log Watcher pour PyCharm/Continue.
"""
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .core.database import init_database, create_session, get_active_session
from .config.loader import load_config
from .services.websocket_manager import create_connection_manager
from .services.cline_polling import ClinePollingConfig, create_cline_polling_service
from .features.log_watcher import create_log_watcher
from .api.router import api_router
from .api.routes.health import set_log_watcher


def _get_log_source_family(source_type: str, metrics) -> str:
    """Normalise une source analytics pour le backend et le dashboard."""
    if source_type in {"compile_chat", "continue_compile_chat"} or metrics.is_compile_chat:
        return "continue_compile"
    if source_type in {
        "api_error",
        "continue_api_error",
        "kimi_global_error",
        "kimi_global_context_limit_error",
        "kimi_global_auth_error",
        "kimi_global_request_error",
        "kimi_global_transport_error",
        "kimi_global_runtime_error",
    } or metrics.is_api_error:
        return "error"
    if source_type in {"logs", "continue_logs"}:
        return "continue_logs"
    if source_type == "kimi_global":
        return "kimi_global"
    if source_type.startswith("kimi_session"):
        return "kimi_session"
    return source_type or "logs"


def _get_log_source_label(source_type: str, source_family: str) -> str:
    """Retourne un libellé frontend rétrocompatible pour la source."""
    if source_family == "continue_compile":
        return "CompileChat Continue"
    if source_family == "error":
        if source_type == "kimi_global_context_limit_error":
            return "Limite de contexte Kimi"
        if source_type == "kimi_global_auth_error":
            return "Erreur auth Kimi"
        if source_type == "kimi_global_request_error":
            return "Erreur requête Kimi"
        if source_type == "kimi_global_transport_error":
            return "Erreur transport Kimi"
        if source_type == "kimi_global_runtime_error":
            return "Erreur runtime Kimi"
        if source_type == "kimi_global_error":
            return "Erreur Kimi globale"
        if source_type == "continue_api_error":
            return "Erreur Continue"
        return "Erreur analytics"
    if source_family == "continue_logs":
        return "Logs Continue"
    if source_family == "kimi_global":
        return "Log global Kimi"
    if source_family == "kimi_session":
        return "Session Kimi"
    return source_type or "Logs"


def _looks_like_context_limit_error(source_type: str, metrics) -> bool:
    if source_type == "kimi_global_context_limit_error":
        return True

    raw_line = (metrics.raw_line or "").lower()
    if metrics.total_tokens > 0 or metrics.context_length > 0:
        return True

    context_keywords = (
        "message exceeds context limit",
        "context length",
        "context window",
        "maximum context",
        "input_token_count",
        "too many tokens",
    )
    return any(keyword in raw_line for keyword in context_keywords)


def _format_log_error_message(source_type: str, metrics) -> str:
    if _looks_like_context_limit_error(source_type, metrics):
        token_label = metrics.total_tokens if metrics.total_tokens > 0 else "inconnus"
        return f"⚠️ [API ERROR] Tokens: {token_label} (limite de contexte atteinte)"

    if source_type == "kimi_global_auth_error":
        return "⚠️ [API ERROR] Authentification Kimi refusée"
    if source_type == "kimi_global_request_error":
        return "⚠️ [API ERROR] Requête Kimi invalide détectée"
    if source_type == "kimi_global_transport_error":
        return "⚠️ [API ERROR] Erreur réseau/timeout Kimi"
    if source_type == "kimi_global_runtime_error":
        return "⚠️ [API ERROR] Erreur runtime Kimi détectée"
    if source_type == "continue_api_error":
        return "⚠️ [API ERROR] Erreur Continue détectée"
    return "⚠️ [API ERROR] Erreur provider détectée"


def _should_emit_error_log(
    error_log_cache: dict[str, float],
    rendered_message: str,
    now_ts: float,
    cooldown_seconds: float = 2.0,
) -> bool:
    """Évite de spammer la console avec la même erreur à très courte échéance."""
    last_seen_ts = error_log_cache.get(rendered_message)
    if last_seen_ts is not None and (now_ts - last_seen_ts) < cooldown_seconds:
        return False

    error_log_cache[rendered_message] = now_ts

    expired_messages = [
        message
        for message, seen_ts in error_log_cache.items()
        if (now_ts - seen_ts) >= cooldown_seconds
    ]
    for expired_message in expired_messages:
        if expired_message != rendered_message:
            error_log_cache.pop(expired_message, None)

    return True


def create_app() -> FastAPI:
    """
    Factory pour créer l'application FastAPI.
    
    Returns:
        Instance configurée de FastAPI
    """
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Gestion du cycle de vie de l'application."""
        # Startup
        _startup(app)
        yield
        # Shutdown
        await _shutdown(app)
    
    app = FastAPI(
        title="Kimi Proxy Dashboard",
        description="Proxy transparent avec monitoring temps réel de tokens LLM",
        version="2.0.0",
        lifespan=lifespan
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount fichiers statiques
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Inclusion des routes API
    app.include_router(api_router)
    
    # Route favicon.ico pour éviter les erreurs 404
    @app.get("/favicon.ico")
    async def favicon():
        favicon_path = os.path.join(static_dir, "favicon.ico")
        if os.path.exists(favicon_path):
            from fastapi.responses import FileResponse
            return FileResponse(favicon_path)
        
        # Fallback: répondre 204 No Content pour éviter l'erreur
        from fastapi.responses import Response
        return Response(status_code=204)
    
    # Route principale (dashboard)
    @app.get("/", response_class=HTMLResponse)
    async def get_dashboard():
        html_file = os.path.join(static_dir, "index.html")
        if os.path.exists(html_file):
            with open(html_file, "r", encoding="utf-8") as f:
                return f.read()
        return HTMLResponse(content="<h1>Dashboard non trouvé</h1>", status_code=404)
    
    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """
        Endpoint WebSocket pour les mises à jour temps réel.

        Envoie:
        - Initialisation avec la session active
        - Mises à jour de métriques en temps réel
        - Alertes de seuils
        - Événements de routing/sanitizer

        Reçoit:
        - Messages de commandes (compression, similarité, etc.)
        """
        manager = create_connection_manager()
        await manager.connect(websocket)

        try:
            # Envoie l'état initial
            session = get_active_session()
            if session:
                from .core.database import get_session_stats
                stats = get_session_stats(session["id"])
                await websocket.send_json({
                    "type": "init",
                    "session": session,
                    **stats
                })

            # Garde la connexion ouverte et traite les messages entrants
            while True:
                data_raw = await websocket.receive_text()
                try:
                    import json
                    from .api.routes.memory import WEBSOCKET_HANDLERS
                    
                    data = json.loads(data_raw)
                    message_type = data.get("type")

                    # Dispatch vers le handler approprié
                    if message_type in WEBSOCKET_HANDLERS:
                        handler = WEBSOCKET_HANDLERS[message_type]
                        await handler(websocket, data)
                    else:
                        print(f"⚠️ Type de message WebSocket inconnu: {message_type}")

                except json.JSONDecodeError as e:
                    print(f"⚠️ Message WebSocket invalide JSON: {e}")
                except Exception as e:
                    print(f"⚠️ Erreur traitement message WebSocket: {e}")

        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception as e:
            print(f"⚠️ Erreur WebSocket: {e}")
            manager.disconnect(websocket)
    
    return app


def _startup(app: FastAPI):
    """Initialisation au démarrage."""
    print("🚀 Démarrage du Kimi Proxy Dashboard...")
    
    # Charge la configuration
    config = load_config()
    providers = config.get("providers", {})
    models = config.get("models", {})
    
    print(f"✅ {len(providers)} provider(s) chargé(s)")
    print(f"✅ {len(models)} modèle(s) chargé(s)")
    
    # Initialise la base de données
    init_database()
    
    # Crée une session par défaut si aucune
    if not get_active_session():
        provider_key = "managed:kimi-code"
        create_session("Session par défaut", provider_key)
        print(f"✅ Session par défaut créée (provider: {provider_key})")
    
    # Démarre le Log Watcher
    manager = create_connection_manager()
    error_log_cache: dict[str, float] = {}
    
    async def broadcast_log_metrics(metrics, watcher):
        """Callback pour diffuser les métriques du log watcher."""
        from .core.database import get_active_session
        from .config.display import get_max_context_for_session
        
        session = get_active_session()
        if not session:
            return
        
        max_context = watcher.get_max_context(
            get_max_context_for_session(session, models)
        )
        total_tokens = metrics.total_tokens
        percentage = (total_tokens / max_context) * 100 if max_context > 0 else 0
        
        # Préserve les nouvelles sources enrichies quand elles sont disponibles.
        source_type = metrics.source or "logs"
        if source_type == "logs":
            if metrics.is_compile_chat:
                source_type = "compile_chat"
            elif metrics.is_api_error:
                source_type = "api_error"
        source_family = _get_log_source_family(source_type, metrics)
        source_label = _get_log_source_label(source_type, source_family)
        
        message = {
            "type": "log_metric",
            "source": source_type,
            "source_family": source_family,
            "source_label": source_label,
            "metrics": {
                "prompt_tokens": metrics.prompt_tokens,
                "completion_tokens": metrics.completion_tokens,
                "tools_tokens": metrics.tools_tokens,
                "system_message_tokens": metrics.system_message_tokens,
                "total_tokens": total_tokens,
                "context_length": metrics.context_length or max_context,
                "max_context": max_context,
                "percentage": percentage
            },
            "session_id": session["id"],
            "timestamp": datetime.now().isoformat()
        }
        
        await manager.broadcast(message)
        
        # Log détaillé selon le type
        if source_family == "continue_compile":
            print(f"📊 [COMPILE] Context: {metrics.context_length}, "
                  f"Tools: {metrics.tools_tokens}, "
                  f"System: {metrics.system_message_tokens} "
                  f"= {total_tokens} ({percentage:.1f}%)")
        elif source_family == "error":
            rendered_error = _format_log_error_message(source_type, metrics)
            if _should_emit_error_log(error_log_cache, rendered_error, time.monotonic()):
                print(rendered_error)
        elif source_family == "kimi_global":
            print(f"📊 [KIMI GLOBAL] Context: {metrics.context_length} ({percentage:.1f}%)")
        elif source_family == "kimi_session":
            print(f"📊 [KIMI SESSION] Tokens: {total_tokens} ({percentage:.1f}%)")
        elif total_tokens > 100:
            print(f"📊 [LOGS] Tokens: {total_tokens} ({percentage:.1f}%)")
    
    log_watcher = create_log_watcher(broadcast_callback=broadcast_log_metrics)

    # Démarre le polling Cline (ledger local) + broadcast WS (optionnel)
    cline_polling_raw = config.get("cline", {}).get("polling", {})
    try:
        cline_polling_enabled = bool(cline_polling_raw.get("enabled", True))
        cline_interval_seconds = float(cline_polling_raw.get("interval_seconds", 60.0))
        cline_backoff_max_seconds = float(cline_polling_raw.get("backoff_max_seconds", 600.0))
    except (TypeError, ValueError):
        cline_polling_enabled = True
        cline_interval_seconds = 60.0
        cline_backoff_max_seconds = 600.0

    cline_polling_config = ClinePollingConfig(
        enabled=cline_polling_enabled,
        interval_seconds=max(cline_interval_seconds, 5.0),
        # backoff >= interval (sinon on clamp au minimum fonctionnel)
        backoff_max_seconds=max(cline_backoff_max_seconds, max(cline_interval_seconds, 30.0)),
    )
    cline_polling = create_cline_polling_service(manager=manager, config=cline_polling_config)
    
    # Stocke le log watcher dans l'app state
    app.state.log_watcher = log_watcher
    app.state.cline_polling = cline_polling
    app.state.config = config
    
    # Enregistre pour le health check
    set_log_watcher(log_watcher)
    
    # Démarre le watcher (dans la lifespan async)
    import asyncio
    asyncio.create_task(log_watcher.start())

    # Démarre le polling Cline (tâche asyncio)
    asyncio.create_task(cline_polling.start())
    
    print(f"🌐 Dashboard disponible sur http://localhost:8000")


async def _shutdown(app: FastAPI):
    """Arrêt de l'application."""
    print("\n👋 Arrêt du serveur...")
    
    # Arrête le Log Watcher
    if hasattr(app.state, 'log_watcher'):
        await app.state.log_watcher.stop()

    # Arrête le polling Cline
    if hasattr(app.state, 'cline_polling'):
        await app.state.cline_polling.stop()
    
    print("✅ Serveur arrêté proprement")


# Crée l'application pour uvicorn
app = create_app()
