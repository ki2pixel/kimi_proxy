#!/bin/bash
# =============================================================================
# Script de démarrage du Kimi Proxy Dashboard
# Gère l'arrêt des processus existants et le nettoyage
# Intègre automatiquement les serveurs MCP externes (Phase 3)
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

echo "🚀 Démarrage du Kimi Proxy Dashboard..."

# 1. Vérifier si un processus utilise déjà le port
echo "🔍 Vérification du port $PORT..."
PID=$(lsof -ti:$PORT 2>/dev/null)
if [[ ! -z "$PID" ]]; then
    echo "⚠️  Port $PORT occupé par le processus $PID - Arrêt en cours..."
    kill -9 $PID 2>/dev/null
    sleep 1
fi

# 2. Vérifier si un ancien processus Python/uvicorn tourne
echo "🔍 Vérification des processus uvicorn/python..."
pkill -9 -f "uvicorn main:app" 2>/dev/null
pkill -9 -f "python.*main.py" 2>/dev/null
sleep 1

# 3. Vérifier à nouveau que le port est libre
PID=$(lsof -ti:$PORT 2>/dev/null)
if [[ ! -z "$PID" ]]; then
    log_error "Impossible de libérer le port $PORT (PID: $PID)"
    echo "   Essayez: sudo kill -9 $PID"
    exit 1
fi

echo "✅ Port $PORT libéré"

# 4. Activer l'environnement virtuel si existe
if [[ -d "venv" ]]; then
    echo "🐍 Activation de l'environnement virtuel..."
    source venv/bin/activate
fi

# 5. Charger automatiquement les variables d'environnement
if [[ -f ".env" ]]; then
    echo "🔑 Chargement des variables d'environnement depuis .env..."
    set -a
    source .env
    set +a
    log_success "Variables d'environnement chargées"
elif [[ -f ".env.example" ]]; then
    log_warning "Fichier .env non trouvé, mais .env.example existe"
    log_info "Copiez .env.example vers .env et configurez vos clés API"
    echo "   cp .env.example .env"
    echo "   nano .env  # ou votre éditeur préféré"
else
    log_warning "Aucun fichier .env trouvé"
    log_info "Le proxy utilisera les valeurs par défaut des fichiers de config"
fi

# 6. Vérifier les dépendances
echo "📦 Vérification des dépendances..."
pip show fastapi >/dev/null 2>&1 || pip install fastapi uvicorn httpx websockets -q

# =============================================================================
# 6. Démarrage des serveurs MCP externes (Phase 3)
# =============================================================================
echo ""
if [[ -f "$SCRIPT_DIR/start-mcp-servers.sh" ]]; then
    "$SCRIPT_DIR/start-mcp-servers.sh" start
    MCP_STATUS=$?
    if [[ $MCP_STATUS -eq 0 ]]; then
        log_success "Serveurs MCP démarrés avec succès"
    else
        log_warning "Les serveurs MCP n'ont pas pu démarrer (code: $MCP_STATUS)"
        log_info "Le proxy continuera sans les fonctionnalités MCP avancées"
    fi
else
    log_warning "Script start-mcp-servers.sh non trouvé"
    log_info "Les fonctionnalités MCP avancées ne seront pas disponibles"
fi

# 6. Supprimer l'ancienne DB si problème de schéma (optionnel - commenter si vous voulez garder l'historique)
# rm -f sessions.db
# echo "🗑️  Base de données réinitialisée"

# 7. Lancer le serveur
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🌐 Lancement du serveur sur http://localhost:$PORT"
echo "═══════════════════════════════════════════════════════════════"
echo "   Appuyez sur Ctrl+C pour arrêter"
echo ""

# Sauvegarde le PID pour le script stop
# Lancement en arrière-plan avec nohup pour pouvoir détacher
trap 'echo ""; echo "👋 Arrêt du serveur..."; exit 0' INT

PYTHONPATH=src python3 -m kimi_proxy

# Si on arrive ici, le serveur s'est arrêté
echo ""
echo "🛑 Serveur arrêté"
