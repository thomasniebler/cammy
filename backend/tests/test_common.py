"""Unit tests for common modules."""

import unittest
import tempfile
import threading
import time
from pathlib import Path
import os
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cammy.common.logging import setup_logger, get_logger
from cammy.common.queue import ThreadSafeQueue, PipelineQueue, TimestampedFrame
from cammy.common.metrics import SystemMetrics, PipelineMetrics, Timer
from cammy.common.config import (
    CammyConfig,
    ConfigManager,
    DetectionConfig,
    CameraConfig,
)
from cammy.common.types import (
    GestureType,
    ActionType,
    DetectedFace,
    DetectedHand,
    BoundingBox,
)


class TestLogging(unittest.TestCase):
    """Tests for logging module."""

    def test_setup_logger(self):
        """Test logger setup."""
        logger = setup_logger("test_logger")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "test_logger")

    def test_get_logger(self):
        """Test get existing logger."""
        logger1 = get_logger("test_get")
        logger2 = get_logger("test_get")
        self.assertEqual(logger1, logger2)


class TestQueue(unittest.TestCase):
    """Tests for queue module."""

    def test_thread_safe_queue_put_get(self):
        """Test basic put and get."""
        queue = ThreadSafeQueue(maxsize=2, name="test")
        self.assertTrue(queue.put("item1"))
        self.assertTrue(queue.put("item2"))
        self.assertEqual(queue.get(), "item1")
        self.assertEqual(queue.get(), "item2")

    def test_thread_safe_queue_full(self):
        """Test queue full behavior."""
        queue = ThreadSafeQueue(maxsize=2, name="test")
        queue.put("item1")
        queue.put("item2")
        self.assertTrue(queue.full())
        self.assertFalse(queue.put_nowait("item3"))

    def test_thread_safe_queue_empty(self):
        """Test queue empty behavior."""
        queue = ThreadSafeQueue(maxsize=2, name="test")
        self.assertTrue(queue.empty())
        queue.put("item1")
        self.assertFalse(queue.empty())

    def test_thread_safe_queue_clear(self):
        """Test queue clear."""
        queue = ThreadSafeQueue(maxsize=2, name="test")
        queue.put("item1")
        queue.put("item2")
        queue.clear()
        self.assertTrue(queue.empty())

    def test_pipeline_queue(self):
        """Test pipeline queue."""
        pq = PipelineQueue(frame_maxsize=2)
        self.assertEqual(pq.frames.name, "frame")
        self.assertEqual(pq.faces.name, "face")
        self.assertEqual(pq.hands.name, "hand")


class TestTimestampedFrame(unittest.TestCase):
    """Tests for TimestampedFrame."""

    def test_create(self):
        """Test creation."""
        frame = TimestampedFrame.create({"data": "test"})
        self.assertEqual(frame.data, {"data": "test"})
        self.assertIsInstance(frame.timestamp, float)


class TestMetrics(unittest.TestCase):
    """Tests for metrics module."""

    def test_pipeline_metrics(self):
        """Test pipeline metrics."""
        metrics = PipelineMetrics(name="test")
        metrics.record_latency(10.0)
        metrics.record_latency(20.0)

        self.assertEqual(metrics.count, 2)
        self.assertEqual(metrics.total_latency_ms, 30.0)
        self.assertEqual(metrics.avg_latency_ms, 15.0)
        self.assertEqual(metrics.min_latency_ms, 10.0)
        self.assertEqual(metrics.max_latency_ms, 20.0)

    def test_pipeline_metrics_error(self):
        """Test error recording."""
        metrics = PipelineMetrics(name="test")
        metrics.record_error()

        self.assertEqual(metrics.errors, 1)

    def test_system_metrics_fps(self):
        """Test FPS calculation."""
        metrics = SystemMetrics(fps_window=5)

        # Record several frames over time
        for _ in range(5):
            time.sleep(0.01)
            metrics.record_fps()

        fps = metrics.get_fps()
        self.assertIsInstance(fps, float)
        self.assertGreater(fps, 0)

    def test_timer(self):
        """Test timer."""
        timer = Timer()
        timer.start()
        time.sleep(0.01)
        elapsed = timer.stop()

        self.assertGreater(elapsed, 0)


class TestConfig(unittest.TestCase):
    """Tests for config module."""

    def test_detection_config_defaults(self):
        """Test default detection config."""
        config = DetectionConfig()
        self.assertEqual(config.face_similarity_threshold, 0.65)
        self.assertEqual(config.gesture_confidence_threshold, 0.80)

    def test_camera_config_defaults(self):
        """Test default camera config."""
        config = CameraConfig()
        self.assertEqual(config.device_index, 0)
        self.assertEqual(config.width, 640)
        self.assertEqual(config.height, 480)

    def test_cammy_config_from_dict(self):
        """Test config creation from dict."""
        data = {
            "performance": {"tier": "high"},
            "detection": {"face_similarity_threshold": 0.7},
            "camera": {"device_index": 1},
        }
        config = CammyConfig.from_dict(data)

        self.assertEqual(config.detection.face_similarity_threshold, 0.7)
        self.assertEqual(config.camera.device_index, 1)

    def test_config_manager(self):
        """Test config manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            manager = ConfigManager(tmp_path)
            config = manager.load()

            self.assertIsInstance(config, CammyConfig)


class TestTypes(unittest.TestCase):
    """Tests for types module."""

    def test_bounding_box(self):
        """Test bounding box."""
        bbox = BoundingBox(x=10, y=20, width=100, height=150)
        data = bbox.to_dict()

        self.assertEqual(data["x"], 10)
        self.assertEqual(data["width"], 100)

    def test_detected_face(self):
        """Test detected face."""
        face = DetectedFace(
            identity="alice",
            confidence=0.92,
            bbox=BoundingBox(10, 20, 100, 150),
        )
        data = face.to_dict()

        self.assertEqual(data["identity"], "alice")
        self.assertEqual(data["confidence"], 0.92)

    def test_detected_hand(self):
        """Test detected hand."""
        hand = DetectedHand(
            gesture=GestureType.FIST,
            gesture_confidence=0.85,
        )
        data = hand.to_dict()

        self.assertEqual(data["type"], "fist")
        self.assertEqual(data["confidence"], 0.85)

    def test_gesture_action_mapping(self):
        """Test gesture action mapping."""
        from cammy.common.types import GESTURE_ACTION_MAPPING

        self.assertEqual(
            GESTURE_ACTION_MAPPING[GestureType.FIST], ActionType.MEDIA_PAUSE
        )
        self.assertEqual(
            GESTURE_ACTION_MAPPING[GestureType.OPEN_PALM], ActionType.MEDIA_PLAY
        )


if __name__ == "__main__":
    unittest.main()
