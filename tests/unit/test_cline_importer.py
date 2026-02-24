"""Tests unitaires — ClineImporter (ledger local).

Objectifs:
    - Aucun accès au vrai /home/kidpixel/.cline
    - Vérifier allowlist strict + refus symlink
    - Vérifier parsing minimal + import DB isolée
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kimi_proxy.core import database as db
from kimi_proxy.features.cline_importer.importer import (
    ClineImporter,
    validate_allowlisted_path,
)
from kimi_proxy.features.cline_importer.exceptions import ClineLedgerPathError


def _write_ledger(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_validate_allowlisted_path_accepts_exact_allowlist(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "taskHistory.json"
    _write_ledger(ledger, [])

    # Patch l'allowlist vers le fichier tmp, et vérifier que la même string est acceptée.
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )

    resolved = validate_allowlisted_path(str(ledger))
    assert resolved == ledger.resolve(strict=True)


def test_validate_allowlisted_path_rejects_non_allowlisted(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "taskHistory.json"
    other = tmp_path / "other.json"
    _write_ledger(ledger, [])
    _write_ledger(other, [])

    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )

    with pytest.raises(ClineLedgerPathError):
        validate_allowlisted_path(str(other))


def test_validate_allowlisted_path_rejects_symlink(tmp_path: Path, monkeypatch):
    # Certains environnements/FS peuvent ne pas supporter la création de symlink.
    if not hasattr(Path, "symlink_to"):
        pytest.skip("symlink_to non supporté")

    target = tmp_path / "taskHistory.json"
    _write_ledger(target, [])

    link = tmp_path / "taskHistory_link.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Création de symlink impossible sur cet environnement")

    # Patch allowlist vers le chemin du symlink.
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(link)
    )

    with pytest.raises(ClineLedgerPathError):
        validate_allowlisted_path(str(link))


@pytest.mark.asyncio
async def test_import_default_ledger_imports_valid_rows_and_skips_invalid(tmp_path: Path, monkeypatch):
    # DB isolée
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_FILE", str(tmp_db))
    db.init_database()

    # Ledger tmp
    ledger = tmp_path / "taskHistory.json"
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )

    payload = [
        {
            "id": "t-1",
            "ts": 1000,
            "tokensIn": 10,
            "tokensOut": 5,
            "totalCost": 0.01,
            "modelId": "kimi" ,
        },
        {
            "id": "t-2",
            "ts": "2000",
            "tokensIn": "20",
            "tokensOut": 10,
            "totalCost": "0.02",
            "modelId": "" ,
        },
        # Entrées invalides -> skipped
        {"id": "", "ts": 1, "tokensIn": 1, "tokensOut": 1, "totalCost": 0.0},
        "not-an-object",
    ]
    _write_ledger(ledger, payload)

    importer = ClineImporter(ledger_path=str(ledger))
    result = await importer.import_default_ledger()

    assert result["imported_count"] == 2
    assert result["skipped_count"] >= 2
    assert result["error_count"] == 0
    assert result["latest_ts"] == 2000

    rows = db.list_cline_task_usage(limit=10, offset=0)
    assert len(rows) == 2
    # Tri ts DESC
    assert rows[0]["ts"] >= rows[1]["ts"]

    # Vérifie le schéma minimal
    row = rows[0]
    assert set(row.keys()) == {
        "task_id",
        "ts",
        "model_id",
        "tokens_in",
        "tokens_out",
        "total_cost",
        "imported_at",
    }


@pytest.mark.asyncio
async def test_import_ledger_schema_error_when_not_list(tmp_path: Path, monkeypatch):
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_FILE", str(tmp_db))
    db.init_database()

    ledger = tmp_path / "taskHistory.json"
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )

    # JSON objet (pas tableau)
    _write_ledger(ledger, {"hello": "world"})

    importer = ClineImporter(ledger_path=str(ledger))
    from kimi_proxy.features.cline_importer.exceptions import ClineLedgerSchemaError

    with pytest.raises(ClineLedgerSchemaError):
        await importer.import_default_ledger()
