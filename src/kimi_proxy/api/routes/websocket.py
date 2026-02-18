"""
Route WebSocket pour les mises à jour temps réel.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...services.websocket_manager import get_connection_manager
from ...core.database import get_active_session, get_session_stats

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
        
        # Garde la connexion ouverte et écoute les messages entrants
        while True:
            data = await websocket.receive_text()
            # Traitement des messages entrants si nécessaire
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"⚠️ Erreur WebSocket: {e}")
        manager.disconnect(websocket)
