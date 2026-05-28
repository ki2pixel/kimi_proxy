# Token Economist & Budgets
Parent: [[index]]
Tags: #optimization
---

## Summary
The `TokenEconomist` tracks token counts and decides when to compress tool outputs. It reads configured limits and applies a multi-tiered decision structure.

## Code References
*   [token_economist.py](file:///Users/k3x/Developer/MCE/mce-core/engine/token_economist.py) — Token accounting and budget evaluations.
*   [mce_config.py](file:///Users/k3x/Developer/MCE/mce-core/schemas/mce_config.py) — Validates that limits satisfy `safe_limit <= squeeze_trigger <= absolute_max`.

## Token Limits & Evaluation Matrix
MCE evaluates output tokens against three thresholds:

| Tier | Size Range | Action | Description |
|---|---|---|---|
| **Tier 1 (Safe)** | `tokens <= safe_limit` | `PASS_THROUGH` | Output returned intact. |
| **Tier 2 (Squeeze-Check)** | `safe_limit < tokens <= squeeze_trigger` | `PASS_THROUGH` | Output returned intact. |
| **Tier 3 (Squeeze-Target)** | `squeeze_trigger < tokens <= absolute_max` | `SQUEEZE` | Output sent to the [[squeezing]] pipeline. |
| **Tier 4 (Critical)** | `tokens > absolute_max` | `SQUEEZE` | Compressed and flagged with a CRITICAL alert. |

## Budget Configuration (YAML)
```yaml
token_limits:
  safe_limit: 1000       # target token size after squeezing
  squeeze_trigger: 2000  # payloads larger than this trigger squeezing
  absolute_max: 8000     # ceiling (flagged as critical)
```
