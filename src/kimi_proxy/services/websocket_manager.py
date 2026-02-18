"""
Gestionnaire de connexions WebSocket.
"""
from typing import Set, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket


class ConnectionManager:
    """Gère les connexions WebSocket actives."""
    
    def __init__(self):
        self.active_connections: Set["WebSocket"] = set()
    
    async def connect(self, websocket: "WebSocket"):
        """Accepte une nouvelle connexion WebSocket."""
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: "WebSocket"):
        """Déconnecte une connexion WebSocket."""
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Diffuse un message à toutes les connexions actives.
        
        Args:
            message: Message à diffuser (sera converti en JSON)
        """
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Nettoie les connexions déconnectées
        for conn in disconnected:
            self.active_connections.discard(conn)
    
    async def send_to(self, websocket: "WebSocket", message: Dict[str, Any]) -> bool:
        """
        Envoie un message à une connexion spécifique.
        
        Args:
            websocket: Connexion cible
            message: Message à envoyer
            
        Returns:
            True si envoyé avec succès, False sinon
        """
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            self.active_connections.discard(websocket)
            return False
    
    def get_connection_count(self) -> int:
        """Retourne le nombre de connexions actives."""
        return len(self.active_connections)
    
    def is_connected(self, websocket: "WebSocket") -> bool:
        """Vérifie si une connexion est active."""
        return websocket in self.active_connections


# Instance globale du gestionnaire
_manager: Optional[ConnectionManager] = None


def create_connection_manager() -> ConnectionManager:
    """
    Crée ou retourne l'instance globale du gestionnaire de connexions.
    
    Returns:
        Instance de ConnectionManager
    """
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


def get_connection_manager() -> ConnectionManager:
    """
    Alias de create_connection_manager pour compatibilité.
    """
    return create_connection_manager()
