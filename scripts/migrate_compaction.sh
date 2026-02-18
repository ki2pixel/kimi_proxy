#!/bin/bash
# =============================================================================
# Script de migration Phase 1: Infrastructure Context Compaction
# Kimi Proxy Dashboard v2.1
# =============================================================================

set -e

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_FILE="${DB_FILE:-./sessions.db}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
MIGRATION_FILE="./scripts/migrate_compaction.sql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# =============================================================================
# Fonctions utilitaires
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Vérifications préalables
# =============================================================================

check_prerequisites() {
    log_info "Vérification des prérequis..."
    
    # Vérifie que sqlite3 est installé
    if ! command -v sqlite3 &> /dev/null; then
        log_error "sqlite3 n'est pas installé"
        exit 1
    fi
    
    # Vérifie que le fichier de migration existe
    if [ ! -f "$MIGRATION_FILE" ]; then
        log_error "Fichier de migration non trouvé: $MIGRATION_FILE"
        exit 1
    fi
    
    # Vérifie que la base de données existe
    if [ ! -f "$DB_FILE" ]; then
        log_error "Base de données non trouvée: $DB_FILE"
        exit 1
    fi
    
    log_success "Prérequis OK"
}

# =============================================================================
# Sauvegarde de la base de données
# =============================================================================

create_backup() {
    log_info "Création de la sauvegarde..."
    
    # Crée le répertoire de backup si nécessaire
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_FILE="$BACKUP_DIR/sessions.db.backup.compaction_${TIMESTAMP}"
    
    # Sauvegarde la base
    cp "$DB_FILE" "$BACKUP_FILE"
    
    # Vérifie l'intégrité de la sauvegarde
    if sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
        log_success "Sauvegarde créée: $BACKUP_FILE"
        echo "$BACKUP_FILE" > "$BACKUP_DIR/.last_compaction_backup"
    else
        log_error "La sauvegarde est corrompue"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
}

# =============================================================================
# Exécution de la migration
# =============================================================================

run_migration() {
    log_info "Exécution de la migration SQL..."
    
    # Exécute le script SQL
    if sqlite3 "$DB_FILE" < "$MIGRATION_FILE"; then
        log_success "Migration SQL exécutée avec succès"
    else
        log_error "Échec de la migration SQL"
        exit 1
    fi
}

# =============================================================================
# Vérification post-migration
# =============================================================================

verify_migration() {
    log_info "Vérification de la migration..."
    
    # Vérifie que les colonnes existent
    local columns
    columns=$(sqlite3 "$DB_FILE" "SELECT name FROM pragma_table_info('sessions') WHERE name IN ('reserved_tokens', 'compaction_count', 'last_compaction_at');")
    
    if echo "$columns" | grep -q "reserved_tokens" && \
       echo "$columns" | grep -q "compaction_count" && \
       echo "$columns" | grep -q "last_compaction_at"; then
        log_success "Colonnes ajoutées correctement"
    else
        log_error "Colonnes manquantes dans la table sessions"
        return 1
    fi
    
    # Vérifie que la table compaction_history existe
    if sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='compaction_history';" | grep -q "compaction_history"; then
        log_success "Table compaction_history créée"
    else
        log_error "Table compaction_history manquante"
        return 1
    fi
    
    # Vérifie que les index existent
    local indexes
    indexes=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_compaction_%';")
    
    if echo "$indexes" | grep -q "idx_compaction_session"; then
        log_success "Index créés correctement"
    else
        log_warn "Index manquants (non critique)"
    fi
    
    # Affiche les statistiques
    log_info "Statistiques post-migration:"
    echo "  - Sessions existantes: $(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM sessions;")"
    echo "  - Sessions avec compaction: $(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM sessions WHERE compaction_count > 0;")"
    
    log_success "Vérification terminée"
}

# =============================================================================
# Rollback (en cas d'échec)
# =============================================================================

rollback() {
    log_warn "Exécution du rollback..."
    
    if [ -f "$BACKUP_DIR/.last_compaction_backup" ]; then
        BACKUP_FILE=$(cat "$BACKUP_DIR/.last_compaction_backup")
        if [ -f "$BACKUP_FILE" ]; then
            cp "$BACKUP_FILE" "$DB_FILE"
            log_success "Rollback effectué depuis: $BACKUP_FILE"
        else
            log_error "Fichier de backup introuvable: $BACKUP_FILE"
        fi
    else
        log_error "Aucune sauvegarde de rollback disponible"
    fi
}

# =============================================================================
# Affiche l'aide
# =============================================================================

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Migration Phase 1: Infrastructure Context Compaction pour Kimi Proxy Dashboard

Options:
    -h, --help          Affiche cette aide
    -b, --backup-only   Crée uniquement une sauvegarde
    -r, --rollback      Restaure la dernière sauvegarde
    -d, --dry-run       Simule la migration sans l'exécuter
    -y, --yes           Répond oui à toutes les questions

Variables d'environnement:
    DB_FILE             Chemin vers la base SQLite (défaut: ./sessions.db)
    BACKUP_DIR          Répertoire des sauvegardes (défaut: ./backups)

Exemples:
    $0                  Exécute la migration complète
    $0 --backup-only    Crée uniquement une sauvegarde
    $0 --rollback       Restaure la dernière sauvegarde
EOF
}

# =============================================================================
# Main
# =============================================================================

main() {
    local backup_only=false
    local do_rollback=false
    local dry_run=false
    local yes_flag=false
    
    # Parse les arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -b|--backup-only)
                backup_only=true
                shift
                ;;
            -r|--rollback)
                do_rollback=true
                shift
                ;;
            -d|--dry-run)
                dry_run=true
                shift
                ;;
            -y|--yes)
                yes_flag=true
                shift
                ;;
            *)
                log_error "Option inconnue: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Rollback
    if [ "$do_rollback" = true ]; then
        rollback
        exit 0
    fi
    
    # Vérifications
    check_prerequisites
    
    # Backup only
    if [ "$backup_only" = true ]; then
        create_backup
        exit 0
    fi
    
    # Confirmation
    if [ "$yes_flag" = false ]; then
        echo -e "${YELLOW}Cette opération va modifier la structure de la base de données.${NC}"
        read -p "Continuer? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Opération annulée"
            exit 0
        fi
    fi
    
    # Dry run
    if [ "$dry_run" = true ]; then
        log_info "Mode simulation - aucune modification ne sera effectuée"
        log_info "Script SQL à exécuter:"
        cat "$MIGRATION_FILE"
        exit 0
    fi
    
    # Exécution
    log_info "Démarrage de la migration Phase 1..."
    log_info "Base de données: $DB_FILE"
    log_info "Timestamp: $TIMESTAMP"
    
    create_backup
    run_migration
    verify_migration
    
    log_success "Migration Phase 1 terminée avec succès!"
    log_info "Backup disponible: $BACKUP_FILE"
}

main "$@"
