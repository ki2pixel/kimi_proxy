"""
MCE CLI — Profile Commands
Manage permission profiles: list, switch, show.
"""

from __future__ import annotations

import re
import typer
import httpx
from pathlib import Path
from rich.console import Console
from rich.table import Table

from schemas.mce_config import PermissionProfilesConfig, PermissionProfile

app = typer.Typer()
console = Console()


def _load_config() -> PermissionProfilesConfig:
    """Load permission profiles from config."""
    try:
        import yaml
        from pathlib import Path

        config_path = Path.cwd() / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
            pp_data = data.get("permission_profiles", {})
            profiles = {}
            for name, settings in pp_data.get("profiles", {}).items():
                profiles[name] = PermissionProfile(**settings)
            return PermissionProfilesConfig(
                active=pp_data.get("active", "focused_work"),
                profiles=profiles,
            )
    except Exception:
        pass
    return PermissionProfilesConfig()


@app.command("list")
def list_profiles():
    """List all permission profiles."""
    config = _load_config()

    from engine.guardian.permission_gate import PermissionGate
    gate = PermissionGate(config)

    table = Table(title="Permission Profiles")
    table.add_column("Profile", style="cyan")
    table.add_column("File Read", justify="center")
    table.add_column("File Write", justify="center")
    table.add_column("Shell Exec", justify="center")
    table.add_column("Destructive", justify="center")
    table.add_column("Active", justify="center")

    for name, info in gate.list_profiles().items():
        active_badge = "[green]●[/green]" if info["active"] else "[dim]○[/dim]"
        table.add_row(
            name,
            _format_perm(info["file_read"]),
            _format_perm(info["file_write"]),
            _format_perm(info["shell_exec"]),
            _format_perm(info["destructive"]),
            active_badge,
        )
    console.print(table)


def _get_proxy_port() -> int:
    try:
        import yaml
        config_path = Path.cwd() / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
            return data.get("proxy", {}).get("port", 3025)
    except Exception:
        pass
    return 3025


def _save_active_profile(profile_name: str) -> bool:
    config_path = Path.cwd() / "config.yaml"
    if not config_path.exists():
        return False
    try:
        content = config_path.read_text(encoding="utf-8")
        # permission_profiles:
        #   active: "focused_work"
        pattern = r"(permission_profiles:\s*\n\s*active:\s*['\"]?)\w+(['\"]?)"
        if re.search(pattern, content):
            new_content = re.sub(pattern, rf"\g<1>{profile_name}\g<2>", content)
            config_path.write_text(new_content, encoding="utf-8")
            return True
    except Exception as e:
        console.print(f"[red]Error saving config.yaml: {e}[/red]")
    return False


def _notify_running_proxy(profile_name: str, port: int):
    try:
        url = f"http://127.0.0.1:{port}/profile/switch"
        response = httpx.post(url, json={"profile": profile_name}, timeout=1.0)
        if response.status_code == 200:
            console.print("[green]✓[/green] Dynamic switch completed (running proxy updated)")
        else:
            console.print(f"[yellow]![/yellow] Failed to update running proxy: {response.text}")
    except httpx.RequestError:
        console.print("[dim]Note: Running proxy server not detected. Profile updated locally in config.yaml.[/dim]")


@app.command()
def switch(
    profile_name: str = typer.Argument(..., help="Profile to switch to"),
):
    """Switch to a different permission profile."""
    config = _load_config()

    from engine.guardian.permission_gate import PermissionGate
    gate = PermissionGate(config)

    if gate.switch_profile(profile_name):
        # 1. Persist in config.yaml
        if _save_active_profile(profile_name):
            console.print(f"[green]✓[/green] Switched to '{profile_name}' profile in config.yaml")
        else:
            console.print(f"[red]✗[/red] Failed to update config.yaml")
        
        # 2. Notify proxy server dynamically
        port = _get_proxy_port()
        _notify_running_proxy(profile_name, port)
    else:
        console.print(f"[red]✗[/red] Profile '{profile_name}' not found")
        console.print("Available profiles:")
        for name in gate.list_profiles():
            console.print(f"  • {name}")


def _format_perm(value: str) -> str:
    """Format a permission value with color."""
    if value == "auto":
        return "[green]auto[/green]"
    elif value == "block":
        return "[red]block[/red]"
    return "[yellow]prompt[/yellow]"
