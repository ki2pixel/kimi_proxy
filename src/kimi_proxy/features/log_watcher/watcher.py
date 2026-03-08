"""
Log Watcher - Surveillance multi-source des signaux analytics.
"""
import os
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, List, Sequence, Dict

import aiofiles

from .parser import KimiGlobalLogParser, KimiSessionParser, LogParser
from ...core.constants import (
    DEFAULT_MAX_CONTEXT,
    DEFAULT_CONTINUE_LOG_PATH,
    DEFAULT_KIMI_LOG_PATH,
    DEFAULT_KIMI_SESSIONS_PATH,
)
from ...core.models import TokenMetrics, AnalyticsEvent, AnalyticsSourceState


@dataclass
class KimiSessionState:
    """État incrémental d'un artefact de session Kimi."""

    session_path: str
    context_path: str
    metadata_path: str
    context_position: int = 0
    context_mtime: float = 0.0
    metadata_mtime: float = 0.0
    metadata: Dict[str, object] = field(default_factory=dict)


class AnalyticsSource:
    """Source analytics abstraite pour l'orchestrateur multi-source."""

    def __init__(self, source_id: str, source_kind: str, path: str):
        self.source_id = source_id
        self.source_kind = source_kind
        self.path = os.path.expanduser(path)
        self.available = False
        self.healthy = True
        self.last_error: Optional[str] = None
        self.last_event_at: Optional[str] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialise la source avant son premier poll."""
        self.available = os.path.exists(self.path)
        self.healthy = True
        self.last_error = None
        self._initialized = True

    async def poll(self) -> List[AnalyticsEvent]:
        """Retourne les événements détectés depuis le dernier cycle."""
        return []

    def snapshot_state(self) -> AnalyticsSourceState:
        """Retourne un snapshot sérialisable de l'état runtime."""
        return AnalyticsSourceState(
            source_id=self.source_id,
            source_kind=self.source_kind,
            path=self.path,
            available=self.available,
            healthy=self.healthy,
            last_error=self.last_error,
            last_event_at=self.last_event_at,
        )

    def _mark_error(self, error: Exception) -> None:
        self.healthy = False
        self.last_error = str(error)

    def _mark_event(self) -> None:
        self.healthy = True
        self.last_error = None
        self.last_event_at = datetime.now().isoformat()


class ContinueLogSource(AnalyticsSource):
    """Adaptateur de compatibilité pour l'ancien flux Continue mono-fichier."""

    def __init__(self, log_path: Optional[str] = None):
        super().__init__(
            source_id="continue_logs",
            source_kind="continue",
            path=log_path or DEFAULT_CONTINUE_LOG_PATH,
        )
        self.parser = LogParser()
        self.last_position = 0

    async def initialize(self) -> None:
        await super().initialize()
        if not self.available:
            return

        async with aiofiles.open(self.path, 'r', encoding='utf-8', errors='ignore') as file_handle:
            await file_handle.seek(0, 2)
            self.last_position = await file_handle.tell()

    async def poll(self) -> List[AnalyticsEvent]:
        if not self._initialized:
            await self.initialize()

        if not os.path.exists(self.path):
            self.available = False
            return []

        self.available = True
        current_size = os.path.getsize(self.path)
        if current_size < self.last_position:
            self.last_position = 0

        if current_size == self.last_position:
            return []

        async with aiofiles.open(self.path, 'r', encoding='utf-8', errors='ignore') as file_handle:
            await file_handle.seek(self.last_position)
            new_content = await file_handle.read()
            self.last_position = await file_handle.tell()

        events: List[AnalyticsEvent] = []
        for raw_line in new_content.split('\n'):
            line = raw_line.strip()
            if not line:
                continue

            metrics = self.parser.parse_line(line)
            if metrics is None:
                continue

            if metrics.is_compile_chat:
                metrics.source = "continue_compile_chat"
            elif metrics.is_api_error:
                metrics.source = "continue_api_error"
            else:
                metrics.source = "continue_logs"

            events.append(
                AnalyticsEvent(
                    source_id=self.source_id,
                    source_kind=self.source_kind,
                    timestamp=datetime.now().isoformat(),
                    metrics=metrics,
                    preview=metrics.raw_line,
                    severity="error" if metrics.is_api_error else "info",
                )
            )

        if events:
            self._mark_event()

        return events


