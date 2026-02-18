#!/bin/bash
# =============================================================================
# Script de Migration vers Structure Modulaire
# Kimi Proxy Dashboard - Phase de Transition
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backup_$(date +%Y%m%d_%H%M%S)"
MIGRATION_LOG="$PROJECT_ROOT/migration.log"

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Fonctions utilitaires
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$MIGRATION_LOG"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1" | tee -a "$MIGRATION_LOG"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$MIGRATION_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$MIGRATION_LOG"
}

# =============================================================================
# Pré-vérifications
# =============================================================================

check_prerequisites() {
    log_info "Vérification des prérequis..."
    
    # Vérifier Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 non trouvé"
        exit 1
    fi
    
    # Vérifier que nous sommes à la racine du projet
    if [ ! -f "$PROJECT_ROOT/main.py" ]; then
        log_error "main.py non trouvé. Veuillez exécuter depuis la racine du projet."
        exit 1
    fi
    
    # Vérifier espace disque (minimum 100MB)
    AVAILABLE=$(df "$PROJECT_ROOT" | tail -1 | awk '{print $4}')
    if [ "$AVAILABLE" -lt 102400 ]; then
        log_warn "Espace disque faible (${AVAILABLE}KB disponible)"
    fi
    
    log_success "Prérequis OK"
}

# =============================================================================
# Backup des données critiques
# =============================================================================

create_backup() {
    log_info "Création du backup dans $BACKUP_DIR..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup base de données
    if [ -f "$PROJECT_ROOT/sessions.db" ]; then
        cp "$PROJECT_ROOT/sessions.db" "$BACKUP_DIR/"
        log_success "Backup sessions.db"
    fi
    
    # Backup configurations
    for config in config.toml config.yaml; do
        if [ -f "$PROJECT_ROOT/$config" ]; then
            cp "$PROJECT_ROOT/$config" "$BACKUP_DIR/"
            log_success "Backup $config"
        fi
    done
    
    # Backup scripts originaux
    mkdir -p "$BACKUP_DIR/scripts"
    for script in start.sh stop.sh test_dashboard.sh; do
        if [ -f "$PROJECT_ROOT/$script" ]; then
            cp "$PROJECT_ROOT/$script" "$BACKUP_DIR/scripts/"
        fi
    done
    log_success "Backup scripts originaux"
    
    # Sauvegarder la structure actuelle
    tree "$PROJECT_ROOT" > "$BACKUP_DIR/structure-before.txt" 2>/dev/null || \
        ls -laR "$PROJECT_ROOT" > "$BACKUP_DIR/structure-before.txt"
    
    log_success "Backup complet dans $BACKUP_DIR"
}

# =============================================================================
# Création de la nouvelle structure
# =============================================================================

create_directory_structure() {
    log_info "Création de la structure de répertoires..."
    
    cd "$PROJECT_ROOT"
    
    # Structure Python
    mkdir -p src/kimi_proxy/{config,core,features/{mcp,sanitizer,compression,log_watcher},proxy,api/routes,services}
    
    # Structure tests
    mkdir -p tests/{unit,integration,e2e}
    
    # Structure bin
    mkdir -p bin
    
    log_success "Structure de répertoires créée"
}

# =============================================================================
# Création des fichiers __init__.py
# =============================================================================

create_init_files() {
    log_info "Création des fichiers __init__.py..."
    
    cd "$PROJECT_ROOT/src/kimi_proxy"
    
    # __init__.py principal
    cat > __init__.py << 'EOF'
"""
Kimi Proxy Dashboard - Monitoring temps réel multi-provider LLM

Package principal contenant:
- core: Tokenization, base de données, modèles
- features: MCP, Sanitizer, Compression, Log Watcher
- proxy: Logique de proxy HTTP
- api: Routes FastAPI
- services: WebSocket manager, rate limiter
"""

__version__ = "2.0.0"
__author__ = "Kimi Proxy Team"

from .core.tokens import count_tokens_tiktoken, count_tokens_text
from .core.database import get_db, init_database

__all__ = [
    "count_tokens_tiktoken",
    "count_tokens_text", 
    "get_db",
    "init_database",
]
EOF

    # __main__.py pour python -m kimi_proxy
    cat > __main__.py << 'EOF'
"""Point d'entrée CLI: python -m kimi_proxy"""
import sys
import uvicorn
from pathlib import Path

# Ajoute src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kimi_proxy.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
EOF

    # Créer tous les __init__.py vides
    find . -type d -exec touch {}/__init__.py \;
    
    log_success "Fichiers __init__.py créés"
}

# =============================================================================
# Extraction des modules Core
# =============================================================================

