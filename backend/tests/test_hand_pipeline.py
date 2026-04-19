"""Unit tests for hand_pipeline module."""

import unittest
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cammy.hand_pipeline import (
    HandPipeline,
    HandDetector,
    GestureClassifier,
    create_hand_pipeline,
)
from tests.common import create_test_frame, create_mock_landmarks


class TestGestureClassifier(unittest.TestCase):
    """Tests for GestureClassifier."""

    def test_create_builtin(self):
        """Test creation with builtin."""
        classifier = GestureClassifier(use_builtin=True)
        self.assertIsNotNone(classifier)

    def test_create_rule_based(self):
        """Test creation with rule-based."""
        classifier = GestureClassifier(use_builtin=False)
        self.assertIsNotNone(classifier)

    def test_classify_with_landmarks(self):
        """Test classification with landmarks."""
        classifier = GestureClassifier(use_builtin=False)
        landmarks = create_mock_landmarks()

        gesture, confidence = classifier.classify(landmarks, "right")

        self.assertIsNotNone(gesture)
        self.assertIsInstance(confidence, float)

    def test_classify_empty_landmarks(self):
        """Test classification with empty landmarks."""
        classifier = GestureClassifier(use_builtin=False)

        gesture, confidence = classifier.classify([], "right")

        self.assertEqual(gesture.value, "unknown")
        self.assertEqual(confidence, 0.0)

    def test_classify_rule_based_fist(self):
        """Test rule-based fist detection."""
        classifier = GestureClassifier(use_builtin=False)

        # Create landmarks for closed fist
        landmarks = [[0.5, 0.5, 0.0]] * 21

        gesture, confidence = classifier.classify(landmarks, "right")

        # Should detect as some gesture
        self.assertIsNotNone(gesture)


class TestHandDetector(unittest.TestCase):
    """Tests for HandDetector."""

    def test_create(self):
        """Test detector creation."""
        detector = HandDetector()
        self.assertIsNotNone(detector)

    def test_detect(self):
        """Test hand detection."""
        detector = HandDetector()
        frame = create_test_frame()

        hands = detector.detect(frame)

        self.assertIsInstance(hands, list)


class TestCreateHandPipeline(unittest.TestCase):
    """Tests for create_hand_pipeline factory."""

    def test_create_default(self):
        """Test default creation."""
        pipeline = create_hand_pipeline()
        self.assertIsInstance(pipeline, HandPipeline)

    def test_create_with_params(self):
        """Test creation with params."""
        pipeline = create_hand_pipeline(max_hands=1, min_confidence=0.7)

        self.assertIsInstance(pipeline, HandPipeline)


class TestHandPipeline(unittest.TestCase):
    """Tests for HandPipeline."""

    def test_create(self):
        """Test pipeline creation."""
        pipeline = HandPipeline()
        self.assertIsNotNone(pipeline)
        self.assertFalse(pipeline.is_running)

    def test_process(self):
        """Test frame processing."""
        pipeline = HandPipeline()
        frame = create_test_frame()

        hands = pipeline.process(frame)

        self.assertIsInstance(hands, list)

    def test_start_stop(self):
        """Test start and stop."""
        from cammy.common import ThreadSafeQueue

        pipeline = HandPipeline()
        input_queue = ThreadSafeQueue(maxsize=2)
        output_queue = ThreadSafeQueue(maxsize=2)

        pipeline.start(input_queue, output_queue)
        self.assertTrue(pipeline.is_running)

        pipeline.stop()
        self.assertFalse(pipeline.is_running)


if __name__ == "__main__":
    unittest.main()
