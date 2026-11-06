#!/usr/bin/env python3
"""Audit statique du code mort de Kimi Proxy Middleware MCP.

Le script est volontairement autonome : il n'importe pas l'application, ne
charge pas la configuration et ne modifie aucun fichier. Il produit un rapport
Markdown ou JSON utilisable pour l'audit et pour les revues futures.

Usage:
    PYTHONPATH=src python scripts/audit_dead_code.py --format markdown
    PYTHONPATH=src python scripts/audit_dead_code.py --format json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "kimi_proxy"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
SETUP_FILE = PROJECT_ROOT / "setup.py"


@dataclass
class ModuleInfo:
    name: str
    path: Path
    is_package: bool = False
    imports: Set[str] = field(default_factory=set)
    defined: Dict[str, int] = field(default_factory=dict)
    routes: List[Tuple[str, str, int]] = field(default_factory=list)
    router_prefix: str = ""


@dataclass
class AuditResult:
    modules: Dict[str, ModuleInfo]
    reachable: Set[str]
    orphan_modules: List[str]
    unused_symbols: Dict[str, List[Tuple[str, int]]]
    routes: List[Tuple[str, str, str, int, bool]]
    tables: Dict[str, Dict[str, int]]
    dependencies: Dict[str, Set[str]]
    declared_dependencies: Set[str]


def module_name_for(path: Path) -> str:
    relative = path.relative_to(SRC_ROOT.parent)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def iter_python_files() -> Iterable[Path]:
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def resolve_relative_import(
    module_name: str, is_package: bool, level: int, imported: Optional[str]
) -> Optional[str]:
    if level <= 0:
        return imported
    package_parts = module_name.split(".")
    if not is_package:
        package_parts = package_parts[:-1]
    keep = len(package_parts) - (level - 1)
    if keep < 0:
        keep = 0
    base = package_parts[:keep]
    if imported:
        base.extend(imported.split("."))
    return ".".join(base)


def collect_imports(tree: ast.AST, module_name: str, is_package: bool) -> Set[str]:
    imports: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            resolved = resolve_relative_import(module_name, is_package, node.level, node.module)
            if resolved:
                imports.add(resolved)
                for alias in node.names:
                    if alias.name != "*":
                        imports.add(f"{resolved}.{alias.name}")
    return imports


def has_route_decorator(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        if decorator.func.attr in {"get", "post", "put", "delete", "patch", "websocket"}:
            return True
    return False


def collect_definitions(tree: ast.AST) -> Dict[str, int]:
    definitions: Dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if has_route_decorator(node):
                continue
            definitions[node.name] = node.lineno
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node.lineno
    return definitions


def collect_routes(tree: ast.AST) -> Tuple[List[Tuple[str, str, int]], str]:
    routes: List[Tuple[str, str, int]] = []
    router_prefix = ""
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if getattr(call.func, "id", "") == "APIRouter":
                for keyword in call.keywords:
                    if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                        router_prefix = str(keyword.value.value)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in {"get", "post", "put", "delete", "patch", "websocket"}:
                continue
            if not isinstance(func.value, ast.Name):
                continue
            if func.value.id not in {"router", "app"}:
                continue
            path = ""
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                path = str(decorator.args[0].value)
            routes.append((func.value.id, func.attr.upper(), path, decorator.lineno))
    return routes, router_prefix


def collect_symbol_references(modules: Dict[str, ModuleInfo]) -> Dict[str, int]:
    references: Dict[str, int] = defaultdict(int)
    for module in modules.values():
        source = module.path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(module.path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                references[node.id] += 1
            elif isinstance(node, ast.Attribute):
                references[node.attr] += 1
    return references


def build_modules() -> Dict[str, ModuleInfo]:
    modules: Dict[str, ModuleInfo] = {}
    for path in iter_python_files():
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            print(f"SyntaxError: {path}: {exc}", file=sys.stderr)
            continue
        name = module_name_for(path)
        is_package = path.name == "__init__.py"
        routes, prefix = collect_routes(tree)
        modules[name] = ModuleInfo(
            name=name,
            path=path,
            is_package=is_package,
            imports=collect_imports(tree, name, is_package),
            defined=collect_definitions(tree),
            routes=routes,
            router_prefix=prefix,
        )
    return modules


def reachable_modules(modules: Dict[str, ModuleInfo], root: str = "kimi_proxy.main") -> Set[str]:
    reachable: Set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        module = modules.get(current)
        if module is None:
            continue
        for imported in module.imports:
            parts = imported.split(".")
            for index in range(len(parts), 0, -1):
                candidate = ".".join(parts[:index])
                if candidate in modules and candidate not in reachable:
                    stack.append(candidate)
                    break
    return reachable


def module_referenced(module_name: str, modules: Dict[str, ModuleInfo], excluded: Set[str]) -> bool:
    if module_name in excluded:
        return False
    for other in modules.values():
        if other.name == module_name:
            continue
        if module_name in other.imports:
            return True
        for imported in other.imports:
            if imported.startswith(module_name + "."):
                return True
    return False


def collect_unused_symbols(
    modules: Dict[str, ModuleInfo], references: Dict[str, int]
) -> Dict[str, List[Tuple[str, int]]]:
    unused: Dict[str, List[Tuple[str, int]]] = {}
    for module in modules.values():
        dead: List[Tuple[str, int]] = []
        for name, line in module.defined.items():
            if name.startswith("__") and name.endswith("__"):
                continue
            if references.get(name, 0) == 0:
                dead.append((name, line))
        if dead:
            unused[module.name] = dead
    return unused


def collect_table_usage(modules: Dict[str, ModuleInfo]) -> Dict[str, Dict[str, int]]:
    usage: Dict[str, Dict[str, int]] = defaultdict(lambda: {"create": 0, "read": 0, "write": 0})
    create_re = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
    for module in modules.values():
        source = module.path.read_text(encoding="utf-8", errors="ignore")
        for table in create_re.findall(source):
            usage[table]["create"] += 1
        for table in list(usage.keys()):
            if re.search(rf"\bSELECT\b[^;]*\bFROM\s+{table}\b", source, re.IGNORECASE | re.DOTALL):
                usage[table]["read"] += 1
            if re.search(rf"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+{table}\b", source, re.IGNORECASE):
                usage[table]["write"] += 1
    return dict(usage)


def declared_requirements() -> Set[str]:
    declared: Set[str] = set()
    if REQUIREMENTS_FILE.exists():
        for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r"):
                continue
            match = re.match(r"([a-zA-Z0-9_.-]+)", line)
            if match:
                declared.add(match.group(1).lower())
    if SETUP_FILE.exists():
        source = SETUP_FILE.read_text(encoding="utf-8")
        for match in re.findall(r'"([a-zA-Z0-9_.-]+)(?:[<>=!~\[].*)?"', source):
            declared.add(match.lower())
    return declared


def imported_top_level_packages(modules: Dict[str, ModuleInfo]) -> Dict[str, Set[str]]:
    packages: Dict[str, Set[str]] = defaultdict(set)
    for module in modules.values():
        for imported in module.imports:
            top = imported.split(".")[0]
            if top and top not in {"kimi_proxy"}:
                packages[top].add(module.name)
    return dict(packages)


def run_audit() -> AuditResult:
    modules = build_modules()
    reachable = reachable_modules(modules)
    entry_points = {"kimi_proxy.__main__"}
    orphan_modules = [
        name
        for name in modules
        if name not in reachable
        and name not in entry_points
        and not module_referenced(name, modules, reachable)
    ]
    references = collect_symbol_references(modules)
    unused_symbols = collect_unused_symbols(modules, references)

    routes: List[Tuple[str, str, str, int, bool]] = []
    router_source = (SRC_ROOT / "api" / "router.py").read_text(encoding="utf-8", errors="ignore")
    for module in modules.values():
        if not module.name.startswith("kimi_proxy.api.routes"):
            continue
        short = module.name.rsplit(".", 1)[-1]
        mounted = f"{short}.router" in router_source or f"{short}.openai_router" in router_source
        for owner, method, path, line in module.routes:
            full_path = f"{module.router_prefix}{path}"
            routes.append((module.name, method, full_path, line, mounted))

    return AuditResult(
        modules=modules,
        reachable=reachable,
        orphan_modules=sorted(orphan_modules),
        unused_symbols=unused_symbols,
        routes=routes,
        tables=collect_table_usage(modules),
        dependencies=imported_top_level_packages(modules),
        declared_dependencies=declared_requirements(),
    )


def render_markdown(result: AuditResult) -> str:
    lines: List[str] = []
    lines.append("# Audit statique — code mort Kimi Proxy")
    lines.append("")
    lines.append(f"- Modules Python analysés : {len(result.modules)}")
    lines.append(f"- Modules atteignables depuis `kimi_proxy.main` : {len(result.reachable)}")
    lines.append(f"- Modules orphelins : {len(result.orphan_modules)}")
    lines.append(f"- Routes détectées : {len(result.routes)}")
    lines.append("")

    lines.append("## Modules orphelins")
    lines.append("")
    if result.orphan_modules:
        lines.append("| Module | Fichier |")
        lines.append("| :--- | :--- |")
        for name in result.orphan_modules:
            lines.append(f"| `{name}` | `{result.modules[name].path.relative_to(PROJECT_ROOT)}` |")
    else:
        lines.append("Aucun module totalement orphelin.")
    lines.append("")

    lines.append("## Symboles définis sans référence")
    lines.append("")
    if result.unused_symbols:
        lines.append("| Module | Symboles |")
        lines.append("| :--- | :--- |")
        for module_name, symbols in sorted(result.unused_symbols.items()):
            rendered = ", ".join(f"`{name}` (L{line})" for name, line in symbols)
            lines.append(f"| `{module_name}` | {rendered} |")
    else:
        lines.append("Aucun symbole sans référence.")
    lines.append("")

    lines.append("## Routes")
    lines.append("")
    lines.append("| Module | Méthode | Chemin | Ligne | Monté |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for module_name, method, path, line, mounted in sorted(result.routes):
        lines.append(f"| `{module_name}` | {method} | `{path}` | {line} | {'oui' if mounted else 'non'} |")
    lines.append("")

    lines.append("## Tables SQL")
    lines.append("")
    lines.append("| Table | CREATE | Lectures | Écritures |")
    lines.append("| :--- | :--- | :--- | :--- |")
    for table, counters in sorted(result.tables.items()):
        lines.append(
            f"| `{table}` | {counters['create']} | {counters['read']} | {counters['write']} |"
        )
    lines.append("")

    lines.append("## Dépendances")
    lines.append("")
    lines.append("| Paquet importé | Modules importateurs |")
    lines.append("| :--- | :--- |")
    for package, importers in sorted(result.dependencies.items()):
        lines.append(f"| `{package}` | {', '.join(sorted(importers))} |")
    lines.append("")

    third_party = {
        package
        for package in result.dependencies
        if package not in sys.stdlib_module_names and package not in result.declared_dependencies
    }
    lines.append("## Imports tiers non déclarés")
    lines.append("")
    if third_party:
        lines.append(", ".join(f"`{package}`" for package in sorted(third_party)))
    else:
        lines.append("Aucun.")
    lines.append("")

    unused_declared = sorted(
        dep for dep in result.declared_dependencies if dep not in result.dependencies
    )
    lines.append("## Dépendances déclarées non importées")
    lines.append("")
    if unused_declared:
        lines.append(", ".join(f"`{dep}`" for dep in unused_declared))
    else:
        lines.append("Aucune.")
    lines.append("")

    return "\n".join(lines)


def render_json(result: AuditResult) -> str:
    payload = {
        "module_count": len(result.modules),
        "reachable_count": len(result.reachable),
        "orphan_modules": result.orphan_modules,
        "unused_symbols": result.unused_symbols,
        "routes": result.routes,
        "tables": result.tables,
        "dependencies": {key: sorted(value) for key, value in result.dependencies.items()},
        "declared_dependencies": sorted(result.declared_dependencies),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit statique du code mort Kimi Proxy")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    result = run_audit()
    if args.format == "json":
        print(render_json(result))
    else:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
