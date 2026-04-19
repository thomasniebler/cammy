"""Hand gesture detection pipeline.

This module handles:
- Hand landmark detection using MediaPipe Hands
- Gesture classification (built-in or custom)
- Multi-hand detection

CODEMAP:
- HandDetector: Detect hands and landmarks
- GestureClassifier: Classify gestures from landmarks
- HandPipeline: Combined detection + classification
"""

import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np

from .common.logging import setup_logger
from .common.queue import ThreadSafeQueue
from .common.metrics import SystemMetrics, LatencyTracker
from .common.types import (
    DetectedHand,
    GestureType,
    HandType,
)


logger = setup_logger(__name__)


# Check MediaPipe availability
def _check_mediapipe():
    """Check if MediaPipe is available."""
    try:
        import mediapipe as mp

        return True
    except ImportError:
        return False


MEDIAPIPE_AVAILABLE = _check_mediapipe()


class HandDetector:
    """Hand landmark detector using MediaPipe Hands."""

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1,
    ):
        """Initialize hand detector.

        Args:
            max_hands: Maximum hands to detect
            min_detection_confidence: Minimum detection confidence
            min_tracking_confidence: Minimum tracking confidence
            model_complexity: 0=lite, 1=full
        """
        self._max_hands = max_hands
        self._min_detection_confidence = min_detection_confidence
        self._min_tracking_confidence = min_tracking_confidence
        self._model_complexity = model_complexity
        self._detector = None
        self._drawing_utils = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the detector."""
        if not MEDIAPIPE_AVAILABLE:
            logger.warning("MediaPipe not available for hand detection")
            return

        try:
            import mediapipe as mp

            self._detector = mp.solutions.hands.Hands(
                max_num_hands=self._max_hands,
                min_detection_confidence=self._min_detection_confidence,
                min_tracking_confidence=self._min_tracking_confidence,
                model_complexity=self._model_complexity,
            )
            self._drawing_utils = mp.solutions.drawing_utils
            logger.info(
                f"Hand detector initialized (max_hands={self._max_hands}, "
                f"complexity={self._model_complexity})"
            )
        except Exception as e:
            logger.warning(f"MediaPipe hand init failed: {e}")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect hands in a frame.

        Args:
            frame: Image frame (BGR)

        Returns:
            List of detection dicts with landmarks and hand type
        """
        if self._detector is None:
            return []

        # Convert to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._detector.process(rgb_frame)

        hands = []
        if results.multi_hand_landmarks:
            # Get handedness if available
            handedness = results.multi_handedness if results.multi_handedness else []

            for idx, landmarks in enumerate(results.multi_hand_landmarks):
                # Get hand type (left/right)
                hand_type = HandType.UNKNOWN
                if idx < len(handedness):
                    hand_classification = handedness[idx].classification
                    if hand_classification:
                        label = hand_classification[0].label
                        hand_type = HandType.LEFT if label == "Left" else HandType.RIGHT

                # Extract landmark coordinates (normalized)
                landmark_list = []
                for lm in landmarks.landmark:
                    landmark_list.append([lm.x, lm.y, lm.z])

                # Get detection confidence
                confidence = 1.0
                if idx < len(handedness):
                    confidence = handedness[idx].classification[0].score

                hands.append(
                    {
                        "landmarks": landmark_list,
                        "hand_type": hand_type,
                        "confidence": confidence,
                    }
                )

        return hands

    def draw_landmarks(
        self, frame: np.ndarray, landmarks: List[List[float]]
    ) -> np.ndarray:
        """Draw hand landmarks on frame (for visualization).

        Args:
            frame: Image frame
            landmarks: Hand landmarks

        Returns:
            Frame with landmarks drawn
        """
        if self._drawing_utils is None or landmarks is None:
            return frame

        # Convert landmarks back to MediaPipe format
        # This is a simplified version - in production would use proper conversion
        return frame

    def close(self) -> None:
        """Close the detector."""
        if self._detector:
            self._detector.close()
            self._detector = None


