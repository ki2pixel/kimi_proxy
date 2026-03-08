"""
Parser pour extraire les métriques de tokens des logs.
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from .patterns import (
    TOKEN_PATTERNS, COMPILE_CHAT_PATTERNS, API_ERROR_PATTERNS,
    COMPILE_CHAT_START, COMPILE_CHAT_END, KIMI_GLOBAL_LOG_LINE,
    KIMI_PROVIDER_PATTERN, KIMI_MODEL_PATTERN, KIMI_TOOLS_PATTERN,
    KIMI_CONFIG_PATTERN, KIMI_AUTH_ERROR_PATTERN,
    KIMI_BAD_REQUEST_ERROR_PATTERN,
    KIMI_CONTEXT_LIMIT_ERROR_PATTERN, KIMI_TRANSPORT_ERROR_PATTERN,
    is_relevant_line
)
from ...core.models import TokenMetrics, AnalyticsEvent


class LogParser:
    """Parse les lignes de log pour extraire les métriques de tokens."""
    
    def __init__(self):
        self._compile_chat_buffer: List[str] = []
        self._in_compile_chat_block = False
    
    def parse_line(self, line: str) -> Optional[TokenMetrics]:
        """
        Parse une ligne de log et retourne les métriques si trouvées.
        
        Args:
            line: Ligne de log à parser
            
        Returns:
            TokenMetrics si des métriques sont trouvées, None sinon
        """
        # Détection du bloc CompileChat multi-lignes
        if COMPILE_CHAT_START.search(line):
            self._in_compile_chat_block = True
            self._compile_chat_buffer = [line]
            return None
        
        if self._in_compile_chat_block:
            self._compile_chat_buffer.append(line)
            
            # Fin du bloc si ligne vide ou nouvelle section
            if line.strip() == '' or (not line.startswith('-') and not line.startswith(' ')):
                self._in_compile_chat_block = False
                return self._parse_compile_chat_block()
            
            # Continue d'accumuler
            if len(self._compile_chat_buffer) < 10:  # Limite de sécurité
                return None
            else:
                self._in_compile_chat_block = False
                return self._parse_compile_chat_block()
        
        if not is_relevant_line(line):
            return None
        
        return self._extract_standard_metrics(line)
    
    def _extract_standard_metrics(self, line: str) -> Optional[TokenMetrics]:
        """
        Extrait les métriques standard d'une ligne de log avec support multi-formats.
        
        Supporte les formats OpenAI, Continue, Gemini, et JSON-like.
        Gère les estimations avec tilde (~) et les erreurs API.
        """
        metrics = TokenMetrics(
            source="logs",
            raw_line=line[:200],
            is_compile_chat=False,
            is_api_error=False
        )
        
        found = False
        
        # Extraction des patterns standards
        for pattern in TOKEN_PATTERNS:
            matches = pattern.findall(line)
            for match in matches:
                try:
                    value = int(match)
                    pattern_str = pattern.pattern.lower()
                    
                    if 'prompt' in pattern_str:
                        metrics.prompt_tokens = value
                        found = True
                    elif 'completion' in pattern_str:
                        metrics.completion_tokens = value
                        found = True
                    elif 'context' in pattern_str:
                        metrics.context_length = value
                        found = True
                    elif 'total' in pattern_str or pattern_str.startswith(r'"total_tokens"'):
                        metrics.total_tokens = value
                        found = True
                    else:
                        if metrics.total_tokens == 0:
                            metrics.total_tokens = value
                            found = True
                except (ValueError, IndexError):
                    continue
        
        # Extraction des erreurs API
        for pattern in API_ERROR_PATTERNS:
            match = pattern.search(line)
            if match:
                try:
                    value = int(match.group(1))
                    metrics.total_tokens = value
                    metrics.is_api_error = True
                    found = True
                except (ValueError, IndexError):
                    continue
        
        # Extraction des patterns CompileChat individuels
        for key, pattern in COMPILE_CHAT_PATTERNS.items():
            match = pattern.search(line)
            if match:
                try:
                    value = int(match.group(1))
                    if key == 'tools':
                        metrics.tools_tokens = value
                    elif key == 'system_message':
                        metrics.system_message_tokens = value
                    elif key == 'context_length':
                        metrics.context_length = value
                    found = True
                except (ValueError, IndexError):
                    continue
        
        # Calcul du total si on a des composants séparés
        components = [
            metrics.prompt_tokens,
            metrics.completion_tokens,
            metrics.tools_tokens,
            metrics.system_message_tokens
        ]
        
        if any(components):
            calculated_total = sum(c for c in components if c > 0)
            if calculated_total > 0:
                if metrics.total_tokens > 0:
                    metrics.total_tokens = max(metrics.total_tokens, calculated_total)
                else:
                    metrics.total_tokens = calculated_total
                found = True
        
        return metrics if found else None
    
    def _parse_compile_chat_block(self) -> Optional[TokenMetrics]:
        """Parse le bloc CompileChat accumulé."""
        if not self._compile_chat_buffer:
            return None
        
        block_text = '\n'.join(self._compile_chat_buffer)
        
        metrics = TokenMetrics(
            source="logs",
            raw_line=block_text[:300],
            is_compile_chat=True,
            is_api_error=False
        )
        
        found = False
        
        # Parse chaque ligne du bloc
        for line in self._compile_chat_buffer:
            for key, pattern in COMPILE_CHAT_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    try:
                        value = int(match.group(1))
                        if key == 'tools':
                            metrics.tools_tokens = value
                        elif key == 'system_message':
                            metrics.system_message_tokens = value
                        elif key == 'context_length':
                            metrics.context_length = value
                        found = True
                    except (ValueError, IndexError):
                        continue
        
        # Calcule le total à partir des composants
        if found:
            total = (
                metrics.tools_tokens +
                metrics.system_message_tokens +
                metrics.prompt_tokens
            )
            
            if metrics.context_length > 0:
                metrics.total_tokens = min(total, metrics.context_length)
            else:
                metrics.total_tokens = total
        
        self._compile_chat_buffer = []
        return metrics if found else None
    
    def reset(self):
        """Réinitialise l'état du parser."""
        self._compile_chat_buffer = []
        self._in_compile_chat_block = False


