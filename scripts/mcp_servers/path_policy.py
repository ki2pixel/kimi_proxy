"""Politique de résolution des chemins pour le serveur fast-filesystem.

Principes de sécurité :
- ``MCP_ALLOWED_ROOT`` est la frontière d'autorisation. Un chemin absolu doit
  rester sous cette racine.
- Un chemin relatif n'est accepté que si un workspace root est fourni via
  ``params._meta["ai.kimi-proxy/workspaceRoot"]``. Il doit alors rester sous ce
  workspace (pas d'évasion via ``..``).
- Le workspace root est une base de résolution, jamais une extension de la
  racine autorisée.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

WORKSPACE_META_KEY = "ai.kimi-proxy/workspaceRoot"
FILE_PARAMS = ("path", "file_path", "directory", "source", "destination")


class PathPolicyError(ValueError):
    """Erreur de chemin corrigeable par le client (JSON-RPC -32602)."""

    reason = "INVALID_PATH"

    def __init__(
        self,
        message: str,
        *,
        parameter: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.parameter = parameter
        if reason is not None:
            self.reason = reason


class RelativePathError(PathPolicyError):
    reason = "RELATIVE_PATH_UNSUPPORTED"


class RelativePathEscapesWorkspaceError(PathPolicyError):
    reason = "RELATIVE_PATH_ESCAPES_WORKSPACE"


class WorkspaceRootError(PathPolicyError):
    reason = "INVALID_WORKSPACE_ROOT"


class PathOutsideAllowedRootError(PermissionError):
    """Refus de sécurité (JSON-RPC -32000, HTTP 403)."""

    reason = "PATH_OUTSIDE_ALLOWED_ROOT"

    def __init__(
        self,
        message: str,
        *,
        parameter: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.parameter = parameter
        self.path = path


def load_allowed_root() -> Path:
    """Charge et valide la racine autorisée au démarrage du serveur."""

    raw = (
        os.getenv("MCP_ALLOWED_ROOT")
        or os.getenv("WORKSPACE_PATH")
        or "/home/kidpixel"
    )
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise SystemExit(f"MCP_ALLOWED_ROOT doit être un chemin absolu: {raw!r}")

    root = root.resolve(strict=False)
    if root == Path("/") and os.getenv("MCP_ALLOWED_ROOT_UNSAFE") != "1":
        raise SystemExit(
            "MCP_ALLOWED_ROOT=/ interdit. Définissez une racine explicite "
            "(ex: /home/kidpixel) ou MCP_ALLOWED_ROOT_UNSAFE=1 pour un usage contrôlé."
        )
    if not root.is_dir():
        raise SystemExit(f"MCP_ALLOWED_ROOT inexistant ou non répertoire: {root}")
    return root


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def workspace_root_from_params(
    params: Mapping[str, Any] | object,
    allowed_root: Path,
) -> Path | None:
    """Extrait et valide le workspace root transporté dans ``params._meta``."""

    if not isinstance(params, Mapping):
        return None

    meta = params.get("_meta")
    if meta is None:
        return None
    if not isinstance(meta, Mapping):
        raise WorkspaceRootError("workspaceRoot invalide: objet _meta attendu.")

    raw = meta.get(WORKSPACE_META_KEY)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise WorkspaceRootError("workspaceRoot invalide: chaîne non vide attendue.")

    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise WorkspaceRootError("workspaceRoot invalide: chemin absolu attendu.")

    root = root.resolve(strict=False)
    if not _is_within(root, allowed_root):
        raise WorkspaceRootError(
            f"workspaceRoot invalide: hors de la racine autorisée '{allowed_root}'."
        )
    return root


def resolve_allowed_path(
    raw: object,
    *,
    allowed_root: Path,
    workspace_root: Path | None = None,
    parameter: str = "path",
) -> Path:
    """Résout et valide un paramètre de chemin.

    - absolu : doit rester sous ``allowed_root`` ;
    - relatif : exige ``workspace_root`` et doit rester sous ce workspace.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise PathPolicyError(
            "Paramètre de chemin requis. Fournissez un chemin absolu.",
            parameter=parameter,
            reason="PATH_REQUIRED",
        )

    requested = Path(raw).expanduser()
    if not requested.is_absolute():
        if workspace_root is None:
            raise RelativePathError(
                "Chemin relatif non supporté sur fast-filesystem distant. "
                "Fournissez un chemin absolu.",
                parameter=parameter,
            )
        resolved = (workspace_root / requested).resolve(strict=False)
        if not _is_within(resolved, workspace_root):
            raise RelativePathEscapesWorkspaceError(
                "Chemin relatif hors du workspace courant. Utilisez un chemin "
                "absolu explicite si l'accès inter-projets est intentionnel.",
                parameter=parameter,
            )
        return resolved

    resolved = requested.resolve(strict=False)
    if not _is_within(resolved, allowed_root):
        raise PathOutsideAllowedRootError(
            f"Accès refusé: chemin '{raw}' hors de la racine autorisée '{allowed_root}'",
            parameter=parameter,
            path=raw,
        )
    return resolved


def normalize_path_params(
    params: Mapping[str, Any],
    *,
    allowed_root: Path,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """Retourne une copie des paramètres avec tous les chemins normalisés."""

    if not isinstance(params, Mapping):
        return dict(params) if isinstance(params, dict) else {}

    normalized: dict[str, Any] = dict(params)
    for key in FILE_PARAMS:
        if key in normalized:
            normalized[key] = str(
                resolve_allowed_path(
                    normalized[key],
                    allowed_root=allowed_root,
                    workspace_root=workspace_root,
                    parameter=key,
                )
            )

    if "paths" in normalized:
        paths = normalized["paths"]
        if not isinstance(paths, list):
            raise PathPolicyError(
                "Paramètre 'paths' invalide: liste attendue.",
                parameter="paths",
                reason="INVALID_PATHS",
            )
        normalized["paths"] = [
            str(
                resolve_allowed_path(
                    item,
                    allowed_root=allowed_root,
                    workspace_root=workspace_root,
                    parameter="paths",
                )
            )
            for item in paths
        ]

    return normalized