class GestureClassifier:
    """Gesture classifier using MediaPipe or rule-based."""

    def __init__(self, use_builtin: bool = True):
        """Initialize gesture classifier.

        Args:
            use_builtin: Use MediaPipe built-in gesture recognizer
        """
        self._use_builtin = use_builtin
        self._recognizer = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the classifier."""
        if not MEDIAPIPE_AVAILABLE or not self._use_builtin:
            logger.info("Using rule-based gesture classification")
            return

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            # Initialize gesture recognizer
            # Note: Requires downloading the gesture model
            logger.info("MediaPipe gesture classifier ready (using rule-based)")
        except Exception as e:
            logger.warning(f"MediaPipe gesture init failed: {e}")

    def classify(
        self,
        landmarks: List[List[float]],
        hand_type: HandType,
    ) -> Tuple[GestureType, float]:
        """Classify gesture from landmarks.

        Args:
            landmarks: 21 hand landmarks [[x,y,z], ...]
            hand_type: Left or right hand

        Returns:
            Tuple of (gesture_type, confidence)
        """
        return self._classify_rule_based(landmarks)

    def _classify_rule_based(
        self,
        landmarks: List[List[float]],
    ) -> Tuple[GestureType, float]:
        """Rule-based gesture classification.

        Classifies based on finger states.

        Args:
            landmarks: 21 hand landmarks (normalized 0-1)

        Returns:
            Tuple of (gesture_type, confidence)
        """
        if not landmarks or len(landmarks) != 21:
            return GestureType.UNKNOWN, 0.0

        # Extract key points for classification
        # Landmark indices:
        # Thumb: 1 (MCP), 2 (IP), 3 (tip), 4 (tip direction)
        # Index: 5 (MCP), 6 (PIP), 7 (DIP), 8 (tip)
        # Middle: 9 (MCP), 10 (PIP), 11 (DIP), 12 (tip)
        # Ring: 13 (MCP), 14 (PIP), 15 (DIP), 16 (tip)
        # Pinky: 17 (MCP), 18 (PIP), 19 (DIP), 20 (tip)
        # Wrist: 0

        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        thumb_ip = landmarks[3]
        index_pip = landmarks[7]
        middle_pip = landmarks[11]
        ring_pip = landmarks[15]
        pinky_pip = landmarks[19]

        # Check finger extension (tip is above PIP joint)
        def is_extended(tip, pip):
            return tip[1] < pip[1] - 0.02

        index_ext = is_extended(index_tip, index_pip)
        middle_ext = is_extended(middle_tip, middle_pip)
        ring_ext = is_extended(ring_tip, ring_pip)
        pinky_ext = is_extended(pinky_tip, pinky_pip)

        # Thumb extension (horizontal check for thumb)
        thumb_ext = abs(thumb_tip[0] - thumb_ip[0]) > 0.08

        # Count extended fingers
        fingers_extended = sum([index_ext, middle_ext, ring_ext, pinky_ext, thumb_ext])

        # Determine gesture based on finger pattern
        if fingers_extended == 0:
            return GestureType.FIST, 0.85
        elif fingers_extended == 5:
            return GestureType.OPEN_PALM, 0.85
        elif (
            fingers_extended == 4
            and index_ext
            and middle_ext
            and not ring_ext
            and not pinky_ext
        ):
            return GestureType.PEACE, 0.80
        elif fingers_extended == 1 and index_ext:
            return GestureType.POINTING, 0.75
        elif thumb_ext and fingers_extended == 1:
            # Check thumb direction
            if thumb_tip[1] < wrist[1]:
                return GestureType.THUMBS_UP, 0.80
            else:
                return GestureType.THUMBS_DOWN, 0.80
        elif (
            index_ext
            and thumb_ext
            and not middle_ext
            and not ring_ext
            and not pinky_ext
        ):
            # Check if thumb and index form OK sign
            thumb_index_dist = (
                (thumb_tip[0] - index_tip[0]) ** 2 + (thumb_tip[1] - index_tip[1]) ** 2
            ) ** 0.5
            if thumb_index_dist < 0.08:
                return GestureType.OK_SIGN, 0.70
        elif (
            not index_ext
            and not middle_ext
            and not ring_ext
            and not pinky_ext
            and thumb_ext
        ):
            return GestureType.THUMBS_UP if thumb_tip[1] < wrist[
                1
            ] else GestureType.THUMBS_DOWN, 0.70

        return GestureType.UNKNOWN, 0.3


class HandPipeline:
    """Combined hand detection and gesture classification."""

    def __init__(
        self,
        max_hands: int = 2,
        min_confidence: float = 0.5,
        use_builtin_gestures: bool = True,
        metrics: Optional[SystemMetrics] = None,
    ):
        """Initialize hand pipeline.

        Args:
            max_hands: Maximum hands to detect
            min_confidence: Minimum confidence threshold
            use_builtin_gestures: Use MediaPipe built-in gestures
            metrics: System metrics
        """
        self._max_hands = max_hands
        self._min_confidence = min_confidence
        self._metrics = metrics or SystemMetrics()

        self._detector = HandDetector(max_hands=max_hands)
        self._classifier = GestureClassifier(use_builtin=use_builtin_gestures)

        self._running = False
        self._input_queue: Optional[ThreadSafeQueue] = None
        self._output_queue: Optional[ThreadSafeQueue] = None

        logger.info(
            f"HandPipeline initialized (max_hands={max_hands}, min_conf={min_confidence})"
        )

    def start(
        self,
        input_queue: ThreadSafeQueue,
        output_queue: ThreadSafeQueue,
    ) -> None:
        """Start the pipeline.

        Args:
            input_queue: Queue to read frames from
            output_queue: Queue to write results to
        """
        self._input_queue = input_queue
        self._output_queue = output_queue
        self._running = True
        logger.info("Hand pipeline started")

    def stop(self) -> None:
        """Stop the pipeline."""
        self._running = False
        logger.info("Hand pipeline stopped")

    def process(self, frame: np.ndarray) -> List[DetectedHand]:
        """Process a frame and detect gestures.

        Args:
            frame: Image frame (BGR)

        Returns:
            List of detected hands with gestures
        """
        with LatencyTracker(self._metrics, "hand_detection"):
            detections = self._detector.detect(frame)

        hands = []
        for det in detections[: self._max_hands]:
            landmarks = det.get("landmarks", [])
            hand_type = det.get("hand_type", HandType.UNKNOWN)
            confidence = det.get("confidence", 1.0)

            # Classify gesture
            gesture, gesture_conf = self._classifier.classify(landmarks, hand_type)

            # Apply confidence threshold
            combined_conf = gesture_conf * confidence

            if combined_conf >= self._min_confidence:
                hand = DetectedHand(
                    gesture=gesture,
                    gesture_confidence=combined_conf,
                    hand_type=hand_type,
                    landmarks=landmarks,
                )
                hands.append(hand)

        return hands

    @property
    def is_running(self) -> bool:
        """Check if running."""
        return self._running

    def close(self) -> None:
        """Close the pipeline."""
        self._detector.close()
        logger.info("Hand pipeline closed")


def create_hand_pipeline(
    max_hands: int = 2,
    min_confidence: float = 0.5,
) -> HandPipeline:
    """Factory to create hand pipeline.

    Args:
        max_hands: Maximum hands to detect
        min_confidence: Minimum confidence

    Returns:
        HandPipeline instance
    """
    return HandPipeline(
        max_hands=max_hands,
        min_confidence=min_confidence,
    )
