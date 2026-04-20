"""Command definitions and persistence.

CODEMAP:
- CommandDef: A user-defined command (keypress / shell / webhook)
- CommandsManager: Load/save commands + gesture mappings to ~/.config/cammy/commands.json
"""

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from .logging import setup_logger

logger = setup_logger(__name__)

DEFAULT_COMMANDS_FILE = Path.home() / ".config" / "cammy" / "commands.json"

DEFAULT_COMMANDS: Dict[str, Dict[str, Any]] = {
    "media_play":  {"label": "Play",         "type": "keypress", "payload": {"key": "play"},                    "cooldown_ms": 1000},
    "media_pause": {"label": "Pause",        "type": "keypress", "payload": {"key": "play"},                    "cooldown_ms": 1000},
    "media_next":  {"label": "Next Track",   "type": "keypress", "payload": {"key": "nexttrack"},               "cooldown_ms": 1000},
    "media_prev":  {"label": "Prev Track",   "type": "keypress", "payload": {"key": "prevtrack"},               "cooldown_ms": 1000},
    "volume_up":   {"label": "Volume Up",    "type": "keypress", "payload": {"key": "volumeup",   "count": 2}, "cooldown_ms": 500},
    "volume_down": {"label": "Volume Down",  "type": "keypress", "payload": {"key": "volumedown", "count": 2}, "cooldown_ms": 500},
    "volume_mute": {"label": "Mute",         "type": "keypress", "payload": {"key": "volumemute"},              "cooldown_ms": 1000},
}

DEFAULT_GESTURE_MAPPINGS: Dict[str, str] = {
    "fist":        "media_pause",
    "open_palm":   "media_play",
    "thumbs_up":   "volume_up",
    "thumbs_down": "volume_down",
    "peace":       "media_next",
}


@dataclass
class CommandDef:
    """A user-defined or built-in command."""

    name: str
    label: str
    type: str          # "keypress" | "shell" | "webhook"
    payload: Dict[str, Any]
    cooldown_ms: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "payload": self.payload,
            "cooldown_ms": self.cooldown_ms,
        }


class CommandsManager:
    """Manages command definitions and gesture mappings, persisted to disk."""

    def __init__(self, commands_file: Optional[Path] = None):
        self._file = commands_file or DEFAULT_COMMANDS_FILE
        self._commands: Dict[str, CommandDef] = {}
        self._gesture_mappings: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._load()

    # ------------------------------------------------------------------ load/save

    def _load(self) -> None:
        if self._file.exists():
            try:
                with open(self._file) as f:
                    data = json.load(f)
                self._commands = {
                    k: CommandDef(name=k, **{kk: vv for kk, vv in v.items() if kk != "name"})
                    for k, v in data.get("commands", {}).items()
                }
                self._gesture_mappings = data.get("gesture_mappings", dict(DEFAULT_GESTURE_MAPPINGS))
                # Merge any missing built-in defaults non-destructively
                for name, cmd in DEFAULT_COMMANDS.items():
                    if name not in self._commands:
                        self._commands[name] = CommandDef(name=name, **cmd)
                for gesture, action in DEFAULT_GESTURE_MAPPINGS.items():
                    if gesture not in self._gesture_mappings:
                        self._gesture_mappings[gesture] = action
                logger.info(f"Commands loaded from {self._file}")
                return
            except Exception as e:
                logger.warning(f"Failed to load commands: {e}, using defaults")

        self._commands = {k: CommandDef(name=name, **cmd) for k, (name, cmd) in
                         zip(DEFAULT_COMMANDS.keys(), [(k, v) for k, v in DEFAULT_COMMANDS.items()])}
        self._gesture_mappings = dict(DEFAULT_GESTURE_MAPPINGS)
        self._save()

    def _save(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "commands": {
                    k: {kk: vv for kk, vv in v.to_dict().items() if kk != "name"}
                    for k, v in self._commands.items()
                },
                "gesture_mappings": self._gesture_mappings,
            }
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save commands: {e}")

    # ------------------------------------------------------------------ commands

    def get_commands(self) -> Dict[str, CommandDef]:
        with self._lock:
            return dict(self._commands)

    def get_command(self, name: str) -> Optional[CommandDef]:
        with self._lock:
            return self._commands.get(name)

    def upsert_command(self, cmd: CommandDef) -> None:
        with self._lock:
            self._commands[cmd.name] = cmd
            self._save()

    def delete_command(self, name: str) -> bool:
        with self._lock:
            if name not in self._commands:
                return False
            del self._commands[name]
            # Remove from any gesture mappings that referenced this command
            self._gesture_mappings = {g: a for g, a in self._gesture_mappings.items() if a != name}
            self._save()
            return True

    # ------------------------------------------------------------------ gesture mappings

    def get_gesture_mappings(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._gesture_mappings)

    def set_gesture_mapping(self, gesture: str, command_name: str) -> None:
        with self._lock:
            self._gesture_mappings[gesture] = command_name
            self._save()

    def remove_gesture_mapping(self, gesture: str) -> None:
        with self._lock:
            self._gesture_mappings.pop(gesture, None)
            self._save()
