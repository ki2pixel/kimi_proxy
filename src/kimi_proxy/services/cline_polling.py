"""Service — Polling périodique Cline (ledger local) + broadcast WebSocket.

Objectif:
    - Importer automatiquement le ledger local Cline (Solution 1)
    - Notifier le dashboard via WebSocket uniquement si de nouvelles données sont détectées

Contraintes:
    - Async I/O uniquement (aiofiles + asyncio.to_thread déjà dans ClineImporter)
    - Pas de dépendances vers l'API (layering: API ← Services ← Features)
    - Broadcast "best-effort" : ne doit jamais faire crasher le polling
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TypedDict

from ..features.cline_importer import ClineImporter, ClineImportResult
from .websocket_manager import ConnectionManager


class ClineUsageUpdatedMessage(TypedDict):
    """Message WebSocket envoyé au dashboard quand l'usage Cline évolue."""

    type: str
    latest_ts: Optional[int]
    latest_count: int
    imported_count: int
    timestamp: str


@dataclass(frozen=True)
class ClinePollingConfig:
    """Configuration du polling Cline."""

    enabled: bool = True
    interval_seconds: float = 60.0
    backoff_max_seconds: float = 600.0


class ClinePollingService:
    """Service de polling pour l'import Cline (ledger local)."""

    def __init__(
        self,
        manager: ConnectionManager,
        importer: ClineImporter,
        config: ClinePollingConfig,
    ):
        self._manager = manager
        self._importer = importer
        self._config = config

        self._running = False
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def config(self) -> ClinePollingConfig:
        return self._config

    async def start(self) -> None:
        """Démarre le polling dans une tâche asyncio."""

        if not self._config.enabled:
            return

        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Arrête le polling proprement (annule la tâche)."""

        self._running = False
        if not self._task:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def poll_once(self) -> bool:
        """Exécute un cycle d'import et broadcast si changement détecté.

        Returns:
            True si un broadcast a été envoyé, False sinon.
        """

        before_ts = await self._importer.get_latest_ts()
        before_count = await self._importer.get_usage_count()
        result: ClineImportResult = await self._importer.import_default_ledger()
        after_ts = await self._importer.get_latest_ts()
        after_count = await self._importer.get_usage_count()

        # Signal "nouvelle donnée" (best-effort) :
        # - ts max a changé, OU
        # - nombre de lignes a changé
        #
        # Note: importer.import_default_ledger() upsert en DB, donc after_* reflète
        # bien l'état DB post-import.
        if after_ts == before_ts and after_count == before_count:
            return False

        message: ClineUsageUpdatedMessage = {
            "type": "cline_usage_updated",
            "latest_ts": after_ts,
            "latest_count": int(after_count),
            "imported_count": int(result.get("imported_count", 0)),
            "timestamp": datetime.now().isoformat(),
        }

        # Ne jamais laisser le broadcast casser le service.
        try:
            await self._manager.broadcast(message)
        except Exception as e:
            print(f"⚠️ Erreur broadcast WebSocket (cline): {e}")
            return False

        return True

    async def _poll_loop(self) -> None:
        """Boucle principale: import périodique + backoff exponentiel sur erreurs."""

        # Délai courant (peut augmenter via backoff). Minimum hard pour éviter un busy-loop.
        delay = max(self._config.interval_seconds, 1.0)

        while self._running:
            try:
                await self.poll_once()
                delay = max(self._config.interval_seconds, 1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Backoff exponentiel borné.
                print(f"⚠️ Erreur polling Cline: {e}")
                backoff_cap = max(self._config.backoff_max_seconds, delay)
                delay = min(delay * 2.0, backoff_cap)

            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break


def create_cline_polling_service(
    manager: ConnectionManager,
    config: ClinePollingConfig,
    importer: Optional[ClineImporter] = None,
) -> ClinePollingService:
    """Factory: crée le service de polling Cline."""

    return ClinePollingService(
        manager=manager,
        importer=importer or ClineImporter(),
        config=config,
    )
