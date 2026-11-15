#!/usr/bin/env python3
"""
Serveur MCP Fast Filesystem HTTP
Gère les opérations fichiers haute performance
"""

import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List

# Le module path_policy est colocalisé : on l'importe aussi bien en exécution
# directe (python3 scripts/mcp_servers/fast_filesystem_server.py) qu'en test.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from path_policy import (  # noqa: E402
    WORKSPACE_META_KEY,
    PathOutsideAllowedRootError,
    PathPolicyError,
    load_allowed_root,
    normalize_path_params,
    resolve_allowed_path,
    workspace_root_from_params,
)

# Configuration
HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8004"))

# MCP minimal handshake support
DEFAULT_MCP_PROTOCOL_VERSION = "2025-11-25"

# Racine autorisée : remplacée au démarrage par load_allowed_root().
# La valeur par défaut ne sert qu'aux imports/tests ; elle n'est jamais utilisée
# pour élargir la politique de sécurité.
ALLOWED_ROOT: Path = Path("/home/kidpixel")

__all__ = ["ALLOWED_ROOT", "FastFilesystemHandler", "WORKSPACE_META_KEY", "run_server"]

# Paramètres de chemin obligatoires par outil (fail-closed avant les handlers).
REQUIRED_PATH_PARAMS: Dict[str, tuple[str, ...]] = {
    "fast_list_directory": ("path",),
    "fast_read_file": ("path",),
    "fast_write_file": ("path",),
    "fast_search_files": ("directory",),
    "fast_read_multiple_files": ("paths",),
    "fast_get_directory_tree": ("path",),
}

LEGACY_REQUIRED_PATH_PARAMS: Dict[str, tuple[str, ...]] = {
    "list_directory": ("path",),
    "read_file": ("path",),
    "write_file": ("path",),
    "search_files": ("directory",),
}

class FastFilesystemHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes JSON-RPC 2.0"""

    def log_message(self, format, *args):
        """Supprime les logs par défaut"""
        pass

    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Envoie une réponse JSON"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _is_path_allowed(self, path: str) -> bool:
        """Compatibilité : vérifie si un chemin absolu est sous la racine.

        La validation réelle est déléguée à path_policy.resolve_allowed_path.
        Les chemins relatifs ne sont pas autorisés par ce helper (fail-closed).
        """
        try:
            resolve_allowed_path(
                path,
                allowed_root=ALLOWED_ROOT,
                workspace_root=None,
                parameter="path",
            )
            return True
        except (PathPolicyError, PathOutsideAllowedRootError, ValueError):
            return False

    def _restrict_to_workspace(
        self,
        params: Dict[str, Any],
        workspace_root: Path | None = None,
    ) -> Dict[str, Any]:
        """Normalise et valide tous les chemins avant d'appeler un handler."""
        return normalize_path_params(
            params,
            allowed_root=ALLOWED_ROOT,
            workspace_root=workspace_root,
        )

    def do_OPTIONS(self):
        """Répond aux preflight sans wildcard CORS."""
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        """Gère les requêtes GET (health check)"""
        if self.path == "/health":
            self._send_json_response({
                "status": "healthy",
                "server": "fast-filesystem-mcp",
                "version": "1.0.0",
                "capabilities": ["file_operations", "directory_management", "search"],
                "tools_count": 6
            })
        else:
            self._send_json_response({"error": "Not found"}, 404)

    def do_POST(self):
        """Gère les requêtes POST (JSON-RPC)"""
        if self.path != "/rpc":
            self._send_json_response({"error": "Not found"}, 404)
            return

        req_id = None
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)

            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")

            # MCP handshake + tools
            if method == "initialize":
                protocol_version = DEFAULT_MCP_PROTOCOL_VERSION
                if isinstance(params, dict) and isinstance(params.get("protocolVersion"), str):
                    protocol_version = str(params.get("protocolVersion"))
                self._send_json_response(
                    {
                        "jsonrpc": "2.0",
                        "result": {
                            "protocolVersion": protocol_version,
                            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                            "serverInfo": {"name": "fast-filesystem-mcp", "version": "1.0.0"},
                            "instructions": (
                                "Chemins absolus obligatoires pour tous les outils fast_*. "
                                f"Racine autorisée: {ALLOWED_ROOT}. "
                                "Les chemins relatifs, '.' et '..' sont refusés. "
                                "Utilisez le pont local pour un contexte workspace."
                            ),
                        },
                        "id": req_id,
                    }
                )
                return

            if method == "notifications/initialized":
                self._send_json_response({"jsonrpc": "2.0", "result": {"ok": True}, "id": req_id})
                return

            if method == "tools/list":
                self._send_json_response(
                    {
                        "jsonrpc": "2.0",
                        "result": {
                            "tools": [
                                {
                                    "name": "fast_list_directory",
                                    "description": (
                                        "Lister un répertoire. Chemin absolu obligatoire "
                                        f"sous {ALLOWED_ROOT}."
                                    ),
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {"path": {"type": "string"}},
                                        "required": ["path"],
                                    },
                                },
                                {
                                    "name": "fast_read_file",
                                    "description": (
                                        "Lire un fichier texte. Chemin absolu obligatoire "
                                        f"sous {ALLOWED_ROOT}."
                                    ),
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {"path": {"type": "string"}},
                                        "required": ["path"],
                                    },
                                },
                                {
                                    "name": "fast_write_file",
                                    "description": (
                                        "Écrire un fichier texte. Chemin absolu obligatoire "
                                        f"sous {ALLOWED_ROOT}."
                                    ),
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "path": {"type": "string"},
                                            "content": {"type": "string"},
                                        },
                                        "required": ["path", "content"],
                                    },
                                },
                                {
                                    "name": "fast_search_files",
                                    "description": (
                                        "Recherche simple de fichiers (substring match). "
                                        "'directory' doit être un chemin absolu sous "
                                        f"{ALLOWED_ROOT}."
                                    ),
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "directory": {"type": "string"},
                                            "pattern": {"type": "string"},
                                        },
                                        "required": ["directory", "pattern"],
                                    },
                                },
                                {
                                    "name": "fast_read_multiple_files",
                                    "description": (
                                        "Lire plusieurs fichiers texte. Chaque chemin doit "
                                        f"être absolu sous {ALLOWED_ROOT}."
                                    ),
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
                                        "required": ["paths"],
                                    },
                                },
                                {
                                    "name": "fast_get_directory_tree",
                                    "description": (
                                        "Arborescence d'un répertoire. Chemin absolu "
                                        f"obligatoire sous {ALLOWED_ROOT}."
                                    ),
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "path": {"type": "string"},
                                            "max_depth": {"type": "integer"},
                                            "include_files": {"type": "boolean"},
                                        },
                                        "required": ["path"],
                                    },
                                },
                            ]
                        },
                        "id": req_id,
                    }
                )
                return

            if method == "tools/call":
                tool_name = None
                tool_args: Dict[str, Any] = {}
                if isinstance(params, dict):
                    tool_name = params.get("name")
                    if isinstance(params.get("arguments"), dict):
                        tool_args = params.get("arguments")

                try:
                    workspace_root = workspace_root_from_params(params, ALLOWED_ROOT)
                    required = REQUIRED_PATH_PARAMS.get(tool_name or "", ())
                    for required_param in required:
                        if required_param not in tool_args:
                            raise PathPolicyError(
                                f"Paramètre '{required_param}' requis. "
                                "Fournissez un chemin absolu.",
                                parameter=required_param,
                                reason="PATH_REQUIRED",
                            )

                    tool_args = self._restrict_to_workspace(tool_args, workspace_root)

                    if tool_name == "fast_list_directory":
                        tool_result = self._handle_list_directory(tool_args)
                    elif tool_name == "fast_read_file":
                        tool_result = self._handle_read_file(tool_args)
                    elif tool_name == "fast_write_file":
                        tool_result = self._handle_write_file(tool_args)
                    elif tool_name == "fast_search_files":
                        tool_result = self._handle_search_files(tool_args)
                    elif tool_name == "fast_read_multiple_files":
                        paths = tool_args.get("paths", [])
                        if not isinstance(paths, list):
                            raise ValueError("Paramètre 'paths' invalide")
                        tool_result = self._handle_read_multiple_files(paths)
                    elif tool_name == "fast_get_directory_tree":
                        tool_result = self._handle_get_directory_tree(tool_args)
                    else:
                        self._send_json_response(
                            {
                                "jsonrpc": "2.0",
                                "error": {"code": -32602, "message": f"Outil inconnu: {tool_name}"},
                                "id": req_id,
                            }
                        )
                        return
                except PathPolicyError as e:
                    error_data: Dict[str, Any] = {
                        "reason": e.reason,
                        "allowed_root": str(ALLOWED_ROOT),
                    }
                    if e.parameter:
                        error_data["parameter"] = e.parameter
                    self._send_json_response(
                        {
                            "jsonrpc": "2.0",
                            "error": {"code": -32602, "message": str(e), "data": error_data},
                            "id": req_id,
                        },
                        200,
                    )
                    return
                except PermissionError as e:
                    error_data = {
                        "reason": getattr(e, "reason", "PATH_OUTSIDE_ALLOWED_ROOT"),
                        "allowed_root": str(ALLOWED_ROOT),
                    }
                    parameter = getattr(e, "parameter", None)
                    if parameter:
                        error_data["parameter"] = parameter
                    self._send_json_response(
                        {
                            "jsonrpc": "2.0",
                            "error": {"code": -32000, "message": str(e), "data": error_data},
                            "id": req_id,
                        },
                        403,
                    )
                    return
                except Exception as e:
                    self._send_json_response(
                        {"jsonrpc": "2.0", "error": {"code": -32602, "message": str(e)}, "id": req_id},
                        200,
                    )
                    return

                if isinstance(tool_result, dict) and "content" in tool_result:
                    text_content = str(tool_result["content"])
                elif isinstance(tool_result, str):
                    text_content = tool_result
                else:
                    text_content = json.dumps(tool_result, ensure_ascii=False, indent=2)

                self._send_json_response(
                    {
                        "jsonrpc": "2.0",
                        "result": {"content": [{"type": "text", "text": text_content}]},
                        "id": req_id,
                    }
                )
                return

            # -----------------------------------------------------------------
            # MCP optional discovery APIs (Continue.dev compatibility)
            # -----------------------------------------------------------------
            if method == "resources/list":
                self._send_json_response(
                    {"jsonrpc": "2.0", "result": {"resources": []}, "id": req_id}
                )
                return

            if method == "resources/templates/list":
                self._send_json_response(
                    {"jsonrpc": "2.0", "result": {"resourceTemplates": []}, "id": req_id}
                )
                return

            if method == "prompts/list":
                self._send_json_response(
                    {"jsonrpc": "2.0", "result": {"prompts": []}, "id": req_id}
                )
                return

            # Legacy routes (compat)
            # Vérifier les permissions pour toutes les méthodes filesystem legacy
            legacy_params = params if isinstance(params, dict) else {}
            for required_param in LEGACY_REQUIRED_PATH_PARAMS.get(method or "", ()):
                if required_param not in legacy_params:
                    raise PathPolicyError(
                        f"Paramètre '{required_param}' requis. Fournissez un chemin absolu.",
                        parameter=required_param,
                        reason="PATH_REQUIRED",
                    )
            legacy_workspace_root = workspace_root_from_params(legacy_params, ALLOWED_ROOT)
            params = self._restrict_to_workspace(legacy_params, legacy_workspace_root)

            if method == "health":
                result = self._handle_health()
                self._send_json_response({"jsonrpc": "2.0", "result": result, "id": req_id})
                return
            if method == "list_directory":
                result = self._handle_list_directory(params)
                self._send_json_response({"jsonrpc": "2.0", "result": result, "id": req_id})
                return
            if method == "read_file":
                result = self._handle_read_file(params)
                self._send_json_response({"jsonrpc": "2.0", "result": result, "id": req_id})
                return
            if method == "write_file":
                result = self._handle_write_file(params)
                self._send_json_response({"jsonrpc": "2.0", "result": result, "id": req_id})
                return
            if method == "search_files":
                result = self._handle_search_files(params)
                self._send_json_response({"jsonrpc": "2.0", "result": result, "id": req_id})
                return

            self._send_json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": req_id,
                }
            )
            return

        except PathPolicyError as e:
            error_data: Dict[str, Any] = {
                "reason": e.reason,
                "allowed_root": str(ALLOWED_ROOT),
            }
            if e.parameter:
                error_data["parameter"] = e.parameter
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": str(e), "data": error_data},
                "id": req_id
            }, 200)
        except PermissionError as e:
            error_data = {
                "reason": getattr(e, "reason", "PATH_OUTSIDE_ALLOWED_ROOT"),
                "allowed_root": str(ALLOWED_ROOT),
            }
            parameter = getattr(e, "parameter", None)
            if parameter:
                error_data["parameter"] = parameter
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e), "data": error_data},
                "id": req_id
            }, 403)
        except Exception as e:
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id
            }, 500)

    def _handle_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "capabilities": ["file_operations", "search"],
            "tools": ["list_directory", "read_file", "write_file", "search_files"],
            "timestamp": datetime.now().isoformat()
        }

    def _handle_list_directory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params["path"]
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                items.append({
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                })
            return {"path": path, "items": items, "count": len(items)}
        except Exception as e:
            return {"error": str(e)}

    def _handle_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params["path"]
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"content": content, "size": len(content)}
        except Exception as e:
            return {"error": str(e)}

    def _handle_write_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params["path"]
        content = params.get("content", "")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"path": path, "success": True, "bytes_written": len(content)}
        except Exception as e:
            return {"error": str(e)}

    def _handle_search_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        directory = params["directory"]
        pattern = params.get("pattern", "*")
        try:
            matches = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if pattern in file:
                        matches.append(os.path.join(root, file))
            return {"directory": directory, "matches": matches, "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}

    def _handle_read_multiple_files(self, paths: List[str]) -> Dict[str, Any]:
        results = []
        for p in paths:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                results.append({"path": p, "content": content, "size": len(content)})
            except Exception as e:
                results.append({"path": p, "error": str(e)})
        return {"files": results, "count": len(results)}

    def _handle_get_directory_tree(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params["path"]
        max_depth = params.get("max_depth", 3)
        include_files = params.get("include_files", True)

        if not isinstance(max_depth, int) or max_depth < 0:
            max_depth = 3

        def _build_tree(current_path: str, depth: int) -> Dict[str, Any]:
            node: Dict[str, Any] = {
                "name": os.path.basename(current_path) or current_path,
                "path": current_path,
                "type": "directory" if os.path.isdir(current_path) else "file",
            }

            if not os.path.isdir(current_path) or depth >= max_depth:
                if os.path.isfile(current_path):
                    try:
                        node["size"] = os.path.getsize(current_path)
                    except Exception:
                        node["size"] = 0
                return node

            children = []
            try:
                for entry in os.scandir(current_path):
                    if entry.is_dir(follow_symlinks=False):
                        children.append(_build_tree(entry.path, depth + 1))
                    elif include_files:
                        try:
                            size = entry.stat(follow_symlinks=False).st_size
                        except Exception:
                            size = 0
                        children.append({"name": entry.name, "path": entry.path, "type": "file", "size": size})
            except Exception as e:
                node["error"] = str(e)
                return node

            node["children"] = children
            return node

        return {"tree": _build_tree(path, 0)}

def run_server():
    """Démarre le serveur HTTP après validation de la racine autorisée."""
    global ALLOWED_ROOT
    ALLOWED_ROOT = load_allowed_root()
    server = HTTPServer((HOST, PORT), FastFilesystemHandler)
    print(f"🚀 Serveur MCP Fast Filesystem démarré sur http://{HOST}:{PORT}")
    print(f"🔒 Racine autorisée: {ALLOWED_ROOT}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
