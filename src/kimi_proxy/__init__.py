"""
Kimi Proxy Dashboard - Package principal.
"""

__version__ = "2.0.0"
__author__ = "Kimi Proxy Team"

from .main import create_app, app

__all__ = ["create_app", "app", "__version__"]
