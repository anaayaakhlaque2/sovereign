"""
Sovereign Launcher Script
Starts the FastAPI gateway, supervises node processes, and opens the 3D kingdom dashboard.
Usage:
    python run.py
    python run.py --port 8000 --nodes 5 --algo bully
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import webbrowser
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

console = Console(safe_box=True)


def print_banner(host: str, port: int, nodes: int, algo: str) -> None:
    try:
        console.print()
        console.print(
            Panel.fit(
                f"[bold gold1]★  S O V E R E I G N  ★[/]\n"
                f"[bold white]3D Distributed Leader Election Simulator[/]\n"
                f"[dim cyan]Bully & Ring Algorithms over Real TCP Sockets[/]",
                border_style="gold1",
                padding=(1, 4),
            )
        )

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan")
        table.add_column("Details", style="yellow")

        table.add_row("Dashboard UI", f"http://{host}:{port}")
        table.add_row("REST API & Docs", f"http://{host}:{port}/docs")
        table.add_row("WebSocket Stream", f"ws://{host}:{port}/ws")
        table.add_row("Node Cluster", f"{nodes} OS Processes (Ports 9001 - {9000 + nodes})")
        table.add_row("Active Algorithm", f"{algo.upper()}")
        table.add_row("Logical Clock", "Lamport Timestamps on all messages")
        table.add_row("Persistence", "SQLite Database (sovereign.db)")

        console.print(table)
        console.print("[dim italic]Press [bold red]Ctrl+C[/] to gracefully terminate the kingdom cluster.[/]\n")
    except Exception:
        print(f"Sovereign running at http://{host}:{port}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Sovereign Distributed Simulator")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Gateway host")
    parser.add_argument("--port", type=int, default=8000, help="Gateway port (default 8000)")
    parser.add_argument("--nodes", type=int, default=5, help="Initial node count (3-9, default 5)")
    parser.add_argument("--algo", type=str, default="bully", choices=["bully", "ring"], help="Initial algorithm")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")

    args = parser.parse_args()

    # Support cloud environment variables (e.g. Render, Railway, Heroku, Docker)
    host = os.environ.get("HOST", args.host)
    port = int(os.environ.get("PORT", args.port))

    print_banner(host, port, args.nodes, args.algo)

    # Optional auto-launch browser (only in local non-cloud mode)
    if not args.no_browser and not os.environ.get("PORT"):
        import threading
        def open_browser():
            time.sleep(1.8)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    # Start FastAPI server
    try:
        uvicorn.run(
            "backend.gateway.app:app",
            host=host,
            port=port,
            log_level="info",
            reload=False,
        )
    except KeyboardInterrupt:
        console.print("\n[bold red]Sovereign shutting down. Safe travel, traveler.[/]")


if __name__ == "__main__":
    main()
