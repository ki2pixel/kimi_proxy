# Agent Developer Cookbook
Parent: [[index]]
Tags: #documentation
---

## Summary
Quick-start reference guide for AI agents modifying the MCE codebase.

## Mappings

### 1. Adding a Component to the Pipeline
Modify [proxy_server.py](file:///Users/k3x/Developer/MCE/mce-core/core/proxy_server.py):
1.  Instantiate the component inside `ProxyServer.__init__()`:
    ```python
    self.new_helper = NewHelper(config.new_config)
    ```
2.  Plug the execution call inside `_process_request()` at the desired step:
    ```python
    res = await self.new_helper.evaluate(request)
    ```

### 2. Adding a Policy Rule
Modify:
1.  [mce_config.py](file:///Users/k3x/Developer/MCE/mce-core/schemas/mce_config.py) to add configuration parameters:
    ```python
    class PolicyConfig(BaseModel):
        new_block_pattern: list[str] = []
    ```
2.  [policy_engine.py](file:///Users/k3x/Developer/MCE/mce-core/engine/policy_engine.py) to enforce the logic:
    ```python
    self._patterns = [re.compile(p) for p in config.new_block_pattern]
    ```
3.  [config.yaml](file:///Users/k3x/Developer/MCE/mce-core/config.yaml) to customize YAML entries.

### 3. Adding a Squeezing Layer
Modify:
1.  Create the layer class in `engine/squeeze/`.
2.  Register execution handler in [proxy_server.py](file:///Users/k3x/Developer/MCE/mce-core/core/proxy_server.py) inside `_squeeze()`.

### 4. Running Unit Tests
Execute virtualenv pytest suite:
```bash
./venv/bin/pytest tests/ -v
```
