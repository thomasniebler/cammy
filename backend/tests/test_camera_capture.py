"""Unit tests for camera_capture module."""

import unittest
import tempfile
import threading
import time
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cammy.camera_capture import (
    get_available_cameras,
    CameraCapture,
    CameraReader,
    CameraInfo,
    CameraFrame,
    create_camera_capture,
)
from tests.common import (
    create_test_frame,
    MockCamera,
    assert_frame_valid,
)


class TestGetAvailableCameras(unittest.TestCase):
    """Tests for get_available_cameras."""

    def test_get_available_cameras(self):
        """Test camera discovery."""
        # This will return available cameras on the system
        cameras = get_available_cameras()

        # Should return a list
        self.assertIsInstance(cameras, list)

        # Each should be CameraInfo
        for camera in cameras:
            self.assertIsInstance(camera, CameraInfo)
            self.assertIsInstance(camera.index, int)


class TestCameraInfo(unittest.TestCase):
    """Tests for CameraInfo."""

    def test_create(self):
        """Test CameraInfo creation."""
        info = CameraInfo(index=0, name="Test Camera", available=True)

        self.assertEqual(info.index, 0)
        self.assertEqual(info.name, "Test Camera")
        self.assertTrue(info.available)


class TestCameraFrame(unittest.TestCase):
    """Tests for CameraFrame."""

    def test_create(self):
        """Test CameraFrame creation."""
        frame_data = create_test_frame()
        cam_frame = CameraFrame(
            frame=frame_data,
            timestamp=time.time(),
            width=640,
            height=480,
        )

        assert_frame_valid(cam_frame.frame)
        self.assertEqual(cam_frame.width, 640)
        self.assertEqual(cam_frame.height, 480)


class TestCreateCameraCapture(unittest.TestCase):
    """Tests for create_camera_capture factory."""

    def test_create_default(self):
        """Test default creation."""
        capture = create_camera_capture()
        self.assertIsInstance(capture, CameraCapture)

    def test_create_with_params(self):
        """Test creation with parameters."""
        capture = create_camera_capture(device_index=1, target_fps=15)

        self.assertIsInstance(capture, CameraCapture)


class TestCameraCapture(unittest.TestCase):
    """Tests for CameraCapture."""

    def test_create(self):
        """Test CameraCapture creation."""
        capture = CameraCapture()
        self.assertIsNone(capture.get_error())
        self.assertFalse(capture.is_running())

    def test_start_stop(self):
        """Test start and stop."""
        capture = create_camera_capture()

        # Try to start (may fail if no camera)
        # Just verify methods work without error
        result = capture.start()

        # Cleanup
        capture.stop()

        # Result depends on camera availability
        # Just verify stop doesn't error
        self.assertFalse(capture.is_running())


class TestCameraReader(unittest.TestCase):
    """Tests for CameraReader."""

    def test_create(self):
        """Test CameraReader creation."""
        reader = CameraReader(device_index=0, target_fps=10)

        self.assertEqual(reader._device_index, 0)
        self.assertEqual(reader._target_fps, 10)
        self.assertFalse(reader.is_running())

    def test_frame_queue(self):
        """Test frame queue."""
        reader = CameraReader(device_index=0, target_fps=10)

        self.assertIsNotNone(reader.frame_queue)
        self.assertEqual(reader.frame_queue.name, "frames")


if __name__ == "__main__":
    unittest.main()
