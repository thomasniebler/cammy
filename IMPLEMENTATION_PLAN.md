# Cammy Implementation Plan

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CAMMY SYSTEM                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐                    ┌────────────────────────────────┐  │
│  │   WEBCAM     │                    │        REACT FRONTEND            │  │
│  │  (Video0)    │                    │  ┌──────────┬──────────┬─────┐  │  │
│  └──────┬───────┘                    │  │CameraView│FaceManager│Gest │  │  │
│         │ frame                      │  │(live)    │(training) │.Map │  │  │
│         ▼                           │  └──────────┴──────────┴─────┘  │  │
│  ┌──────────────────────────────┐   │              │                    │  │
│  │      PYTHON BACKEND          │   │              │ WebSocket            │  │
│  │  ┌────────────────────────┐  │   │              ▼                    │  │
│  │  │    FRAME PROCESSOR     │  │◄─►        ┌─────────┐                  │  │
│  │  │  (OpenCV + threading) │  │   │        │ Socket  │                  │  │
│  │  └───────────┬────────────┘  │   │        └─────────┘                  │  │
│  │              │               │   │              │                    │  │
│  │    ┌─────────┴─────────┐     │   │              │ config                 │  │
│  │    │                   │     │   │              ▼                    │  │
│  │    ▼                   ▼     │   │        ┌─────────┐                  │  │
│  │  ┌────────┐      ┌────────┐  │   │        │  JSON   │                  │  │
│  │  │ FACE   │      │ HAND   │  │   │        │ Config  │                  │  │
│  │  │PIPELINE│      │PIPELINE│  │   │        └─────────┘                  │  │
│  │  └───┬────┘      └───┬────┘  │   │              │                    │  │
│  │      │               │       │   │              ▼                    │  │
│  │      ▼               ▼       │   │        ┌─────────┐                  │  │
│  │  ┌─────────┐    ┌─────────┐  │   │        │ Action  │                  │  │
│  │  │ Identity│    │Gesture  │  │   │        │Executor│                  │  │
│  │  │ Matcher │    │Classifier│ │   │        │(pyauto)│                  │  │
│  │  └─────────┘    └─────────┘  │   │        └─────────┘                  │  │
│  │              │               │   │              │                    │  │
│  │              ▼               │   │              ▼                    │  │
│  │         ┌──────────┐         │   │        ┌──────────┐                  │  │
│  │         │ Event    │         │   │        │ pyautogui│                  │  │
│  │         │ Dispatch │         │   │        │ webhooks │                  │  │
│  │         └──────────┘         │   │        │ commands │                  │  │
│  │              │               │   │        └──────────┘                  │  │
│  │              ▼               │   │              │                    │  │
│  │         ┌──────────┐         │   │              ▼                    │  │
│  │         │ Actions  │         │   │        ┌──────────┐                  │  │
│  │         │(executed)│         │   │        │ External │                  │  │
│  │         └──────────┘         │   │        │ Systems  │                  │  │
│  └──────────────────────────────┘   │        └──────────┘                  │  │
│                                      │                                      │  │
│                                      │         (keyboard, HTTP, shell)    │  │
│                                      └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Remediations Applied (from Critical Review)

1. **Parallel Threaded Pipeline** — Separate threads for capture, face detection, hand detection
2. **Tiered Performance** — Configurable performance_tier: auto|high|medium|low
3. **Pre-trained Gestures** — Use MediaPipe built-in gesture recognizer first
4. **Two-Channel Communication** — WebSocket (stream) + REST (config)
5. **Graceful Degradation** — Pipeline continues on partial failures
6. **Observability** — Structured logging + /metrics endpoint
7. **Simplified Frontend** — HTML+Vanilla JS, React only if needed
8. **Revised Timeline** — 16 days instead of 11

---

## Phase Breakdown with Risk Mitigation

### Phase 1: Foundation & Camera Pipeline (Days 1-2)

| Step | Task | File | Risk | Mitigation |
|------|------|------|------|-------------|
| 1.1 | Set up Python project structure | `backend/pyproject.toml`, `requirements.txt` | Dependency conflicts | Use virtual environment, pin versions |
| 1.2 | Install OpenCV with video support | Test `cv2.VideoCapture(0)` | Missing video codecs, camera not found | Add camera auto-detection with fallback list |
| 1.3 | Build async frame reader | `camera_capture.py` | Frame drops at high FPS | Use thread-based capture with queue (maxsize=2) |
| 1.4 | Add frame preprocessing | Grayscale option, resize, histogram equalization | Slow processing | Only preprocess needed frames |
| 1.5 | Create frame publisher pattern | `FramePublisher` class with callbacks | Tight coupling | Use observer pattern with typed events |
| 1.6 | **Add error handling + graceful degradation** | Retry logic, fallback | System crashes on camera loss | Retry 3x, then error state, reattempt every 5s |
| 1.7 | **Add structured logging** | `logger` with levels | No visibility into failures | Log DEBUG/INFO/WARNING/ERROR at each pipeline stage |
| 1.8 | **Add performance tier config** | `config.json` → performance_tier | Can't adapt to hardware | Tier selector: auto, high, medium, low |

### Phase 2: Face Detection & Recognition (Days 3-6) → REVISED: Days 3-6

