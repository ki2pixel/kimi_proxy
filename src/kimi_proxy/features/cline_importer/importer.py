"""Importer ledger local Cline (Solution 1).

Entrée allowlistée:
    /home/kidpixel/.cline/data/state/taskHistory.json

Sortie:
    Table SQLite cline_task_usage (voir core.database)

Sécurité:
    - Lecture seule
    - Allowlist strict (chemin exact + refus symlink)
    - Ne stocke que des métriques numériques (pas de payload)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TypedDict

import aiofiles

from ...core.database import (
    ClineTaskUsageInsert,
    get_latest_cline_task_usage_ts,
    upsert_cline_task_usage_bulk,
)
from .exceptions import (
    ClineLedgerNotFoundError,
    ClineLedgerParseError,
    ClineLedgerPathError,
    ClineLedgerSchemaError,
)


ALLOWED_LEDGER_PATH = "/home/kidpixel/.cline/data/state/taskHistory.json"


class ClineImportResult(TypedDict):
    imported_count: int
    skipped_count: int
    error_count: int
    latest_ts: Optional[int]


def validate_allowlisted_path(requested_path: str) -> Path:
    """Valide un chemin selon allowlist strict.

    Règles (volontairement strictes):
    - le chemin doit être EXACTEMENT égal à ALLOWED_LEDGER_PATH
    - le fichier doit exister et être un fichier régulier
    - le fichier ne doit pas être un symlink
    """

    candidate = Path(requested_path).expanduser()
    allowed = Path(ALLOWED_LEDGER_PATH)

    # Refuse toute variante (.., chemins relatifs, etc.)
    if str(candidate) != str(allowed):
        raise ClineLedgerPathError(
            f"Chemin non allowlisté: {candidate} (attendu: {allowed})"
        )

    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as e:
        raise ClineLedgerNotFoundError(f"Fichier introuvable: {candidate}") from e

    # Si un composant du chemin est un symlink, resolve() changera le path.
    # On refuse pour garantir l'allowlist strict.
    if str(resolved) != str(candidate):
        raise ClineLedgerPathError(f"Symlink (ou redirection) refusé: {candidate}")

    if not resolved.is_file():
        raise ClineLedgerSchemaError(f"Le ledger n'est pas un fichier: {candidate}")

    if resolved.is_symlink():
        raise ClineLedgerPathError(f"Symlink refusé: {candidate}")

    # Vérifie aussi la cohérence avec le chemin allowlisté résolu.
    try:
        allowed_resolved = allowed.resolve(strict=True)
    except FileNotFoundError as e:
        raise ClineLedgerNotFoundError(f"Fichier introuvable: {allowed}") from e
    if resolved != allowed_resolved:
        raise ClineLedgerPathError("Chemin résolu différent de l'allowlist")

    return resolved


def _coerce_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} doit être un int (bool reçu)")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            return int(stripped)
    raise ValueError(f"{field_name} doit être un int")


def _coerce_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} doit être un float (bool reçu)")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        try:
            return float(stripped)
        except ValueError as e:
            raise ValueError(f"{field_name} doit être un float") from e
    raise ValueError(f"{field_name} doit être un float")


def _coerce_timestamp_to_int(value: object) -> int:
    """Convertit ts en int.

    Supporte:
    - epoch ms/seconds (int/float)
    - string numérique
    - ISO 8601 (best-effort)
    """

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)

        # ISO 8601 best-effort (sans timezone -> local)
        normalized = stripped.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass

    raise ValueError("ts doit être un timestamp")


def _coerce_optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _parse_entry(obj: object) -> ClineTaskUsageInsert:
    if not isinstance(obj, dict):
        raise ValueError("entrée non objet")

    raw_id = obj.get("id")
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError("id manquant")

    ts = _coerce_timestamp_to_int(obj.get("ts"))
    tokens_in = _coerce_int(obj.get("tokensIn"), "tokensIn")
    tokens_out = _coerce_int(obj.get("tokensOut"), "tokensOut")
    total_cost = _coerce_float(obj.get("totalCost"), "totalCost")
    model_id = _coerce_optional_str(obj.get("modelId"))

    return {
        "task_id": raw_id.strip(),
        "ts": ts,
        "model_id": model_id,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "total_cost": total_cost,
    }


async def _read_json_with_retry(path: Path, attempts: int = 3) -> object:
    last_error: Optional[Exception] = None

    for attempt in range(attempts):
        try:
            async with aiofiles.open(path, "r", encoding="utf-8", errors="strict") as f:
                content = await f.read()
            return json.loads(content)
        except json.JSONDecodeError as e:
            last_error = e
            if attempt < attempts - 1:
                await asyncio.sleep(0.05 * (2 ** attempt))
                continue
            raise ClineLedgerParseError("JSONDecodeError sur taskHistory.json") from e
        except FileNotFoundError as e:
            raise ClineLedgerNotFoundError(f"Fichier introuvable: {path}") from e
        except UnicodeDecodeError as e:
            raise ClineLedgerParseError("Erreur encoding UTF-8 sur taskHistory.json") from e
        except Exception as e:
            last_error = e
            raise ClineLedgerParseError("Erreur lecture ledger Cline") from e

    # Théoriquement inatteignable
    raise ClineLedgerParseError("Erreur lecture ledger Cline") from last_error


@dataclass(frozen=True)
class ClineImporter:
    """Importer ledger local Cline (Solution 1)."""

    ledger_path: str = ALLOWED_LEDGER_PATH

    async def import_ledger(self, requested_path: Optional[str] = None) -> ClineImportResult:
        """Importe le ledger Cline (idempotent via upsert)."""

        effective_path = requested_path or self.ledger_path
        path = validate_allowlisted_path(effective_path)

        data = await _read_json_with_retry(path, attempts=3)

        if not isinstance(data, list):
            raise ClineLedgerSchemaError("taskHistory.json doit être un tableau JSON")

        imported: List[ClineTaskUsageInsert] = []
        skipped_count = 0
        error_count = 0

        for entry in data:
            try:
                imported.append(_parse_entry(entry))
            except ValueError:
                # Entrée invalide -> ignorée
                skipped_count += 1
                continue
            except Exception:
                # Erreur inattendue, on n'arrête pas tout l'import.
                error_count += 1
                continue

        latest_ts: Optional[int]
        if imported:
            latest_ts = max(row["ts"] for row in imported)
        else:
            latest_ts = None

        # Upsert DB sync dans un thread pour éviter blocage event loop
        imported_count = await asyncio.to_thread(upsert_cline_task_usage_bulk, imported)

        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "latest_ts": latest_ts,
        }

    async def import_default_ledger(self) -> ClineImportResult:
        """Importe le ledger allowlisté par défaut."""
        return await self.import_ledger(requested_path=self.ledger_path)

    async def get_latest_ts(self) -> Optional[int]:
        """Dernier ts en DB (helper, DB sync dans thread)."""
        return await asyncio.to_thread(get_latest_cline_task_usage_ts)
