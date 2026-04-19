# Action Executor Module CODEMAP

## Overview

This module handles gesture-to-action mapping and action execution (keyboard, webhook, shell).

## Directory

```
src/cammy/action_executor.py
```

## Dependencies

- `pyautogui` (optional)
- `requests` (optional)
- `subprocess` (stdlib)
- `threading` (stdlib)
- `time` (stdlib)

## Public API

### Functions

| Function | Description | Returns |
|----------|-------------|--------|
| `create_action_executor(mapping, cooldown_ms)` | Factory to create executor | `ActionExecutor` |

### Classes

| Class | Description |
|-------|-------------|
| `ActionExecutor` | Main executor with debouncing |
| `ActionMapper` | Maps gestures to actions |
| `KeyPressAction` | Execute keyboard presses |
| `WebhookAction` | Execute HTTP webhooks |
| `ShellAction` | Execute shell commands |

## Data Flow

```
[DetectedHand]
     │
     ▼ (get action config)
[ActionMapper.get_action()]
     │
     ▼ (check cooldown)
[ActionExecutor._check_cooldown()]
     │
     ▼ (execute)
[KeyPressAction / WebhookAction / ShellAction]
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

## Usage

```python
from cammy.action_executor import ActionExecutor, create_action_executor
from cammy.common import GestureType, DetectedHand

# Create executor
executor = create_action_executor()

# Execute based on detected hands
actions = executor.execute([hand])

for action in actions:
    print(f"Executed: {action.action_name}")

# Customize mapping
executor.mapper.set_mapping(GestureType.POINTING, "volume_mute")

# Configure action
config = executor.mapper._action_configs["volume_mute"]
config.cooldown_ms = 2000
```

## Internal Structure

```
ActionExecutor
├── _mapper: ActionMapper
├── _key_press: KeyPressAction
├── _webhook: WebhookAction
├── _shell: ShellAction
├── _last_action_time: Dict[action_name, timestamp]
├── _enabled: bool
└── execute(hands) → List[Action]

ActionMapper
├── _mapping: Dict[GestureType, action_name]
├── _action_configs: Dict[action_name, ActionConfig]
├── set_mapping(gesture, action_name)
└── get_action(gesture) → ActionConfig

KeyPressAction
└── execute(payload) → ActionResult

WebhookAction
└── execute(payload) → ActionResult

ShellAction
└── execute(payload) → ActionResult
```

## Error Handling

- Missing pyautogui: Skips key actions
- Missing requests: Skips webhook actions
- Shell timeout: Fails after 10s
- Action failure: Logs error, continues

## Metrics Tracked

- Action execution count
- Action failure count

## Thread Safety

- ActionExecutor uses threading.Lock for debounce tracking

## Notes for Future Agents

- To add new action types: Add to ActionType enum and add handler
- To add action sequences: Create composite actions in payload
- To add conditional actions: Add condition field to ActionConfig
- To add action logging: Extend execute() to log all actions