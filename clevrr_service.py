"""NEMO-OS Service Manager - Main CLI entry point."""

from __future__ import annotations

import argparse
import logging
import platform
import sys
import threading
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


CONFIG_DIR = Path("./clevrr_data")
VERSION = "3.0.0"

BANNER = """
  ███╗   ██╗███████╗███╗   ███╗ ██████╗ 
  ████╗  ██║██╔════╝████╗ ████║██╔═══██╗
  ██╔██╗ ██║█████╗  ██╔████╔██║██║   ██║
  ██║╚██╗██║██╔══╝  ██║╚██╔╝██║██║   ██║
  ██║ ╚████║███████╗██║ ╚═╝ ██║╚██████╔╝
  ╚═╝  ╚═══╝╚══════╝╚═╝     ╚═╝ ╚═════╝ 
  
  NEMO-OS Security Automation Layer v{version}
  Platform: {platform}
"""


def _ensure_dirs() -> None:
    """Ensure data directories exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "logs").mkdir(parents=True, exist_ok=True)


def cmd_run(task: str = None) -> int:
    """Run NEMO-OS with all components in foreground."""
    print(BANNER.format(version=VERSION, platform=platform.system()))
    
    _ensure_dirs()

    try:
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format="[%(levelname)s] %(name)s: %(message)s",
        )
        logger = logging.getLogger("nemo.main")

        # Import after logging is setup
        from core.bus import BusServer, BusClient
        from core.security import SecurityGateway, AuditLogger
        from bridge.nemo_server import start_server as start_http

        logger.info("=" * 60)
        logger.info("Starting NEMO-OS with all components")
        logger.info("=" * 60)

        # 1. Start BusServer (IPC message bus)
        logger.info("[1/4] Starting IPC Bus Server...")
        bus_server = BusServer()
        bus_thread = threading.Thread(
            target=bus_server.start,
            daemon=True,
        )
        bus_thread.start()
        time.sleep(0.5)
        logger.info("      ✓ IPC Bus running")

        # 2. Initialize SecurityGateway and AuditLogger
        logger.info("[2/4] Initializing Security Layer...")
        gateway = SecurityGateway(
            data_dir=CONFIG_DIR,
            dry_run=False,
        )
        audit_logger = AuditLogger(
            log_path=CONFIG_DIR / "audit.jsonl",
        )
        logger.info("      ✓ RBAC engine active")
        logger.info("      ✓ Audit logger ready")

        # 3. Start NEMO HTTP Server
        logger.info("[3/4] Starting HTTP API Server on :8765...")
        http_thread = threading.Thread(
            target=start_http,
            args=(gateway, audit_logger, "0.0.0.0", 8765),
            daemon=True,
        )
        http_thread.start()
        time.sleep(0.5)
        logger.info("      ✓ HTTP API ready")

        # 4. Connect BusClient for demos (optional - not needed for HTTP API)
        logger.info("[4/4] Starting message bus client...")
        try:
            bus_client = BusClient()
            bus_client.connect()
            logger.info("      ✓ BusClient connected")
        except Exception as e:
            logger.warning(f"      ⚠ BusClient failed (optional): {e}")
            bus_client = None

        # Print startup info
        print("\n" + "=" * 60)
        print("NEMO-OS is running")
        print("=" * 60)
        print(f"  IPC Bus:       http://localhost:8765 (via NEMO HTTP API)")
        print(f"  HTTP API:      http://localhost:8765")
        print(f"  Security:      ✓ RBAC + ThreatDetection + Sandbox")
        print(f"  Data dir:      {CONFIG_DIR}")
        print(f"  Audit log:     {CONFIG_DIR / 'audit.log'}")
        print("=" * 60)

        # Execute task if provided
        if task:
            print(f"\nExecuting task: {task}\n")
            _execute_task(task)
            print("\nTask completed. NEMO is still running.")

        # Keep alive
        print("\nPress Ctrl+C to stop NEMO\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Shutting down NEMO...")
            bus_server.stop()
            if bus_client:
                bus_client.disconnect()
            logger.info("NEMO shut down cleanly")
            return 0

    except Exception as e:
        print(f"\n[!] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _execute_task(task: str) -> None:
    """Execute a demo task via HTTP API."""
    from bridge.nemo_server import app as nemo_app

    with nemo_app.test_client() as client:
        # Simple task parser: "open chrome and search TERM"
        if "open" in task.lower() and ("chrome" in task.lower() or "browser" in task.lower()):
            print("  [>] Opening Chrome...")
            resp = client.post(
                "/execute",
                json={
                    "action": "open_app",
                    "target": "chrome",
                    "user": "demo",
                    "channel": "demo",
                },
            )
            result = resp.get_json()
            print(f"      {'✓' if result.get('success') else '✗'} {result.get('success', False)}")

        search_term = ""
        if "search" in task.lower():
            # Extract search term after "search"
            parts = task.lower().split("search")
            if len(parts) > 1:
                search_term = parts[1].strip()

        if search_term:
            time.sleep(0.5)
            print(f"  [>] Typing: {search_term}")
            resp = client.post(
                "/execute",
                json={
                    "action": "type",
                    "value": search_term,
                    "user": "demo",
                    "channel": "demo",
                },
            )
            result = resp.get_json()
            print(f"      {'✓' if result.get('success') else '✗'} {result.get('text_length', 0)} characters typed")

            time.sleep(0.2)
            print("  [>] Pressing Enter...")
            resp = client.post(
                "/execute",
                json={
                    "action": "press_key",
                    "value": "enter",
                    "user": "demo",
                    "channel": "demo",
                },
            )
            result = resp.get_json()
            print(f"      {'✓' if result.get('success') else '✗'} {result.get('keys', '?')}")


def cmd_health() -> int:
    """Check NEMO health."""
    import requests
    try:
        resp = requests.get("http://localhost:8765/health", timeout=2)
        data = resp.json()
        print(f"✓ NEMO is running")
        print(f"  Status: {data['status']}")
        print(f"  Security: {data['security']}")
        return 0
    except Exception as e:
        print(f"✗ NEMO is not running")
        print(f"  Error: {e}")
        print(f"\nStart it with: python clevrr_service.py run")
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="nemo_service",
        description="NEMO-OS Service Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  run       Run NEMO-OS in foreground (development mode)
  health    Check if NEMO is running
  
Examples:
  python clevrr_service.py run
  python clevrr_service.py run --task "open chrome and search python"
  python clevrr_service.py health
        """
    )

    parser.add_argument(
        "command",
        choices=["run", "health"],
        nargs="?",
        default="run",
        help="Command to execute (default: run)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Demo task to execute (e.g., 'open chrome and search python')",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"NEMO-OS v{VERSION}",
    )

    args = parser.parse_args()

    if args.command == "run":
        return cmd_run(args.task)
    elif args.command == "health":
        return cmd_health()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
