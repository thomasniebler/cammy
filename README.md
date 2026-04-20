# Cammy 🎥🤚

Real-time face detection/recognition and hand gesture recognition with a React configuration UI.
Gestures trigger fully customisable commands — keypress, shell scripts, or webhooks.

---

## Features

- **Face detection & recognition** via MediaPipe + DeepFace (ArcFace)
- **Hand gesture recognition** — 7 gesture types, classified from 21-point MediaPipe landmarks
- **Custom commands** — create keypress, shell, or webhook actions and assign them to any gesture
- **Cooldown UI** — see the last triggered command and a live countdown bar before the next trigger is accepted
- **Live MJPEG camera stream** in the browser with detection overlays
- **WebSocket** real-time event streaming (faces, gestures, action_executed)
- **REST API** (FastAPI) for full configuration

---

## Gesture → Action mapping

| Gesture | Default action |
|---------|---------------|
| ✊ Fist | Pause |
| ✋ Open Palm | Play |
| 👍 Thumbs Up | Volume Up |
| 👎 Thumbs Down | Volume Down |
| ✌️ Peace | Next Track |

All mappings are configurable in the UI.

---

## Quick start

### Prerequisites

- Python ≥ 3.11 with [uv](https://github.com/astral-sh/uv)
- Node.js ≥ 18
- [Task](https://taskfile.dev) (optional but recommended)
- A webcam

### Install & run

```bash
# Clone
git clone https://github.com/thomasniebler/cammy.git
cd cammy

# Backend
task backend:install   # uv sync
task backend:run       # python -m cammy.main

# Frontend (separate terminal)
task frontend:install  # npm install
task frontend:dev      # vite dev server on :5173
```

Then open **http://localhost:5173**.

### Without Task

```bash
# Backend
cd backend
uv sync
uv run python -m cammy.main

# Frontend
cd frontend
npm install
npm run dev
```

---

## Architecture

```
Browser (React/Vite :5173)
  │  /api/*  →  FastAPI :8000
  │  /ws     →  WebSocket :8765
  │  /api/video/stream  →  MJPEG stream
  │
Backend (Python)
  ├── camera_capture.py   Webcam frames (OpenCV)
  ├── face_pipeline.py    Face detection + recognition (MediaPipe + DeepFace)
  ├── hand_pipeline.py    Hand gesture classification (MediaPipe Tasks API)
  ├── action_executor.py  Command dispatch (keypress / shell / webhook)
  ├── server.py           FastAPI REST + WebSocket server
  └── common/
        ├── commands.py   CommandDef + CommandsManager (persisted to ~/.config/cammy/commands.json)
        ├── config.py     CammyConfig (persisted to ~/.config/cammy/config.json)
        └── types.py      Shared dataclasses & enums
```

---

## Custom commands

In the **Commands** panel you can create three types of commands:

| Type | What it does | Key fields |
|------|-------------|-----------|
| `keypress` | Presses a key via pyautogui | `key` (e.g. `play`, `volumeup`), `count` |
| `shell` | Runs a shell command | `command` (e.g. `notify-send hi`) |
| `webhook` | HTTP request | `url`, `method` (GET/POST/PUT), `body` JSON |

Each command has a **cooldown (ms)** — the minimum time between two consecutive triggers.

---

## REST API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/commands` | List all commands |
| POST | `/api/commands` | Create a command |
| PUT | `/api/commands/{name}` | Update a command |
| DELETE | `/api/commands/{name}` | Delete a command |
| GET | `/api/gestures/mapping` | Get gesture→command mappings |
| POST | `/api/gestures/mapping` | Set a gesture→command mapping |
| GET | `/api/identities` | List enrolled face identities |
| DELETE | `/api/identities/{name}` | Delete a face identity |
| GET | `/api/config` | Get configuration |
| POST | `/api/config` | Update configuration |
| GET | `/api/video/stream` | MJPEG camera stream |

---

## Configuration

Config file: `~/.config/cammy/config.json`

```json
{
  "performance": { "tier": "auto", "target_fps": 30 },
  "detection":   { "gesture_confidence_threshold": 0.7, "max_hands": 2, "max_faces": 5 },
  "action":      { "cooldown_ms": 1000, "enabled": true },
  "server":      { "host": "127.0.0.1", "port": 8765 },
  "camera":      { "device_index": 0 }
}
```

---

## Development

```bash
# Run tests
task backend:test       # pytest (75 tests)

# Lint
task backend:lint       # ruff check

# Format
task backend:format     # ruff format
```

---

## Dependencies

| Package | Purpose | Required |
|---------|---------|---------|
| `mediapipe` | Face + hand detection (Tasks API) | Yes |
| `opencv-python` | Camera capture | Yes |
| `numpy<2` | Array processing (mediapipe constraint) | Yes |
| `fastapi` + `uvicorn` | REST API | Yes |
| `websockets` | WebSocket server | Yes |
| `deepface` | Face recognition | Optional |
| `pyautogui` | Keypress actions | Optional |
| `requests` | Webhook actions | Optional |

---

## License

MIT
