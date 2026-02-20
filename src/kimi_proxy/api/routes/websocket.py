"""
Route WebSocket pour les mises à jour temps réel.
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...services.websocket_manager import get_connection_manager
from ...core.database import get_active_session, get_session_stats
from ...api.routes.memory import WEBSOCKET_HANDLERS

router = APIRouter()


@router.websocket("/ws")
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
    manager = get_connection_manager()
    await manager.connect(websocket)

    try:
        # Envoie l'état initial
        session = get_active_session()
        if session:
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
