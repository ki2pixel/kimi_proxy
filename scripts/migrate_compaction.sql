-- =============================================================================
-- Migration Phase 1: Infrastructure de Base Context Compaction
-- Kimi Proxy Dashboard v2.1
-- =============================================================================
-- Cette migration ajoute les colonnes et tables nécessaires pour la gestion
-- avancée de la compaction du contexte LLM.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Étape 1: Ajout des colonnes à la table sessions
-- ---------------------------------------------------------------------------

-- Colonne pour les tokens réservés (espace tampon pour compaction)
ALTER TABLE sessions ADD COLUMN reserved_tokens INTEGER DEFAULT 0;

-- Colonne pour le compteur de compactions effectuées
ALTER TABLE sessions ADD COLUMN compaction_count INTEGER DEFAULT 0;

-- Colonne pour la date de dernière compaction
ALTER TABLE sessions ADD COLUMN last_compaction_at TIMESTAMP;

-- ---------------------------------------------------------------------------
-- Étape 2: Création de la table compaction_history
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compaction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_saved INTEGER NOT NULL,
    preserved_messages INTEGER NOT NULL,
    summarized_messages INTEGER NOT NULL,
    compaction_ratio REAL NOT NULL,
    trigger_reason TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Index pour accélérer les requêtes par session
CREATE INDEX IF NOT EXISTS idx_compaction_session ON compaction_history(session_id);

-- Index pour les requêtes temporelles
CREATE INDEX IF NOT EXISTS idx_compaction_timestamp ON compaction_history(timestamp);

-- ---------------------------------------------------------------------------
-- Étape 3: Migration des données existantes (si applicable)
-- ---------------------------------------------------------------------------

-- Initialise les compteurs pour les sessions existantes
UPDATE sessions 
SET reserved_tokens = 0, 
    compaction_count = 0 
WHERE reserved_tokens IS NULL;

-- ---------------------------------------------------------------------------
-- Vérification de la migration
-- ---------------------------------------------------------------------------

-- Vérifie que les colonnes existent
SELECT 
    'Colonnes sessions ajoutées' as check_item,
    COUNT(*) as result
FROM pragma_table_info('sessions')
WHERE name IN ('reserved_tokens', 'compaction_count', 'last_compaction_at');

-- Vérifie que la table existe
SELECT 
    'Table compaction_history créée' as check_item,
    COUNT(*) as result
FROM sqlite_master 
WHERE type='table' AND name='compaction_history';

-- Compte les index créés
SELECT 
    'Index créés' as check_item,
    COUNT(*) as result
FROM sqlite_master 
WHERE type='index' AND name LIKE 'idx_compaction_%';
