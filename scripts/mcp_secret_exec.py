#!/usr/bin/env python3
"""Exécute un serveur MCP avec des secrets chargés depuis un fichier .env.

Antigravity injecte le champ `env` tel quel et ne garantit pas l'expansion des
variables `${VAR}`. Ce wrapper permet donc de garder les secrets hors de
`mcp_config.json` tout en les injectant dans l'environnement du processus enfant.
"""
from __future__ import annotations

import argparse
import os
import re
import stat
import sys
from pathlib import Path


_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_KEY_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_env_file(path: Path) -> dict[str, str]:
    """Lit un fichier .env simple et retourne les variables qu'il contient."""
    values: dict[str, str] = {}
    content = path.read_text(encoding="utf-8")

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not _KEY_PATTERN.fullmatch(key):
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value

    return values


def _warn_if_permissive(path: Path) -> None:
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        print(
            f"⚠️ Le fichier de secrets {path} est accessible au groupe ou aux autres ; "
            "applique chmod 600.",
            file=sys.stderr,
        )


def _expand_args(args: list[str], env: dict[str, str]) -> list[str]:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return env.get(name, match.group(0))

    return [_ENV_VAR_PATTERN.sub(_replace, arg) for arg in args]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Charge un fichier .env puis exécute une commande MCP.",
    )
    parser.add_argument("--env-file", required=True, help="Fichier .env contenant les secrets.")
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Commande à exécuter, précédée de --.",
    )
    namespace = parser.parse_args(argv)

    command = list(namespace.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("Erreur : aucune commande à exécuter.", file=sys.stderr)
        return 2

    env_path = Path(namespace.env_file).expanduser()
    if not env_path.is_file():
        print(f"Erreur : fichier de secrets introuvable : {env_path}", file=sys.stderr)
        return 1

    try:
        _warn_if_permissive(env_path)
        secrets = parse_env_file(env_path)
    except OSError as exc:
        print(f"Erreur : lecture impossible de {env_path} : {exc}", file=sys.stderr)
        return 1

    env = dict(os.environ)
    env.update(secrets)
    command = _expand_args(command, env)

    try:
        os.execvpe(command[0], command, env)
    except OSError as exc:
        print(f"Erreur : impossible de lancer {command[0]} : {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