class KimiGlobalLogParser:
    """Parse les lignes structurées du fichier global `kimi.log`."""

    def parse_line(self, line: str) -> Optional[AnalyticsEvent]:
        match = KIMI_GLOBAL_LOG_LINE.match(line.strip())
        if match is None:
            return None

        timestamp = match.group("timestamp")
        level = match.group("level").strip().upper()
        message = match.group("message").strip()

        error_source = self._classify_error_source(message) if level == "ERROR" else "kimi_global"
        metrics = TokenMetrics(
            source=error_source,
            raw_line=message[:200],
            is_compile_chat=False,
            is_api_error=level == "ERROR",
        )

        provider: Optional[str] = None
        model: Optional[str] = None
        preview = self._build_preview(message)

        provider_match = KIMI_PROVIDER_PATTERN.search(message)
        if provider_match is not None:
            provider = provider_match.group(1)
            preview = f"Provider actif: {provider}"

        model_match = KIMI_MODEL_PATTERN.search(message)
        if model_match is not None:
            provider = model_match.group(1)
            model = model_match.group(2)
            metrics.context_length = int(model_match.group(3))
            preview = f"Modèle actif: {provider}/{model}"

        tools_match = KIMI_TOOLS_PATTERN.search(message)
        if tools_match is not None:
            raw_tools = [item.strip().strip("'") for item in tools_match.group(1).split(",") if item.strip()]
            preview = f"Outils Kimi chargés: {len(raw_tools)}"

        if KIMI_CONFIG_PATTERN.search(message):
            preview = "Configuration Kimi chargée"

        if level == "ERROR":
            preview = self._sanitize_error_preview(message, error_source)

        return AnalyticsEvent(
            source_id="kimi_global",
            source_kind="kimi_global",
            timestamp=timestamp,
            metrics=metrics,
            provider=provider,
            model=model,
            preview=preview,
            severity="error" if level == "ERROR" else "info",
        )

    def _build_preview(self, message: str) -> str:
        sanitized = message
        if "SecretStr(" in sanitized:
            sanitized = sanitized.replace("SecretStr('**********')", "SecretStr('[redacted]')")
            sanitized = sanitized.replace("SecretStr('')", "SecretStr('[redacted]')")
        return sanitized[:160]

    def _classify_error_source(self, message: str) -> str:
        if KIMI_CONTEXT_LIMIT_ERROR_PATTERN.search(message):
            return "kimi_global_context_limit_error"
        if KIMI_AUTH_ERROR_PATTERN.search(message):
            return "kimi_global_auth_error"
        if KIMI_BAD_REQUEST_ERROR_PATTERN.search(message):
            return "kimi_global_request_error"
        if KIMI_TRANSPORT_ERROR_PATTERN.search(message):
            return "kimi_global_transport_error"
        return "kimi_global_runtime_error"

    def _sanitize_error_preview(self, message: str, error_source: str) -> str:
        lowered = message.lower()
        if error_source == "kimi_global_context_limit_error":
            return "Erreur contexte Kimi: limite atteinte"
        if error_source == "kimi_global_auth_error":
            return "Erreur auth Kimi: authentification refusée"
        if error_source == "kimi_global_request_error":
            if "unterminated string" in lowered or "invalid json" in lowered or "json decode" in lowered:
                return "Erreur requête Kimi: payload JSON invalide"
            return "Erreur requête Kimi: requête provider invalide"
        if error_source == "kimi_global_transport_error":
            return "Erreur transport Kimi: réseau/timeout"
        if "node:" in lowered:
            return "Erreur runtime Kimi: Node.js"
        return f"Erreur runtime Kimi: {message[:120]}"


