"""Action executor module for executing actions based on gestures.

This module handles:
- Gesture to action mapping
- Action execution (keyboard, webhook, shell)
- Debouncing to prevent repeated triggers

CODEMAP:
- ActionExecutor: Execute actions based on gesture mappings
- ActionMapper: Map gestures to actions
- KeyPressAction: Keyboard press action
- WebhookAction: HTTP webhook action
- ShellAction: Shell command action
"""

import time
import threading
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from enum import Enum

from .common.logging import setup_logger
from .common.types import (
    Action,
    ActionType,
    DetectedHand,
    GestureType,
    GESTURE_ACTION_MAPPING,
)


logger = setup_logger(__name__)


# Try to import optional dependencies
def _check_pyautogui():
    """Check if pyautogui is available."""
    try:
        import pyautogui

        # Try to access a function to trigger any runtime errors
        _ = pyautogui.FAILSAFE
        return True
    except (ImportError, Exception):
        return False


def _check_requests():
    """Check if requests is available."""
    try:
        import requests

        return True
    except ImportError:
        return False


PYAUTOGUI_AVAILABLE = _check_pyautogui()
REQUESTS_AVAILABLE = _check_requests()


class ActionResult(Enum):
    """Action execution result."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIP = "skip"


@dataclass
class ActionConfig:
    """Configuration for a specific action."""

    action_type: ActionType
    action_name: str
    payload: Dict[str, Any]
    cooldown_ms: int = 1000


class ActionMapper:
    """Maps gestures to actions based on configuration."""

    DEFAULT_MAPPING: Dict[GestureType, str] = {
        GestureType.FIST: "media_pause",
        GestureType.OPEN_PALM: "media_play",
        GestureType.THUMBS_UP: "volume_up",
        GestureType.THUMBS_DOWN: "volume_down",
        GestureType.PEACE: "media_next",
    }

    def __init__(self, mapping: Optional[Dict[GestureType, str]] = None):
        """Initialize action mapper.

        Args:
            mapping: Custom gesture to action name mapping
        """
        self._mapping = mapping or dict(self.DEFAULT_MAPPING)
        self._action_configs: Dict[str, ActionConfig] = {}
        self._load_default_configs()

    def _load_default_configs(self) -> None:
        """Load default action configurations."""
        self._action_configs = {
            "media_play": ActionConfig(
                action_type=ActionType.MEDIA_PLAY,
                action_name="media_play",
                payload={"key": "play"},
            ),
            "media_pause": ActionConfig(
                action_type=ActionType.MEDIA_PAUSE,
                action_name="media_pause",
                payload={"key": "play"},
            ),
            "media_next": ActionConfig(
                action_type=ActionType.MEDIA_NEXT,
                action_name="media_next",
                payload={"key": "nexttrack"},
            ),
            "media_prev": ActionConfig(
                action_type=ActionType.MEDIA_PREV,
                action_name="media_prev",
                payload={"key": "prevtrack"},
            ),
            "volume_up": ActionConfig(
                action_type=ActionType.VOLUME_UP,
                action_name="volume_up",
                payload={"key": "volumeup", "count": 2},
            ),
            "volume_down": ActionConfig(
                action_type=ActionType.VOLUME_DOWN,
                action_name="volume_down",
                payload={"key": "volumedown", "count": 2},
            ),
            "volume_mute": ActionConfig(
                action_type=ActionType.VOLUME_MUTE,
                action_name="volume_mute",
                payload={"key": "volumemute"},
            ),
        }

    def set_mapping(self, gesture: GestureType, action_name: str) -> None:
        """Set gesture to action mapping."""
        self._mapping[gesture] = action_name

    def get_action(self, gesture: GestureType) -> Optional[ActionConfig]:
        """Get action config for a gesture."""
        action_name = self._mapping.get(gesture)
        if action_name:
            return self._action_configs.get(action_name)
        return None

    def update_action_config(self, action_name: str, config: ActionConfig) -> None:
        """Update action configuration."""
        self._action_configs[action_name] = config

    def get_all_mappings(self) -> Dict[GestureType, str]:
        """Get all gesture mappings."""
        return self._mapping.copy()

    def get_all_actions(self) -> Dict[str, ActionConfig]:
        """Get all action configurations."""
        return self._action_configs.copy()


class KeyPressAction:
    """Execute keyboard press actions."""

    def __init__(self):
        """Initialize key press action."""
        self._pyautogui = None
        if PYAUTOGUI_AVAILABLE:
            import pyautogui

            self._pyautogui = pyautogui
            self._pyautogui.FAILSAFE = True
            self._pyautogui.PAUSE = 0.1
            logger.info("KeyPressAction initialized with pyautogui")
        else:
            logger.warning("pyautogui not available")

    def execute(self, payload: Dict[str, Any]) -> ActionResult:
        """Execute key press.

        Args:
            payload: {"key": "play", "count": 1}

        Returns:
            ActionResult
        """
        if not self._pyautogui:
            logger.debug("KeyPress skipped (no pyautogui)")
            return ActionResult.SKIP

        key = payload.get("key", "")
        count = payload.get("count", 1)

        try:
            for _ in range(count):
                self._pyautogui.press(key)
            logger.debug(f"KeyPress: {key} x{count}")
            return ActionResult.SUCCESS
        except Exception as e:
            logger.error(f"KeyPress failed: {e}")
            return ActionResult.FAILURE


class WebhookAction:
    """Execute webhook actions."""

    def __init__(self):
        """Initialize webhook action."""
        self._requests = None
        if REQUESTS_AVAILABLE:
            import requests

            self._requests = requests
            logger.info("WebhookAction initialized")
        else:
            logger.warning("requests not available")

    def execute(self, payload: Dict[str, Any]) -> ActionResult:
        """Execute webhook.

        Args:
            payload: {"url": "...", "method": "POST", "body": {...}}

        Returns:
            ActionResult
        """
        if not self._requests:
            logger.debug("Webhook skipped (no requests)")
            return ActionResult.SKIP

        url = payload.get("url", "")
        method = payload.get("method", "POST").upper()
        body = payload.get("body", {})

        if not url:
            logger.warning("Webhook missing URL")
            return ActionResult.FAILURE

        try:
            if method == "POST":
                resp = self._requests.post(url, json=body, timeout=5)
            elif method == "GET":
                resp = self._requests.get(url, params=body, timeout=5)
            elif method == "PUT":
                resp = self._requests.put(url, json=body, timeout=5)
            else:
                logger.warning(f"Unsupported method: {method}")
                return ActionResult.FAILURE

            if resp.status_code < 400:
                logger.debug(f"Webhook {url}: {resp.status_code}")
                return ActionResult.SUCCESS
            else:
                logger.warning(f"Webhook {url}: {resp.status_code}")
                return ActionResult.FAILURE
        except Exception as e:
            logger.error(f"Webhook failed: {e}")
            return ActionResult.FAILURE


class ShellAction:
    """Execute shell command actions."""

    def __init__(self):
        """Initialize shell action."""
        import subprocess

        self._subprocess = subprocess
        logger.info("ShellAction initialized")

    def execute(self, payload: Dict[str, Any]) -> ActionResult:
        """Execute shell command.

        Args:
            payload: {"command": "...", "shell": true}

        Returns:
            ActionResult
        """
        command = payload.get("command", "")
        use_shell = payload.get("shell", True)

        if not command:
            logger.warning("Shell command empty")
            return ActionResult.FAILURE

        try:
            result = self._subprocess.run(
                command,
                shell=use_shell,
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.debug(f"Shell: {command}")
                return ActionResult.SUCCESS
            else:
                logger.warning(f"Shell {command}: exit {result.returncode}")
                return ActionResult.FAILURE
        except Exception as e:
            logger.error(f"Shell failed: {e}")
            return ActionResult.FAILURE


class ActionExecutor:
    """Main action executor with gesture mapping and debouncing."""

    def __init__(
        self,
        mapper: Optional[ActionMapper] = None,
        cooldown_ms: int = 1000,
    ):
        """Initialize action executor.

        Args:
            mapper: Gesture to action mapper
            cooldown_ms: Default cooldown between triggers
        """
        self._mapper = mapper or ActionMapper()
        self._cooldown_ms = cooldown_ms

        self._key_press = KeyPressAction()
        self._webhook = WebhookAction()
        self._shell = ShellAction()

        # Debounce tracking
        self._last_action_time: Dict[str, float] = {}
        self._lock = threading.Lock()

        self._enabled = True

    def execute(
        self,
        hands: List[DetectedHand],
    ) -> List[Action]:
        """Execute actions based on detected hands.

        Args:
            hands: List of detected hands

        Returns:
            List of executed actions
        """
        if not self._enabled or not hands:
            return []

        executed = []

        for hand in hands:
            gesture = hand.gesture
            if gesture == GestureType.UNKNOWN or gesture == GestureType.NONE:
                continue

            action_config = self._mapper.get_action(gesture)
            if not action_config:
                continue

            # Check cooldown
            action_name = action_config.action_name
            if not self._check_cooldown(action_name, action_config.cooldown_ms):
                continue

            # Execute action
            result = self._execute_action(action_config)

            action = Action(
                action_type=action_config.action_type,
                action_name=action_name,
                payload=action_config.payload,
                timestamp=time.time(),
            )
            executed.append(action)

            # Update cooldown
            self._update_cooldown(action_name)

        return executed

    def _check_cooldown(self, action_name: str, cooldown_ms: int) -> bool:
        """Check if action is off cooldown."""
        with self._lock:
            last_time = self._last_action_time.get(action_name, 0)
            elapsed = (time.time() * 1000) - last_time
            return elapsed >= cooldown_ms

    def _update_cooldown(self, action_name: str) -> None:
        """Update last action time."""
        with self._lock:
            self._last_action_time[action_name] = time.time() * 1000

    def _execute_action(self, config: ActionConfig) -> ActionResult:
        """Execute a single action."""
        action_type = config.action_type

        if action_type in (
            ActionType.MEDIA_PLAY,
            ActionType.MEDIA_PAUSE,
            ActionType.MEDIA_NEXT,
            ActionType.MEDIA_PREV,
            ActionType.VOLUME_UP,
            ActionType.VOLUME_DOWN,
            ActionType.VOLUME_MUTE,
        ):
            return self._key_press.execute(config.payload)
        elif action_type == ActionType.WEBHOOK:
            return self._webhook.execute(config.payload)
        elif action_type == ActionType.SHELL:
            return self._shell.execute(config.payload)

        return ActionResult.SKIP

    def set_cooldown(self, action_name: str, cooldown_ms: int) -> None:
        """Set cooldown for a specific action."""
        config = self._mapper._action_configs.get(action_name)
        if config:
            config.cooldown_ms = cooldown_ms

    def enable(self) -> None:
        """Enable action execution."""
        self._enabled = True

    def disable(self) -> None:
        """Disable action execution."""
        self._enabled = False

    @property
    def mapper(self) -> ActionMapper:
        """Get the action mapper."""
        return self._mapper

    @property
    def is_enabled(self) -> bool:
        """Check if enabled."""
        return self._enabled


def create_action_executor(
    mapping: Optional[Dict[GestureType, str]] = None,
    cooldown_ms: int = 1000,
) -> ActionExecutor:
    """Factory to create action executor.

    Args:
        mapping: Custom gesture to action mapping
        cooldown_ms: Default cooldown

    Returns:
        ActionExecutor instance
    """
    mapper = ActionMapper(mapping)
    return ActionExecutor(mapper=mapper, cooldown_ms=cooldown_ms)
