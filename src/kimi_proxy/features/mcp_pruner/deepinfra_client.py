"""kimi_proxy.features.mcp_pruner.deepinfra_client

Client HTTP minimal pour DeepInfra (Phase 1 POC).

Objectifs:
- Appeler l'endpoint d'inférence DeepInfra (cloud) via httpx.AsyncClient.
- Aucune clé en dur: API key via variable d'environnement DEEPINFRA_API_KEY.
- Exposer une primitive de reranking: (query, documents) -> scores par index.
- Parsing **best-effort** (plusieurs formes de réponses), avec exceptions typées.

Notes:
- Ce module ne décide pas du fallback (fail-open). La stratégie de fallback sera
  implémentée dans le backend manager du serveur MCP Pruner (Task 3).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx

from kimi_proxy.core.exceptions import KimiProxyError


JsonObject = dict[str, object]


DEFAULT_DEEPINFRA_ENDPOINT_URL = "https://api.deepinfra.com/v1/inference/Qwen/Qwen3-Reranker-0.6B"


class DeepInfraError(KimiProxyError):
    """Erreur de base DeepInfra (côté client)."""

    def __init__(self, message: str, code: str = "deepinfra_error", details: JsonObject | None = None):
        super().__init__(message=message, code=code, details=details or {})


class DeepInfraConfigError(DeepInfraError):
    """Configuration manquante ou invalide (env vars, paramètres)."""

    def __init__(self, message: str, *, key: str | None = None):
        details: JsonObject = {}
        if key is not None:
            details["key"] = key
        super().__init__(message=message, code="deepinfra_config_error", details=details)


class DeepInfraHTTPError(DeepInfraError):
    """Erreur HTTP (status != 200) ou transport (timeout, connect, etc.)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        endpoint_url: str | None = None,
        response_preview: str | None = None,
    ):
        details: JsonObject = {}
        if status_code is not None:
            details["status_code"] = int(status_code)
        if endpoint_url is not None:
            details["endpoint_url"] = endpoint_url
        if response_preview is not None:
            details["response_preview"] = response_preview
        super().__init__(message=message, code="deepinfra_http_error", details=details)


class DeepInfraParseError(DeepInfraError):
    """Réponse DeepInfra non conforme / impossible à parser."""

    def __init__(self, message: str, *, endpoint_url: str | None = None, response_keys: list[str] | None = None):
        details: JsonObject = {}
        if endpoint_url is not None:
            details["endpoint_url"] = endpoint_url
        if response_keys is not None:
            details["response_keys"] = response_keys
        super().__init__(message=message, code="deepinfra_parse_error", details=details)


@dataclass(frozen=True)
class DeepInfraClientConfig:
    endpoint_url: str
    api_key: str
    timeout_ms: int
    max_docs: int

    @classmethod
    def from_env(cls) -> "DeepInfraClientConfig":
        endpoint_url = os.getenv("DEEPINFRA_ENDPOINT_URL", DEFAULT_DEEPINFRA_ENDPOINT_URL).strip()
        if not endpoint_url:
            endpoint_url = DEFAULT_DEEPINFRA_ENDPOINT_URL

        api_key = (os.getenv("DEEPINFRA_API_KEY") or "").strip()
        if not api_key:
            raise DeepInfraConfigError("DEEPINFRA_API_KEY manquante", key="DEEPINFRA_API_KEY")

        timeout_ms = _env_int("DEEPINFRA_TIMEOUT_MS", default=20_000, min_value=1, max_value=120_000)
        max_docs = _env_int("DEEPINFRA_MAX_DOCS", default=64, min_value=1, max_value=512)

        return cls(endpoint_url=endpoint_url, api_key=api_key, timeout_ms=timeout_ms, max_docs=max_docs)


@dataclass(frozen=True)
class DeepInfraRerankResult:
    scores_by_index: dict[int, float]
    elapsed_ms: int


class DeepInfraClient:
    """Client DeepInfra minimal.

    Usage:
        cfg = DeepInfraClientConfig.from_env()
        async with DeepInfraClient(cfg) as client:
            result = await client.rerank(query="...", documents=["...", "..."])
    """

    def __init__(self, config: DeepInfraClientConfig, *, http_client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._http_client = http_client
        self._owns_client = http_client is None

    async def __aenter__(self) -> "DeepInfraClient":
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=_timeout_from_ms(self._config.timeout_ms))
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def rerank(self, *, query: str, documents: list[str]) -> DeepInfraRerankResult:
        """Retourne un score par index de document.

        Raises:
            DeepInfraConfigError: configuration absente/invalide.
            DeepInfraHTTPError: erreur transport/HTTP.
            DeepInfraParseError: JSON inattendu.
        """

        if self._http_client is None:
            raise DeepInfraConfigError("DeepInfraClient doit être utilisé via 'async with' (client HTTP non initialisé)")

        if not isinstance(query, str):
            raise DeepInfraConfigError("query doit être une chaîne")
        if not isinstance(documents, list) or any(not isinstance(d, str) for d in documents):
            raise DeepInfraConfigError("documents doit être une liste de chaînes")

        if not documents:
            return DeepInfraRerankResult(scores_by_index={}, elapsed_ms=0)

        if len(documents) > self._config.max_docs:
            raise DeepInfraConfigError(
                f"Trop de documents pour rerank: {len(documents)} > DEEPINFRA_MAX_DOCS={self._config.max_docs}",
                key="DEEPINFRA_MAX_DOCS",
            )

        url = self._config.endpoint_url
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: JsonObject = {
            "input": {
                "query": query,
                "documents": list(documents),
            }
        }

        started = time.perf_counter()
        try:
            resp = await self._http_client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise DeepInfraHTTPError("Timeout DeepInfra", endpoint_url=url) from e
        except httpx.HTTPError as e:
            raise DeepInfraHTTPError("Erreur transport DeepInfra", endpoint_url=url) from e

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if resp.status_code != 200:
            preview = _truncate_text(resp.text, 800)
            raise DeepInfraHTTPError(
                f"DeepInfra HTTP {resp.status_code}",
                status_code=resp.status_code,
                endpoint_url=url,
                response_preview=preview,
            )

        try:
            data: object = resp.json()
        except Exception as e:
            raise DeepInfraParseError("Réponse DeepInfra non-JSON", endpoint_url=url) from e

        scores_by_index = _parse_scores_best_effort(data, expected_docs=len(documents), endpoint_url=url)
        return DeepInfraRerankResult(scores_by_index=scores_by_index, elapsed_ms=elapsed_ms)


