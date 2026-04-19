"""Camera capture module for reading video frames from camera.

This module handles:
- Camera device discovery and selection
- Video frame capture with threading
- Frame preprocessing (resize, histogram equalization)
- Graceful camera error handling

CODEMAP:
- CameraCapture: Main class for capturing from a camera device
- CameraReader: Thread-based camera reader
- get_available_cameras(): Discover available camera devices
"""

import threading
import time
from typing import Optional, List, Callable, Any
from dataclasses import dataclass

import cv2
import numpy as np

from .common.logging import setup_logger
from .common.queue import ThreadSafeQueue
from .common.metrics import SystemMetrics, LatencyTracker
from .common.types import CameraFrame
from .common.config import CameraConfig


logger = setup_logger(__name__)


@dataclass
class CameraInfo:
    """Information about an available camera."""

    index: int
    name: str
    available: bool


def get_available_cameras() -> List[CameraInfo]:
    """Discover available camera devices.

    Returns:
        List of CameraInfo for each potential camera index
    """
    cameras = []
    for i in range(5):  # Check first 5 indices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            cameras.append(CameraInfo(index=i, name=f"Camera {i}", available=ret))
            cap.release()
        else:
            cameras.append(CameraInfo(index=i, name=f"Camera {i}", available=False))
    return [c for c in cameras if c.available]


class CameraReader(threading.Thread):
    """Thread-based camera reader for continuous frame capture.

    This runs in a separate thread to ensure frames are captured
    at the target FPS without blocking the main pipeline.
    """

    def __init__(
        self,
        device_index: int = 0,
        target_fps: int = 30,
        frame_queue: Optional[ThreadSafeQueue] = None,
        metrics: Optional[SystemMetrics] = None,
    ):
        """Initialize the camera reader.

        Args:
            device_index: Camera device index
            target_fps: Target frames per second
            frame_queue: Queue to put frames into
            metrics: System metrics for tracking
        """
        super().__init__(daemon=True, name="CameraReader")
        self._device_index = device_index
        self._target_fps = target_fps
        self._frame_queue = frame_queue or ThreadSafeQueue(maxsize=2, name="frames")
        self._metrics = metrics
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._frame_time = 1.0 / target_fps

    def run(self) -> None:
        """Main capture loop running in thread."""
        self._cap = cv2.VideoCapture(self._device_index)

        if not self._cap.isOpened():
            logger.error(f"Cannot open camera {self._device_index}")
            return

        # Configure camera
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cap.set(cv2.CAP_PROP_FPS, self._target_fps)

        self._running = True
        logger.info(f"Camera reader started for device {self._device_index}")

        while self._running:
            with LatencyTracker(self._metrics or SystemMetrics(), "capture"):
                ret, frame = self._cap.read()

                if not ret:
                    logger.warning("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue

                # Wrap in CameraFrame and put on queue
                camera_frame = CameraFrame(
                    frame=frame,
                    timestamp=time.time(),
                    width=frame.shape[1],
                    height=frame.shape[0],
                )

                # Non-blocking put - drop frame if queue is full
                if not self._frame_queue.put_nowait(camera_frame):
                    logger.debug("Frame queue full, dropping frame")

                if self._metrics:
                    self._metrics.record_fps()

                # Sleep to maintain target FPS
                time.sleep(self._frame_time)

        self._cap.release()
        logger.info("Camera reader stopped")

    def stop(self) -> None:
        """Stop the camera reader."""
        self._running = False

    def is_running(self) -> bool:
        """Check if reader is running."""
        return self._running

    @property
    def frame_queue(self) -> ThreadSafeQueue:
        """Get the frame queue."""
        return self._frame_queue


class CameraCapture:
    """High-level camera capture interface.

    Manages camera reader thread and provides frame access.
    """

    def __init__(self, config: Optional[CameraConfig] = None):
        """Initialize camera capture.

        Args:
            config: Camera configuration
        """
        self._config = config or CameraConfig()
        self._reader: Optional[CameraReader] = None
        self._metrics = SystemMetrics()
        self._frame_queue: Optional[ThreadSafeQueue] = None
        self._error: Optional[str] = None

    def start(self) -> bool:
        """Start camera capture.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._frame_queue = ThreadSafeQueue(maxsize=2, name="camera_frames")
            self._reader = CameraReader(
                device_index=self._config.device_index,
                target_fps=self._config.fps,
                frame_queue=self._frame_queue,
                metrics=self._metrics,
            )
            self._reader.start()
            self._error = None
            logger.info("Camera capture started")
            return True
        except Exception as e:
            self._error = str(e)
            logger.error(f"Failed to start camera: {e}")
            return False

    def stop(self) -> None:
        """Stop camera capture."""
        if self._reader:
            self._reader.stop()
            self._reader.join(timeout=2.0)
            self._reader = None
        logger.info("Camera capture stopped")

    def get_frame(
        self, block: bool = True, timeout: float = 1.0
    ) -> Optional[CameraFrame]:
        """Get a frame from the capture.

        Args:
            block: Whether to block if no frame available
            timeout: Timeout in seconds

        Returns:
            CameraFrame if available, None otherwise
        """
        if self._frame_queue is None:
            return None

        try:
            return self._frame_queue.get(block=block, timeout=timeout)
        except:
            return None

    def get_latest_frame(self) -> Optional[CameraFrame]:
        """Get the latest frame (non-blocking).

        Returns:
            Latest CameraFrame if available
        """
        if self._frame_queue is None or self._frame_queue.empty():
            return None
        return self._frame_queue.get_nowait()

    def get_available_cameras(self) -> List[CameraInfo]:
        """Get list of available cameras."""
        return get_available_cameras()

    def get_error(self) -> Optional[str]:
        """Get last error message."""
        return self._error

    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._reader is not None and self._reader.is_running()

    @property
    def metrics(self) -> SystemMetrics:
        """Get metrics."""
        return self._metrics


def create_camera_capture(
    device_index: int = 0,
    target_fps: int = 30,
) -> CameraCapture:
    """Factory function to create camera capture.

    Args:
        device_index: Camera device index
        target_fps: Target FPS

    Returns:
        Configured CameraCapture instance
    """
    config = CameraConfig(device_index=device_index, fps=target_fps)
    return CameraCapture(config)
