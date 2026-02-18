"""
Client MCP spécialisé pour Sequential Thinking.

Gère le raisonnement séquentiel structuré pour résolution de problèmes complexes.
Performance: <30-60s pour raisonnement complexe.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..base.rpc import MCPRPCClient

# Modèles imports avec TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_proxy.core.models import SequentialThinkingStep, MCPPhase4ServerStatus
    from ..base.config import MCPClientConfig


class SequentialThinkingMCPClient:
    """
    Client spécialisé pour Sequential Thinking MCP.
    
    Supporte le pattern de pensée séquentielle:
    - thought: Pensée actuelle
    - thought_number: Numéro d'ordre
    - total_thoughts: Total prévu
    - next_thought_needed: Nécessité de continuer
    - branches: Alternatives explorées
    
    Use cases:
    - Déconnexion de problèmes complexes
    - Analyse d'algorithmes
    - Debugging systématique
    - Prise de décision structurée
    """
    
    def __init__(self, config: "MCPClientConfig", rpc_client: MCPRPCClient):
        """
        Initialise le client Sequential Thinking MCP.
        
        Args:
            config: Configuration MCP
            rpc_client: Client RPC de base
        """
        self.config = config
        self.rpc_client = rpc_client
        self._status: Optional["MCPPhase4ServerStatus"] = None
    
    async def check_status(self) -> "MCPPhase4ServerStatus":
        """
        Vérifie le statut du serveur Sequential Thinking MCP.
        
        Teste avec une pensée minimale.
        
        Returns:
            Status du serveur
        """
        from kimi_proxy.core.models import MCPPhase4ServerStatus
        
        try:
            start_time = datetime.now()
            
            # Appel minimal pour tester la connectivité
            result = await self.rpc_client.make_rpc_call(
                server_url=self.config.sequential_thinking_url,
                method="sequentialthinking_tools",
                params={
                    "thought": "Test de connexion MCP",
                    "thought_number": 1,
                    "total_thoughts": 1,
                    "next_thought_needed": False
                },
                timeout_ms=2000.0,
                api_key=self.config.sequential_thinking_api_key
            )
            
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            self._status = MCPPhase4ServerStatus(
                name="sequential-thinking-mcp",
                type="sequential_thinking",
                url=self.config.sequential_thinking_url,
                connected=True,
                last_check=datetime.now().isoformat(),
                latency_ms=latency_ms,
                tools_count=1,
                capabilities=["sequential_thinking", "problem_solving", "analysis"]
            )
            return self._status
            
        except Exception as e:
            self._status = MCPPhase4ServerStatus(
                name="sequential-thinking-mcp",
                type="sequential_thinking",
                url=self.config.sequential_thinking_url,
                connected=False,
                last_check=datetime.now().isoformat(),
                error_count=1,
                tools_count=1,
                capabilities=[]
            )
            return self._status
    
    async def call_tool(
        self,
        thought: str,
        thought_number: int = 1,
        total_thoughts: int = 5,
        next_thought_needed: bool = True,
        available_mcp_tools: Optional[List[str]] = None
    ) -> "SequentialThinkingStep":
        """
        Appelle l'outil de raisonnement séquentiel.
        
        Pattern de pensée étape par étape avec exploration des branches.
        
        Args:
            thought: Pensée actuelle à analyser
            thought_number: Numéro de cette pensée (1-based)
            total_thoughts: Nombre total de pensées prévues
            next_thought_needed: Si une prochaine pensée est nécessaire
            available_mcp_tools: Liste des outils MCP disponibles pour l'analyse
            
        Returns:
            Étape de raisonnement avec décision
            
        Example:
            >>> # Analyse d'un bug
            >>> step1 = await client.call_tool(
            ...     thought="L'utilisateur rapporte une erreur 500",
            ...     thought_number=1,
            ...     total_thoughts=3
            ... )
            >>> if step1.next_thought_needed:
            ...     step2 = await client.call_tool(
            ...         thought="Vérifier les logs du serveur",
            ...         thought_number=2,
            ...         total_thoughts=3
            ...     )
        """
        from kimi_proxy.core.models import SequentialThinkingStep
        
        params = {
            "thought": thought,
            "thought_number": thought_number,
            "total_thoughts": total_thoughts,
            "next_thought_needed": next_thought_needed
        }
        
        if available_mcp_tools:
            params["available_mcp_tools"] = available_mcp_tools
        
        result = await self.rpc_client.make_rpc_call(
            server_url=self.config.sequential_thinking_url,
            method="sequentialthinking_tools",
            params=params,
            timeout_ms=self.config.sequential_thinking_timeout_ms,
            api_key=self.config.sequential_thinking_api_key
        )
        
        if not result or not isinstance(result, dict):
            # Fallback minimal si erreur
            return SequentialThinkingStep(
                step_number=thought_number,
                thought=thought,
                next_thought_needed=next_thought_needed,
                total_thoughts=total_thoughts,
                branches=[]
            )
        
        return SequentialThinkingStep(
            step_number=result.get("thought_number", thought_number),
            thought=result.get("thought", thought),
            next_thought_needed=result.get("next_thought_needed", next_thought_needed),
            total_thoughts=result.get("total_thoughts", total_thoughts),
            branches=result.get("branches", [])
        )
    
    def is_available(self) -> bool:
        """
        Vérifie si Sequential Thinking est disponible.
        
        Returns:
            True si le dernier check était connecté
        """
        return self._status is not None and self._status.connected