class KimiGlobalLogSource(AnalyticsSource):
    """Source de lecture du fichier global `kimi.log`."""

    def __init__(self, log_path: Optional[str] = None):
        super().__init__(
            source_id="kimi_global",
            source_kind="kimi_global",
            path=log_path or DEFAULT_KIMI_LOG_PATH,
        )
        self.parser = KimiGlobalLogParser()
        self.last_position = 0

    async def initialize(self) -> None:
        await super().initialize()
        if not self.available:
            return

        async with aiofiles.open(self.path, 'r', encoding='utf-8', errors='ignore') as file_handle:
            await file_handle.seek(0, 2)
            self.last_position = await file_handle.tell()

    async def poll(self) -> List[AnalyticsEvent]:
        if not self._initialized:
            await self.initialize()

        if not os.path.exists(self.path):
            self.available = False
            return []

        self.available = True
        current_size = os.path.getsize(self.path)
        if current_size < self.last_position:
            self.last_position = 0

        if current_size == self.last_position:
            return []

        async with aiofiles.open(self.path, 'r', encoding='utf-8', errors='ignore') as file_handle:
            await file_handle.seek(self.last_position)
            new_content = await file_handle.read()
            self.last_position = await file_handle.tell()

        events: List[AnalyticsEvent] = []
        for raw_line in new_content.split('\n'):
            line = raw_line.strip()
            if not line:
                continue

            event = self.parser.parse_line(line)
            if event is None:
                continue

            events.append(event)

        if events:
            self._mark_event()

        return events


