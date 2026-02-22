# Task-Master MCP Server Persistence Issue - Containment Solution

## Problem Description

The `task-master-ai` MCP server package exhibited persistent auto-start behavior despite complete removal attempts. The server would automatically restart when working in PyCharm, bypassing all cleanup efforts.

## Root Cause Analysis

- **Auto-discovery mechanism**: PyCharm's MCP system automatically discovers and starts MCP-capable npm packages
- **On-demand downloading**: The IDE uses `npx` to download and execute `task-master-ai` from npm registry on demand
- **Cache bypass**: Standard npm cache cleaning didn't prevent re-downloading
- **IDE integration**: PyCharm's MCP integration circumvents shell-level overrides

## Failed Solutions

1. **PyCharm config removal**: Removed `task-master-ai` from `llm.mcpServers.xml`
2. **Package uninstallation**: `npm uninstall -g task-master-ai`
3. **Cache cleaning**: `npm cache clean --force` + manual cache removal
4. **Wrapper script removal**: Deleted `/home/kidpixel/Documents/task-master-mcp`
5. **PATH override**: Created `~/bin/task-master-ai` dummy script
6. **Shell alias**: Added alias in `.bashrc`
7. **npm config**: Set `ignore-scripts`, disabled fund/audit

## Successful Containment Solution

### Background Killer Script

Created `~/task-master-killer.sh` that continuously monitors and kills task-master processes:

```bash
#!/bin/bash
# Script qui surveille et tue les processus task-master

while true; do
    # Tuer tous les processus task-master
    pkill -f "task-master-ai" 2>/dev/null || true
    pkill -f "npm exec task-master-ai" 2>/dev/null || true

    # Attendre 5 secondes avant de vérifier à nouveau
    sleep 5
done
```

### Persistent Startup

Added to crontab for automatic restart on system reboot:

```bash
(crontab -l 2>/dev/null; echo "@reboot nohup /home/kidpixel/task-master-killer.sh > /dev/null 2>&1 &") | crontab -
```

## Verification

```bash
# Check no task-master processes running
ps aux | grep -i task-master || echo "✅ Clean system"

# Check killer script is running
ps aux | grep task-master-killer || echo "Script not running"
```

## Prevention Measures

### For Future MCP Server Issues

1. **Identify auto-start source**: Check IDE MCP configurations
2. **Block at IDE level**: Remove from IDE settings before uninstalling
3. **Containment as fallback**: Use background killer for persistent issues
4. **Monitor processes**: Regularly check for unauthorized MCP server starts

### Cleanup Checklist

- [ ] Remove from IDE MCP configs (`llm.mcpServers.xml`)
- [ ] Uninstall npm package globally
- [ ] Clean npm caches (`npm cache clean --force`)
- [ ] Remove custom scripts/wrappers
- [ ] Add containment script if needed
- [ ] Verify with `ps aux | grep -i <server-name>`

## Files Created/Modified

- `~/task-master-killer.sh` - Background containment script
- `~/bin/task-master-ai` - PATH override (dummy script)
- `~/.bashrc` - Added PATH and alias overrides
- `~/.config/Code/User/settings.json` - Disabled MCP auto-discovery
- PyCharm `llm.mcpServers.xml` - Removed task-master entry
- Code `constants.py` - Removed task_master config

## Status

✅ **RESOLVED** - Containment solution prevents task-master persistence.

Date: 2026-02-22
Solution: Background process killer with crontab persistence
