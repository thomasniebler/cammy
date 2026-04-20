"""Face detection and recognition pipeline.

This module handles:
- Face detection using MediaPipe
- Face embedding extraction using DeepFace (ArcFace/Facenet)
- Identity matching against known faces
- Identity enrollment

CODEMAP:
- FaceDetector: Detects faces in frames
- FaceRecognizer: Matches faces against known identities
- IdentityStore: Stores and manages identity embeddings
- FacePipeline: Combined face detection + recognition
"""

import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass, field
import pickle
import json

import cv2
import numpy as np

from .common.logging import setup_logger
from .common.queue import ThreadSafeQueue
from .common.metrics import SystemMetrics, LatencyTracker
from .common.types import DetectedFace, BoundingBox


logger = setup_logger(__name__)


# Lazy imports for optional dependencies
def _check_mediapipe():
    """Check if MediaPipe is available."""
    try:
        import mediapipe

        return True
    except Exception:
        return False


def _check_deepface():
    """Check if DeepFace is available."""
    try:
        import deepface

        return True
    except Exception:
        return False


MEDIAPIPE_AVAILABLE = _check_mediapipe()
DEEPFACE_AVAILABLE = _check_deepface()


class IdentityStore:
    """Store for identity face embeddings."""

    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize identity store.

        Args:
            storage_dir: Directory for storing identity data
        """
        self._storage_dir = storage_dir or (
            Path.home() / ".config" / "cammy" / "identities"
        )
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._identities: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._load_all()

    def _load_all(self) -> None:
        """Load all identities from storage."""
        for identity_file in self._storage_dir.glob("*.json"):
            try:
                with open(identity_file, "r") as f:
                    data = json.load(f)
                    name = identity_file.stem
                    self._identities[name] = data
                    logger.info(f"Loaded identity: {name}")
            except Exception as e:
                logger.warning(f"Failed to load {identity_file}: {e}")

    def _load_identity(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a single identity."""
        identity_file = self._storage_dir / f"{name}.json"
        if not identity_file.exists():
            return None

        try:
            with open(identity_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load identity {name}: {e}")
            return None

    def save_identity(self, name: str, data: Dict[str, Any]) -> bool:
        """Save an identity.

        Args:
            name: Identity name
            data: Identity data with embeddings

        Returns:
            True if successful
        """
        with self._lock:
            try:
                identity_file = self._storage_dir / f"{name}.json"
                with open(identity_file, "w") as f:
                    json.dump(data, f, indent=2)
                self._identities[name] = data
                logger.info(f"Saved identity: {name}")
                return True
            except Exception as e:
                logger.error(f"Failed to save identity {name}: {e}")
                return False

    def delete_identity(self, name: str) -> bool:
        """Delete an identity.

        Args:
            name: Identity name

        Returns:
            True if successful
        """
        with self._lock:
            identity_file = self._storage_dir / f"{name}.json"
            try:
                if identity_file.exists():
                    identity_file.unlink()
                self._identities.pop(name, None)
                logger.info(f"Deleted identity: {name}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete identity {name}: {e}")
                return False

    def get_identity(self, name: str) -> Optional[Dict[str, Any]]:
        """Get an identity."""
        with self._lock:
            return self._identities.get(name)

    def get_all_identities(self) -> Dict[str, Dict[str, Any]]:
        """Get all identities."""
        with self._lock:
            return self._identities.copy()

    def list_identities(self) -> List[str]:
        """List all identity names."""
        with self._lock:
            return list(self._identities.keys())

    @property
    def storage_dir(self) -> Path:
        """Get storage directory."""
        return self._storage_dir


_FACE_MODEL_PATH = "~/.config/cammy/models/face_detector.tflite"
_FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)


class FaceDetector:
    """Face detector using MediaPipe FaceDetector (Tasks API)."""

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        model_selection: int = 0,
    ):
        self._min_detection_confidence = min_detection_confidence
        self._detector = None
        self._mp = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the detector."""
        if not MEDIAPIPE_AVAILABLE:
            logger.warning("MediaPipe not available, face detection disabled")
            return

        try:
            import os
            import mediapipe as mp
            from mediapipe.tasks import python as mp_tasks
            from mediapipe.tasks.python import vision

            model_path = os.path.expanduser(_FACE_MODEL_PATH)
            if not os.path.exists(model_path):
                logger.warning(
                    f"Face detector model not found at {model_path}. "
                    f"Download with: curl -L {_FACE_MODEL_URL} -o {model_path}"
                )
                return

            base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
            options = vision.FaceDetectorOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                min_detection_confidence=self._min_detection_confidence,
            )
            self._detector = vision.FaceDetector.create_from_options(options)
            self._mp = mp
            logger.info("Face detector initialized with MediaPipe Tasks API")
        except Exception as e:
            logger.warning(f"MediaPipe init failed: {e}")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces in a frame.

        Args:
            frame: Image frame (BGR)

        Returns:
            List of detection dicts with bounding boxes
        """
        if self._detector is None:
            return []

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=rgb_frame
        )
        result = self._detector.detect(mp_image)

        detections = []
        h, w = frame.shape[:2]
        for det in result.detections:
            box = det.bounding_box
            x = max(0, box.origin_x)
            y = max(0, box.origin_y)
            width = min(w - x, box.width)
            height = min(h - y, box.height)
            confidence = det.categories[0].score if det.categories else 0.5

            detections.append(
                {
                    "bbox": BoundingBox(x=x, y=y, width=width, height=height),
                    "confidence": confidence,
                }
            )

        return detections

    def close(self) -> None:
        """Close the detector."""
        if self._detector:
            self._detector.close()
            self._detector = None


