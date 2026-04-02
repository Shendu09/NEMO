"""
Service Configuration - Loads and manages Clevrr service configuration.
"""

import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ServiceConfig:
    """Service configuration with defaults."""
    service_name: str = "clevrr"
    display_name: str = "Clevrr AI OS Layer"
    description: str = "Local AI layer for OS automation"
    data_dir: Path = None  # Set in __post_init__
    log_dir: Path = None   # Set in __post_init__
    log_level: str = "INFO"
    ipc_socket_path: str = "/tmp/clevrr.sock"
    ipc_pipe_name: str = "\\\\.\\pipe\\clevrr"
    health_check_interval: int = 30
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0
    auto_restart: bool = True
    restart_delay: int = 5

    def __post_init__(self):
        """Set default Path objects."""
        if self.data_dir is None:
            object.__setattr__(self, "data_dir", Path("./clevrr_data"))
        if self.log_dir is None:
            object.__setattr__(self, "log_dir", Path("./clevrr_logs"))
        
        # Ensure Path objects
        if not isinstance(self.data_dir, Path):
            object.__setattr__(self, "data_dir", Path(self.data_dir))
        if not isinstance(self.log_dir, Path):
            object.__setattr__(self, "log_dir", Path(self.log_dir))


class ConfigLoader:
    """Load and save ServiceConfig from/to .ini files."""

    @staticmethod
    def load(path: Path) -> ServiceConfig:
        """Load config from .ini file."""
        config = configparser.ConfigParser()
        config.read(path)
        
        # Service section
        service_name = config.get("service", "service_name", fallback="clevrr")
        display_name = config.get("service", "display_name", fallback="Clevrr AI OS Layer")
        description = config.get("service", "description", fallback="Local AI layer for OS automation")
        auto_restart = config.getboolean("service", "auto_restart", fallback=True)
        restart_delay = config.getint("service", "restart_delay", fallback=5)
        
        # Paths section
        data_dir = Path(config.get("paths", "data_dir", fallback="./clevrr_data"))
        log_dir = Path(config.get("paths", "log_dir", fallback="./clevrr_logs"))
        
        # Logging section
        log_level = config.get("logging", "level", fallback="INFO")
        
        # IPC section
        ipc_socket = config.get("ipc", "socket_path", fallback="/tmp/clevrr.sock")
        ipc_pipe = config.get("ipc", "pipe_name", fallback="\\\\.\\pipe\\clevrr")
        
        # Health section
        health_interval = config.getint("health", "check_interval", fallback=30)
        max_memory = config.getint("health", "max_memory_mb", fallback=512)
        max_cpu = config.getfloat("health", "max_cpu_percent", fallback=80.0)
        
        return ServiceConfig(
            service_name=service_name,
            display_name=display_name,
            description=description,
            data_dir=data_dir,
            log_dir=log_dir,
            log_level=log_level,
            ipc_socket_path=ipc_socket,
            ipc_pipe_name=ipc_pipe,
            health_check_interval=health_interval,
            max_memory_mb=max_memory,
            max_cpu_percent=max_cpu,
            auto_restart=auto_restart,
            restart_delay=restart_delay,
        )

    @staticmethod
    def save(config: ServiceConfig, path: Path) -> None:
        """Save config to .ini file."""
        ini = configparser.ConfigParser()
        
        ini["service"] = {
            "service_name": config.service_name,
            "display_name": config.display_name,
            "description": config.description,
            "auto_restart": str(config.auto_restart),
            "restart_delay": str(config.restart_delay),
        }
        
        ini["paths"] = {
            "data_dir": str(config.data_dir),
            "log_dir": str(config.log_dir),
        }
        
        ini["logging"] = {
            "level": config.log_level,
        }
        
        ini["ipc"] = {
            "socket_path": config.ipc_socket_path,
            "pipe_name": config.ipc_pipe_name,
        }
        
        ini["health"] = {
            "check_interval": str(config.health_check_interval),
            "max_memory_mb": str(config.max_memory_mb),
            "max_cpu_percent": str(config.max_cpu_percent),
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            ini.write(f)

    @staticmethod
    def default_config() -> ServiceConfig:
        """Return default ServiceConfig."""
        return ServiceConfig()