| Step | Task | File | Risk | Mitigation |
|------|------|------|------|-------------|
| 2.1 | Integrate face detector (MTCNN or MediaPipe) | `face_detector.py` | Low accuracy in poor lighting | Use MediaPipe (more robust), add histogram equalization |
| 2.2 | Test face detection latency | Benchmark scripts | Too slow (>100ms per frame) | Skip frames, use smaller input size (320x240 for detection) |
| 2.3 | Build identity embedding pipeline | `face_embeddings.py` using DeepFace/FaceNet | Model download fails | Include fallback to bundled small model |
| 2.4 | Create identity storage | `identities/` with JSON/pickle | Corrupt data | Add validation on load, backup before write |
| 2.5 | Build enrollment workflow | CLI/web UI to add new faces | User adds blurry images | Require multiple captures, verify quality score |
| 2.6 | Real-time matching | Cosine similarity with threshold | Wrong identity assigned | Separate "unknown" bucket, tunable threshold (default 0.65) |
| 2.7 | **Add parallel face thread** | Thread-based detection | Sequential bottleneck | Separate thread, put embeddings on queue |
| 2.8 | **Add FPS/latency metrics** | Moving average tracking | No performance visibility | Track per-frame latency, expose via /metrics |

### Phase 3: Hand Gesture Detection (Days 7-9) → REVISED: Days 7-10

| Step | Task | File | Risk | Mitigation |
|------|------|------|------|-------------|
| 3.1 | Integrate MediaPipe Hands | `hand_detector.py` | Hands not detected | Adjust `min_detection_confidence` dynamically based on lighting |
| 3.2 | Test landmark extraction | Visualize 21 points on video | Wrong hand (left vs right) | Mirror check, flip for left-hand users via config |
| 3.3 | Build gesture classifier | `gesture_classifier.py` (custom MLP) | Poor classification | Train on diverse dataset, augment with rotation |
| 3.4 | Create gesture-to-action mapping | `config.json` schema | Conflicting mappings | Validate config on load, first-match wins |
| 3.5 | Add debouncing | Per-gesture cooldown timer | Action fires too often | Default 1-second cooldown, configurable per gesture |
| 3.6 | **Use MediaPipe built-in gesture recognizer** | Pre-trained model | Cold start on custom MLP | Start with built-in (17 gestures), add custom only if needed |
| 3.7 | **Parallel hand thread** | Thread-based detection | Blocks face pipeline | Separate thread, put landmarks on queue |

### Phase 4: WebSocket Server & Frontend (Days 9-12) → REVISED: Days 11-16

| Step | Task | File | Risk | Mitigation |
|------|------|------|------|-------------|
| 4.1 | Build WebSocket server | `server.py` using `websockets` | Connection drops | Auto-reconnect with exponential backoff |
| 4.2 | Define protocol format | JSON schema | Protocol mismatch | Version the protocol, validate incoming/outgoing |
| 4.3 | Throttle to 10-15fps | Frame skip logic | Can't keep up | Drop frames if queue >3 behind |
| 4.4 | Build React app scaffold | Vite + TypeScript + Tailwind | Slow dev server | Use Vite's fast HMR |
| 4.5 | Camera preview component | `CameraView.tsx` | High CPU | Use offscreen canvas for processing |
| 4.6 | Face manager UI | `FaceManager.tsx` | No feedback on enrollment | Show progress indicator, preview crop |
| 4.7 | Gesture mapper UI | `GestureMapper.tsx` | Clunky mapping | Drag-and-drop or simple select |
| 4.8 | Settings panel | Device selection, thresholds | Settings not saved | Auto-save to localStorage + sync to backend |
| 4.9 | **Add REST API (FastAPI)** | Config CRUD fallback | WebSocket fails | REST endpoints for config, identities |
| 4.10 | **Add /metrics endpoint** | Performance monitoring | No visibility | Expose FPS, latencies, error counts |

---

## Communication Protocol

### Outbound (Backend → Frontend)

```json
{
  "type": "camera_frame",
  "version": "1.0",
  "timestamp": 1699999999999,
  "faces": [
    {
      "id": "uuid",
      "identity": "alice",
      "confidence": 0.92,
      "bbox": {"x": 100, "y": 50, "width": 120, "height": 150}
    }
  ],
  "gestures": [
    {
      "type": "fist",
      "confidence": 0.85,
      "hand": "right"
    }
  ]
}
```

### Inbound (Frontend → Backend)

```json
{
  "type": "config_update",
  "action_mappings": {
    "fist": "media_pause",
    "open_palm": "media_play"
  },
  "thresholds": {
    "face_similarity": 0.65,
    "gesture_confidence": 0.80
  }
}
```

---

## Directory Structure

```
cammy/
├── IMPLEMENTATION_PLAN.md          # This file
├── README.md                      # Project overview
├── AGENTS.md                     # Agent workflow instructions
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── src/
│   │   └── cammy/
│   │       ├── __init__.py
│   │       ├── camera_capture.py      # Phase 1: Camera + async frame reading
│   │       ├── face_pipeline.py    # Phase 2: Face detection/recognition
│   │       ├── hand_pipeline.py  # Phase 3: Hand gesture detection
│   │       ├── action_executor.py # Phase 3: Action execution
│   │       ├── websocket_server.py # Phase 4: WebSocket server
│   │       ├── config.py           # Config management
│   │       └── main.py            # Entry point
│   ├── identities/              # Stored face embeddings
│   │   ├── .gitkeep
│   └── config/
│       ├── gestures.json        # Gesture→action mappings
│       └── settings.json        # System settings
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── CameraView.tsx
│       │   ├── FaceManager.tsx
│       │   ├── GestureMapper.tsx
│       │   └── Settings.tsx
│       └── hooks/
│           └── useWebSocket.ts
└── tests/
    ├── test_camera.py
    ├── test_face.py
    └── test_gesture.py
```