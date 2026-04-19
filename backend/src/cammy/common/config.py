"""Common config infrastructure."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict
from threading import Lock


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "cammy"


@dataclass
class PerformanceConfig:
    """Performance-related configuration."""

    tier: str = "auto"  # auto, high, medium, low
    target_fps: int = 15
    frame_skip: int = 1
    detection_resolution: tuple = (320, 240)
    parallel_processing: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DetectionConfig:
    """Detection-related configuration."""

    face_similarity_threshold: float = 0.65
    gesture_confidence_threshold: float = 0.80
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    max_faces: int = 5
    max_hands: int = 2

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ActionConfig:
    """Action-related configuration."""

    cooldown_ms: int = 1000
    enabled: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ServerConfig:
    """Server-related configuration."""

    host: str = "127.0.0.1"
    port: int = 8765
    ws_heartbeat_interval: int = 30

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CameraConfig:
    """Camera-related configuration."""

    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    auto_exposure: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CammyConfig:
    """Main configuration for cammy system."""

    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    action: ActionConfig = field(default_factory=ActionConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)

    @classmethod
    def from_dict(cls, data: Dict) -> "CammyConfig":
        """Create from dictionary."""
        return cls(
            performance=PerformanceConfig(**data.get("performance", {})),
            detection=DetectionConfig(**data.get("detection", {})),
            action=ActionConfig(**data.get("action", {})),
            server=ServerConfig(**data.get("server", {})),
            camera=CameraConfig(**data.get("camera", {})),
        )

    def to_dict(self) -> Dict:
        return {
            "performance": self.performance.to_dict(),
            "detection": self.detection.to_dict(),
            "action": self.action.to_dict(),
            "server": self.server.to_dict(),
            "camera": self.camera.to_dict(),
        }


class ConfigManager:
    """Thread-safe configuration manager."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config manager.

        Args:
            config_dir: Custom config directory (default: ~/.config/cammy)
        """
        self._config_dir = config_dir or DEFAULT_CONFIG_DIR
        self._config_file = self._config_dir / "config.json"
        self._config: Optional[CammyConfig] = None
        self._lock = Lock()
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure config directory exists."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def _load_from_file(self) -> CammyConfig:
        """Load config from file."""
        if not self._config_file.exists():
            return CammyConfig()

        try:
            with open(self._config_file, "r") as f:
                data = json.load(f)
            return CammyConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            return CammyConfig()

    def _save_to_file(self) -> None:
        """Save config to file."""
        if self._config is None:
            return

        with open(self._config_file, "w") as f:
            json.dump(self._config.to_dict(), f, indent=2)

    def load(self) -> CammyConfig:
        """Load configuration."""
        with self._lock:
            self._config = self._load_from_file()
            return self._config

    def save(self, config: Optional[CammyConfig] = None) -> None:
        """Save configuration."""
        with self._lock:
            if config is not None:
                self._config = config
            self._save_to_file()

    def get(self) -> CammyConfig:
        """Get current configuration."""
        with self._lock:
            if self._config is None:
                self._config = self._load_from_file()
            return self._config

    def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration with partial updates."""
        with self._lock:
            if self._config is None:
                self._config = self._load_from_file()

            # Apply updates to nested configs
            for key, value in updates.items():
                if key in ("performance", "detection", "action", "server", "camera"):
                    if hasattr(self._config, key):
                        nested = getattr(self._config, key)
                        if isinstance(value, dict):
                            for k, v in value.items():
                                if hasattr(nested, k):
                                    setattr(nested, k, v)

            self._save_to_file()

    @property
    def config_dir(self) -> Path:
        """Get config directory."""
        return self._config_dir

    @property
    def config_file(self) -> Path:
        """Get config file path."""
        return self._config_file


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: Optional[Path] = None) -> ConfigManager:
    """Get global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager
