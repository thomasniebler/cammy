"""Cammy - Real-time face and gesture recognition system."""

__version__ = "0.1.0"

from .camera_capture import CameraCapture, create_camera_capture
from .face_pipeline import FacePipeline, create_face_pipeline
from .hand_pipeline import HandPipeline, create_hand_pipeline
from .action_executor import ActionExecutor, create_action_executor
from .server import CammyServer, create_server
from .common import (
    CammyConfig,
    ConfigManager,
    get_config_manager,
    SystemMetrics,
    ThreadSafeQueue,
    PipelineQueue,
    DetectedFace,
    DetectedHand,
    Action,
    GestureType,
    ActionType,
)

__all__ = [
    # Version
    "__version__",
    # Camera
    "CameraCapture",
    "create_camera_capture",
    # Face
    "FacePipeline",
    "create_face_pipeline",
    # Hand
    "HandPipeline",
    "create_hand_pipeline",
    # Action
    "ActionExecutor",
    "create_action_executor",
    # Server
    "CammyServer",
    "create_server",
    # Common
    "CammyConfig",
    "ConfigManager",
    "get_config_manager",
    "SystemMetrics",
    "ThreadSafeQueue",
    "PipelineQueue",
    "DetectedFace",
    "DetectedHand",
    "Action",
    "GestureType",
    "ActionType",
]