extract_core_modules() {
    log_info "Extraction des modules core..."
    
    cd "$PROJECT_ROOT"
    
    # core/constants.py
    cat > src/kimi_proxy/core/constants.py << 'EOF'
"""Constantes globales du projet."""

# Contexte
DEFAULT_MAX_CONTEXT: int = 262_144  # 256K tokens
DEFAULT_PROVIDER: str = "managed:kimi-code"
DATABASE_FILE: str = "sessions.db"

# Rate Limiting
DEFAULT_MAX_RPM: int = 40
RATE_LIMIT_WARNING_THRESHOLD: float = 0.875
RATE_LIMIT_CRITICAL_THRESHOLD: float = 0.95

# MCP Memory
MCP_MIN_MEMORY_TOKENS: int = 50

# Sanitizer
DEFAULT_MASKING_THRESHOLD: int = 1000
DEFAULT_PREVIEW_LENGTH: int = 200
CONTEXT_FALLBACK_THRESHOLD: float = 0.90

# Compression
COMPRESSION_THRESHOLD_PERCENTAGE: int = 85
COMPRESSION_PRESERVE_RECENT: int = 5
COMPRESSION_SUMMARY_MAX_TOKENS: int = 500
EOF

    # core/exceptions.py
    cat > src/kimi_proxy/core/exceptions.py << 'EOF'
"""Exceptions personnalisées."""


class KimiProxyError(Exception):
    """Exception de base du projet."""
    pass


class ConfigurationError(KimiProxyError):
    """Erreur de configuration."""
    pass


class ProviderError(KimiProxyError):
    """Erreur de provider (clé API invalide, etc.)."""
    pass


class RateLimitExceeded(KimiProxyError):
    """Rate limit dépassé."""
    pass


class CompressionError(KimiProxyError):
    """Erreur lors de la compression."""
    pass
EOF

    log_success "Modules core extraits"
}

# =============================================================================
# Création des scripts bin/
# =============================================================================

create_bin_scripts() {
    log_info "Création des scripts bin/..."
    
    cd "$PROJECT_ROOT"
    
    # Script principal kimi-proxy
    cat > bin/kimi-proxy << 'EOF'
#!/bin/bash
# Kimi Proxy Dashboard - Commande principale

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/.server.pid"
PORT=8000

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo "Usage: kimi-proxy <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start       Démarrer le serveur"
    echo "  stop        Arrêter le serveur"
    echo "  restart     Redémarrer le serveur"
    echo "  status      Vérifier le statut"
    echo "  test        Lancer les tests"
    echo "  backup      Backup la base de données"
    echo ""
    echo "Options:"
    echo "  -p, --port  Spécifier le port (défaut: 8000)"
    echo "  -h, --help  Afficher cette aide"
}

start_server() {
    echo -e "${BLUE}🚀 Démarrage du Kimi Proxy Dashboard...${NC}"
    
    # Vérifier port libre
    if lsof -ti:$PORT >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Port $PORT occupé${NC}"
        exit 1
    fi
    
    # Activer venv
    if [ -d "$PROJECT_ROOT/venv" ]; then
        source "$PROJECT_ROOT/venv/bin/activate"
    fi
    
    # Lancer
    cd "$PROJECT_ROOT"
    python -m kimi_proxy &
    echo $! > "$PID_FILE"
    
    echo -e "${GREEN}✅ Serveur démarré sur http://localhost:$PORT${NC}"
}

stop_server() {
    echo -e "${BLUE}🛑 Arrêt du serveur...${NC}"
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm "$PID_FILE"
            echo -e "${GREEN}✅ Serveur arrêté${NC}"
        else
            echo -e "${YELLOW}⚠️  Processus déjà arrêté${NC}"
            rm "$PID_FILE"
        fi
    else
        # Fallback: tuer par port
        PID=$(lsof -ti:$PORT 2>/dev/null) && kill "$PID" 2>/dev/null || true
        echo -e "${GREEN}✅ Serveur arrêté (via port)${NC}"
    fi
}

show_status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "${GREEN}✅ Serveur en cours d'exécution${NC}"
        curl -s "http://localhost:$PORT/health" 2>/dev/null || echo "Health check indisponible"
    else
        echo -e "${RED}❌ Serveur arrêté${NC}"
    fi
}

# Parse commande
COMMAND="${1:-}"
shift || true

