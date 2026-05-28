"""
MCE — Semantic Cache Tests
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.semantic_cache import SemanticCache


@pytest.fixture
def cache() -> SemanticCache:
    return SemanticCache(max_entries=4, ttl_seconds=1)


class TestCacheBasics:
    def test_miss_on_empty(self, cache: SemanticCache):
        assert cache.get("tool_a", {"x": 1}) is None
        assert cache.miss_count == 1

    def test_hit_after_put(self, cache: SemanticCache):
        cache.put("tool_a", {"x": 1}, "result", 10)
        entry = cache.get("tool_a", {"x": 1})
        assert entry is not None
        assert entry.payload == "result"
        assert entry.token_count == 10
        assert cache.hit_count == 1

    def test_different_args_miss(self, cache: SemanticCache):
        cache.put("tool_a", {"x": 1}, "result", 10)
        assert cache.get("tool_a", {"x": 2}) is None

    def test_ttl_expiry(self, cache: SemanticCache):
        cache.put("tool_a", {"x": 1}, "result", 10)
        time.sleep(1.1)
        assert cache.get("tool_a", {"x": 1}) is None

    def test_update_existing(self, cache: SemanticCache):
        cache.put("tool_a", {"x": 1}, "old", 10)
        cache.put("tool_a", {"x": 1}, "new", 20)
        entry = cache.get("tool_a", {"x": 1})
        assert entry.payload == "new"
        assert entry.token_count == 20


class TestCacheEviction:
    def test_lru_eviction(self, cache: SemanticCache):
        cache.put("a", {}, "A", 1)
        cache.put("b", {}, "B", 1)
        cache.put("c", {}, "C", 1)
        cache.put("d", {}, "D", 1)
        # Access 'a' to make it recently used
        cache.get("a", {})
        # Add 'e' — should evict 'b' (oldest untouched)
        cache.put("e", {}, "E", 1)
        assert cache.get("a", {}) is not None
        assert cache.get("b", {}) is None
        assert cache.get("e", {}) is not None


class TestCacheInvalidate:
    def test_invalidate_existing(self, cache: SemanticCache):
        cache.put("tool_a", {"x": 1}, "result", 10)
        assert cache.invalidate("tool_a", {"x": 1}) is True
        assert cache.get("tool_a", {"x": 1}) is None

    def test_invalidate_missing(self, cache: SemanticCache):
        assert cache.invalidate("tool_a", {"x": 1}) is False

    def test_clear(self, cache: SemanticCache):
        cache.put("a", {}, "A", 1)
        cache.clear()
        assert cache.entry_count == 0
        assert cache.hit_count == 0
        assert cache.miss_count == 0
        # After clear, a get should be a miss
        assert cache.get("a", {}) is None
        assert cache.miss_count == 1


class TestCacheKey:
    def test_key_determinism(self):
        k1 = SemanticCache.make_key("tool", {"b": 2, "a": 1})
        k2 = SemanticCache.make_key("tool", {"a": 1, "b": 2})
        assert k1 == k2

    def test_key_differs_by_tool(self):
        k1 = SemanticCache.make_key("tool_a", {})
        k2 = SemanticCache.make_key("tool_b", {})
        assert k1 != k2
