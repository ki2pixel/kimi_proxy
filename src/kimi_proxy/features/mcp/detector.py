"""Détection des boucles d'appels MCP."""

import json
import re
import time
from typing import Any, Dict, List, Tuple


class MCPCircuitBreaker:
    """Détecte les boucles infinies d'appels MCP via similarité Jaccard."""

    def __init__(
        self,
        max_failures: int = 5,
        similarity_threshold: float = 0.85,
        enabled: bool = True,
        ttl_seconds: float = 30.0,
    ):
        self.max_failures = max_failures
        self.similarity_threshold = similarity_threshold
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.call_history: List[Tuple[float, set[str]]] = []

    def _tokenize(self, params_str: str) -> set[str]:
        return set(re.findall(r"\w+", params_str.lower()))

    def check_call(self, params: Dict[str, Any]) -> bool:
        """Retourne True si le circuit doit s'ouvrir (bloquer l'appel)."""
        if not self.enabled:
            return False

        now = time.time()
        self.call_history = [
            (ts, tok) for ts, tok in self.call_history if now - ts < self.ttl_seconds
        ]

        params_str = json.dumps(params, sort_keys=True)
        current_tokens = self._tokenize(params_str)

        if not current_tokens:
            return False

        similar_count = 0
        for _ts, past_tokens in self.call_history:
            if not past_tokens:
                continue
            intersection = len(current_tokens.intersection(past_tokens))
            union = len(current_tokens.union(past_tokens))
            jaccard = intersection / union if union > 0 else 0
            if jaccard >= self.similarity_threshold:
                similar_count += 1

        self.call_history.append((now, current_tokens))

        if len(self.call_history) > 20:
            self.call_history.pop(0)

        return similar_count >= self.max_failures
