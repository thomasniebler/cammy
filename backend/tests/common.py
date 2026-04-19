"""Common test utilities for cammy tests."""

import time
import threading
import numpy as np
from typing import Any, Callable, Optional
from contextlib import contextmanager


def create_test_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a test frame.

    Args:
        width: Frame width
        height: Frame height

    Returns:
        Test frame as numpy array
    """
    return np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)


def create_test_frames(count: int = 10, **kwargs) -> list:
    """Create multiple test frames.

    Args:
        count: Number of frames
        **kwargs: Arguments for create_test_frame

    Returns:
        List of test frames
    """
    return [create_test_frame(**kwargs) for _ in range(count)]


def create_mock_landmarks() -> list:
    """Create mock hand landmarks (21 points).

    Returns:
        List of 21 landmarks [[x,y,z], ...]
    """
    # Simple mock - random 3D points in normalized space
    return np.random.rand(21, 3).tolist()


def create_mock_face_bbox() -> dict:
    """Create mock face bounding box.

    Returns:
        Dict with bbox data
    """
    return {
        "x": 100,
        "y": 50,
        "width": 200,
        "height": 250,
    }


class MockCamera:
    """Mock camera for testing without actual camera."""

    def __init__(self, frame: Optional[np.ndarray] = None):
        """Initialize mock camera.

        Args:
            frame: Frame to return (or generate random)
        """
        self._frame = frame or create_test_frame()
        self._is_opened = True
        self._read_count = 0

    def isOpened(self) -> bool:
        """Check if camera is opened."""
        return self._is_opened

    def read(self) -> tuple:
        """Read a frame.

        Returns:
            (success, frame)
        """
        self._read_count += 1
        return True, self._frame.copy()

    def release(self) -> None:
        """Release camera."""
        self._is_opened = False

    def get(self, prop_id: int) -> float:
        """Get camera property."""
        return 1.0

    def set(self, prop_id: int, value: float) -> bool:
        """Set camera property."""
        return True


class FrameCapturer:
    """Utility to capture frames in a thread."""

    def __init__(self, capture_func: Callable[[], Any], interval: float = 0.1):
        """Initialize capturer.

        Args:
            capture_func: Function to capture frames
            interval: Interval between captures
        """
        self._capture_func = capture_func
        self._interval = interval
        self._captures: list = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start capturing."""
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        """Capture loop."""
        while self._running:
            frame = self._capture_func()
            if frame is not None:
                self._captures.append((time.time(), frame))
            time.sleep(self._interval)

    def stop(self) -> list:
        """Stop capturing.

        Returns:
            List of captured frames with timestamps
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        return self._captures

    @property
    def captures(self) -> list:
        """Get captured frames."""
        return self._captures


@contextmanager
def temp_config_dir():
    """Context manager for temporary config directory."""
    import tempfile
    import shutil

    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@contextmanager
def temp_identity_dir():
    """Context manager for temporary identity directory."""
    import tempfile
    import shutil

    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def assert_frame_valid(frame: np.ndarray) -> None:
    """Assert a frame is valid.

    Args:
        frame: Frame to check
    """
    assert frame is not None, "Frame is None"
    assert isinstance(frame, np.ndarray), "Frame is not numpy array"
    assert len(frame.shape) >= 2, "Frame has wrong dimensions"
    assert frame.dtype == np.uint8, "Frame has wrong dtype"


def assert_metrics_valid(metrics: dict) -> None:
    """Assert metrics are valid.

    Args:
        metrics: Metrics dict to check
    """
    assert isinstance(metrics, dict), "Metrics is not dict"
    assert "fps" in metrics, "Metrics missing fps"
    assert "pipelines" in metrics, "Metrics missing pipelines"


def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 1.0,
    interval: float = 0.01,
) -> bool:
    """Wait for a condition to be true.

    Args:
        condition: Function that returns bool
        timeout: Maximum wait time
        interval: Check interval

    Returns:
        True if condition met, False if timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False
