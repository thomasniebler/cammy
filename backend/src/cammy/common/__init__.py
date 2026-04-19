"""Common utilities for cammy pipeline."""

from .logging import setup_logger, get_logger
from .queue import ThreadSafeQueue, PipelineQueue, TimestampedFrame
from .metrics import SystemMetrics, PipelineMetrics, LatencyTracker, Timer
from .config import (
    CammyConfig,
    ConfigManager,
    get_config_manager,
    DEFAULT_CONFIG_DIR,
)
from .types import (
    HandType,
    GestureType,
    ActionType,
    BoundingBox,
    DetectedFace,
    DetectedHand,
    Action,
    CameraFrame,
    PipelineResult,
    GESTURE_ACTION_MAPPING,
)

__all__ = [
    # Logging
    "setup_logger",
    "get_logger",
    # Queue
    "ThreadSafeQueue",
    "PipelineQueue",
    "TimestampedFrame",
    # Metrics
    "SystemMetrics",
    "PipelineMetrics",
    "LatencyTracker",
    "Timer",
    # Config
    "CammyConfig",
    "ConfigManager",
    "get_config_manager",
    "DEFAULT_CONFIG_DIR",
    # Types
    "HandType",
    "GestureType",
    "ActionType",
    "BoundingBox",
    "DetectedFace",
    "DetectedHand",
    "Action",
    "CameraFrame",
    "PipelineResult",
    "GESTURE_ACTION_MAPPING",
]
