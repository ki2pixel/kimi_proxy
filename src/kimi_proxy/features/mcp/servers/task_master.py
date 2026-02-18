"""
Client MCP spécialisé pour Task Master.

Gère les 14 outils de gestion de tâches et le workflow de développement.
Performance: <30s pour les opérations complexes (analyse PRD, expansion).
"""
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..base.rpc import MCPRPCClient

# Modèles imports avec TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_proxy.core.models import TaskMasterTask, TaskMasterStats, MCPPhase4ServerStatus
    from ..base.config import MCPClientConfig


class TaskMasterMCPClient:
    """
    Client spécialisé pour Task Master MCP.
    
    Supporte 14 outils:
    - get_tasks: Lister toutes les tâches
    - next_task: Obtenir la prochaine tâche prioritaire
    - get_task: Détails d'une tâche spécifique
    - set_task_status: Mettre à jour le statut
    - update_subtask: Mettre à jour une sous-tâche
    - parse_prd: Analyser un cahier des charges
    - expand_task: Décomposer une tâche en sous-tâches
    - initialize_project: Initialiser un projet Task Master
    - analyze_project_complexity: Analyser la complexité
    - expand_all: Décomposer toutes les tâches
    - add_subtask: Ajouter une sous-tâche
    - remove_task: Supprimer une tâche
    - add_task: Ajouter une nouvelle tâche
    - complexity_report: Générer un rapport de complexité
    
    Performance:
    - get_tasks: <2s
    - parse_prd: <30s
    - expand_task: <10s
    - complexity_report: <5s
    """
    
    # Liste des outils valides pour validation
    VALID_TOOLS = [
        "get_tasks", "next_task", "get_task", "set_task_status", "update_subtask",
        "parse_prd", "expand_task", "initialize_project", "analyze_project_complexity",
        "expand_all", "add_subtask", "remove_task", "add_task", "complexity_report"
    ]
    
    def __init__(self, config: "MCPClientConfig", rpc_client: MCPRPCClient):
        """
        Initialise le client Task Master MCP.
        
        Args:
            config: Configuration MCP
            rpc_client: Client RPC de base
        """
        self.config = config
        self.rpc_client = rpc_client
        self._status: Optional["MCPPhase4ServerStatus"] = None
    
    async def check_status(self) -> "MCPPhase4ServerStatus":
        """
        Vérifie le statut du serveur Task Master MCP.
        
        Teste avec un appel get_tasks basique.
        
        Returns:
            Status du serveur Task Master
        """
        from kimi_proxy.core.models import MCPPhase4ServerStatus
        
        try:
            start_time = datetime.now()
            
            result = await self.call_tool(
                tool_name="get_tasks",
                params={}
            )
            
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            self._status = MCPPhase4ServerStatus(
                name="task-master-mcp",
                type="task_master",
                url=self.config.task_master_url,
                connected=True,
                last_check=datetime.now().isoformat(),
                latency_ms=latency_ms,
                tools_count=len(self.VALID_TOOLS),
                capabilities=[
                    "task_management", "project_init", "complexity_analysis",
                    "prd_parsing", "task_expansion", "workflow"
                ]
            )
            return self._status
            
        except Exception as e:
            self._status = MCPPhase4ServerStatus(
                name="task-master-mcp",
                type="task_master",
                url=self.config.task_master_url,
                connected=False,
                last_check=datetime.now().isoformat(),
                error_count=1,
                tools_count=len(self.VALID_TOOLS),
                capabilities=[]
            )
            return self._status
    
    async def call_tool(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Appelle un outil Task Master avec validation.
        
        Args:
            tool_name: Nom de l'outil (doit être dans VALID_TOOLS)
            params: Paramètres spécifiques à l'outil
            
        Returns:
            Résultat de l'appel
            
        Raises:
            ValueError: Si l'outil n'est pas valide
            Exception: Erreur de l'appel
            
        Example:
            >>> # Lister toutes les tâches
            >>> tasks = await client.call_tool("get_tasks", {})
            >>> 
            >>> # Parser un PRD
            >>> result = await client.call_tool("parse_prd", {"input": "prd.txt"})
        """
        if tool_name not in self.VALID_TOOLS:
            return {
                "error": f"Outil invalide: {tool_name}",
                "valid_tools": self.VALID_TOOLS
            }
        
        result = await self.rpc_client.make_rpc_call(
            server_url=self.config.task_master_url,
            method=tool_name,
            params=params,
            timeout_ms=self.config.task_master_timeout_ms,
            api_key=self.config.task_master_api_key
        )
        
        return result if result is not None else {}
    
    async def get_tasks(self, status_filter: Optional[str] = None) -> List["TaskMasterTask"]:
        """
        Récupère toutes les tâches avec filtre optionnel.
        
        Args:
            status_filter: Filtrer par statut (pending, in-progress, done, etc.)
            
        Returns:
            Liste des tâches Task Master
            
        Example:
            >>> # Toutes les tâches
            >>> all_tasks = await client.get_tasks()
            >>> 
            >>> # Tâches en attente uniquement
            >>> pending = await client.get_tasks(status_filter="pending")
        """
        from kimi_proxy.core.models import TaskMasterTask
        
        try:
            result = await self.call_tool("get_tasks", {"status": status_filter})
            
            if not result or not isinstance(result, dict):
                return []
            
            tasks = result.get("tasks", [])
            return [TaskMasterTask(**task) for task in tasks if isinstance(task, dict)]
            
        except Exception:
            return []
    
    async def get_next_task(self) -> Optional["TaskMasterTask"]:
        """
        Récupère la prochaine tâche prioritaire.
        
        Utilise l'algorithme de priorité Task Master (dépendances + complexité).
        
        Returns:
            Prochaine tâche à travailler ou None
            
        Example:
            >>> next_task = await client.get_next_task()
            >>> if next_task:
            ...     print(f"Prochaine tâche: {next_task.id} - {next_task.title}")
        """
        from kimi_proxy.core.models import TaskMasterTask
        
        try:
            result = await self.call_tool("next_task", {})
            
            if not result or not isinstance(result, dict):
                return None
            
            task_data = result.get("task")
            if not isinstance(task_data, dict):
                return None
            
            return TaskMasterTask(**task_data)
            
        except Exception:
            return None
    
    async def get_stats(self) -> "TaskMasterStats":
        """
        Récupère les statistiques globales des tâches.
        
        Returns:
            Stats avec counts par statut
            
        Example:
            >>> stats = await client.get_stats()
            >>> print(f"{stats.total_tasks} tâches total")
            >>> print(f"{stats.pending} en attente")
            >>> print(f"{stats.done} terminées")
        """
        from kimi_proxy.core.models import TaskMasterStats
        
        try:
            tasks = await self.get_tasks()
            
            stats = TaskMasterStats(total_tasks=len(tasks))
            
            # Compte par statut
            for task in tasks:
                status = task.status if hasattr(task, 'status') else "pending"
                if status == "pending":
                    stats.pending += 1
                elif status == "in-progress":
                    stats.in_progress += 1
                elif status == "done":
                    stats.done += 1
                elif status == "blocked":
                    stats.blocked += 1
                elif status == "deferred":
                    stats.deferred += 1
            
            return stats
            
        except Exception:
            return TaskMasterStats()
    
    async def parse_prd(
        self,
        input_file: str,
        research_enabled: bool = True,
        num_tasks: int = 0
    ) -> Dict[str, Any]:
        """
        Analyse un cahier des charges et génère des tâches.
        
        Args:
            input_file: Chemin vers le fichier PRD (.txt, .md)
            research_enabled: Activer la recherche pour l'analyse
            num_tasks: Nombre de tâches à générer (0 = auto)
            
        Returns:
            Résultat avec tâches générées
            
        Performance: 15-30s pour un PRD standard
        
        Example:
            >>> result = await client.parse_prd(
            ...     input_file="docs/prd.txt",
            ...     research_enabled=True,
            ...     num_tasks=10
            ... )
            >>> print(f"{len(result.get('tasks', []))} tâches créées")
        """
        return await self.call_tool("parse_prd", {
            "input": input_file,
            "research": research_enabled,
            "numTasks": num_tasks
        })
    
    async def expand_task(
        self,
        task_id: int,
        num_subtasks: int = 5,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Décompose une tâche en sous-tâches détaillées.
        
        Args:
            task_id: ID de la tâche à décomposer
            num_subtasks: Nombre de sous-tâches cible
            prompt: Contexte additionnel
            
        Returns:
            Tâche avec sous-tâches
            
        Performance: 5-10s
        
        Example:
            >>> result = await client.expand_task(
            ...     task_id=42,
            ...     num_subtasks=8,
            ...     prompt="Utiliser FastAPI et pytest"
            ... )
        """
        params = {
            "id": task_id,
            "num": str(num_subtasks)
        }
        
        if prompt:
            params["prompt"] = prompt
        
        return await self.call_tool("expand_task", params)
    
    async def initialize_project(self, project_root: str) -> Dict[str, Any]:
        """
        Initialise Task Master pour un projet.
        
        Args:
            project_root: Répertoire racine du projet
            
        Returns:
            Confirmation d'initialisation
        """
        return await self.call_tool("initialize_project", {
            "projectRoot": project_root,
            "addAliases": True,
            "initGit": True
        })
    
    async def set_task_status(
        self,
        task_id: int,
        status: str,
        subtask_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Met à jour le statut d'une tâche ou sous-tâche.
        
        Args:
            task_id: ID de la tâche
            status: Nouveau statut (pending, in-progress, done, etc.)
            subtask_id: ID de la sous-tâche (optionnel)
            
        Returns:
            Confirmation de mise à jour
        """
        params = {
            "id": str(task_id) if subtask_id is None else f"{task_id},{subtask_id}",
            "status": status,
            "projectRoot": "/home/kidpixel/kimi-proxy"  # À rendre configurable
        }
        
        return await self.call_tool("set_task_status", params)
    
    def is_available(self) -> bool:
        """
        Vérifie si Task Master est disponible.
        
        Returns:
            True si le dernier check était connecté
        """
        return self._status is not None and self._status.connected