class FaceEmbedder:
    """Face embedding extractor using DeepFace."""

    def __init__(self, model_name: str = "ArcFace", detector_backend: str = "opencv"):
        """Initialize face embedder.

        Args:
            model_name: DeepFace model name (ArcFace, Facenet, VGGFace, etc.)
            detector_backend: Detection backend
        """
        self._model_name = model_name
        self._detector_backend = detector_backend
        self._embedding_size = 512  # ArcFace outputs 512-dim
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the embedder."""
        if not DEEPFACE_AVAILABLE:
            logger.warning("DeepFace not available, embedding disabled")
            return

        try:
            # Test that we can import and initialize
            from deepface import DeepFace

            # Pre-warm the model by doing a dummy inference
            logger.info(f"Face embedder initialized with {self._model_name}")
        except Exception as e:
            logger.warning(f"DeepFace init failed: {e}")

    def extract_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """Extract embedding from a face image.

        Args:
            face_image: Cropped face image (BGR)

        Returns:
            Embedding vector or None
        """
        if not DEEPFACE_AVAILABLE:
            return None

        try:
            from deepface import DeepFace

            # Ensure image is valid
            if face_image is None or face_image.size == 0:
                return None

            # Extract embedding using DeepFace
            # Use enforce_detection=False since we already have a face crop
            result = DeepFace.represent(
                face_image,
                model_name=self._model_name,
                enforce_detection=False,
                detector_backend=self._detector_backend,
            )

            if result and len(result) > 0:
                embedding = np.array(result[0]["embedding"], dtype=np.float32)
                return embedding

            return None

        except Exception as e:
            logger.debug(f"Embedding extraction failed: {e}")
            return None

    def extract_embedding_from_frame(
        self, frame: np.ndarray, bbox: BoundingBox
    ) -> Optional[np.ndarray]:
        """Extract embedding from a face in a frame.

        Args:
            frame: Full frame (BGR)
            bbox: Bounding box of face

        Returns:
            Embedding vector or None
        """
        # Crop face from frame
        x, y, w, h = bbox.x, bbox.y, bbox.width, bbox.height

        # Add margin
        margin = int(w * 0.1)
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(frame.shape[1], x + w + margin)
        y2 = min(frame.shape[0], y + h + margin)

        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size == 0:
            return None

        return self.extract_embedding(face_crop)

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between embeddings.

        Args:
            emb1: First embedding
            emb2: Second embedding

        Returns:
            Similarity score (-1 to 1)
        """
        if emb1 is None or emb2 is None:
            return 0.0

        # Cosine similarity
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(emb1, emb2) / (norm1 * norm2))


