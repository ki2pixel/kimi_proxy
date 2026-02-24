"""Feature: import ledger local Cline (Solution 1).

Objectif: importer en lecture seule les métriques d'usage depuis
`/home/kidpixel/.cline/data/state/taskHistory.json`.

⚠️ Sécurité: ce module ne doit lire AUCUN autre fichier (secrets, logs, histories).
"""

from .importer import (
    ALLOWED_LEDGER_PATH,
    ClineImporter,
    ClineImportResult,
    validate_allowlisted_path,
)
from .exceptions import (
    ClineImportError,
    ClineLedgerNotFoundError,
    ClineLedgerParseError,
    ClineLedgerPathError,
    ClineLedgerSchemaError,
)

__all__ = [
    "ALLOWED_LEDGER_PATH",
    "ClineImporter",
    "ClineImportResult",
    "validate_allowlisted_path",
    "ClineImportError",
    "ClineLedgerNotFoundError",
    "ClineLedgerParseError",
    "ClineLedgerPathError",
    "ClineLedgerSchemaError",
]
