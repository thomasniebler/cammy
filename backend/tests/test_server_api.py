"""Tests for camera/identity REST endpoints and related hardening."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cammy.camera_capture import CameraCapture, CameraFrame, CameraInfo
from cammy.common.types import (
    DetectedHand,
    GestureType,
    HandType,
    is_valid_identity_name,
)
from cammy.face_pipeline import IdentityStore
from cammy.hand_pipeline import HandPipeline

try:
    from fastapi.testclient import TestClient

    from cammy.server import RestAPI

    HAVE_CLIENT = True
except Exception:  # pragma: no cover
    HAVE_CLIENT = False


class FakeCamera:
    def __init__(self, ok=True):
        self.device_index = 0
        self.ok = ok

    def get_available_cameras(self):
        return [CameraInfo(0, "Cam A", True), CameraInfo(2, "Cam B", True)]

    def set_device(self, index):
        if self.ok:
            self.device_index = index
        return self.ok

    def get_latest_frame(self):
        import numpy as np

        return CameraFrame(frame=np.zeros((4, 4, 3), dtype="uint8"), timestamp=1.0, width=4, height=4)


class FakeFacePipeline:
    def __init__(self, ok=True):
        self.ok = ok
        self.enrolled = []

    def enroll_identity(self, name, frame, bbox=None, metadata=None):
        if self.ok:
            self.enrolled.append(name)
        return self.ok

    def remove_identity(self, name):
        return True


class TestIdentityNames(unittest.TestCase):
    def test_valid_and_invalid(self):
        for ok in ["Alice", "bob smith", "a.b-c_1"]:
            self.assertTrue(is_valid_identity_name(ok), ok)
        for bad in ["", "../config", "/etc/x", "a/b", ".hidden", "a..b", "x" * 65]:
            self.assertFalse(is_valid_identity_name(bad), bad)

    def test_store_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            store = IdentityStore(Path(d) / "ids")
            self.assertFalse(store.save_identity("../evil", {"x": 1}))
            self.assertFalse((Path(d) / "evil.json").exists())
            self.assertTrue(store.save_identity("ok", {"x": 1}))


class TestSetDevice(unittest.TestCase):
    def _capture(self, opens):
        cap = CameraCapture()
        state = {"idx": None}

        class Reader:
            def __init__(self, device_index, **kw):
                state["idx"] = device_index
                self.i = device_index

            def start(self):
                pass

            def stop(self):
                pass

            def join(self, timeout=None):
                pass

            def is_running(self):
                return self.i in opens

        import cammy.camera_capture as cc

        self._orig = cc.CameraReader
        cc.CameraReader = Reader
        self.addCleanup(setattr, cc, "CameraReader", self._orig)
        return cap, state

    def test_switch_success(self):
        cap, state = self._capture(opens={0, 2})
        self.assertTrue(cap.set_device(2))
        self.assertEqual(cap.device_index, 2)

    def test_switch_failure_reverts(self):
        cap, state = self._capture(opens={0})
        import cammy.camera_capture as cc

        orig_time = cc.time.time
        t = [0.0]
        cc.time.time = lambda: (t.__setitem__(0, t[0] + 1.5) or t[0])
        self.addCleanup(setattr, cc.time, "time", orig_time)
        self.assertFalse(cap.set_device(3))
        self.assertEqual(cap.device_index, 0)
        self.assertEqual(state["idx"], 0)


class TestMouseGestureThreshold(unittest.TestCase):
    def _pipeline(self, gesture, conf):
        from cammy.common.metrics import SystemMetrics

        class Det:
            def detect(self, frame):
                return [{"landmarks": [[0.5, 0.5, 0.0]] * 21, "hand_type": HandType.RIGHT, "confidence": 1.0}]

        class Cls:
            def classify(self, lm, ht):
                return gesture, conf

        p = HandPipeline.__new__(HandPipeline)
        p._detector, p._classifier = Det(), Cls()
        p._max_hands, p._min_confidence = 2, 0.80  # the default config value
        p._metrics = SystemMetrics()
        return p

    def test_mouse_gestures_pass_default_threshold(self):
        self.assertEqual(len(self._pipeline(GestureType.POINTING, 0.75).process(None)), 1)
        self.assertEqual(len(self._pipeline(GestureType.OK_SIGN, 0.70).process(None)), 1)

    def test_other_gestures_still_filtered(self):
        self.assertEqual(len(self._pipeline(GestureType.PEACE, 0.75).process(None)), 0)


@unittest.skipUnless(HAVE_CLIENT, "fastapi test client not available")
class TestRestEndpoints(unittest.TestCase):
    def _client(self, camera=None, face=None):
        api = RestAPI()
        api.set_dependencies(camera=camera or FakeCamera(), face_pipeline=face or FakeFacePipeline())
        return TestClient(api.create_app())

    def test_list_cameras(self):
        r = self._client().get("/api/cameras")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["current"], 0)
        self.assertEqual([c["index"] for c in r.json()["cameras"]], [0, 2])

    def test_select_camera_ok_and_fail(self):
        self.assertEqual(self._client().post("/api/camera", json={"device_index": 2}).status_code, 200)
        r = self._client(camera=FakeCamera(ok=False)).post("/api/camera", json={"device_index": 9})
        self.assertEqual(r.status_code, 422)

    def test_enroll(self):
        face = FakeFacePipeline()
        c = self._client(face=face)
        self.assertEqual(c.post("/api/identities", json={"name": "Alice"}).status_code, 200)
        self.assertEqual(face.enrolled, ["Alice"])
        self.assertEqual(c.post("/api/identities", json={"name": "../config"}).status_code, 400)
        c2 = self._client(face=FakeFacePipeline(ok=False))
        self.assertEqual(c2.post("/api/identities", json={"name": "Bob"}).status_code, 422)
