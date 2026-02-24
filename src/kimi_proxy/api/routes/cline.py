"""Routes API — Intégration Cline (Solution 1 : import ledger local).

⚠️ Sécurité
- Lecture seule
- Allowlist strict: `/home/kidpixel/.cline/data/state/taskHistory.json`
- Aucun accès à secrets/logs/historiques conversationnels
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...core.database import list_cline_task_usage, get_latest_cline_task_usage_ts
from ...core.exceptions import DatabaseError
from ...features.cline_importer import ClineImporter
from ...features.cline_importer.exceptions import (
    ClineLedgerNotFoundError,
    ClineLedgerParseError,
    ClineLedgerPathError,
    ClineLedgerSchemaError,
)


router = APIRouter(prefix="/api/cline", tags=["cline"])


class ClineImportRequest(BaseModel):
    """Body optionnel.

    Note: le champ `path` n'est pas destiné à accepter un chemin arbitraire.
    Il peut être fourni pour compat/debug mais sera validé via allowlist strict.
    """

    path: Optional[str] = Field(default=None, description="Chemin ledger (allowlist strict)")


@router.post("/import")
async def import_cline_ledger(request: ClineImportRequest) -> dict:
    """Importe le ledger local Cline (Solution 1)."""
    importer = ClineImporter()

    try:
        return await importer.import_ledger(requested_path=request.path)
    except ClineLedgerPathError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except ClineLedgerNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except (ClineLedgerParseError, ClineLedgerSchemaError) as e:
        raise HTTPException(status_code=422, detail=e.message)
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.message)


@router.get("/usage")
async def get_cline_usage(limit: int = 100, offset: int = 0) -> dict:
    """Retourne les métriques importées (payload minimal, safe)."""
    try:
        rows = list_cline_task_usage(limit=limit, offset=offset)
        return {
            "items": rows,
            "limit": min(max(limit, 0), 1000),
            "offset": max(offset, 0),
        }
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.message)


@router.get("/status")
async def get_cline_status() -> dict:
    """Retourne un statut minimal pour l'UI (dernier ts importé)."""
    try:
        latest_ts = get_latest_cline_task_usage_ts()
        return {"latest_ts": latest_ts}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.message)
