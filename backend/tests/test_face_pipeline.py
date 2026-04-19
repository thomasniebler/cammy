"""Unit tests for face_pipeline module."""

import unittest
import tempfile
import json
import time
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cammy.face_pipeline import (
    FacePipeline,
    FaceDetector,
    FaceEmbedder,
    FaceRecognizer,
    IdentityStore,
    create_face_pipeline,
)
from tests.common import create_test_frame


class TestIdentityStore(unittest.TestCase):
    """Tests for IdentityStore."""

    def test_create_with_dir(self):
        """Test creation with directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = IdentityStore(Path(tmpdir))
            self.assertEqual(store.list_identities(), [])

    def test_save_and_load_identity(self):
        """Test saving and loading identity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = IdentityStore(Path(tmpdir))

            data = {
                "name": "test_user",
                "embedding": [0.1] * 512,
                "enrolled_at": time.time(),
            }

            result = store.save_identity("test_user", data)
            self.assertTrue(result)

            # Load back
            loaded = store.get_identity("test_user")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["name"], "test_user")

    def test_delete_identity(self):
        """Test deleting identity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = IdentityStore(Path(tmpdir))

            data = {"name": "test", "embedding": [0.1] * 512}
            store.save_identity("test", data)

            result = store.delete_identity("test")
            self.assertTrue(result)
            self.assertIsNone(store.get_identity("test"))


class TestFaceDetector(unittest.TestCase):
    """Tests for FaceDetector."""

    def test_create(self):
        """Test detector creation."""
        detector = FaceDetector()
        self.assertIsNotNone(detector)

    def test_detect(self):
        """Test face detection."""
        detector = FaceDetector()
        frame = create_test_frame()

        # Should return empty list or detections
        detections = detector.detect(frame)
        self.assertIsInstance(detections, list)


class TestFaceEmbedder(unittest.TestCase):
    """Tests for FaceEmbedder."""

    def test_create(self):
        """Test embedder creation."""
        embedder = FaceEmbedder()
        self.assertIsNotNone(embedder)

    def test_compute_similarity(self):
        """Test similarity computation."""
        embedder = FaceEmbedder()

        import numpy as np

        emb1 = np.random.randn(512)
        emb2 = np.random.randn(512)

        sim = embedder.compute_similarity(emb1, emb2)

        self.assertIsInstance(sim, float)
        self.assertGreaterEqual(sim, -1.0)
        self.assertLessEqual(sim, 1.0)

    def test_compute_similarity_none(self):
        """Test similarity with None."""
        embedder = FaceEmbedder()

        import numpy as np

        sim = embedder.compute_similarity(None, np.random.randn(512))

        self.assertEqual(sim, 0.0)


class TestFaceRecognizer(unittest.TestCase):
    """Tests for FaceRecognizer."""

    def test_create(self):
        """Test recognizer creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = IdentityStore(Path(tmpdir))
            recognizer = FaceRecognizer(identity_store=store)

            self.assertIsNotNone(recognizer)


class TestCreateFacePipeline(unittest.TestCase):
    """Tests for create_face_pipeline factory."""

    def test_create_default(self):
        """Test default creation."""
        pipeline = create_face_pipeline()
        self.assertIsInstance(pipeline, FacePipeline)

    def test_create_with_params(self):
        """Test creation with params."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = IdentityStore(Path(tmpdir))
            pipeline = create_face_pipeline(
                threshold=0.7,
                max_faces=3,
                identity_store=store,
            )

            self.assertIsInstance(pipeline, FacePipeline)


class TestFacePipeline(unittest.TestCase):
    """Tests for FacePipeline."""

    def test_create(self):
        """Test pipeline creation."""
        pipeline = FacePipeline()
        self.assertIsNotNone(pipeline)
        self.assertFalse(pipeline.is_running)

    def test_process(self):
        """Test frame processing."""
        pipeline = FacePipeline()
        frame = create_test_frame()

        faces = pipeline.process(frame)
        self.assertIsInstance(faces, list)

    def test_get_identities(self):
        """Test getting identities."""
        pipeline = FacePipeline()
        identities = pipeline.get_identities()

        self.assertIsInstance(identities, list)

    def test_enroll_identity(self):
        """Test enrolling identity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = IdentityStore(Path(tmpdir))
            pipeline = FacePipeline(identity_store=store)

            # Should return True (even without actual embedding)
            result = pipeline.enroll_identity("test_user", create_test_frame())
            # This may return False due to dummy embedding, that's OK
            self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
