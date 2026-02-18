"""
Log Watcher - Surveillance temps réel des logs Continue.
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, Callable, Any

import aiofiles

from .parser import LogParser
from .patterns import is_relevant_line
from ...core.constants import DEFAULT_MAX_CONTEXT, DEFAULT_LOG_PATH
from ...core.models import TokenMetrics


class LogWatcher:
    """
    Surveille en temps réel le fichier core.log de Continue
    pour extraire les métriques de tokens avec parsing avancé.
    
    Supporte:
    - Symboles ~ (tilde) pour les estimations
    - Bloc de diagnostic "CompileChat" (contextLength, tools, system message)
    - Erreurs API (429/quota)
    - Mise à jour dynamique du contexte max
    """
    
    def __init__(self, log_path: str = None, broadcast_callback: Callable = None):
        self.log_path = os.path.expanduser(log_path or DEFAULT_LOG_PATH)
        self.running = False
        self.last_position = 0
        self.task = None
        self.parser = LogParser()
        self.broadcast_callback = broadcast_callback
        
        # Contexte max dynamique (peut être mis à jour par les logs)
        self.dynamic_max_context = None
    
    def get_max_context(self, default_context: int = DEFAULT_MAX_CONTEXT) -> int:
        """
        Retourne le contexte max à utiliser.
        Priorité: contexte dynamique des logs > contexte de session > défaut
        """
        if self.dynamic_max_context and self.dynamic_max_context > 0:
            return self.dynamic_max_context
        return default_context
    
    async def start(self):
        """Démarre la surveillance des logs."""
        if not os.path.exists(self.log_path):
            print(f"⚠️ Fichier log non trouvé: {self.log_path}")
            print("   Le Log Watcher démarrera automatiquement quand le fichier sera créé.")
        
        self.running = True
        self.task = asyncio.create_task(self._watch_loop())
        print(f"📁 Log Watcher démarré (surveillance: ~/.continue/logs/core.log)")
        print(f"   Patterns actifs: CompileChat, API errors, Token metrics")
    
    async def stop(self):
        """Arrête la surveillance."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        print("📁 Log Watcher arrêté")
    
    async def _watch_loop(self):
        """Boucle principale de surveillance."""
        while self.running and not os.path.exists(self.log_path):
            await asyncio.sleep(5)
        
        if not self.running:
            return
        
        try:
            async with aiofiles.open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                await f.seek(0, 2)
                self.last_position = await f.tell()
        except Exception as e:
            print(f"⚠️ Erreur initialisation log watcher: {e}")
            return
        
        print(f"   Position initiale: {self.last_position} bytes")
        
        while self.running:
            try:
                await self._check_for_updates()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ Erreur log watcher: {e}")
                await asyncio.sleep(2)
    
    async def _check_for_updates(self):
        """Vérifie les nouvelles lignes dans le fichier log."""
        try:
            current_size = os.path.getsize(self.log_path)
            
            if current_size < self.last_position:
                self.last_position = 0
            
            if current_size == self.last_position:
                return
            
            async with aiofiles.open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                await f.seek(self.last_position)
                new_content = await f.read()
                self.last_position = await f.tell()
            
            if new_content:
                lines = new_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        metrics = self.parser.parse_line(line)
                        if metrics:
                            await self._broadcast_metrics(metrics)
                            
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"⚠️ Erreur lecture log: {e}")
    
    async def _broadcast_metrics(self, metrics: TokenMetrics):
        """Diffuse les métriques extraites via WebSocket."""
        if self.broadcast_callback:
            await self.broadcast_callback(metrics, self)
    
    def set_broadcast_callback(self, callback: Callable):
        """Définit la fonction de callback pour le broadcast."""
        self.broadcast_callback = callback


def create_log_watcher(log_path: str = None, broadcast_callback: Callable = None) -> LogWatcher:
    """
    Factory pour créer une instance de LogWatcher.
    
    Args:
        log_path: Chemin vers le fichier log (optionnel)
        broadcast_callback: Fonction de callback pour broadcaster les métriques
        
    Returns:
        Instance de LogWatcher configurée
    """
    return LogWatcher(log_path=log_path, broadcast_callback=broadcast_callback)
