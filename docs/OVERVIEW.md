# Cammy - Face & Gesture Recognition System

Cammy is a real-time face detection and hand gesture recognition system that lets you control your computer using hand gestures and facial recognition.

## Features

### Face Recognition
- **Real-time face detection** using MediaPipe
- **Face identification** using DeepFace (ArcFace model)
- **Identity enrollment** - Add new faces to recognize
- **Unknown face detection** - Detects faces that aren't enrolled

### Hand Gesture Recognition
- **21-point hand tracking** with MediaPipe
- **Multiple gesture support**:
  - ✊ Fist - Media pause
  - ✋ Open Palm - Media play
  - 👍 Thumbs Up - Volume up
  - 👎 Thumbs Down - Volume down
  - ✌️ Peace - Next track
  - 👆 Pointing - Customizable
  - 👌 OK Sign - Customizable

### Action System
- **Keyboard automation** - Control media players, presentations
- **Webhook support** - Trigger HTTP endpoints
- **Shell commands** - Execute custom scripts
- **Debouncing** - Prevent accidental repeated triggers

### Web Interface
- **Live camera preview** with detection overlays
- **Identity management** - Add/remove recognized faces
- **Gesture mapping** - Customize which gesture triggers which action
- **Real-time metrics** - FPS, detection counts

## Architecture

```
┌─────────────────────────────────────────────────┐
│              React Frontend (Web)                │
│  - Camera preview                                │
│  - Identity management                          │
│  - Gesture configuration                        │
└─────────────────┬───────────────────────────────┘
                  │ WebSocket + REST API
                  ▼
┌─────────────────────────────────────────────────┐
│              Python Backend                      │
│  - Camera capture (OpenCV)                       │
│  - Face pipeline (MediaPipe + DeepFace)          │
│  - Hand pipeline (MediaPipe)                     │
│  - Action executor (pyautogui)                   │
└─────────────────────────────────────────────────┘
```

## Use Cases

### Media Control
- Pause/play music with hand gestures
- Skip tracks without touching keyboard
- Adjust volume silently

### Presentations
- Navigate slides with gestures
- Control screen sharing
- Trigger animations

### Accessibility
- Touchless computer control
- Voice-free interaction
- Custom gesture commands

### Smart Home
- Trigger webhooks for automation
- Control smart devices
- Scene switching

## Technology Stack

| Component | Technology |
|-----------|------------|
| Face Detection | MediaPipe |
| Face Recognition | DeepFace (ArcFace) |
| Hand Tracking | MediaPipe Hands |
| Web Server | FastAPI + websockets |
| Frontend | React + TypeScript |
| Keyboard Control | pyautogui |

## Getting Started

See the [Quickstart Guide](./quickstart.md) to get up and running in 5 minutes.

## Configuration

See the [Configuration Guide](./configuration.md) to customize gestures, actions, and performance settings.
