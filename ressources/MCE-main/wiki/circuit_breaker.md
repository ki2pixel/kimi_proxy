# Circuit Breaker Loop Prevention
Parent: [[index]]
Tags: #safeguard
---

## Summary
The `CircuitBreaker` detects infinite execution loops. If the client agent executes the same tool with identical or highly similar failing arguments $T$ times (default: 3) within a sliding window, the breaker trips to prevent credit/token waste.

## Code References
*   [circuit_breaker.py](file:///Users/k3x/Developer/MCE/mce-core/engine/circuit_breaker.py) — Sliding-window loop detector.
*   [test_circuit_breaker.py](file:///Users/k3x/Developer/MCE/mce-core/tests/test_circuit_breaker.py) — Unit tests for identical and fuzzy loop triggers.

## Algorithmic Details

### 1. Sliding Window & Fingerprinting
Each tool call is logged inside a sliding `deque` window. MCE calculates a `fingerprint` for every tool execution using the hash of `tool_name` + hashed canonical arguments + `is_error` flag.

### 2. Fuzzy Argument Matching (Token Jaccard Similarity)
To prevent agents from bypassing loop detection by changing spacing or minor options (e.g. `npm run test` vs `npm  run  test --force`), MCE calculates Token Jaccard Similarity on consecutive argument sets:
- **Tokenization**: Arguments are serialized to a lowercase string and parsed into alphanumeric word sets.
- **Jaccard Formula**:
  $$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
- **Threshold**: If similarity is $\ge 85\%$ (0.85), the arguments are flagged as fuzzy-similar.
- **Breaker Trip**: If similar/identical failing calls reach the threshold size, uvicorn rejects upstream execution and returns error code `-32002` with a warning message forcing a change of approach.

### 3. Logical Error Checking
Instead of only catching transport-level JSON-RPC protocol issues, the [[proxy_server]] checks if the return dictionary has `isError: true` or `is_error: true`. If so, a logical error is registered in the circuit breaker window.
