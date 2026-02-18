#!/usr/bin/env python3
"""
Script d'exécution des tests MCP.

Usage:
    # Tous les tests unitaires (rapides, sans serveurs)
    python tests/run_mcp_tests.py --unit

    # Tests spécifiques à un client
    python tests/run_mcp_tests.py --client qdrant
    python tests/run_mcp_tests.py --client task_master

    # Test E2E (nécessite serveurs MCP démarrés)
    python tests/run_mcp_tests.py --e2e

    # Tous les tests (unitaires + intégration)
    python tests/run_mcp_tests.py --all

    # Avec coverage
    python tests/run_mcp_tests.py --unit --coverage

    # Avec verbose
    python tests/run_mcp_tests.py --unit --verbose
"""
import sys
import subprocess
import argparse
from pathlib import Path


# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text):
    """Print section header."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_success(text):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}", file=sys.stderr)


def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠ {text}{RESET}")


def check_servers_status():
    """Vérifie si les serveurs MCP sont disponibles."""
    import httpx

    servers = {
        "Qdrant": "http://localhost:6333/healthz",
        "Compression": "http://localhost:8001/health",
        "Task Master": "http://localhost:8002/health",
        "Sequential": "http://localhost:8003/health",
        "Filesystem": "http://localhost:8004/health",
        "JSON Query": "http://localhost:8005/health",
    }

    status = {}
    for name, url in servers.items():
        try:
            response = httpx.get(url, timeout=2.0)
            status[name] = response.status_code == 200
        except Exception:
            status[name] = False
    
    return status


def run_pytest(args, markers=None, verbose=False):
    """Run pytest with arguments."""
    cmd = [
        "pytest",
        "-v" if verbose else "-q",
        "--tb=short"
    ]
    
    if markers:
        cmd.extend(["-m", markers])
    
    cmd.extend(args)
    
    print(f"\n{BOLD}Running: {' '.join(cmd)}{RESET}\n")
    result = subprocess.run(cmd, cwd="tests")
    
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Run MCP tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Unit tests only
  python tests/run_mcp_tests.py --unit

  # Test specific client
  python tests/run_mcp_tests.py --client compression

  # E2E tests with servers
  python tests/run_mcp_tests.py --e2e

  # All tests
  python tests/run_mcp_tests.py --all
        """
    )
    
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Run all unit tests (fast, no external deps)"
    )
    
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Run E2E tests (requires MCP servers)"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests (unit + E2E)"
    )
    
    parser.add_argument(
        "--client",
        choices=["qdrant", "compression", "task_master", "sequential", "filesystem", "json_query", "integration"],
        help="Test specific client"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all test files"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--server-status",
        action="store_true",
        help="Check MCP servers status"
    )
    
    args = parser.parse_args()
    
    # Gère --server-status
    if args.server_status:
        print_header("MCP Servers Status")
        status = check_servers_status()
        for name, available in status.items():
            if available:
                print_success(f"{name}: Available")
            else:
                print_error(f"{name}: Unavailable")
        return
    
    # Gère --list
    if args.list:
        print_header("Available Test Files")
        test_dir = Path("tests/mcp")
        for test_file in sorted(test_dir.glob("test_*.py")):
            print(f"  {test_file.name}")
        return
    
    # Build pytest args
    pytest_args = []
    markers = []
    
    # Collecte tests
    if args.all:
        # Tous les tests
        pytest_args.extend([
            "mcp/test_mcp_*.py"
        ])
        if not args.verbose:
            print_warning("E2E tests nécessitent serveurs MCP")
    
    elif args.unit:
        # Tests unitaires (pas E2E)
        markers.extend(["not e2e"])
        pytest_args.extend([
            "mcp/test_mcp_client_integration.py",
            "mcp/test_mcp_qdrant.py",
            "mcp/test_mcp_compression.py",
            "mcp/test_mcp_task_master.py",
            "mcp/test_mcp_sequential.py",
            "mcp/test_mcp_filesystem.py",
            "mcp/test_mcp_json_query.py"
        ])
        print_header("Running UNIT Tests")
    
    elif args.e2e:
        # Tests E2E uniquement
        markers.extend(["e2e"])
        pytest_args.append("mcp/test_mcp_e2e_real_servers.py")
        
        # Vérifie serveurs
        status = check_servers_status()
        if not any(status.values()):
            print_error("Aucun serveur MCP disponible. Démarrez avec:")
            print_warning("  ./scripts/start-mcp-servers.sh start")
            sys.exit(1)
        
        print_header("Running E2E Tests with Real MCP Servers")
    
    elif args.client:
        # Client spécifique
        client_test_map = {
            "qdrant": "mcp/test_mcp_qdrant.py",
            "compression": "mcp/test_mcp_compression.py",
            "task_master": "mcp/test_mcp_task_master.py",
            "sequential": "mcp/test_mcp_sequential.py",
            "filesystem": "mcp/test_mcp_filesystem.py",
            "json_query": "mcp/test_mcp_json_query.py",
            "integration": "mcp/test_mcp_client_integration.py"
        }
        pytest_args.append(client_test_map[args.client])
        print_header(f"Testing {args.client.upper()} Client")
    
    else:
        # Par défaut: tests unitaires
        markers.extend(["not e2e"])
        pytest_args.append("mcp/")
        print_header("Running Default Tests (unit)")
    
    # Coverage
    if args.coverage:
        pytest_args.extend([
            "--cov=../src/kimi_proxy/features/mcp",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])
    
    # Run tests
    success = run_pytest(pytest_args, " and ".join(markers) if markers else None, args.verbose)
    
    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\nTests interrupted by user")
        sys.exit(130)  # 130 = SIGINT
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
