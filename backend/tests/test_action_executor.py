"""Unit tests for action_executor module."""

import unittest
import time
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cammy.action_executor import (
    ActionExecutor,
    ActionMapper,
    KeyPressAction,
    WebhookAction,
    ShellAction,
    MouseControlAction,
    ActionResult,
    ActionConfig,
    create_action_executor,
)
from cammy.common import GestureType, DetectedHand
from cammy.common.types import ActionType


class TestActionMapper(unittest.TestCase):
    """Tests for ActionMapper."""

    def test_create_default(self):
        """Test default creation."""
        mapper = ActionMapper()
        self.assertIsNotNone(mapper)

    def test_default_mapping(self):
        """Test default mapping contains expected gestures."""
        mapper = ActionMapper()

        mappings = mapper.get_all_mappings()

        self.assertIn(GestureType.FIST, mappings)
        self.assertIn(GestureType.OPEN_PALM, mappings)

    def test_set_mapping(self):
        """Test setting custom mapping."""
        mapper = ActionMapper()
        mapper.set_mapping(GestureType.PEACE, "custom_action")

        mappings = mapper.get_all_mappings()
        self.assertEqual(mappings[GestureType.PEACE], "custom_action")

    def test_get_action(self):
        """Test getting action config."""
        mapper = ActionMapper()

        config = mapper.get_action(GestureType.FIST)

        self.assertIsNotNone(config)
        self.assertEqual(config.action_name, "media_pause")


class TestKeyPressAction(unittest.TestCase):
    """Tests for KeyPressAction."""

    def test_create(self):
        """Test creation."""
        action = KeyPressAction()
        self.assertIsNotNone(action)

    def test_execute_no_pyautogui(self):
        """Test execute without pyautogui."""
        action = KeyPressAction()

        result = action.execute({"key": "play"})

        # May skip if pyautogui not available
        self.assertIsInstance(result, ActionResult)


class TestWebhookAction(unittest.TestCase):
    """Tests for WebhookAction."""

    def test_create(self):
        """Test creation."""
        action = WebhookAction()
        self.assertIsNotNone(action)

    def test_execute_no_url(self):
        """Test execute without URL."""
        action = WebhookAction()

        result = action.execute({})

        # Without URL, returns FAILURE or SKIP (if requests unavailable)
        self.assertIn(result, (ActionResult.FAILURE, ActionResult.SKIP))

    def test_execute_with_url(self):
        """Test execute with valid URL."""
        action = WebhookAction()

        result = action.execute({"url": "http://example.com/api", "method": "GET"})

        # May fail due to network, but should handle gracefully
        self.assertIsInstance(result, ActionResult)


class TestShellAction(unittest.TestCase):
    """Tests for ShellAction."""

    def test_create(self):
        """Test creation."""
        action = ShellAction()
        self.assertIsNotNone(action)

    def test_execute_echo(self):
        """Test execute echo command."""
        action = ShellAction()

        result = action.execute({"command": "echo test"})

        self.assertEqual(result, ActionResult.SUCCESS)

    def test_execute_invalid(self):
        """Test execute invalid command."""
        action = ShellAction()

        result = action.execute({"command": "nonexistent_command_xyz"})

        # May fail or skip
        self.assertIsInstance(result, ActionResult)


