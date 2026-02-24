"""Tests d’intégration — API Cline (Solution 1 : ledger local).

Important:
    - L'app de test inclut uniquement `cline.router` pour éviter les tâches de lifespan
      (log_watcher, cline_polling) démarrées dans `kimi_proxy.main.create_app()`.
    - Aucun accès au vrai /home/kidpixel/.cline (allowlist patchée vers tmp_path).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from kimi_proxy.api.routes import cline
from kimi_proxy.core import database as db


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _write_ledger(path: Path, payload: object) -> None:
    _write_text(path, json.dumps(payload))


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(cline.router)
    return app


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    # httpx>=0.24 utilise ASGITransport au lieu du paramètre `app=`.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_import_ok_then_usage_and_status(tmp_path: Path, monkeypatch, async_client: httpx.AsyncClient):
    # DB isolée
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_FILE", str(tmp_db))
    db.init_database()

    # Ledger allowlisté
    ledger = tmp_path / "taskHistory.json"
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )
    _write_ledger(
        ledger,
        [
            {"id": "t-1", "ts": 1000, "tokensIn": 10, "tokensOut": 5, "totalCost": 0.01},
            {"id": "t-2", "ts": 2000, "tokensIn": 20, "tokensOut": 10, "totalCost": 0.02},
        ],
    )

    resp = await async_client.post("/api/cline/import", json={"path": None})
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported_count"] == 2
    assert body["latest_ts"] == 2000

    usage = await async_client.get("/api/cline/usage", params={"limit": 10, "offset": 0})
    assert usage.status_code == 200
    usage_body = usage.json()
    assert usage_body["limit"] == 10
    assert usage_body["offset"] == 0
    assert len(usage_body["items"]) == 2
    assert usage_body["items"][0]["ts"] >= usage_body["items"][1]["ts"]

    status = await async_client.get("/api/cline/status")
    assert status.status_code == 200
    assert status.json()["latest_ts"] == 2000


@pytest.mark.asyncio
async def test_import_bad_path_returns_400(tmp_path: Path, monkeypatch, async_client: httpx.AsyncClient):
    # DB isolée
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_FILE", str(tmp_db))
    db.init_database()

    # Allowlist patchée vers un autre fichier
    ledger = tmp_path / "taskHistory.json"
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )
    _write_ledger(ledger, [])

    resp = await async_client.post("/api/cline/import", json={"path": str(tmp_path / "other.json")})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_missing_file_returns_404(tmp_path: Path, monkeypatch, async_client: httpx.AsyncClient):
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_FILE", str(tmp_db))
    db.init_database()

    ledger = tmp_path / "taskHistory.json"
    # Patch allowlist vers un fichier qui n'existe pas
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )

    resp = await async_client.post("/api/cline/import", json={"path": None})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_import_invalid_json_returns_422(tmp_path: Path, monkeypatch, async_client: httpx.AsyncClient):
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_FILE", str(tmp_db))
    db.init_database()

    ledger = tmp_path / "taskHistory.json"
    monkeypatch.setattr(
        "kimi_proxy.features.cline_importer.importer.ALLOWED_LEDGER_PATH", str(ledger)
    )
    _write_text(ledger, "{ this is not json }")

    resp = await async_client.post("/api/cline/import", json={"path": None})
    assert resp.status_code == 422