class KimiSessionSource(AnalyticsSource):
    """Source incrémentale pour les artefacts `context.jsonl` des sessions Kimi."""

    def __init__(
        self,
        sessions_path: Optional[str] = None,
        max_sessions_per_poll: int = 32,
        discovery_batch_size: int = 4,
        initial_tail_bytes: int = 8192,
    ):
        super().__init__(
            source_id="kimi_sessions",
            source_kind="kimi_session",
            path=sessions_path or DEFAULT_KIMI_SESSIONS_PATH,
        )
        self.parser = KimiSessionParser()
        self.max_sessions_per_poll = max(1, max_sessions_per_poll)
        self.discovery_batch_size = max(1, discovery_batch_size)
        self.initial_tail_bytes = max(0, initial_tail_bytes)
        self._roots: List[str] = []
        self._root_cursor = 0
        self._session_cursor = 0
        self._sessions: Dict[str, KimiSessionState] = {}

    async def initialize(self) -> None:
        await super().initialize()
        if not self.available:
            return

        self._refresh_roots()
        self._discover_all_existing_sessions()

    async def poll(self) -> List[AnalyticsEvent]:
        if not self._initialized:
            await self.initialize()

        if not os.path.isdir(self.path):
            self.available = False
            return []

        self.available = True
        self._refresh_roots()
        self._discover_new_sessions()

        session_keys = sorted(self._sessions.keys())
        if not session_keys:
            return []

        batch_size = min(len(session_keys), self.max_sessions_per_poll)
        start_index = self._session_cursor % len(session_keys)
        selected_keys = [
            session_keys[(start_index + offset) % len(session_keys)]
            for offset in range(batch_size)
        ]
        self._session_cursor = (start_index + batch_size) % len(session_keys)

        events: List[AnalyticsEvent] = []
        for session_key in selected_keys:
            state = self._sessions[session_key]
            events.extend(await self._poll_session(state))

        if events:
            self._mark_event()

        return events

    def _refresh_roots(self) -> None:
        try:
            self._roots = sorted(
                os.path.join(self.path, entry)
                for entry in os.listdir(self.path)
                if os.path.isdir(os.path.join(self.path, entry))
            )
        except FileNotFoundError:
            self._roots = []

        if self._roots:
            self._root_cursor %= len(self._roots)
        else:
            self._root_cursor = 0

    def _discover_all_existing_sessions(self) -> None:
        for root_path in self._roots:
            for session_path in self._list_session_directories(root_path):
                self._register_session(session_path)

    def _discover_new_sessions(self) -> None:
        if not self._roots:
            return

        batch_size = min(len(self._roots), self.discovery_batch_size)
        start_index = self._root_cursor % len(self._roots)
        selected_roots = [
            self._roots[(start_index + offset) % len(self._roots)]
            for offset in range(batch_size)
        ]
        self._root_cursor = (start_index + batch_size) % len(self._roots)

        for root_path in selected_roots:
            for session_path in self._list_session_directories(root_path):
                self._register_session(session_path)

    def _list_session_directories(self, root_path: str) -> List[str]:
        try:
            return sorted(
                os.path.join(root_path, entry)
                for entry in os.listdir(root_path)
                if os.path.isdir(os.path.join(root_path, entry))
            )
        except FileNotFoundError:
            return []

    def _register_session(self, session_path: str) -> None:
        if session_path in self._sessions:
            return

        context_path = os.path.join(session_path, "context.jsonl")
        metadata_path = os.path.join(session_path, "metadata.json")
        if not os.path.exists(context_path):
            return

        initial_position = 0
        try:
            context_size = os.path.getsize(context_path)
            if self.initial_tail_bytes > 0 and context_size > self.initial_tail_bytes:
                initial_position = context_size - self.initial_tail_bytes
        except OSError:
            initial_position = 0

        self._sessions[session_path] = KimiSessionState(
            session_path=session_path,
            context_path=context_path,
            metadata_path=metadata_path,
            context_position=initial_position,
        )

    async def _poll_session(self, state: KimiSessionState) -> List[AnalyticsEvent]:
        if not os.path.exists(state.context_path):
            return []

        await self._refresh_metadata(state)

        current_size = os.path.getsize(state.context_path)
        if current_size < state.context_position:
            state.context_position = 0

        if current_size == state.context_position:
            return []

        async with aiofiles.open(state.context_path, 'r', encoding='utf-8', errors='ignore') as file_handle:
            await file_handle.seek(state.context_position)
            new_content = await file_handle.read()
            state.context_position = await file_handle.tell()

        try:
            state.context_mtime = os.path.getmtime(state.context_path)
        except OSError:
            state.context_mtime = 0.0

        lines = new_content.splitlines()
        if current_size > self.initial_tail_bytes and state.context_position - len(new_content) > 0 and lines:
            lines = lines[1:]

        external_session_id = self._get_external_session_id(state)
        events: List[AnalyticsEvent] = []
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            event = self.parser.parse_line(
                line=line,
                session_external_id=external_session_id,
                metadata=state.metadata,
            )
            if event is None:
                continue
            events.append(event)

        return events

    async def _refresh_metadata(self, state: KimiSessionState) -> None:
        if not os.path.exists(state.metadata_path):
            state.metadata = {}
            state.metadata_mtime = 0.0
            return

        try:
            metadata_mtime = os.path.getmtime(state.metadata_path)
        except OSError:
            return

        if metadata_mtime == state.metadata_mtime and state.metadata:
            return

        try:
            async with aiofiles.open(state.metadata_path, 'r', encoding='utf-8', errors='ignore') as file_handle:
                raw_metadata = await file_handle.read()
            loaded_metadata = json.loads(raw_metadata)
        except (OSError, json.JSONDecodeError):
            state.metadata = {}
            state.metadata_mtime = metadata_mtime
            return

        if isinstance(loaded_metadata, dict):
            state.metadata = loaded_metadata
        else:
            state.metadata = {}
        state.metadata_mtime = metadata_mtime

    def _get_external_session_id(self, state: KimiSessionState) -> str:
        metadata_session_id = state.metadata.get("session_id")
        if isinstance(metadata_session_id, str) and metadata_session_id.strip():
            return metadata_session_id.strip()
        return os.path.basename(state.session_path)