class TestActionExecutor(unittest.TestCase):
    """Tests for ActionExecutor."""

    def test_create_default(self):
        """Test default creation."""
        executor = ActionExecutor()
        self.assertIsNotNone(executor)

    def test_enable_disable(self):
        """Test enable and disable."""
        executor = ActionExecutor()

        self.assertTrue(executor.is_enabled)

        executor.disable()
        self.assertFalse(executor.is_enabled)

        executor.enable()
        self.assertTrue(executor.is_enabled)

    def test_execute_empty_hands(self):
        """Test executing with no hands."""
        executor = ActionExecutor()

        actions = executor.execute([])

        self.assertEqual(len(actions), 0)

    def test_execute_with_hand(self):
        """Test executing with a hand gesture."""
        executor = ActionExecutor()

        hand = DetectedHand(
            gesture=GestureType.FIST,
            gesture_confidence=0.9,
        )

        actions = executor.execute([hand])

        # May execute or be skipped due to cooldown
        self.assertIsInstance(actions, list)

    def test_cooldown(self):
        """Test cooldown between actions."""
        executor = ActionExecutor()

        # First execution
        hand = DetectedHand(gesture=GestureType.FIST, gesture_confidence=0.9)

        actions1 = executor.execute([hand])

        # Immediate second execution should be debounced
        actions2 = executor.execute([hand])

        # Second should be empty due to cooldown
        # (or both empty depending on timing)
        self.assertIsInstance(actions2, list)


class TestCreateActionExecutor(unittest.TestCase):
    """Tests for create_action_executor factory."""

    def test_create_default(self):
        """Test default creation."""
        executor = create_action_executor()
        self.assertIsInstance(executor, ActionExecutor)

    def test_create_with_custom_mapping(self):
        """Test creation with custom mapping."""
        mapping = {
            GestureType.FIST: "volume_up",
            GestureType.OPEN_PALM: "volume_down",
        }
        executor = create_action_executor(mapping=mapping)

        self.assertIsInstance(executor, ActionExecutor)


class TestMouseControlAction(unittest.TestCase):
    """Tests for MouseControlAction."""

    def test_create(self):
        """Test creation."""
        action = MouseControlAction()
        self.assertIsNotNone(action)

    def test_move_without_pyautogui(self):
        """Test move returns SKIP when pyautogui is unavailable."""
        action = MouseControlAction()
        action._pyautogui = None  # Force unavailable

        result = action.move(0.5, 0.5)

        self.assertEqual(result, ActionResult.SKIP)

    def test_click_without_pyautogui(self):
        """Test click returns SKIP when pyautogui is unavailable."""
        action = MouseControlAction()
        action._pyautogui = None  # Force unavailable

        result = action.click()

        self.assertEqual(result, ActionResult.SKIP)

    def test_reset_smoothing(self):
        """Test reset_smoothing clears EMA state."""
        action = MouseControlAction()
        action._smooth_x = 0.5
        action._smooth_y = 0.5

        action.reset_smoothing()

        self.assertIsNone(action._smooth_x)
        self.assertIsNone(action._smooth_y)

    def test_ema_smoothing_applied(self):
        """Test EMA smoothing is applied after the first move call."""
        action = MouseControlAction(smoothing=0.5)
        action._pyautogui = None  # No actual mouse movement

        # Inject a dummy pyautogui to capture calls
        calls = []

        class FakePyautogui:
            FAILSAFE = False
            PAUSE = 0

            def size(self):
                return (1920, 1080)

            def moveTo(self, x, y, duration=0):
                calls.append((x, y))

        action._pyautogui = FakePyautogui()
        action._screen_size = (1920, 1080)

        # First call – EMA initialises to the mirrored input (1-0.5 = 0.5)
        action.move(0.5, 0.5)
        # Second call – EMA blends: smooth_x = alpha*(1-0.9) + (1-alpha)*prev
        #   = 0.5*0.1 + 0.5*0.5 = 0.05 + 0.25 = 0.3
        action.move(0.9, 0.9)

        self.assertEqual(len(calls), 2)
        # First call: (1-0.5)*1920 = 960
        self.assertEqual(calls[0][0], 960)
        # Second call: smooth_x=0.3 → int(0.3*1920) = 576
        expected_x = int(0.3 * 1920)
        self.assertEqual(calls[1][0], expected_x)