def _timeout_from_ms(timeout_ms: int) -> httpx.Timeout:
    timeout_s = max(0.001, float(timeout_ms) / 1000.0)
    # Connect court pour éviter de bloquer l'event loop; total = timeout_s
    connect_s = min(5.0, timeout_s)
    return httpx.Timeout(timeout_s, connect=connect_s)


def _env_int(name: str, *, default: int, min_value: int, max_value: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)] + "..."


def _parse_scores_best_effort(data: object, *, expected_docs: int, endpoint_url: str) -> dict[int, float]:
    """Accepte plusieurs formes de réponses.

    Formes supportées (best-effort):
    - `{"scores": [0.1, 0.2, ...]}`
    - `[0.1, 0.2, ...]`
    - `[{"index": 0, "score": 0.123}, ...]`
    - Réponses imbriquées via `result|results|output|data` (dict ou list)
    """

    # 1) Liste directe de floats
    floats = _as_float_list(data)
    if floats is not None:
        return _scores_from_float_list(floats, expected_docs=expected_docs, endpoint_url=endpoint_url)

    # 2) Objet dict: scores au top-level
    if isinstance(data, dict):
        direct = _as_float_list(data.get("scores"))
        if direct is not None:
            return _scores_from_float_list(direct, expected_docs=expected_docs, endpoint_url=endpoint_url)

        # 3) Liste d'objets {index, score}
        for key in ("scores", "results", "result", "output", "data"):
            candidate = data.get(key)
            mapping = _as_index_score_mapping(candidate)
            if mapping is not None:
                return _scores_from_mapping(mapping, expected_docs=expected_docs, endpoint_url=endpoint_url)

            nested_floats = _as_float_list(candidate)
            if nested_floats is not None:
                return _scores_from_float_list(nested_floats, expected_docs=expected_docs, endpoint_url=endpoint_url)

            # One more nesting level if dict
            if isinstance(candidate, dict):
                for subkey in ("scores", "results", "result", "output", "data"):
                    sub = candidate.get(subkey)
                    mapping2 = _as_index_score_mapping(sub)
                    if mapping2 is not None:
                        return _scores_from_mapping(mapping2, expected_docs=expected_docs, endpoint_url=endpoint_url)
                    floats2 = _as_float_list(sub)
                    if floats2 is not None:
                        return _scores_from_float_list(floats2, expected_docs=expected_docs, endpoint_url=endpoint_url)

        keys = [str(k) for k in list(data.keys())[:32]]
        raise DeepInfraParseError("Réponse DeepInfra: clés inattendues (scores introuvables)", endpoint_url=endpoint_url, response_keys=keys)

    raise DeepInfraParseError("Réponse DeepInfra: format inattendu", endpoint_url=endpoint_url)


def _as_float_list(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None
    out: list[float] = []
    for item in value:
        if isinstance(item, bool):
            return None
        if isinstance(item, (int, float)):
            out.append(float(item))
            continue
        return None
    return out


def _as_index_score_mapping(value: object) -> dict[int, float] | None:
    if not isinstance(value, list):
        return None
    mapping: dict[int, float] = {}
    for item in value:
        if not isinstance(item, dict):
            return None
        idx_obj = item.get("index")
        score_obj = item.get("score")

        if not isinstance(idx_obj, int) or isinstance(idx_obj, bool):
            # accept {rank, score} without index? => not handled here
            return None
        if isinstance(score_obj, bool) or not isinstance(score_obj, (int, float)):
            return None
        mapping[int(idx_obj)] = float(score_obj)

    if not mapping:
        return None
    return mapping


def _scores_from_float_list(floats: list[float], *, expected_docs: int, endpoint_url: str) -> dict[int, float]:
    if len(floats) < expected_docs:
        # On tolère si l'API ne renvoie que top-k, mais on doit au moins avoir 1 score.
        if not floats:
            raise DeepInfraParseError("Réponse DeepInfra: liste de scores vide", endpoint_url=endpoint_url)
    return {i: floats[i] for i in range(min(len(floats), expected_docs))}


def _scores_from_mapping(mapping: dict[int, float], *, expected_docs: int, endpoint_url: str) -> dict[int, float]:
    # Filtrer les index hors-range; si tout est hors range, on considère invalide.
    filtered: dict[int, float] = {i: s for i, s in mapping.items() if 0 <= i < expected_docs}
    if not filtered:
        raise DeepInfraParseError("Réponse DeepInfra: indices hors plage", endpoint_url=endpoint_url)
    return filtered
