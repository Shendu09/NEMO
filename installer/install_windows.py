"""Windows installer for NEMO-OS service."""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent

INSTALL_DIR = Path("C:/Program Files/Clevrr")
DATA_DIR = Path("C:/ProgramData/Clevrr/data")
LOG_DIR = Path("C:/ProgramData/Clevrr/logs")
CONFIG_DIR = Path("C:/ProgramData/Clevrr")
CONFIG_FILE = CONFIG_DIR / "clevrr.ini"
SERVICE_NAME = "ClevrrAI"
PYTHON_MIN = (3, 11)

REQUIRED_PACKAGES = [
    "psutil>=5.9",
    "pydantic>=2.0",
    "pywin32>=306",
]


def _is_admin() -> bool:
    """Check if running as Administrator."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _run(cmd: list[str]) -> None:
    """Run command and raise on failure."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip()
        )


class WindowsInstaller:
    """NEMO-OS Windows installer."""

    def __init__(self, dry_run: bool = False) -> None:
        """Initialize installer."""
        self._dry_run = dry_run
        self._errors: list[str] = []
        self._steps_done: list[str] = []

    def install(self) -> bool:
        """Run installation steps in order."""
        steps = [
            ("Checking requirements", self._check_requirements),
            ("Creating directories", self._create_directories),
            ("Copying project files", self._copy_files),
            ("Installing dependencies", self._install_dependencies),
            ("Writing config", self._write_config),
            ("Installing Windows service", self._install_service),
            ("Setting permissions", self._set_permissions),
            ("Adding to PATH", self._add_to_path),
            ("Verifying installation", self._verify),
        ]

        print("\n  NEMO-OS Windows Installer")
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
        # Check Administrator
        if not _is_admin():
            raise PermissionError(
                "Must run as Administrator.\n"
                "Right-click CMD → 'Run as administrator'"
            )

        # Check Python version
        if sys.version_info < PYTHON_MIN:
            raise RuntimeError(
                f"Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]}+ required. "
                f"Found: {sys.version}"
            )

        # Check pip
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError("pip not available")

        # Check Windows version (Win10+)
        import platform
        ver = platform.version().split(".")
        if int(ver[0]) < 10:
            raise RuntimeError("Windows 10 or later required")

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

        # Run pywin32 post-install script
        try:
            import win32com  # noqa: F401
            scripts_dir = Path(sys.executable).parent / "Scripts"
            post_install = scripts_dir / "pywin32_postinstall.py"
            if post_install.exists():
                subprocess.run(
                    [sys.executable, str(post_install), "-install"],
                    capture_output=True,
                )
        except ImportError:
            pass

    def _write_config(self) -> None:
        """Write default configuration file."""
        sys.path.insert(0, str(INSTALL_DIR))
        from core.service.config import ServiceConfig, ConfigLoader

        config = ServiceConfig(
            data_dir=DATA_DIR,
            log_dir=LOG_DIR,
            ipc_pipe_name="\\\\.\\pipe\\clevrr",
            health_check_interval=30,
            max_memory_mb=512,
            auto_restart=True,
            restart_delay=5,
        )
        ConfigLoader.save(config, CONFIG_FILE)

    def _install_service(self) -> None:
        """Install Windows service via sc.exe."""
        service_exe = INSTALL_DIR / "clevrr_service.py"

        _run([
            "sc", "create", SERVICE_NAME,
            "binPath=",
            f'"{sys.executable}" "{service_exe}" run --config "{CONFIG_FILE}"',
            "DisplayName=", "NEMO AI OS Layer",
            "start=", "delayed-auto",
            "obj=", "LocalSystem",
        ])

        _run([
            "sc", "description", SERVICE_NAME,
            "Local AI layer for secure OS automation",
        ])

        delay_ms = 5000
        _run([
            "sc", "failure", SERVICE_NAME,
            "reset=", "86400",
            "actions=",
            f"restart/{delay_ms}/restart/{delay_ms}/restart/{delay_ms}/",
        ])

    def _set_permissions(self) -> None:
        """Set secure permissions using icacls."""
        # Lock DATA_DIR
        _run([
            "icacls", str(DATA_DIR),
            "/inheritance:r",
            "/grant:r", "SYSTEM:(OI)(CI)F",
            "/grant:r", "Administrators:(OI)(CI)F",
        ])

        # Lock LOG_DIR
        _run([
            "icacls", str(LOG_DIR),
            "/inheritance:r",
            "/grant:r", "SYSTEM:(OI)(CI)F",
            "/grant:r", "Administrators:(OI)(CI)F",
        ])

        # Set INSTALL_DIR permissions
        _run([
            "icacls", str(INSTALL_DIR),
            "/inheritance:r",
            "/grant:r", "SYSTEM:(OI)(CI)F",
            "/grant:r", "Administrators:(OI)(CI)F",
            "/grant:r", "Users:(OI)(CI)RX",
        ])

    def _add_to_path(self) -> None:
        """Add installation directory to system PATH."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0,
                winreg.KEY_READ | winreg.KEY_SET_VALUE,
            )
            current_path, _ = winreg.QueryValueEx(key, "Path")
            install_str = str(INSTALL_DIR)

            if install_str not in current_path:
                new_path = current_path + ";" + install_str
                winreg.SetValueEx(
                    key, "Path", 0,
                    winreg.REG_EXPAND_SZ, new_path
                )
            winreg.CloseKey(key)

            # Broadcast WM_SETTINGCHANGE
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x001A, 0, "Environment",
                0x0002, 5000, None
            )
        except Exception as exc:
            raise RuntimeError(f"Could not update PATH: {exc}")

    def _verify(self) -> None:
        """Verify critical files and service registration."""
        critical = [
            INSTALL_DIR / "clevrr_service.py",
            INSTALL_DIR / "core" / "security" / "gateway.py",
            CONFIG_FILE,
        ]
        for path in critical:
            if not path.exists():
                raise RuntimeError(f"Verification failed — missing: {path}")

        # Verify service registered
        result = subprocess.run(
            ["sc", "query", SERVICE_NAME],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Service '{SERVICE_NAME}' not found in SCM"
            )

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
        print(f"    sc start {SERVICE_NAME}")
        print(f"    sc query {SERVICE_NAME}")
        print(f"    Get-EventLog -LogName Application")
        print()
        print("  Or start from Services panel:")
        print("    Win+R → services.msc → NEMO AI OS Layer → Start")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NEMO-OS Windows Installer",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show steps without executing",
    )
    args = parser.parse_args()

    installer = WindowsInstaller(dry_run=args.dry_run)
    success = installer.install()
    sys.exit(0 if success else 1)