class FaceRecognizer:
    """Face recognizer matching faces against identities."""

    def __init__(
        self,
        identity_store: Optional[IdentityStore] = None,
        threshold: float = 0.65,
        embedder: Optional[FaceEmbedder] = None,
    ):
        """Initialize face recognizer.

        Args:
            identity_store: Store for known identities
            threshold: Similarity threshold for matching
            embedder: Face embedder instance
        """
        self._identity_store = identity_store or IdentityStore()
        self._threshold = threshold
        self._embedder = embedder or FaceEmbedder()
        self._embedding_cache: Dict[str, np.ndarray] = {}

    def _get_cached_embedding(self, name: str) -> Optional[np.ndarray]:
        """Get cached embedding or load from store."""
        if name in self._embedding_cache:
            return self._embedding_cache[name]

        identity = self._identity_store.get_identity(name)
        if identity and "embedding" in identity:
            emb = np.array(identity["embedding"], dtype=np.float32)
            self._embedding_cache[name] = emb
            return emb

        return None

    def recognize(
        self,
        embedding: np.ndarray,
    ) -> Optional[Dict[str, Any]]:
        """Recognize a face from its embedding.

        Args:
            embedding: Face embedding

        Returns:
            Dict with identity and confidence, or None
        """
        if embedding is None:
            return None

        identities = self._identity_store.get_all_identities()
        best_match = None
        best_score = 0.0

        for name in identities.keys():
            stored_emb = self._get_cached_embedding(name)
            if stored_emb is None:
                continue

            score = self._embedder.compute_similarity(embedding, stored_emb)

            if score > best_score and score >= self._threshold:
                best_match = name
                best_score = score

        if best_match:
            return {"identity": best_match, "confidence": best_score}

        return None

    def enroll(
        self,
        name: str,
        embedding: np.ndarray,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Enroll a new identity.

        Args:
            name: Identity name
            embedding: Face embedding
            metadata: Additional metadata

        Returns:
            True if successful
        """
        # Clear cache for this identity
        self._embedding_cache.pop(name, None)

        data = {
            "name": name,
            "embedding": embedding.tolist(),
            "enrolled_at": time.time(),
            "metadata": metadata or {},
        }
        return self._identity_store.save_identity(name, data)

    def clear_cache(self) -> None:
        """Clear embedding cache."""
        self._embedding_cache.clear()


class FacePipeline:
    """Combined face detection and recognition pipeline."""

    def __init__(
        self,
        threshold: float = 0.65,
        max_faces: int = 5,
        identity_store: Optional[IdentityStore] = None,
        metrics: Optional[SystemMetrics] = None,
        embedder: Optional[FaceEmbedder] = None,
    ):
        """Initialize face pipeline.

        Args:
            threshold: Recognition threshold
            max_faces: Maximum faces to detect
            identity_store: Store for identities
            metrics: System metrics
            embedder: Face embedder instance
        """
        self._threshold = threshold
        self._max_faces = max_faces
        self._identity_store = identity_store or IdentityStore()
        self._metrics = metrics or SystemMetrics()

        self._detector = FaceDetector()
        self._embedder = embedder or FaceEmbedder()
        self._recognizer = FaceRecognizer(
            identity_store=self._identity_store,
            threshold=threshold,
            embedder=self._embedder,
        )

        self._running = False
        self._input_queue: Optional[ThreadSafeQueue] = None
        self._output_queue: Optional[ThreadSafeQueue] = None

        logger.info(
            f"FacePipeline initialized (threshold={threshold}, max_faces={max_faces})"
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
        logger.info("Face pipeline started")

    def stop(self) -> None:
        """Stop the pipeline."""
        self._running = False
        logger.info("Face pipeline stopped")

    def process(self, frame: np.ndarray) -> List[DetectedFace]:
        """Process a frame and detect/recognize faces.

        Args:
            frame: Image frame (BGR)

        Returns:
            List of detected faces
        """
        with LatencyTracker(self._metrics, "face_detection"):
            detections = self._detector.detect(frame)

        faces = []
        for det in detections[: self._max_faces]:
            bbox = det["bbox"]

            # Extract embedding from detected face
            with LatencyTracker(self._metrics, "face_embedding"):
                embedding = self._embedder.extract_embedding_from_frame(frame, bbox)

            # Try to recognize
            result = self._recognizer.recognize(embedding)

            if result:
                face = DetectedFace(
                    identity=result["identity"],
                    confidence=result["confidence"],
                    bbox=bbox,
                )
            else:
                face = DetectedFace(
                    identity="unknown",
                    confidence=det.get("confidence", 0),
                    bbox=bbox,
                )

            faces.append(face)

        return faces

    def get_identities(self) -> List[str]:
        """Get list of enrolled identities."""
        return self._identity_store.list_identities()

    def enroll_identity(
        self,
        name: str,
        frame: np.ndarray,
        bbox: Optional[BoundingBox] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Enroll a new identity.

        Args:
            name: Identity name
            frame: Frame with face
            bbox: Optional bounding box (if None, uses detector)
            metadata: Additional metadata

        Returns:
            True if successful
        """
        if bbox is None:
            detections = self._detector.detect(frame)
            if not detections:
                logger.warning(f"No face detected for enrollment: {name}")
                return False
            bbox = detections[0]["bbox"]

        embedding = self._embedder.extract_embedding_from_frame(frame, bbox)

        if embedding is None:
            logger.warning(f"Failed to extract embedding for: {name}")
            return False

        return self._recognizer.enroll(name, embedding, metadata)

    def remove_identity(self, name: str) -> bool:
        """Remove an identity."""
        self._recognizer.clear_cache()
        return self._identity_store.delete_identity(name)

    @property
    def identity_store(self) -> IdentityStore:
        """Get the identity store."""
        return self._identity_store

    def close(self) -> None:
        """Close the pipeline and release resources."""
        self._detector.close()
        self._recognizer.clear_cache()
        logger.info("Face pipeline closed")

    @property
    def is_running(self) -> bool:
        """Check if running."""
        return self._running


def create_face_pipeline(
    threshold: float = 0.65,
    max_faces: int = 5,
    identity_store: Optional[IdentityStore] = None,
) -> FacePipeline:
    """Factory to create face pipeline.

    Args:
        threshold: Recognition threshold
        max_faces: Maximum faces
        identity_store: Identity store

    Returns:
        FacePipeline instance
    """
    return FacePipeline(
        threshold=threshold,
        max_faces=max_faces,
        identity_store=identity_store,
    )
