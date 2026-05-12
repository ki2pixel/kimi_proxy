"""Route API /v1/chat/completions — Passthrough MCP session-less.

Pourquoi: permettre a n'importe quel modele de transiter via le proxy
sans session pre-configuree. Les features MCP (tool fixing,
observation masking, context pruning) sont appliquees avant envoi.

Retro-compatibilite: la route /chat/completions existante est conservee
et inchangee.
"""
from __future__ import annotations

import json
from typing import Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...config.loader import get_config
from ...proxy.passthrough import PassthroughProcessor

router = APIRouter()


@router.post("/v1/chat/completions")
async def mcp_passthrough(request: Request):
    """Endpoint OpenAI-compatible session-less avec features MCP.

    Architecture radicale (agnostique provider):
        Cline envoie X-Target-Base-URL + Authorization (cle API).
        Kimi Proxy applique les features MCP puis forward vers la cible.

    Fallback legacy (si X-Target-Base-URL absent):
        Resolution provider depuis config.toml (X-Provider / body / model).

    Les features MCP appliquees:
        - Fix tool calls (IDs manquants, arguments malformes)
        - Observation Masking Schema 1 (troncature resultats tool anciens)
        - Context Pruning via MCP Pruner (elagage messages tool)

    Args:
        request: Requete OpenAI-compatible (body JSON).

    Returns:
        StreamingResponse (SSE) ou JSONResponse selon body["stream"].
    """
    try:
        body_bytes = await request.body()
        body_json: Dict[str, Any] = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        return JSONResponse(
            content={
                "error": "Requete JSON invalide",
                "message": "Le body de la requete n'est pas un JSON valide.",
            },
            status_code=400,
        )

    # Application des features MCP
    config = get_config()
    processor = PassthroughProcessor(config)
    processed_body = await processor.apply_features(body_json)

    # Forward vers le provider (radicale ou legacy)
    raw_headers = dict(request.headers)
    return await processor.forward(processed_body, raw_headers, request)
