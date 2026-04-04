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
        from core.bus import BusServer
        from core.security.gateway_v2 import SecurityGateway
        from core.security.audit_logger_v2 import AuditLogger
        from bridge.nemo_server import start_server as start_http
        import requests

        logger.info("=" * 60)
        logger.info("Starting NEMO-OS with all components")
        logger.info("=" * 60)

        # 1. Start BusServer (IPC message bus)
        logger.info("[1/6] Starting IPC Bus Server...")
        bus_server = BusServer()
        bus_thread = threading.Thread(
            target=bus_server.start,
            daemon=True,
        )
        bus_thread.start()
        time.sleep(0.3)
        logger.info("      ✓ IPC Bus running")

        # 2. Initialize SecurityGateway and AuditLogger
        logger.info("[2/6] Initializing Security Layer...")
        gateway = SecurityGateway(
            data_dir=CONFIG_DIR,
            dry_run=False,
        )
        audit_logger = AuditLogger(
            log_path=CONFIG_DIR / "audit.jsonl",
        )
        logger.info("      ✓ RBAC engine active")
        logger.info("      ✓ Audit logger ready")

        # 3. Start NEMO HTTP Server on port 8765
        logger.info("[3/6] Starting HTTP API Server on :8765...")
        http_thread = threading.Thread(
            target=start_http,
            args=(gateway, audit_logger, "0.0.0.0", 8765),
            daemon=True,
        )
        http_thread.start()
        time.sleep(0.5)  # Give server time to start
        logger.info("      ✓ HTTP API ready on :8765")

        # 4. Start Voice Listener
        logger.info("[4/6] Starting Voice Listener...")
        try:
            from core.voice import wake_listener
            
            def handle_voice_command(command: str) -> None:
                """Handle voice command by sending to /task endpoint."""
                logger.info(f"Voice command received: {command}")
                try:
                    response = requests.post(
                        "http://localhost:8765/task",
                        json={
                            "command": command,
                            "user": "voice",
                            "channel": "voice",
                        },
                        timeout=60,
                    )
                    result = response.json()
                    logger.info(f"✓ Voice command executed: {result.get('message', 'done')}")
                except Exception as e:
                    logger.error(f"Voice command failed: {e}")
            
            # Start voice listener in daemon thread
            wake_listener.start(handle_voice_command)
            logger.info("      ✓ Voice listener active")
        except ImportError:
            logger.warning("      ⚠ Voice module not available (optional)")
        except Exception as e:
            logger.warning(f"      ⚠ Voice listener failed to start (optional): {e}")

        # 5. Start Health Monitor
        logger.info("[5/6] Starting Health Monitor...")
        try:
            from core.service.health_monitor import HealthMonitor
            from core.service.config import ServiceConfig
            
            health_config = ServiceConfig()
            
            def on_critical(status):
                logger.warning(f"Health alert: {status.summary()}")
            
            health_monitor = HealthMonitor(
                config=health_config,
                on_critical=on_critical,
            )
            health_thread = threading.Thread(
                target=health_monitor.start,
                daemon=True,
            )
            health_thread.start()
            logger.info("      ✓ Health monitor running")
        except Exception as e:
            logger.warning(f"      ⚠ Health monitor failed (optional): {e}")
            health_monitor = None

        # 6. Print startup banner
        logger.info("[6/6] System startup complete")
        
        print("\n")
        print("╔══════════════════════════════════════╗")
        print("║         NEMO-OS  is  running         ║")
        print("║  HTTP  →  http://localhost:8765      ║")
        print("║  Dashboard → http://localhost:8766   ║")
        print("║  Voice → Say  \"V <your command>\"    ║")
        print("╚══════════════════════════════════════╝")
        print()

        # Execute task if provided (via --task argument)
        if task:
            logger.info(f"Executing task via /task endpoint: {task}")
            print(f"\n[*] Executing task: {task}\n")
            try:
                response = requests.post(
                    "http://localhost:8765/task",
                    json={
                        "command": task,
                        "user": "cli",
                        "channel": "cli_task",
                    },
                    timeout=60,
                )
                result = response.json()
                
                # Print results
                print(f"Command: {result.get('command')}")
                print(f"Status:  {'✓ SUCCESS' if result.get('success') else '✗ FAILED'}")
                print(f"Message: {result.get('message')}")
                print(f"Steps:   {result.get('steps_completed')}/{result.get('total_steps')}")
                
                if result.get('actions'):
                    print("\nAction Details:")
                    for action in result.get('actions', []):
                        status = "✓" if action.get('status') == 'success' else "✗"
                        print(f"  {status} Step {action.get('step')}: {action.get('action')}", end="")
                        if action.get('target'):
                            print(f" → {action.get('target')}", end="")
                        if action.get('value'):
                            print(f" ('{action.get('value')}')", end="")
                        if action.get('error'):
                            print(f"\n       Error: {action.get('error')}", end="")
                        print()
                
                print(f"\n[*] Task completed. NEMO is still running.\n")
                
            except Exception as e:
                logger.error(f"Task execution failed: {e}")
                print(f"[!] Task failed: {e}\n")

        # Keep alive loop
        print("[*] Press Ctrl+C to stop NEMO\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Shutting down NEMO...")
            bus_server.stop()
            logger.info("NEMO shut down cleanly")
            return 0

    except Exception as e:
        print(f"\n[!] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


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
  run       Run NEMO-OS in foreground with all components
  health    Check if NEMO is running
  
Examples:
  # Start NEMO with voice listening
  python clevrr_service.py run
  
  # Execute a task and keep running
  python clevrr_service.py run --task "play BTS V on youtube"
  python clevrr_service.py run --task "summarize https://bbc.com"
  python clevrr_service.py run --task "open whatsapp and send hi to Rohitha"
  
  # Check health
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
