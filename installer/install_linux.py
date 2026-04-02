"""Linux installer for NEMO-OS service."""

from __future__ import annotations

import argparse
import grp
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent

INSTALL_DIR = Path("/opt/clevrr")
DATA_DIR = Path("/var/lib/clevrr")
LOG_DIR = Path("/var/log/clevrr")
CONFIG_DIR = Path("/etc/clevrr")
CONFIG_FILE = CONFIG_DIR / "clevrr.ini"
SERVICE_USER = "clevrr"
SERVICE_GROUP = "clevrr"
PYTHON_MIN = (3, 11)

REQUIRED_PACKAGES = [
    "psutil>=5.9",
    "pydantic>=2.0",
]


def _run(cmd: list[str]) -> None:
    """Run command and raise on failure."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def _chown_recursive(path: Path, uid: int, gid: int) -> None:
    """Recursively change ownership of path and all contents."""
    os.chown(path, uid, gid)
    if path.is_dir():
        for child in path.rglob("*"):
            os.chown(child, uid, gid)


class LinuxInstaller:
    """NEMO-OS Linux installer."""

    def __init__(self, dry_run: bool = False) -> None:
        """Initialize installer."""
        self._dry_run = dry_run
        self._errors: list[str] = []
        self._steps_done: list[str] = []

    def install(self) -> bool:
        """Run installation steps in order."""
        steps = [
            ("Checking requirements", self._check_requirements),
            ("Creating system user", self._create_system_user),
            ("Creating directories", self._create_directories),
            ("Copying project files", self._copy_files),
            ("Installing dependencies", self._install_dependencies),
            ("Writing config", self._write_config),
            ("Installing systemd unit", self._install_systemd),
            ("Setting permissions", self._set_permissions),
            ("Verifying installation", self._verify),
        ]

        print("\n  NEMO-OS Linux Installer")
        print("  " + "─" * 40)

        for step_name, step_fn in steps:
            print(f"\n  [ ] {step_name}...", end=" ", flush=True)
            try:
                step_fn()
                self._steps_done.append(step_name)
                print("done")
            except Exception as exc:
                print(f"FAILED\n      {exc}")
                self._errors.append(f"{step_name}: {exc}")
                return False

        self._print_success()
        return True

    def _check_requirements(self) -> None:
        """Check system requirements."""
        # Check root
        if os.geteuid() != 0:
            raise PermissionError(
                "Must run as root. Try: sudo python installer/install_linux.py"
            )

        # Check Python version
        if sys.version_info < PYTHON_MIN:
            raise RuntimeError(
                f"Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]}+ required. "
                f"Found: {sys.version}"
            )

        # Check systemd
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError("systemd not found on this system")

        # Check pip
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError("pip not available")

    def _create_system_user(self) -> None:
        """Create system user if not exists."""
        try:
            pwd.getpwnam(SERVICE_USER)
            return   # Already exists
        except KeyError:
            pass

        _run([
            "useradd",
            "--system",
            "--no-create-home",
            "--shell", "/usr/sbin/nologin",
            "--comment", "NEMO AI OS Layer",
            SERVICE_USER,
        ])

    def _create_directories(self) -> None:
        """Create all required directories."""
        for d in [INSTALL_DIR, DATA_DIR, LOG_DIR, CONFIG_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def _copy_files(self) -> None:
        """Copy project files to install directory."""
        dirs_to_copy = ["core", "installer"]
        files_to_copy = ["clevrr_service.py", "requirements.txt"]

        for d in dirs_to_copy:
            src = PROJECT_ROOT / d
            dst = INSTALL_DIR / d
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

        for f in files_to_copy:
            src = PROJECT_ROOT / f
            if src.exists():
                shutil.copy2(src, INSTALL_DIR / f)

    def _install_dependencies(self) -> None:
        """Install required Python packages."""
        _run([
            sys.executable, "-m", "pip", "install",
            "--quiet",
            "--upgrade",
            *REQUIRED_PACKAGES,
        ])

    def _write_config(self) -> None:
        """Write default configuration file."""
        sys.path.insert(0, str(INSTALL_DIR))
        from core.service.config import ServiceConfig, ConfigLoader

        config = ServiceConfig(
            data_dir=DATA_DIR,
            log_dir=LOG_DIR,
            ipc_socket_path="/tmp/clevrr.sock",
            health_check_interval=30,
            max_memory_mb=512,
            auto_restart=True,
            restart_delay=5,
        )
        ConfigLoader.save(config, CONFIG_FILE)

    def _install_systemd(self) -> None:
        """Install and enable systemd unit."""
        unit = f"""[Unit]
Description=NEMO AI OS Layer
Documentation=https://github.com/Shendu09/clevrr-os
After=network.target
Wants=network.target

[Service]
Type=simple
ExecStart={sys.executable} {INSTALL_DIR}/clevrr_service.py run --config {CONFIG_FILE}
Restart=always
RestartSec=5
User={SERVICE_USER}
Group={SERVICE_GROUP}
WorkingDirectory={INSTALL_DIR}
StandardOutput=journal
StandardError=journal
SyslogIdentifier=clevrr
KillMode=mixed
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1
ReadWritePaths={DATA_DIR} {LOG_DIR}
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes

[Install]
WantedBy=multi-user.target"""

        unit_path = Path("/etc/systemd/system/clevrr.service")
        unit_path.write_text(unit)

        _run(["systemctl", "daemon-reload"])
        _run(["systemctl", "enable", "clevrr"])

    def _set_permissions(self) -> None:
        """Set secure permissions on all directories."""
        uid = pwd.getpwnam(SERVICE_USER).pw_uid
        gid = grp.getgrnam(SERVICE_GROUP).gr_gid

        for path in [INSTALL_DIR, DATA_DIR, LOG_DIR, CONFIG_DIR]:
            _chown_recursive(path, uid, gid)

        INSTALL_DIR.chmod(0o755)
        DATA_DIR.chmod(0o700)
        LOG_DIR.chmod(0o750)
        CONFIG_DIR.chmod(0o750)
        CONFIG_FILE.chmod(0o640)

    def _verify(self) -> None:
        """Verify critical files exist."""
        critical = [
            INSTALL_DIR / "clevrr_service.py",
            INSTALL_DIR / "core" / "security" / "gateway.py",
            CONFIG_FILE,
            Path("/etc/systemd/system/clevrr.service"),
        ]
        for path in critical:
            if not path.exists():
                raise RuntimeError(f"Verification failed — missing: {path}")

    def _print_success(self) -> None:
        """Print success message and next steps."""
        print("\n\n  Installation complete!")
        print("  " + "─" * 40)
        print(f"  Install dir : {INSTALL_DIR}")
        print(f"  Data dir    : {DATA_DIR}")
        print(f"  Log dir     : {LOG_DIR}")
        print(f"  Config      : {CONFIG_FILE}")
        print()
        print("  Next steps:")
        print("    sudo systemctl start clevrr")
        print("    sudo systemctl status clevrr")
        print("    journalctl -u clevrr -f")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NEMO-OS Linux Installer",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it",
    )
    args = parser.parse_args()

    installer = LinuxInstaller(dry_run=args.dry_run)
    success = installer.install()
    sys.exit(0 if success else 1)
