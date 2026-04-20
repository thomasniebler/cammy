# Copilot Instructions for Cammy

Cammy is a real-time face detection/recognition and hand gesture recognition system. The Python backend runs a multi-threaded pipeline; the React frontend connects via WebSocket (live detections) and REST (configuration).

## Commands

### Backend
```bash
# Install (uses uv, not pip directly)
cd backend && uv pip install -e ".[dev]"

# Run
cd backend && python -m cammy.main
# or: cammy (after install)

# Test all
cd backend && python -m pytest tests/ -v

# Test single file
cd backend && python -m pytest tests/test_face_pipeline.py -v

# Test single test
cd backend && python -m pytest tests/test_face_pipeline.py::TestFacePipeline::test_process_empty -v

# Lint
cd backend && ruff check src/
```

### Frontend
```bash
cd frontend && npm install
cd frontend && npm run dev       # dev server at http://localhost:5173
cd frontend && npm run build     # tsc + vite build
```

### Task runner
`task` (Taskfile.yml) wraps the above: `task test`, `task lint`, `task dev-backend`, `task dev-frontend`.

## Architecture

### Pipeline threading model
`CammyApp` in `main.py` spawns two daemon threads — `FaceProcessor` and `HandProcessor` — that each pull frames from `CameraCapture` independently. There is no shared frame queue between the two pipelines; each calls `camera.get_frame()` separately.

```
CameraCapture (CameraReader thread → ThreadSafeQueue)
      │
      ├──→ FaceProcessor thread → FacePipeline → server.broadcast_faces()
      │
      └──→ HandProcessor thread → HandPipeline → ActionExecutor → server.broadcast_gestures()
```

### Dual server
`CammyServer` runs two servers simultaneously:
- **WebSocket** on port `8765` — streams detection results to the frontend in real time
- **REST (FastAPI/uvicorn)** on port `8000` — configuration endpoints (`/api/identities`, `/api/gestures/mapping`, `/api/action/enable|disable`)

The Vite dev server proxies `/api` → `http://localhost:8000` and `/ws` → `ws://localhost:8765`.

### Optional dependencies
All heavy dependencies are optional. Each module guards its import with a `_check_*()` function and a module-level `*_AVAILABLE` boolean. Code must degrade gracefully when they are absent.

```python
PYAUTOGUI_AVAILABLE = _check_pyautogui()
WEBSOCKETS_AVAILABLE = _check_websockets()
# etc.
```

Install extras selectively: `uv pip install -e ".[face,hand,action,server]"`

## Key conventions

### CODEMAP files
Every pipeline module has a `*_CODEMAP.md` sibling file documenting its public API, class hierarchy, and data flow. **Update the corresponding CODEMAP when changing module structure.**

### Module isolation
Modules import only from `cammy.common`, never from sibling modules. Cross-module data flows exclusively through the types in `common/types.py`.

### Shared types in `common/types.py`
All pipeline data classes live here: `CameraFrame`, `DetectedFace`, `DetectedHand`, `Action`, `PipelineResult`. Each implements `to_dict()` for JSON serialization. The default gesture→action mapping `GESTURE_ACTION_MAPPING` is also defined here.

### Factory functions
Every major component exposes a `create_*()` factory (e.g., `create_camera_capture()`, `create_face_pipeline()`). Use these rather than instantiating classes directly.

### Common utilities
| Import | Use for |
|--------|---------|
| `from cammy.common import ThreadSafeQueue, PipelineQueue` | inter-thread queues |
| `from cammy.common import SystemMetrics, LatencyTracker` | performance tracking |
| `from cammy.common import get_config_manager` | config access |
| `from cammy.common.logging import setup_logger` | per-module logger |

### Test utilities
`tests/common.py` provides `MockCamera`, `create_test_frame()`, `create_mock_landmarks()`, `temp_config_dir()`, and `wait_for_condition()`. Use these instead of rolling your own mocks.

### Extending the system
- **New gesture**: add to `GestureType` in `common/types.py` → update `GestureClassifier` in `hand_pipeline.py` → add mapping in `ActionMapper` in `action_executor.py` → add tests in `test_hand_pipeline.py`
- **New action type**: add to `ActionType` in `common/types.py` → add handler class in `action_executor.py` → update tests
- **New pipeline stage**: create module + CODEMAP, register in `main.py`, add tests
