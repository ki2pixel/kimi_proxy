"""kimi_proxy.features.mcp.gateway

Service métier pour le MCP Gateway.

Responsabilités (couche Features):
- Appliquer l'Observation Masking sur des payloads JSON (dict/list/str)
- Préserver la structure JSON-RPC 2.0 (jsonrpc/id/result/error)

Ce module est **sans I/O** (pas d'appels réseau) et ne dépend pas de la couche Proxy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationMaskingConfig:
    """Configuration de troncature des observations."""

    max_chars: int = 4000
    head_chars: int = 2000
    tail_chars: int = 2000


class MCPGatewayService:
    """Service métier pour masquer/tronquer les observations MCP."""

    def __init__(self, config: ObservationMaskingConfig | None = None):
        self._config = config or ObservationMaskingConfig()

    def apply_observation_masking(
        self,
        payload: object,
        *,
        max_chars: int | None = None,
        head_chars: int | None = None,
        tail_chars: int | None = None,
    ) -> object:
        """Masque récursivement un payload JSON (dict/list/str).

        Règle principale:
        - Si une string dépasse `max_chars`, renvoyer `head + marker + tail`.
        """

        cfg = ObservationMaskingConfig(
            max_chars=max_chars if max_chars is not None else self._config.max_chars,
            head_chars=head_chars if head_chars is not None else self._config.head_chars,
            tail_chars=tail_chars if tail_chars is not None else self._config.tail_chars,
        )

        return self._mask_object(payload, cfg)

    def mask_jsonrpc_response(self, response_json: object) -> object:
        """Applique l'Observation Masking à une réponse JSON-RPC 2.0.

        - Si `result` est présent: masque `result`.
        - Sinon, si `error.data` est présent: masque `error.data`.
        - Préserve les autres champs (jsonrpc, id, etc.).
        """

        if not isinstance(response_json, dict):
            return response_json

        # Copie superficielle: on ne veut pas muter l'objet upstream.
        masked: dict[object, object] = dict(response_json)

        if "result" in masked:
            masked["result"] = self.apply_observation_masking(masked.get("result"))
            return masked

        error_obj = masked.get("error")
        if isinstance(error_obj, dict) and "data" in error_obj:
            masked_error: dict[object, object] = dict(error_obj)
            masked_error["data"] = self.apply_observation_masking(masked_error.get("data"))
            masked["error"] = masked_error

        return masked

    def build_jsonrpc_error(
        self,
        request_json: object,
        *,
        code: int,
        message: str,
        data: object | None = None,
    ) -> dict[str, object]:
        """Construit une réponse d'erreur JSON-RPC 2.0.

        Note: conserve `id` si présent dans la requête.
        """

        req_id: object | None = None
        if isinstance(request_json, dict):
            req_id = request_json.get("id")

        error: dict[str, object] = {
            "code": int(code),
            "message": message,
        }
        if data is not None:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "error": error,
            "id": req_id,
        }

    def _mask_object(self, obj: object, cfg: ObservationMaskingConfig) -> object:
        if isinstance(obj, str):
            return self._mask_string(obj, cfg)

        if isinstance(obj, list):
            return [self._mask_object(item, cfg) for item in obj]

        if isinstance(obj, dict):
            return {key: self._mask_object(value, cfg) for key, value in obj.items()}

        return obj

    def _mask_string(self, value: str, cfg: ObservationMaskingConfig) -> str:
        if cfg.max_chars <= 0:
            return value

        original_len = len(value)
        if original_len <= cfg.max_chars:
            return value

        head = value[: max(cfg.head_chars, 0)] if cfg.head_chars > 0 else ""
        tail = value[-max(cfg.tail_chars, 0) :] if cfg.tail_chars > 0 else ""

        marker = (
            "\n... [KIMI_PROXY_OBSERVATION_MASKED "
            f"original_chars={original_len} head={len(head)} tail={len(tail)}] ...\n"
        )

        return f"{head}{marker}{tail}"
