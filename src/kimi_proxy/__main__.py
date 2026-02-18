"""
Point d'entrée pour `python -m kimi_proxy`.
"""
import sys
import uvicorn

from .main import create_app


def main():
    """Fonction principale."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Kimi Proxy Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Host (défaut: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port (défaut: 8000)")
    parser.add_argument("--reload", action="store_true", help="Activer le reload auto")
    
    args = parser.parse_args()
    
    print(f"🚀 Démarrage du Kimi Proxy Dashboard sur {args.host}:{args.port}")
    
    uvicorn.run(
        "kimi_proxy.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
