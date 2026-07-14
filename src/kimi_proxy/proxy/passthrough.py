"""Passthrough MCP session-less pour /v1/chat/completions.

Pourquoi: permettre a n'importe quel modele de transiter via le proxy
sans necessiter une session pre-configuree dans config.toml.
Les features MCP (tool fixing, observation masking, context pruning)
sont appliquees avant envoi au provider.
"""
from __future__ import annotations

import json
import os
import re
import socket
import urllib.parse
import ipaddress
from typing import Dict, Any

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..config.loader import (
    get_config,
    get_observation_masking_schema1_config,
    get_context_pruning_config,
)
from ..core.constants import DEFAULT_PROVIDER
from ..features.observation_masking import mask_old_tool_results, build_mask_policy_from_config
from ..features.pruner_goal_hint import derive_goal_hint
from .tool_utils import fix_tool_calls_in_request, normalize_tool_call_arguments
from .context_pruning import prune_tool_messages_best_effort
from .client import create_proxy_client
from .stream import stream_generator
from .router import get_provider_host_header
from .transformers import build_gemini_endpoint, convert_to_gemini_format


def sanitize_url(url: str) -> str:
    """Masque les clés d'API et jetons sensibles dans les URLs."""
    if not url:
        return url
    url = re.sub(r'([?&]key=)[^&]*', r'\1[MASQUÉ]', url)
    url = re.sub(r'([?&]api_key=)[^&]*', r'\1[MASQUÉ]', url)
    return url


def validate_and_normalize_target_url(url_str: str) -> str:
    """
    Normalise et valide une URL cible pour éviter les failles SSRF.
    - Utilise urllib.parse pour découper l'URL.
    - Valide le protocole (HTTPS obligatoire, sauf loopback local si KIMI_ENV == "development").
    - Résout l'IP via DNS et bloque loopback/private/link-local/multicast en production.
    - Valide l'allowlist en production.
    - Reconstruit l'URL proprement.
    """
    url_str = url_str.strip()
    try:
        parsed = urllib.parse.urlparse(url_str)
    except Exception as e:
        raise ValueError(f"URL malformée : {e}")

    scheme = parsed.scheme.lower()
    host = parsed.hostname
    port = parsed.port
    
    if not host:
        raise ValueError("URL invalide : hôte manquant.")

    env = os.getenv("KIMI_ENV", "development").strip().lower()
    
    # 1. Validation du protocole
    is_loopback_host = host.lower() in ("localhost", "127.0.0.1", "::1")
    if scheme == "http":
        if env == "production" or not is_loopback_host:
            raise ValueError("Le protocole HTTP non sécurisé est interdit (HTTPS requis).")
    elif scheme != "https":
        raise ValueError(f"Protocole non supporté : {scheme}. Seuls HTTP (dev local uniquement) et HTTPS sont autorisés.")

    # 2. Résolution DNS & Protection SSRF (IP check)
    try:
        addr_info = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80))
        resolved_ips = {info[4][0] for info in addr_info}
    except Exception as dns_err:
        raise ValueError(f"Impossible de résoudre l'hôte '{host}' : {dns_err}")

    # En production, on interdit les IPs de réseaux privés ou loopback
    if env == "production":
        for ip_str in resolved_ips:
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast:
                    raise ValueError(f"Accès à une adresse IP interdite/privée ({ip_str}) détecté.")
            except ValueError as ip_err:
                if "Accès à une adresse IP" in str(ip_err):
                    raise
                raise ValueError(f"Adresse IP invalide résolue ({ip_str}) : {ip_err}")

    # 3. Validation de l'allowlist en production
    config = get_config()
    default_allowlist = {
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com"
    }
    allowlist = set(config.get("security", {}).get("target_allowlist", []))
    if not allowlist:
        allowlist = default_allowlist

    if env != "production":
        allowlist.add("localhost")
        allowlist.add("127.0.0.1")

    host_lower = host.lower()
    allowed = False
    for allowed_domain in allowlist:
        allowed_domain_lower = allowed_domain.lower()
        if host_lower == allowed_domain_lower or host_lower.endswith("." + allowed_domain_lower):
            allowed = True
            break
            
    if not allowed and env == "production":
        raise ValueError(f"L'hôte '{host}' n'est pas autorisé par l'allowlist de sécurité.")

    # 4. Reconstruction propre de l'URL
    netloc = host
    if port:
        netloc = f"{host}:{port}"
    
    path = parsed.path
    rebuilt = urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))
    return rebuilt


