# Squeezing & Caching Engine
Parent: [[index]]
Tags: #optimization
---

## Summary
The MCE Squeeze Engine compresses oversized payloads through a 3-layer pipeline to save token context, backed by an LRU cache that auto-invalidates on mutations.

## Code References
*   [layer1_pruner.py](file:///Users/k3x/Developer/MCE/mce-core/engine/squeeze/layer1_pruner.py) — Zero-latency deterministic pruners.
*   [layer2_semantic.py](file:///Users/k3x/Developer/MCE/mce-core/engine/squeeze/layer2_semantic.py) — CPU sentence embedding chunk retrieval.
*   [layer3_synthesizer.py](file:///Users/k3x/Developer/MCE/mce-core/engine/squeeze/layer3_synthesizer.py) — Local LLM summarizer.
*   [semantic_cache.py](file:///Users/k3x/Developer/MCE/mce-core/models/semantic_cache.py) — LRU cache.

## The 3-Layer Squeeze Pipeline

### Layer 1: Deterministic Pruning (~0ms)
Runs regex and structural transforms to discard metadata overhead:
- **HTML-to-Markdown**: Converts rich HTML blocks to clean Markdown formatting.
- **Base64 Stripping**: Locates and removes binary Base64 blobs.
- **Null Value Pruning**: Removes null fields from JSON objects.
- **Array Truncation**: Truncates arrays exceeding limits, adding a metadata count.
- **Whitespace Collapsing**: Simplifies vertical/horizontal spacing.

### Layer 2: Semantic Router (CPU RAG)
If the payload is still too large, MCE splits it into semantic chunks:
- Embeds the chunks and the original query using a micro-transformer (e.g. `all-MiniLM-L6-v2`).
- Runs cosine similarity utilizing the pre-normalized `VectorStore`.
- Selects the top $K$ most relevant chunks and attempts to reconstruct the payload while maintaining type constraints.

### Layer 3: Local Synthesizer
Optional local LLM fallback that pings Ollama (e.g., Qwen 2.5 3B) to generate an information-dense, highly-terse bulleted summary.

---

## Semantic Caching & State Invalidation

### Lookup Keys
The cache is keyed on the deterministic hash of the tool name and sorted arguments:
`hash(tool_name + canonical(arguments))`

### Cache Invalidation on Mutations
To prevent stale reads, any successful invocation of a state-mutating tool clears the cache. Mutators include:
- `write_file`, `edit_file`, `create_file`, `replace_file_content`, `multi_replace_file_content`
- `delete_file`, `rm`, `rmdir`
- `execute_command`, `run_command`, `shell_exec`
