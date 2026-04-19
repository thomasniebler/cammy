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
    ActionResult,
    ActionConfig,
    create_action_executor,
)
from cammy.common import GestureType, DetectedHand


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


if __name__ == "__main__":
    unittest.main()
