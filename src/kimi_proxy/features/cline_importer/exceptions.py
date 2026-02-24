"""Exceptions pour l'import ledger local Cline (Solution 1)."""

from ...core.exceptions import KimiProxyError


class ClineImportError(KimiProxyError):
    """Erreur de base pour l'import Cline."""

    def __init__(self, message: str, code: str = "cline_import_error"):
        super().__init__(message=message, code=code)


class ClineLedgerPathError(ClineImportError):
    """Chemin demandé non autorisé (allowlist strict)."""

    def __init__(self, message: str = "Chemin ledger Cline non autorisé"):
        super().__init__(message=message, code="cline_ledger_path_error")


class ClineLedgerNotFoundError(ClineImportError):
    """Ledger absent (fichier non trouvé)."""

    def __init__(self, message: str = "Ledger Cline introuvable"):
        super().__init__(message=message, code="cline_ledger_not_found")


class ClineLedgerParseError(ClineImportError):
    """Ledger invalide (JSON corrompu / parse impossible)."""

    def __init__(self, message: str = "Ledger Cline invalide (parse JSON)"):
        super().__init__(message=message, code="cline_ledger_parse_error")


class ClineLedgerSchemaError(ClineImportError):
    """Ledger incompatible (schéma inattendu)."""

    def __init__(self, message: str = "Schéma ledger Cline incompatible"):
        super().__init__(message=message, code="cline_ledger_schema_error")
