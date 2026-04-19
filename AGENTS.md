# Agent Instructions for Cammy

This file provides instructions and context for any agents working on this project.

## Project Overview

Cammy is a real-time face detection/recognition and hand gesture recognition system with a React frontend for configuration.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Frontend (React/WebSocket)           │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│              Backend (Python)                    │
├─────────────────────────────────────────────────┤
│  camera_capture.py  │ Frames from webcam         │
│  face_pipeline.py  │ Face detection/recognition│
│  hand_pipeline.py │ Hand gesture detection      │
│  action_executor.py│ Execute actions            │
│  server.py         │ WebSocket + REST server    │
│  common/          │ Shared utilities          │
└─────────────────────────────────────────────────┘
```

## Module Structure

### Main Modules

| Module | File | Purpose |
|--------|------|---------|
| Camera | `camera_capture.py` | Video frame capture |
| Face | `face_pipeline.py` | Face detection + recognition |
| Hand | `hand_pipeline.py` | Hand gesture detection |
| Action | `action_executor.py` | Execute actions from gestures |
| Server | `server.py` | WebSocket + REST API |

### Common Modules (in `common/`)

| Module | Purpose |
|--------|---------|
| `logging.py` | Logging setup |
| `queue.py` | Thread-safe queues |
| `metrics.py` | Performance metrics |
| `config.py` | Configuration management |
| `types.py` | Shared types and enums |

## CODEMAP Files

Each module has a corresponding `CODEMAP.md` file that describes its layout:
- `camera_capture_CODEMAP.md`
- `face_pipeline_CODEMAP.md`
- `hand_pipeline_CODEMAP.md`
- `action_executor_CODEMAP.md`
- `server_CODEMAP.md`

**When modifying module structure, UPDATE the corresponding CODEMAP file.**

## Testing

Tests are in `backend/tests/`:
- `test_common.py` - Common module tests
- `test_camera_capture.py` - Camera tests
- `test_face_pipeline.py` - Face pipeline tests
- `test_hand_pipeline.py` - Hand pipeline tests
- `test_action_executor.py` - Action executor tests
- `common.py` - Test utilities

**Run tests with:**
```bash
cd backend
python -m pytest tests/
```

## Key Types

Defined in `common/types.py`:

```python
# Enums
GestureType: FIST, OPEN_PALM, THUMBS_UP, THUMBS_DOWN, PEACE, POINTING, OK_SIGN
ActionType: MEDIA_PLAY, MEDIA_PAUSE, MEDIA_NEXT, VOLUME_UP, ...

# Data classes
DetectedFace: identity, confidence, bbox
DetectedHand: gesture, gesture_confidence, hand_type
Action: action_type, action_name, payload
```

## Configuration

Config is stored in `~/.config/cammy/config.json`:
- `performance`: tier, target_fps, frame_skip
- `detection`: thresholds, max_faces, max_hands
- `action`: cooldown, enabled
- `server`: host, port
- `camera`: device_index, resolution, fps

## Adding New Features

### 1. Adding a New Gesture

1. Add to `GestureType` enum in `common/types.py`
2. Update `GestureClassifier` in `hand_pipeline.py`
3. Add mapping in `ActionMapper` in `action_executor.py`
4. Add tests in `test_hand_pipeline.py`

### 2. Adding a New Action Type

1. Add to `ActionType` enum in `common/types.py`
2. Add handler in `action_executor.py` (e.g., KeyPressAction)
3. Update tests

### 3. Adding a New Pipeline Stage

1. Create module in `src/cammy/`
2. Create corresponding CODEMAP.md
3. Add to pipeline in `main.py`
4. Add tests

### 4. Modifying the Pipeline

1. When adding data classes: Add to `common/types.py`
2. When adding queue: Use `common/PipelineQueue`
3. When adding metrics: Use `common/SystemMetrics`
4. When adding config: Use `common/ConfigManager`

## Common Patterns

### Using queues for threading:
```python
from cammy.common import ThreadSafeQueue, PipelineQueue

# Method 1: Individual queues
queue = ThreadSafeQueue(maxsize=2, name="frames")

# Method 2: Pipeline queues
pq = PipelineQueue(frame_maxsize=2)
pq.frames.put(frame)
```

### Using metrics:
```python
from cammy.common import SystemMetrics, LatencyTracker

metrics = SystemMetrics()
with LatencyTracker(metrics, "pipeline_name"):
    # do work
    pass
```

### Using config:
```python
from cammy.common import get_config_manager

config = get_config_manager().get()
settings = config.detection  # DetectionConfig
```

## Running the System

```bash
cd backend
python -m cammy.main
```

## Dependencies

Core:
- `numpy`
- `opencv-python`

Optional:
- `mediapipe` (face/hand detection)
- `deepface` (face recognition)
- `pyautogui` (keyboard control)
- `requests` (webhooks)
- `websockets` (WebSocket server)
- `fastapi` (REST API)

## Notes for Future Agents

- Always update CODEMAP when changing module layout
- Keep modules isolated - import from common, not from other modules
- Use types from common/types.py for data classes
- Add unit tests for any new function
- Follow existing naming conventions
- Keep dependencies optional where possible