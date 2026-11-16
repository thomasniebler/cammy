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


class TestReaderCancelDuringOpen(unittest.TestCase):
    def test_stop_during_slow_open_prevents_capture(self):
        import threading

        import cammy.camera_capture as cc

        open_started = threading.Event()
        allow_open = threading.Event()
        reads = []
        released = []

        class SlowCap:
            def __init__(self, idx):
                open_started.set()
                allow_open.wait(5)  # simulate a camera that takes long to open

            def isOpened(self):
                return True

            def set(self, *a):
                pass

            def read(self):
                reads.append(1)
                return False, None

            def release(self):
                released.append(1)

        orig = cc.cv2.VideoCapture
        cc.cv2.VideoCapture = SlowCap
        self.addCleanup(setattr, cc.cv2, "VideoCapture", orig)

        reader = cc.CameraReader(device_index=7, target_fps=30)
        reader.start()
        self.assertTrue(open_started.wait(2))
        reader.stop()          # rollback gives up while the open is still pending
        allow_open.set()       # ...then the open finally completes
        reader.join(timeout=3)

        self.assertFalse(reader.is_alive(), "reader thread must exit")
        self.assertFalse(reader.is_running())
        self.assertEqual(reads, [], "cancelled reader must not capture")
        self.assertEqual(released, [1], "device must be released")


class TestSetDeviceConcurrency(unittest.TestCase):
    def test_overlapping_switches_leave_exactly_one_reader(self):
        import threading
        import time as _time

        import cammy.camera_capture as cc

        live = set()
        created = []

        class Reader:
            def __init__(self, device_index, **kw):
                self.i = device_index
                created.append(self)

            def start(self):
                live.add(self)

            def stop(self):
                live.discard(self)

            def join(self, timeout=None):
                _time.sleep(0.05)  # widen the race window

            def is_running(self):
                return self in live

        orig = cc.CameraReader
        cc.CameraReader = Reader
        self.addCleanup(setattr, cc, "CameraReader", orig)

        cap = CameraCapture()
        cap.start()
        results = []
        threads = [
            threading.Thread(target=lambda i=i: results.append(cap.set_device(i))) for i in (1, 2, 3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results, [True, True, True])
        self.assertEqual(len(live), 1, "orphaned reader left running")
        self.assertEqual(next(iter(live)).i, cap.device_index)


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
