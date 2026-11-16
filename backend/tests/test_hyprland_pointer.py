"""Tests for the real HyprlandPointer class (all system access mocked)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cammy.action_executor as ae
from cammy.action_executor import ActionResult, HyprlandPointer, MouseControlAction

REAL_HYPRLAND = HyprlandPointer  # bound at import, before other modules stub it

MONITORS = [
    {"name": "eDP-1", "x": 0, "y": 0, "width": 1920, "height": 1200, "scale": 1.0, "focused": False},
    {"name": "DP-3", "x": 1920, "y": 0, "width": 3440, "height": 1440, "scale": 2.0, "focused": True},
]
ENV = {
    "HYPRLAND_INSTANCE_SIGNATURE": "sig",
    "XDG_RUNTIME_DIR": "/run/user/1",
    "YDOTOOL_SOCKET": "/run/user/1/.ydotool_socket",
}


def _run_ok(monitors=MONITORS):
    def fake_run(cmd, **kw):
        if cmd[0] == "hyprctl":
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(monitors), stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    return fake_run


def make(env=ENV, exists=lambda p: True, which="/usr/bin/ydotool", run=None, extra_env=None):
    environ = dict(env)
    environ.update(extra_env or {})
    with mock.patch.dict("os.environ", environ, clear=True), \
         mock.patch("os.path.exists", side_effect=exists), \
         mock.patch("shutil.which", return_value=which), \
         mock.patch("subprocess.run", side_effect=run or _run_ok()):
        return REAL_HYPRLAND()


class TestAvailability(unittest.TestCase):
    def test_unavailable_without_signature(self):
        self.assertFalse(make(env={"XDG_RUNTIME_DIR": "/run/user/1"}).available)

    def test_unavailable_without_socket_file(self):
        self.assertFalse(make(exists=lambda p: False).available)

    def test_unavailable_when_monitor_lookup_fails(self):
        def boom(cmd, **kw):
            raise subprocess.CalledProcessError(1, cmd)

        self.assertFalse(make(run=boom).available)

    def test_available_and_click_disabled_without_ydotool(self):
        p = make(which=None)
        self.assertTrue(p.available)
        self.assertFalse(p.click())

    def test_click_disabled_without_ydotool_socket(self):
        p = make(exists=lambda path: "ydotool" not in path)
        self.assertTrue(p.available)
        self.assertFalse(p.click())


class TestMonitorSelection(unittest.TestCase):
    def test_focused_monitor_with_scale(self):
        p = make()
        self.assertEqual(p.monitor, "DP-3")
        self.assertEqual(p.origin, (1920, 0))
        self.assertEqual(p.size, (1720, 720))  # 3440x1440 at scale 2

    def test_env_override(self):
        p = make(extra_env={"CAMMY_MONITOR": "eDP-1"})
        self.assertEqual(p.monitor, "eDP-1")
        self.assertEqual(p.size, (1920, 1200))

    def test_unknown_override_falls_back_to_focused(self):
        self.assertEqual(make(extra_env={"CAMMY_MONITOR": "nope"}).monitor, "DP-3")

    def test_no_focused_monitor_uses_first(self):
        unfocused = [dict(m, focused=False) for m in MONITORS]
        self.assertEqual(make(run=_run_ok(unfocused)).monitor, "eDP-1")


class TestMoveAndClick(unittest.TestCase):
    def test_move_to_offsets_by_origin_and_sends_command(self):
        p = make()
        sock = mock.MagicMock()
        sock.__enter__.return_value = sock
        sock.recv.return_value = b"ok"
        with mock.patch("socket.socket", return_value=sock):
            self.assertTrue(p.move_to(100, 50))
        sock.connect.assert_called_once_with("/run/user/1/hypr/sig/.socket.sock")
        sock.sendall.assert_called_once_with(b"dispatch movecursor 2020 50")

    def test_move_to_reports_error_reply(self):
        p = make()
        sock = mock.MagicMock()
        sock.__enter__.return_value = sock
        sock.recv.return_value = b"unknown request"
        with mock.patch("socket.socket", return_value=sock):
            self.assertFalse(p.move_to(1, 1))

    def test_click_runs_ydotool_with_socket_env(self):
        p = make()
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(p.click())
        args, kw = run.call_args
        self.assertEqual(args[0], ["/usr/bin/ydotool", "click", "0xC0"])
        self.assertEqual(kw["env"]["YDOTOOL_SOCKET"], "/run/user/1/.ydotool_socket")

    def test_click_failure(self):
        p = make()
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertFalse(p.click())


class TestBackendPrecedence(unittest.TestCase):
    def test_hyprland_preferred_over_importable_pyautogui(self):
        class Avail:
            available = True
            size = (10, 10)

        with mock.patch.object(ae, "HyprlandPointer", Avail), \
             mock.patch.object(ae, "PYAUTOGUI_AVAILABLE", True):
            action = MouseControlAction()
        self.assertIsInstance(action._hypr, Avail)
        self.assertIsNone(action._pyautogui)

    def test_falls_back_to_pyautogui_when_hyprland_unavailable(self):
        class Unavail:
            available = False

        fake = mock.MagicMock()
        with mock.patch.object(ae, "HyprlandPointer", Unavail), \
             mock.patch.object(ae, "PYAUTOGUI_AVAILABLE", True), \
             mock.patch.dict(sys.modules, {"pyautogui": fake}):
            action = MouseControlAction()
        self.assertIsNone(action._hypr)
        self.assertIs(action._pyautogui, fake)
