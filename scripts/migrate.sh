#!/bin/bash
# =============================================================================
# Script de migration de données
# =============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backup_$(date +%Y%m%d_%H%M%S)"

echo "🔄 Migration Kimi Proxy Dashboard"
echo "=================================="

# Backup
echo "📦 Création du backup..."
mkdir -p "$BACKUP_DIR"
[ -f "$PROJECT_DIR/sessions.db" ] && cp "$PROJECT_DIR/sessions.db" "$BACKUP_DIR/"
[ -f "$PROJECT_DIR/config.toml" ] && cp "$PROJECT_DIR/config.toml" "$BACKUP_DIR/"
echo "✅ Backup créé: $BACKUP_DIR"

# Vérification structure
if [ ! -d "$PROJECT_DIR/src/kimi_proxy" ]; then
    echo "❌ Structure cible non trouvée. Abandon."
    exit 1
fi

# Tests de régression
echo "🧪 Exécution des tests de régression..."
if [ -f "$PROJECT_DIR/tests/e2e/test_regression.py" ]; then
    cd "$PROJECT_DIR"
    if [ -d "$PROJECT_DIR/venv" ]; then
        source "$PROJECT_DIR/venv/bin/activate"
    fi
    PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH" python -m pytest tests/e2e/test_regression.py -v || {
        echo "❌ Tests échoués, migration annulée"
        exit 1
    }
fi

echo ""
echo "✅ Migration prête!"
echo "Pour finaliser: ./bin/kimi-proxy start"
