#!/bin/bash
# =============================================================================
# Wrapper systemd pour Kimi Proxy Dashboard
# Non-interactif, compatible avec Type=simple systemd
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Activer l'environnement virtuel
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Charger les variables d'environnement
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Démarrer les serveurs MCP (optionnel, ne bloque pas le dashboard)
if [ -f "$SCRIPT_DIR/start-mcp-servers.sh" ]; then
    bash "$SCRIPT_DIR/start-mcp-servers.sh" start || {
        echo "[kimi-proxy-systemd] MCP servers failed to start, continuing anyway" >&2
    }
fi

# Lancer le dashboard principal en foreground
# exec remplace le shell par le process python, permettant à systemd
# de tracker directement le PID de uvicorn
export PYTHONPATH=src
exec python -m kimi_proxy --host 0.0.0.0 --port 8000
