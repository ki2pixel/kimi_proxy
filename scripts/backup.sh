#!/bin/bash
# =============================================================================
# Script de backup de la base de données
# =============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "📦 Backup de la base de données"
echo "================================"

# Crée le répertoire de backup
mkdir -p "$BACKUP_DIR"

# Backup de la base
if [[ -f "$PROJECT_DIR/sessions.db" ]]; then
    BACKUP_FILE="$BACKUP_DIR/sessions_$TIMESTAMP.db"
    cp "$PROJECT_DIR/sessions.db" "$BACKUP_FILE"
    gzip "$BACKUP_FILE"
    echo "✅ Backup créé: $BACKUP_FILE.gz"
else
    echo "⚠️  Aucune base de données trouvée"
fi

# Backup de la config
if [[ -f "$PROJECT_DIR/config.toml" ]]; then
    CONFIG_BACKUP="$BACKUP_DIR/config_$TIMESTAMP.toml"
    cp "$PROJECT_DIR/config.toml" "$CONFIG_BACKUP"
    echo "✅ Config backup: $CONFIG_BACKUP"
fi

# Nettoie les vieux backups (garde 10 derniers)
ls -t "$BACKUP_DIR"/sessions_*.db.gz 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true

echo ""
echo "✅ Backup terminé!"
