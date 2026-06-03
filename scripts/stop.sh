#!/bin/bash
# =============================================================================
# Script d'arrêt du Kimi Proxy Dashboard
# Gère l'arrêt propre du serveur FastAPI et des serveurs MCP externes
# =============================================================================

# Détecter le répertoire du script et se positionner à la racine du projet
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

PORT=8000
PID_FILE=".server.pid"

# Couleurs pour le logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonctions utilitaires de logging
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

echo "🛑 Arrêt du Kimi Proxy Dashboard..."

# =============================================================================
# 1. Arrêter le serveur FastAPI principal
# =============================================================================
echo ""
echo "📡 Arrêt du serveur FastAPI..."

# Arrêter le processus sur le port
PID=$(lsof -ti:$PORT 2>/dev/null)
if [[ ! -z "$PID" ]]; then
    echo "🔪 Arrêt du processus sur le port $PORT (PID: $PID)..."
    kill $PID 2>/dev/null
    sleep 1
    
    # Vérifier s'il est encore là (forcer si nécessaire)
    if kill -0 $PID 2>/dev/null; then
        echo "⚠️  Forçage de l'arrêt..."
        kill -9 $PID 2>/dev/null
        sleep 1
    fi
    
    if [[ -z "$(lsof -ti:$PORT 2>/dev/null)" ]]; then
        log_success "Port $PORT libéré"
    else
        log_error "Impossible d'arrêter le processus"
    fi
else
    log_info "Aucun processus trouvé sur le port $PORT"
fi

# 2. Arrêter tous les processus uvicorn/python liés à main
echo "🔍 Recherche de processus uvicorn..."
UVICORN_PIDS=$(pgrep -f "uvicorn main:app")
if [[ ! -z "$UVICORN_PIDS" ]]; then
    echo "🔪 Arrêt des processus uvicorn: $UVICORN_PIDS"
    echo $UVICORN_PIDS | xargs kill -9 2>/dev/null
    sleep 1
    log_success "Processus uvicorn arrêtés"
fi

PYTHON_PIDS=$(pgrep -f "python.*main.py")
if [[ ! -z "$PYTHON_PIDS" ]]; then
    echo "🔪 Arrêt des processus python: $PYTHON_PIDS"
    echo $PYTHON_PIDS | xargs kill -9 2>/dev/null
    sleep 1
    log_success "Processus python arrêtés"
fi

# 3. Nettoyer le fichier PID si existe
if [[ -f "$PID_FILE" ]]; then
    rm -f "$PID_FILE"
    echo "🗑️  Fichier PID nettoyé"
fi

log_success "Serveur FastAPI arrêté"

# =============================================================================
# 4. Arrêter les serveurs MCP externes (Phase 3)
# =============================================================================
echo ""
echo "🔌 Arrêt des serveurs MCP externes..."
if [[ -f "$SCRIPT_DIR/start-mcp-servers.sh" ]]; then
    "$SCRIPT_DIR/start-mcp-servers.sh" stop
    MCP_STATUS=$?
    if [[ $MCP_STATUS -eq 0 ]]; then
        log_success "Serveurs MCP arrêtés avec succès"
    else
        log_warning "Problème lors de l'arrêt des serveurs MCP (code: $MCP_STATUS)"
    fi
else
    log_warning "Script start-mcp-servers.sh non trouvé"
fi

# =============================================================================
# 5. Nettoyage final
# =============================================================================
echo ""
echo "🧹 Nettoyage final..."

# Nettoyer les fichiers PID MCP si présents
if [[ -f "/tmp/mcp_compression.pid" ]]; then
    rm -f /tmp/mcp_compression.pid
    log_info "Fichier PID Compression MCP nettoyé"
fi

if [[ -f ".mcp-servers.pid" ]]; then
    rm -f .mcp-servers.pid
    log_info "Fichier PID MCP servers nettoyé"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
log_success "Kimi Proxy Dashboard arrêté avec succès"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "👋 À bientôt !"
