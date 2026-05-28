# Guardian Security Engine
Parent: [[index]]
Tags: #safeguard
---

## Summary
The MCE Guardian merges pre-execution category checks (`PermissionGate`) and post-execution payload content verifications (`DriftSentinel`) to restrict malicious tool abuse.

## Code References
*   [permission_gate.py](file:///Users/k3x/Developer/MCE/mce-core/engine/guardian/permission_gate.py) — Pre-flight permission profiles.
*   [drift_sentinel.py](file:///Users/k3x/Developer/MCE/mce-core/engine/guardian/drift_sentinel.py) — Content constraint checker.

## 1. Permission Gate (Pre-flight)
Categorizes tools into classes (`file_read`, `file_write`, `shell_exec`, `destructive`) and checks them against the active profile:

### Permission Profiles (YAML)
- **`exploration`**: Auto-allows reads, prompts writes and shells, blocks destructive actions.
- **`focused_work`**: Auto-allows reads and writes, prompts shells and destructive actions.
- **`review`**: Auto-allows reads, blocks writes, shells, and destructive actions.

### Decision Actions
*   `ALLOW` / `AUTO_ALLOW`: Bypasses prompts, executing immediately (while still enforcing policy checks).
*   `BLOCK`: Immediately aborts with code `-32001` (Unauthorized).
*   `PROMPT`: Invokes standard human HitL prompt confirmation.

---

## 2. Drift Sentinel (Post-flight)
Scans tool results for matches against active regex patterns representing constraints (e.g. credential leakage, unauthorized file modifications).
- **Critical Severity**: Blocks the return payload instantly and returns code `-32001`, logging a warning to the console.
- **Normal Severity**: Appends a warning notice to the client response but allows execution to succeed.
