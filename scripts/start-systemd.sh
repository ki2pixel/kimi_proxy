#!/bin/bash
# Démarrage du proxy et des serveurs MCP HTTP pour le service systemd utilisateur.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

cd "$PROJECT_DIR"

# Chargement robuste du fichier .env (sans xargs).
if [ -f ".env" ]; then
    while IFS='=' read -r key value || [ -n "$key" ]; do
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        [[ -z "$key" || "$key" =~ ^# ]] && continue

        key="${key#export }"
        key="${key#"${key%%[![:space:]]*}"}"
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue

        value="${value%$'\r'}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        value="${value#\"}"; value="${value%\"}"
        value="${value#\'}"; value="${value%\'}"

        export "$key=$value"
    done < .env
fi

if [ -d "$VENV_DIR" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi

export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

# Démarre les serveurs MCP HTTP si nécessaire. Le script est idempotent.
if [ -x "$PROJECT_DIR/scripts/start-mcp-servers.sh" ]; then
    "$PROJECT_DIR/scripts/start-mcp-servers.sh" start \
        || echo "⚠️ Démarrage partiel des serveurs MCP" >&2
fi

# Le processus principal reste au premier plan pour systemd (Type=simple).
exec python -m kimi_proxy \
    --host "${KIMI_HOST:-127.0.0.1}" \
    --port "${KIMI_PORT:-8000}"
