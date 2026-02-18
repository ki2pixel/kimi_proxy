"""
Logique de proxy HTTP vers les APIs LLM.
"""

from .router import (
    get_target_url_for_session,
    get_provider_host_header,
    find_heavy_duty_model,
    get_max_context_for_session,
)
from .transformers import (
    convert_to_gemini_format,
    convert_from_gemini_response,
    build_gemini_endpoint,
)
from .stream import (
    stream_generator,
    extract_usage_from_stream,
    extract_usage_from_response,
)
from .client import create_proxy_client, ProxyClient

__all__ = [
    "get_target_url_for_session",
    "get_provider_host_header",
    "find_heavy_duty_model",
    "get_max_context_for_session",
    "convert_to_gemini_format",
    "convert_from_gemini_response",
    "build_gemini_endpoint",
    "stream_generator",
    "extract_usage_from_stream",
    "extract_usage_from_response",
    "create_proxy_client",
    "ProxyClient",
]
