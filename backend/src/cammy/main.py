"""Main entry point for Cammy system.

This module orchestrates:
- Camera capture
- Face detection/recognition
- Hand gesture detection
- Action execution
- WebSocket streaming

CODEMAP:
- main(): Entry point
- CammyApp: Main application class
"""

import asyncio
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional, List

from .camera_capture import CameraCapture, create_camera_capture
from .face_pipeline import FacePipeline, create_face_pipeline
from .hand_pipeline import HandPipeline, create_hand_pipeline
from .action_executor import ActionExecutor, create_action_executor
from .server import CammyServer, create_server

from .common.logging import setup_logger
from .common.config import CammyConfig, ConfigManager, get_config_manager
from .common.queue import ThreadSafeQueue, PipelineQueue
from .common.metrics import SystemMetrics
from .common.types import PipelineResult
from .common.commands import CommandsManager


logger = setup_logger(__name__)


class CammyApp:
    """Main application class orchestrating all components."""

    def __init__(self, config: Optional[CammyConfig] = None):
        """Initialize the application.

        Args:
            config: Configuration (loads from default if not provided)
        """
        self._config = config or get_config_manager().load()
        self._metrics = SystemMetrics()

        self._camera: Optional[CameraCapture] = None
        self._face_pipeline: Optional[FacePipeline] = None
        self._hand_pipeline: Optional[HandPipeline] = None
        self._action_executor: Optional[ActionExecutor] = None
        self._server: Optional[CammyServer] = None
        self._commands_manager: Optional[CommandsManager] = None

        self._running = False
        self._threads: List[threading.Thread] = []

        logger.info("CammyApp initialized")

    def start(self) -> None:
        """Start all components."""
        logger.info("Starting Cammy...")

        # Initialize camera
        self._camera = create_camera_capture(
            device_index=self._config.camera.device_index,
            target_fps=self._config.performance.target_fps,
        )

        # Initialize commands manager (persisted user-defined commands)
        self._commands_manager = CommandsManager()

        # Initialize pipelines
        self._face_pipeline = create_face_pipeline(
            threshold=self._config.detection.face_similarity_threshold,
            max_faces=self._config.detection.max_faces,
        )

        self._hand_pipeline = create_hand_pipeline(
            max_hands=self._config.detection.max_hands,
            min_confidence=self._config.detection.gesture_confidence_threshold,
        )

        self._action_executor = create_action_executor(
            cooldown_ms=self._config.action.cooldown_ms,
            commands_manager=self._commands_manager,
        )

        # Initialize server
        self._server = create_server(
            host=self._config.server.host,
            ws_port=self._config.server.port,
        )

        # Wire dependencies into REST API (also wires action_executed callback)
        self._server.set_dependencies(
            config_manager=get_config_manager(),
            identity_store=self._face_pipeline.identity_store,
            face_pipeline=self._face_pipeline,
            action_executor=self._action_executor,
            camera=self._camera,
            commands_manager=self._commands_manager,
        )

        # Start components
        self._camera.start()
        self._server.start(start_rest=True)

        self._running = True

        # Start processing threads
        self._start_processing_threads()

        logger.info("Cammy started successfully")

    def _start_processing_threads(self) -> None:
        """Start the processing threads."""
        # Thread for face processing
        face_thread = threading.Thread(
            target=self._face_processing_loop,
            daemon=True,
            name="FaceProcessor",
        )
        face_thread.start()
        self._threads.append(face_thread)

        # Thread for hand processing
        hand_thread = threading.Thread(
            target=self._hand_processing_loop,
            daemon=True,
            name="HandProcessor",
        )
        hand_thread.start()
        self._threads.append(hand_thread)

        logger.info(f"Started {len(self._threads)} processing threads")

    def _face_processing_loop(self) -> None:
        """Process frames for face detection."""
        logger.info("Face processing thread started")

        while self._running:
            if not self._camera or not self._camera.is_running():
                time.sleep(0.1)
                continue

            frame = self._camera.get_frame(timeout=1.0)
            if frame is None:
                continue

            # Process frame
            faces = self._face_pipeline.process(frame.frame)

            # Broadcast to server
            if self._server and self._server.is_running:
                self._server.broadcast_faces(faces)

    def _hand_processing_loop(self) -> None:
        """Process frames for hand gesture detection."""
        logger.info("Hand processing thread started")

        while self._running:
            if not self._camera or not self._camera.is_running():
                time.sleep(0.1)
                continue

            frame = self._camera.get_frame(timeout=1.0)
            if frame is None:
                continue

            # Process frame
            hands = self._hand_pipeline.process(frame.frame)

            # Execute actions
            if self._action_executor and self._config.action.enabled:
                actions = self._action_executor.execute(hands)
                if actions:
                    logger.debug(f"Executed {len(actions)} actions")

            # Broadcast to server
            if self._server and self._server.is_running:
                self._server.broadcast_gestures(hands)

    def stop(self) -> None:
        """Stop all components."""
        logger.info("Stopping Cammy...")

        self._running = False

        # Stop threads
        for thread in self._threads:
            thread.join(timeout=2.0)

        # Stop components
        if self._camera:
            self._camera.stop()

        if self._server:
            self._server.stop()

        if self._face_pipeline:
            self._face_pipeline.close()

        if self._hand_pipeline:
            self._hand_pipeline.close()

        logger.info("Cammy stopped")

    def is_running(self) -> bool:
        """Check if application is running."""
        return self._running

    @property
    def metrics(self) -> SystemMetrics:
        """Get system metrics."""
        return self._metrics


def main():
    """Main entry point."""
    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load()

    # Create application
    app = CammyApp(config)

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        app.start()
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        app.stop()
        sys.exit(1)

    # Keep running
    while app.is_running():
        time.sleep(1)


if __name__ == "__main__":
    main()
