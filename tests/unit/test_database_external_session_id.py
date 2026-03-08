from __future__ import annotations

import sqlite3

from kimi_proxy.core import database as db


def test_init_database_adds_external_session_id_and_supports_session_crud(tmp_path, monkeypatch) -> None:
    tmp_db = tmp_path / "sessions.sqlite3"
    monkeypatch.setattr(db, "DATABASE_FILE", str(tmp_db))

    db.init_database()

    conn = sqlite3.connect(tmp_db)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]
    finally:
        conn.close()

    assert "external_session_id" in columns

    session = db.create_session(
        name="Session test",
        provider="managed:kimi-code",
        model="kimi-for-coding",
        external_session_id="ext-001",
    )

    assert session["external_session_id"] == "ext-001"
    assert db.update_session_external_id(session["id"], "ext-002") is True

    reloaded = db.get_session_by_id(session["id"])
    assert reloaded is not None
    assert reloaded["external_session_id"] == "ext-002"