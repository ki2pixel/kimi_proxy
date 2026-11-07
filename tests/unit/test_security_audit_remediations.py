"""Tests unitaires pour les remédiations de sécurité issues de l'audit 2026."""
import inspect
import json
import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _make_request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
        }
    )


def test_tool_utils_has_no_arbitrary_evaluation(monkeypatch):
    import kimi_proxy.proxy.tool_utils as tool_utils

    source = inspect.getsource(tool_utils)
    assert "literal_eval" not in source
    assert "eval(" not in source

    called: list[str] = []
    monkeypatch.setattr(os, "system", lambda command: called.append(command))

    hostile_input = '{"a": __import__("os").system("echo INJECTED")}'
    result = tool_utils.fix_malformed_json_arguments(hostile_input)

    assert called == []
    assert isinstance(result, str)


def test_repair_pipeline_repairs_and_bounds_failure_reasons():
    from kimi_proxy.proxy.tool_utils import (
        JSON_FIX_METRICS,
        fix_malformed_json_arguments,
    )

    repaired = fix_malformed_json_arguments('{"query":"abc" "limit":3}')
    assert json.loads(repaired) == {"query": "abc", "limit": 3}
    assert JSON_FIX_METRICS["failure_reasons"].maxlen == 100


@pytest.mark.asyncio
async def test_ssrf_protection(monkeypatch):
    from kimi_proxy.proxy.passthrough import validate_and_normalize_target_url

    # 1. En mode développement, le loopback reste autorisé.
    monkeypatch.setenv("KIMI_ENV", "development")
    url_dev_ok = await validate_and_normalize_target_url("http://localhost:8000")
    assert "localhost:8000" in url_dev_ok

    url_dev_loopback = await validate_and_normalize_target_url("https://127.0.0.1:8443/v1")
    assert url_dev_loopback == "https://127.0.0.1:8443/v1"

    with pytest.raises(ValueError, match="HTTP non sécurisé est interdit"):
        await validate_and_normalize_target_url("http://api.openai.com")

    # Les plages privées, link-local, multicast et réservées sont bloquées
    # même en développement.
    for blocked_url in (
        "https://10.0.0.1/v1",
        "https://169.254.169.254/latest/meta-data",
        "https://224.0.0.1/v1",
        "https://240.0.0.1/v1",
    ):
        with pytest.raises(ValueError, match="Accès à une adresse IP interdite/privée"):
            await validate_and_normalize_target_url(blocked_url)

    # 2. En mode production, le loopback est refusé et l'allowlist s'applique.
    monkeypatch.setenv("KIMI_ENV", "production")
    with pytest.raises(ValueError, match="Le protocole HTTP non sécurisé est interdit"):
        await validate_and_normalize_target_url("http://127.0.0.1")

    with pytest.raises(ValueError, match="Accès à une adresse IP interdite/privée"):
        await validate_and_normalize_target_url("https://127.0.0.1")

    with pytest.raises(ValueError, match="pas autorisé par l'allowlist"):
        await validate_and_normalize_target_url("https://evil-domain.com/api")

    url_prod_ok = await validate_and_normalize_target_url("https://api.openai.com/v1")
    assert url_prod_ok == "https://api.openai.com/v1"


@pytest.mark.asyncio
async def test_verify_admin_key_reads_environment_dynamically(monkeypatch):
    from kimi_proxy.api.dependencies import verify_admin_key

    monkeypatch.setenv("KIMI_ENV", "development")
    monkeypatch.setenv("KIMI_ADMIN_KEY", "secret-initial")

    wrong_request = _make_request([(b"x-admin-key", b"wrong-key")])
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_key(wrong_request, credentials=None)

    assert exc_info.value.status_code == 401
    assert "Non autorisé" in exc_info.value.detail

    valid_request = _make_request([(b"x-admin-key", b"secret-initial")])
    await verify_admin_key(valid_request, credentials=None)

    # La clé est relue à chaque requête : l'ancien jeton devient invalide.
    monkeypatch.setenv("KIMI_ADMIN_KEY", "secret-rotated")
    with pytest.raises(HTTPException):
        await verify_admin_key(valid_request, credentials=None)
