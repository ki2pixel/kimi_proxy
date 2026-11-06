"""Extraction du header Host pour le passthrough."""
from typing import Optional
from urllib.parse import urlparse


def get_provider_host_header(target_url: str) -> Optional[str]:
    """Extrait le header Host approprié pour l'URL cible."""
    try:
        return urlparse(target_url).netloc or None
    except Exception:
        return None