class LogWatcher:
    """
    Orchestrateur multi-source pour signaux analytics.

    Compatibilité:
    - conserve l'API publique `LogWatcher` et `create_log_watcher()`
    - instancie par défaut une source Continue compatible avec l'implémentation historique
    - permet l'injection future de sources Kimi/futures sans toucher `main.py`
    """

    def __init__(
        self,
        log_path: str = None,
        broadcast_callback: Callable = None,
        sources: Optional[Sequence[AnalyticsSource]] = None,
        poll_interval_seconds: float = 0.5,
    ):
        default_sources = list(sources) if sources is not None else [
            ContinueLogSource(log_path=log_path),
            KimiGlobalLogSource(),
            KimiSessionSource(),
        ]
        self.sources: List[AnalyticsSource] = default_sources
        self.log_path = self.sources[0].path if self.sources else os.path.expanduser(log_path or DEFAULT_CONTINUE_LOG_PATH)
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.broadcast_callback = broadcast_callback
        self.poll_interval_seconds = max(poll_interval_seconds, 0.1)

        # Contexte max dynamique (peut être mis à jour par les logs)
        self.dynamic_max_context: Optional[int] = None

    def get_max_context(self, default_context: int = DEFAULT_MAX_CONTEXT) -> int:
        """
        Retourne le contexte max à utiliser.
        Priorité: contexte dynamique des logs > contexte de session > défaut
        """
        if self.dynamic_max_context and self.dynamic_max_context > 0:
            return self.dynamic_max_context
        return default_context

    def get_source_states(self) -> List[AnalyticsSourceState]:
        """Retourne l'état runtime de toutes les sources surveillées."""
        return [source.snapshot_state() for source in self.sources]

    async def start(self):
        """Démarre la surveillance des logs."""
        for source in self.sources:
            try:
                await source.initialize()
            except Exception as error:
                source._mark_error(error)
                print(f"⚠️ Initialisation source analytics échouée ({source.source_id}): {error}")

        self.running = True
        self.task = asyncio.create_task(self._watch_loop())
        print(f"📁 Analytics Watcher démarré ({len(self.sources)} source(s))")
        for source in self.sources:
            print(f"   - {source.source_id}: {source.path}")

    async def stop(self):
        """Arrête la surveillance."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        print("📁 Analytics Watcher arrêté")

    async def _watch_loop(self):
        """Boucle principale de surveillance."""
        while self.running:
            try:
                await self._check_for_updates()
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as error:
                print(f"⚠️ Erreur analytics watcher: {error}")
                await asyncio.sleep(2)

    async def _check_for_updates(self):
        """Poll toutes les sources et diffuse les événements détectés."""
        for source in self.sources:
            try:
                events = await source.poll()
                for event in events:
                    if event.metrics.context_length > 0:
                        self.dynamic_max_context = event.metrics.context_length
                    if (
                        event.metrics.total_tokens > 0
                        or event.metrics.context_length > 0
                        or event.metrics.is_api_error
                    ):
                        await self._broadcast_metrics(event.metrics)
            except FileNotFoundError:
                source.available = False
            except Exception as error:
                source._mark_error(error)
                print(f"⚠️ Erreur source analytics ({source.source_id}): {error}")

    async def _broadcast_metrics(self, metrics: TokenMetrics):
        """Diffuse les métriques extraites via WebSocket."""
        if self.broadcast_callback:
            await self.broadcast_callback(metrics, self)

    def set_broadcast_callback(self, callback: Callable):
        """Définit la fonction de callback pour le broadcast."""
        self.broadcast_callback = callback


def create_log_watcher(
    log_path: str = None,
    broadcast_callback: Callable = None,
    sources: Optional[Sequence[AnalyticsSource]] = None,
) -> LogWatcher:
    """
    Factory pour créer une instance de LogWatcher.

    Args:
        log_path: Chemin du log Continue historique (optionnel)
        broadcast_callback: Fonction de callback pour broadcaster les métriques
        sources: Sources injectées explicitement pour un orchestrateur multi-source

    Returns:
        Instance de LogWatcher configurée
    """
    return LogWatcher(log_path=log_path, broadcast_callback=broadcast_callback, sources=sources)