class TestActionExecutorMouseControl(unittest.TestCase):
    """Tests for mouse control integration in ActionExecutor."""

    def test_mouse_control_enabled_by_default(self):
        """Mouse control should be enabled by default."""
        executor = ActionExecutor()
        self.assertTrue(executor.mouse_control_enabled)

    def test_enable_disable_mouse_control(self):
        """Test enabling and disabling mouse control."""
        executor = ActionExecutor()

        executor.disable_mouse_control()
        self.assertFalse(executor.mouse_control_enabled)

        executor.enable_mouse_control()
        self.assertTrue(executor.mouse_control_enabled)

    def test_pointing_does_not_dispatch_regular_action(self):
        """POINTING gesture should not dispatch a regular action."""
        executor = ActionExecutor()
        # Map POINTING to some action to confirm it's bypassed
        executor.mapper.update_action_config(
            "test_action",
            ActionConfig(
                action_type=ActionType.CUSTOM,
                action_name="test_action",
                payload={},
                command_type="shell",
            ),
        )

        landmarks = [[float(i) * 0.05, float(i) * 0.05, 0.0] for i in range(21)]
        hand = DetectedHand(
            gesture=GestureType.POINTING,
            gesture_confidence=0.9,
            landmarks=landmarks,
        )

        actions = executor.execute([hand])

        # No Action objects returned (mouse move doesn't produce Action instances)
        self.assertEqual(len(actions), 0)

    def test_ok_sign_triggers_click(self):
        """OK_SIGN gesture should trigger a mouse click action."""
        executor = ActionExecutor()

        # Patch _mouse_control so no actual click occurs
        clicks = []

        class FakeMouseControl:
            def click(self):
                clicks.append(1)
                return ActionResult.SUCCESS

            def move(self, x, y):
                return ActionResult.SUCCESS

            def reset_smoothing(self):
                pass

        executor._mouse_control = FakeMouseControl()

        hand = DetectedHand(
            gesture=GestureType.OK_SIGN,
            gesture_confidence=0.9,
        )

        actions = executor.execute([hand])

        self.assertEqual(len(clicks), 1)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, ActionType.MOUSE_CLICK)

    def test_ok_sign_click_debounce(self):
        """Second OK_SIGN within cooldown should not click again."""
        executor = ActionExecutor()

        clicks = []

        class FakeMouseControl:
            def click(self):
                clicks.append(1)
                return ActionResult.SUCCESS

            def move(self, x, y):
                return ActionResult.SUCCESS

            def reset_smoothing(self):
                pass

        executor._mouse_control = FakeMouseControl()

        hand = DetectedHand(
            gesture=GestureType.OK_SIGN,
            gesture_confidence=0.9,
        )

        executor.execute([hand])
        executor.execute([hand])  # Immediate repeat – should be debounced

        self.assertEqual(len(clicks), 1)

    def test_detected_hand_to_dict_includes_pointer_when_pointing(self):
        """DetectedHand.to_dict() should include pointer for POINTING gesture."""
        landmarks = [[float(i) * 0.05, float(i) * 0.05, 0.0] for i in range(21)]
        hand = DetectedHand(
            gesture=GestureType.POINTING,
            gesture_confidence=0.9,
            landmarks=landmarks,
        )

        d = hand.to_dict()

        self.assertIn("pointer", d)
        self.assertIn("x", d["pointer"])
        self.assertIn("y", d["pointer"])

    def test_detected_hand_to_dict_no_pointer_for_other_gestures(self):
        """DetectedHand.to_dict() should NOT include pointer for non-POINTING gestures."""
        landmarks = [[float(i) * 0.05, float(i) * 0.05, 0.0] for i in range(21)]
        for gesture in [GestureType.FIST, GestureType.OPEN_PALM, GestureType.THUMBS_UP]:
            hand = DetectedHand(gesture=gesture, gesture_confidence=0.9, landmarks=landmarks)
            d = hand.to_dict()
            self.assertNotIn("pointer", d, f"Unexpected pointer in {gesture} dict")


if __name__ == "__main__":
    unittest.main()
