# Action Executor Module CODEMAP

## Overview

This module handles gesture-to-action mapping and action execution (keyboard, webhook, shell, mouse control).

## Directory

```
src/cammy/action_executor.py
```

## Dependencies

- `pyautogui` (optional) — keyboard presses and mouse control
- `requests` (optional)
- `subprocess` (stdlib)
- `threading` (stdlib)
- `time` (stdlib)

## Public API

### Functions

| Function | Description | Returns |
|----------|-------------|--------|
| `create_action_executor(mapping, cooldown_ms, commands_manager, mouse_control_enabled)` | Factory to create executor | `ActionExecutor` |

### Classes

| Class | Description |
|-------|-------------|
| `ActionExecutor` | Main executor with debouncing and mouse control |
| `ActionMapper` | Maps gestures to actions |
| `KeyPressAction` | Execute keyboard presses |
| `WebhookAction` | Execute HTTP webhooks |
| `ShellAction` | Execute shell commands |
| `MouseControlAction` | Move cursor and click via finger pointer tracking |

## Data Flow

```
[DetectedHand]
     │
     ├─ POINTING gesture → MouseControlAction.move(landmark[8].x, .y)
     │
     ├─ OK_SIGN gesture  → MouseControlAction.click()  (debounced 800ms)
     │
     └─ other gestures ──▶ ActionMapper.get_action()
                               │
                               ▼ (check cooldown)
                          ActionExecutor._check_cooldown()
                               │
                               ▼ (execute)
                          KeyPressAction / WebhookAction / ShellAction
                               │
                               ▼
                          [Action executed]
```

## Default Gesture Mappings

| Gesture | Action | Default Cooldown |
|---------|--------|------------------|
| FIST | media_pause | 1000ms |
| OPEN_PALM | media_play | 1000ms |
| THUMBS_UP | volume_up | 1000ms |
| THUMBS_DOWN | volume_down | 1000ms |
| PEACE | media_next | 1000ms |
| POINTING | *mouse move* (built-in) | continuous |
| OK_SIGN | *mouse click* (built-in) | 800ms |

## Mouse Control

`MouseControlAction` uses an **Exponential Moving Average (EMA)** filter to smooth the raw
MediaPipe landmark positions before mapping them to screen coordinates.

- **X axis is mirrored** (`screen_x = (1 − norm_x) × screen_width`) to match the typical
  mirrored/selfie camera preview shown in the UI.
- EMA `alpha` defaults to `0.2` (more smoothing = lower alpha).
- `reset_smoothing()` is called automatically when no POINTING hand is detected, so the
  next pointing frame starts from the raw position without accumulated lag.

Mouse control can be toggled:
```python
executor.enable_mouse_control()
executor.disable_mouse_control()
executor.mouse_control_enabled  # bool property
```

## Usage

```python
from cammy.action_executor import ActionExecutor, create_action_executor
from cammy.common import GestureType, DetectedHand

# Create executor (mouse control on by default)
executor = create_action_executor()

# Execute based on detected hands
actions = executor.execute([hand])

for action in actions:
    print(f"Executed: {action.action_name}")

# Disable mouse control if needed
executor.disable_mouse_control()

# Customize mapping
executor.mapper.set_mapping(GestureType.THUMBS_UP, "volume_up")
```

## Internal Structure

```
ActionExecutor
├── _mapper: ActionMapper
├── _key_press: KeyPressAction
├── _webhook: WebhookAction
├── _shell: ShellAction
├── _mouse_control: MouseControlAction
├── _mouse_enabled: bool
├── _last_action_time: Dict[action_name, timestamp]
├── _enabled: bool
└── execute(hands) → List[Action]

ActionMapper
├── _mapping: Dict[GestureType, action_name]
├── _action_configs: Dict[action_name, ActionConfig]
├── set_mapping(gesture, action_name)
└── get_action(gesture) → ActionConfig

MouseControlAction
├── _smoothing: float        # EMA alpha
├── _smooth_x/y: float|None  # running average
├── move(norm_x, norm_y) → ActionResult
├── click() → ActionResult
└── reset_smoothing()

KeyPressAction
└── execute(payload) → ActionResult

WebhookAction
└── execute(payload) → ActionResult

ShellAction
└── execute(payload) → ActionResult
```

## Error Handling

- Missing pyautogui: Skips key and mouse actions (returns SKIP)
- Missing requests: Skips webhook actions
- Shell timeout: Fails after 10s
- Action failure: Logs error, continues

## Thread Safety

- ActionExecutor uses threading.Lock for debounce tracking

## Notes for Future Agents

- POINTING and OK_SIGN gestures are reserved for mouse control; custom mappings for
  these gestures are silently bypassed when mouse control is enabled.
- To add new action types: Add to ActionType enum and add handler
- To add action sequences: Create composite actions in payload
- To add conditional actions: Add condition field to ActionConfig