def resolve_target(
    request: Request,
    body_json: Dict[str, Any],
    providers: Dict[str, Any],
) -> tuple[str, str, str | None]:
    """Resout la cule finale (base_url, provider_type, api_key).

    Architecture radicale (priorite):
        1. Header X-Target-Base-URL → cible directe (agnostique provider)
        2. Header X-Provider-Type → type de provider (openai/gemini/...)
        3. Legacy: resolution provider depuis config.toml (fallback)

    Args:
        request: Requete FastAPI entrante.
        body_json: Body JSON deja parse.
        providers: Dictionnaire des providers depuis config.toml.

    Returns:
        Tuple (base_url, provider_type, api_key_optionnel).
    """
    # === Architecture radicale : Cline envoie la cible ===
    target_base_url = request.headers.get("x-target-base-url")
    if target_base_url and isinstance(target_base_url, str):
        provider_type = request.headers.get("x-provider-type", "openai")
        # Validation SSRF de la cible
        validated_url = validate_and_normalize_target_url(target_base_url)
        # Cline envoie sa propre cle dans Authorization
        auth_header = request.headers.get("authorization")
        api_key = None
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        print(f"🎯 [PASSTHROUGH] Cible radicale valide: {validated_url} (type={provider_type})")
        return validated_url, provider_type.strip(), api_key

    # === Legacy : resolution depuis config.toml ===
    provider_key = _resolve_provider_legacy(request, body_json)
    provider_cfg = providers.get(provider_key, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider_cfg, dict):
        provider_cfg = {}
    base_url = provider_cfg.get("base_url", "")
    provider_type = provider_cfg.get("type", "openai")
    api_key_raw = provider_cfg.get("api_key", "")
    api_key = api_key_raw.strip() if isinstance(api_key_raw, str) else None
    return base_url, provider_type, api_key


def _resolve_provider_legacy(request: Request, body_json: Dict[str, Any]) -> str:
    """Resolution provider legacy (config.toml) — fallback.

    Ordre:
        1. Header X-Provider
        2. Champ "provider" dans le body JSON
        3. Prefix du nom du modele ("provider/model")
        4. DEFAULT_PROVIDER
    """
    provider_header = request.headers.get("x-provider")
    if provider_header and isinstance(provider_header, str):
        return provider_header.strip()

    body_provider = body_json.get("provider")
    if isinstance(body_provider, str) and body_provider:
        return body_provider.strip()

    model = body_json.get("model", "")
    if isinstance(model, str) and "/" in model:
        return model.split("/", 1)[0]

    return DEFAULT_PROVIDER


def _map_model_for_provider(model_name: str, provider_key: str) -> str:
    """Mappe le nom du modele pour le provider.

    Si le modele commence par 'provider_key/', retire le prefix.
    Sinon, passe le nom tel quel au provider.

    Args:
        model_name: Nom du modele envoye par le client.
        provider_key: Cle du provider cible.

    Returns:
        Nom du modele a envoyer au provider.
    """
    prefix = f"{provider_key}/"
    if model_name.startswith(prefix):
        return model_name[len(prefix):]
    return model_name