class KimiSessionParser:
    """Parse les artefacts JSONL des sessions Kimi Code."""

    def parse_line(
        self,
        line: str,
        session_external_id: str,
        metadata: Optional[dict[str, object]] = None,
    ) -> Optional[AnalyticsEvent]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        raw_role = payload.get("role")
        if not isinstance(raw_role, str) or not raw_role:
            return None

        role = raw_role.strip()
        metrics = TokenMetrics(
            source=self._build_source_name(role),
            raw_line=line[:200],
            is_compile_chat=False,
            is_api_error=False,
        )

        preview = self._build_preview(role=role, payload=payload)
        provider = self._extract_string(payload, "provider") or self._extract_string(metadata, "provider")
        model = self._extract_string(payload, "model") or self._extract_string(metadata, "model")

        if role == "_usage":
            token_count = self._extract_int(payload, "token_count")
            if token_count is not None:
                metrics.total_tokens = token_count
                preview = f"Usage session Kimi: {token_count} tokens"

        return AnalyticsEvent(
            source_id="kimi_sessions",
            source_kind="kimi_session",
            timestamp=datetime.now().isoformat(),
            metrics=metrics,
            provider=provider,
            model=model,
            session_external_id=session_external_id,
            preview=preview,
            severity="info",
        )

    def _build_source_name(self, role: str) -> str:
        normalized_role = role.strip().lower().replace("-", "_")
        if normalized_role.startswith("_"):
            normalized_role = normalized_role[1:]
        return f"kimi_session_{normalized_role or 'event'}"

    def _build_preview(self, role: str, payload: dict[str, object]) -> str:
        if role == "_checkpoint":
            checkpoint_id = self._extract_int(payload, "id")
            if checkpoint_id is not None:
                return f"Checkpoint session Kimi #{checkpoint_id}"
            return "Checkpoint session Kimi"

        if role == "_usage":
            return "Métriques d'usage session Kimi"

        if role == "user":
            return self._extract_content_preview(payload, fallback="Message utilisateur Kimi")

        if role == "assistant":
            assistant_preview = self._extract_content_preview(payload, fallback="Réponse assistant Kimi")
            tool_calls = payload.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                return f"{assistant_preview} · outils: {len(tool_calls)}"
            return assistant_preview

        if role == "tool":
            tool_call_id = self._extract_string(payload, "tool_call_id")
            content_preview = self._extract_content_preview(payload, fallback="Sortie outil Kimi")
            if tool_call_id:
                return f"{content_preview} ({tool_call_id.strip()})"[:160]
            return content_preview

        return self._extract_content_preview(payload, fallback=f"Événement session Kimi: {role}")

    def _extract_content_preview(self, payload: dict[str, object], fallback: str) -> str:
        content = payload.get("content")
        if isinstance(content, str):
            return self._sanitize_preview(content)

        if isinstance(content, list):
            text_fragments: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                item_text = item.get("text")
                if item_type == "text" and isinstance(item_text, str) and item_text.strip():
                    text_fragments.append(item_text.strip())
            if text_fragments:
                return self._sanitize_preview(" ".join(text_fragments))

        return fallback

    def _sanitize_preview(self, value: str) -> str:
        normalized = " ".join(value.split())
        return normalized[:160] if normalized else "Entrée session Kimi"

    def _extract_string(self, payload: Optional[dict[str, object]], key: str) -> Optional[str]:
        if payload is None:
            return None
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _extract_int(self, payload: dict[str, object], key: str) -> Optional[int]:
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None


def parse_token_metrics(line: str) -> Optional[Dict[str, Any]]:
    """
    Fonction utilitaire pour parser une ligne de log.
    
    Args:
        line: Ligne de log
        
    Returns:
        Dictionnaire des métriques ou None
    """
    parser = LogParser()
    metrics = parser.parse_line(line)
    return metrics.to_dict() if metrics else None