case "$COMMAND" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 2
        start_server
        ;;
    status)
        show_status
        ;;
    test)
        cd "$PROJECT_ROOT"
        python -m pytest tests/ -v
        ;;
    backup)
        mkdir -p "$PROJECT_ROOT/backups"
        BACKUP="$PROJECT_ROOT/backups/sessions_$(date +%Y%m%d_%H%M%S).db"
        cp "$PROJECT_ROOT/sessions.db" "$BACKUP"
        echo -e "${GREEN}✅ Backup créé: $BACKUP${NC}"
        ;;
    -h|--help|help)
        usage
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Commande inconnue: $COMMAND${NC}"
        usage
        exit 1
        ;;
esac
EOF

    chmod +x bin/kimi-proxy 2>/dev/null || true
    
    # Créer liens symboliques pour compatibilité
    ln -sf kimi-proxy bin/kimi-proxy-start
    ln -sf kimi-proxy bin/kimi-proxy-stop
    ln -sf kimi-proxy bin/kimi-proxy-test
    
    log_success "Scripts bin/ créés"
}

# =============================================================================
# Création setup.py
# =============================================================================

create_setup_py() {
    log_info "Création setup.py..."
    
    cd "$PROJECT_ROOT"
    
    cat > setup.py << 'EOF'
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="kimi-proxy-dashboard",
    version="2.0.0",
    author="Kimi Proxy Team",
    description="Dashboard de monitoring temps réel pour proxy multi-provider LLM",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kidpixel/kimi-proxy",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "kimi-proxy=kimi_proxy.cli:main",
        ],
    },
)
EOF

    log_success "setup.py créé"
}

# =============================================================================
# Tests de validation
# =============================================================================

run_validation_tests() {
    log_info "Exécution des tests de validation..."
    
    cd "$PROJECT_ROOT"
    
    # Test 1: Structure créée
    if [ -d "src/kimi_proxy/core" ] && [ -d "bin" ]; then
        log_success "Structure de répertoires validée"
    else
        log_error "Structure incomplète"
        exit 1
    fi
    
    # Test 2: Scripts exécutables
    if [ -x "bin/kimi-proxy" ]; then
        log_success "Scripts exécutables validés"
    else
        log_error "Scripts non exécutables"
        exit 1
    fi
    
    # Test 3: Python syntaxe
    if python3 -m py_compile src/kimi_proxy/core/constants.py 2>/dev/null; then
        log_success "Syntaxe Python validée"
    else
        log_error "Erreur de syntaxe Python"
        exit 1
    fi
    
    log_success "Tous les tests de validation passent"
}

# =============================================================================
# Rapport final
# =============================================================================

generate_report() {
    log_info "Génération du rapport de migration..."
    
    cat > "$PROJECT_ROOT/MIGRATION_REPORT.txt" << EOF
===============================================================================
RAPPORT DE MIGRATION - Kimi Proxy Dashboard
===============================================================================
Date: $(date)
Backup: $BACKUP_DIR

STRUCTURE CRÉÉE:
- src/kimi_proxy/           # Package Python
- bin/                      # Scripts exécutables  
- tests/                    # Structure tests

FICHIERS CRÉÉS:
- bin/kimi-proxy            # CLI principale
- setup.py                  # Package Python
- src/kimi_proxy/__init__.py
- src/kimi_proxy/core/constants.py
- src/kimi_proxy/core/exceptions.py

ÉTAPES RESTANTES (manuelles):
1. Extraire les modules depuis main.py
2. Migrer les routes FastAPI vers api/
3. Mettre à jour les imports dans main.py
4. Tester l'application complète
5. Mettre à jour la documentation

POUR REVENIR EN ARRIÈRE:
    cp $BACKUP_DIR/sessions.db .
    cp $BACKUP_DIR/scripts/*.sh .
    rm -rf src/kimi_proxy bin/kimi-proxy setup.py

POUR FINALISER:
    ./bin/kimi-proxy start
===============================================================================
EOF

    log_success "Rapport généré: MIGRATION_REPORT.txt"
}

# =============================================================================
# Fonction principale
# =============================================================================

main() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║    MIGRATION VERS STRUCTURE MODULAIRE - Kimi Proxy Dashboard     ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    log_info "Démarrage de la migration..."
    log_info "Projet: $PROJECT_ROOT"
    
    # Exécution des phases
    check_prerequisites
    create_backup
    create_directory_structure
    create_init_files
    extract_core_modules
    create_bin_scripts
    create_setup_py
    run_validation_tests
    generate_report
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✅ MIGRATION INITIALE TERMINÉE                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    log_info "Backup créé dans: $BACKUP_DIR"
    log_info "Voir MIGRATION_REPORT.txt pour les prochaines étapes"
    echo ""
}

# Gestion des erreurs
trap 'log_error "Migration échouée ligne $LINENO"' ERR

# Lancement
main "$@"