class PassthroughProcessor:
    """Processeur de requete passthrough session-less avec features MCP."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers = config.get("providers", {})
        self.models = config.get("models", {})

    async def apply_features(self, body_json: Dict[str, Any]) -> Dict[str, Any]:
        """Applique les features MCP au body de la requete.

        Pipeline:
            1. Fix tool calls (IDs manquants, arguments malformes)
            2. Observation Masking Schema 1 (troncature resultats tool anciens)
            3. Context Pruning via MCP Pruner (elagage messages tool)

        Args:
            body_json: Body JSON OpenAI-compatible.

        Returns:
            Body nettoye pret pour le provider.
        """
        # 1. Fix tool calls
        body_json = fix_tool_calls_in_request(body_json)
        body_json, fixed_count = normalize_tool_call_arguments(body_json)
        if fixed_count > 0:
            print(f"🛠️  [PASSTHROUGH] Arguments tool_calls normalises: {fixed_count}")

        messages = body_json.get("messages", [])
        if not isinstance(messages, list):
            return body_json

        # 2. Observation Masking Schema 1
        schema1_cfg = get_observation_masking_schema1_config(self.config)
        policy = build_mask_policy_from_config(schema1_cfg)
        if policy.enabled:
            try:
                masked_messages = mask_old_tool_results(messages, policy)
                body_json = dict(body_json)
                body_json["messages"] = masked_messages
                print("🎭 [PASSTHROUGH] Observation masking applique")
            except Exception as e:
                print(f"⚠️  [PASSTHROUGH] Observation masking echoue (no-op): {e}")

        # 3. Context Pruning (MCP Pruner)
        pruning_cfg = get_context_pruning_config(self.config)
        if pruning_cfg.enabled:
            try:
                goal_hint = derive_goal_hint(body_json.get("messages", []))
                pruned_messages, summary = await prune_tool_messages_best_effort(
                    messages=body_json.get("messages", []),
                    goal_hint=goal_hint,
                    cfg=pruning_cfg,
                    source_type="logs",
                )
                if summary.calls_attempted > 0:
                    print(
                        f"✂️ [PASSTHROUGH] Context pruning: "
                        f"calls={summary.calls_attempted} "
                        f"pruned={summary.messages_pruned} "
                        f"fallbacks={summary.used_fallback_count}"
                    )
                body_json = dict(body_json)
                body_json["messages"] = pruned_messages
            except Exception as e:
                print(f"⚠️  [PASSTHROUGH] Context pruning echoue (no-op): {e}")

        return body_json

    async def forward(
        self,
        body_json: Dict[str, Any],
        raw_headers: Dict[str, str],
        request: Request,
    ) -> JSONResponse | StreamingResponse:
        """Forward la requete vers le provider avec gestion streaming/non-streaming.

        Architecture radicale: Cline envoie X-Target-Base-URL et Authorization.
        Fallback legacy: utilise la config providers de config.toml.

        Args:
            body_json: Body JSON OpenAI-compatible (deja nettoye par apply_features).
            raw_headers: Headers bruts de la requete cliente.
            request: Requete FastAPI pour extraire les headers radicaux.

        Returns:
            StreamingResponse ou JSONResponse selon le mode demande.
        """
        try:
            base_url, provider_type, api_key = resolve_target(
                request, body_json, self.providers
            )
        except ValueError as val_err:
            return JSONResponse(
                content={
                    "error": "Cible invalide (SSRF Protection)",
                    "message": str(val_err)
                },
                status_code=400
            )

        if not base_url:
            return JSONResponse(
                content={
                    "error": "Cible manquante",
                    "message": (
                        "Aucune cible specifiee. "
                        "Envoyez X-Target-Base-URL (architecture radicale) "
                        "ou configurez le provider dans config.toml (legacy)."
                    ),
                },
                status_code=503,
            )

        proxy_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Kimi-Proxy-MCP/2.0",
        }

        # Cle API: priorite Cline (Authorization header) > config legacy
        if api_key:
            if provider_type == "gemini":
                proxy_headers["x-goog-api-key"] = api_key
            else:
                proxy_headers["Authorization"] = f"Bearer {api_key}"
            print("🔑 [PASSTHROUGH] Cle API injectee: [PRÉSENTE]")
        else:
            print("⚠️  [PASSTHROUGH] Aucune cle API — forward sans Authorization")

        # Host header
        host = get_provider_host_header(base_url)
        if host:
            proxy_headers["Host"] = host

        # Transfert headers client utiles
        for h in ("x-request-id",):
            if h in raw_headers:
                proxy_headers[h] = raw_headers[h]

        # Mapping du modele (retire le prefix provider/ si present)
        model_name = body_json.get("model", "")
        if isinstance(model_name, str) and "/" in model_name:
            # En mode radicale, le modele est envoye tel quel par Cline
            # On ne mappe que si un prefix legacy est detecte
            parts = model_name.split("/", 1)
            if parts[0] in self.providers:
                mapped_model = parts[1]
                body_json = dict(body_json)
                body_json["model"] = mapped_model
                print(f"📝 [PASSTHROUGH] Modele legacy mappe: {model_name} -> {mapped_model}")

        is_streaming = bool(body_json.get("stream", False))

        # Construction requete
        try:
            if provider_type == "gemini":
                target_endpoint = build_gemini_endpoint(
                    base_url, str(body_json.get("model") or ""), is_streaming
                )
                clean_body = json.dumps(convert_to_gemini_format(body_json))
            else:
                target_endpoint = f"{base_url.rstrip('/')}/chat/completions"
                clean_body = json.dumps(body_json)
        except Exception as e:
            print(f"⚠️  [PASSTHROUGH] Erreur construction body: {e}")
            target_endpoint = f"{base_url.rstrip('/')}/chat/completions"
            clean_body = json.dumps(body_json)

        proxy_client = create_proxy_client(timeout=120.0, max_retries=2)
        req = proxy_client.build_request(
            "POST", target_endpoint, headers=proxy_headers, content=clean_body
        )

        try:
            if is_streaming:
                response = await proxy_client.send_streaming(
                    req, provider_type=provider_type
                )

                if response.status_code >= 400:
                    error_text = await response.aread()
                    text = error_text.decode("utf-8", errors="ignore")[:500]
                    print(f"❌ [PASSTHROUGH] Erreur {response.status_code}: {text}")
                    return JSONResponse(
                        content={"error": text, "code": response.status_code},
                        status_code=response.status_code,
                    )

                return StreamingResponse(
                    stream_generator(
                        response,
                        session_id=0,
                        metric_id=0,
                        provider_type=provider_type,
                        models=self.models,
                        manager=None,
                    ),
                    status_code=response.status_code,
                    headers={
                        "Content-Type": response.headers.get(
                            "content-type", "text/event-stream"
                        ),
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                    media_type="text/event-stream",
                )

            # Non-streaming
            response = await proxy_client.send(req, provider_type=provider_type)

            if response.status_code >= 400:
                print(
                    f"❌ [PASSTHROUGH] Erreur {response.status_code}: "
                    f"{response.text[:500]}"
                )
                return JSONResponse(
                    content={
                        "error": response.text[:500],
                        "code": response.status_code,
                    },
                    status_code=response.status_code,
                )

            return JSONResponse(
                content=response.json(), status_code=response.status_code
            )

        except httpx.ReadError as e:
            print(f"🔴 [PASSTHROUGH] ReadError: {e}")
            return JSONResponse(
                content={
                    "error": "Connexion interrompue par le provider",
                    "detail": str(e),
                },
                status_code=502,
            )
        except httpx.TimeoutException as e:
            print(f"🔴 [PASSTHROUGH] Timeout: {e}")
            return JSONResponse(
                content={
                    "error": "Timeout lors de l'appel au provider",
                    "detail": str(e),
                },
                status_code=504,
            )
        except Exception as e:
            print(f"🔴 [PASSTHROUGH] Erreur inattendue: {e}")
            return JSONResponse(
                content={"error": "Erreur inattendue", "detail": str(e)},
                status_code=500,
            )
