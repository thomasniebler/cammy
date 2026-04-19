# Configuration Guide

Customize Cammy to fit your needs.

## Configuration File

Configuration is stored at: `~/.config/cammy/config.json`

### Full Configuration Example

```json
{
  "performance": {
    "tier": "auto",
    "target_fps": 15,
    "frame_skip": 1,
    "detection_resolution": [320, 240],
    "parallel_processing": true
  },
  "detection": {
    "face_similarity_threshold": 0.65,
    "gesture_confidence_threshold": 0.80,
    "min_detection_confidence": 0.5,
    "min_tracking_confidence": 0.5,
    "max_faces": 5,
    "max_hands": 2
  },
  "action": {
    "cooldown_ms": 1000,
    "enabled": true
  },
  "server": {
    "host": "127.0.0.1",
    "port": 8765,
    "ws_heartbeat_interval": 30
  },
  "camera": {
    "device_index": 0,
    "width": 640,
    "height": 480,
    "fps": 30,
    "auto_exposure": true
  }
}
```

## Performance Settings

### `performance.tier`

| Value | Description | Use Case |
|-------|-------------|----------|
| `auto` | Automatically adjust | Default |
| `high` | Maximum quality, lower FPS | Desktop with GPU |
| `medium` | Balanced | Most laptops |
| `low` | Maximum FPS, lower quality | Older hardware |

### `performance.target_fps`

Target frames per second (1-60). Lower values reduce CPU usage.

### `performance.detection_resolution`

Resolution for detection model `[width, height]`. Lower = faster but less accurate.

## Detection Settings

### `detection.face_similarity_threshold`

Threshold for face matching (0.0-1.0):

- **Lower (0.5)** - More matches, including false positives
- **Default (0.65)** - Balanced
- **Higher (0.8)** - Strict matching, more "unknown"

### `detection.gesture_confidence_threshold`

Minimum confidence for gesture recognition (0.0-1.0).

### `detection.max_faces` / `max_hands`

Maximum number of faces/hands to track simultaneously.

## Camera Settings

### `camera.device_index`

Camera device to use:

- `0` - Default camera
- `1`, `2` - Additional cameras

List available cameras:

```bash
python -c "from cammy.camera_capture import get_available_cameras; print(get_available_cameras())"
```

## Gesture Mappings

Customize which gesture triggers which action via the web interface or REST API.

### Available Actions

| Action | Description |
|--------|-------------|
| `media_play` | Play media |
| `media_pause` | Pause media |
| `media_next` | Next track/slide |
| `media_prev` | Previous track/slide |
| `volume_up` | Increase volume |
| `volume_down` | Decrease volume |
| `volume_mute` | Toggle mute |
| `webhook:URL` | Send webhook |
| `shell:command` | Run shell command |

### Set via REST API

```bash
# Get current mappings
curl http://localhost:8000/api/gestures/mapping

# Update mapping
curl -X POST http://localhost:8000/api/gestures/mapping \
  -H "Content-Type: application/json" \
  -d '{"gesture": "pointing", "action": "volume_mute"}'
```

## Webhook Actions

Trigger HTTP endpoints with gestures:

```json
{
  "action_type": "webhook",
  "action_name": "my_webhook",
  "payload": {
    "url": "http://localhost:8080/trigger",
    "method": "POST",
    "body": {"event": "gesture", "action": "play"}
  }
}
```

## Shell Actions

Execute shell commands:

```json
{
  "action_type": "shell",
  "action_name": "my_command",
  "payload": {
    "command": "open -a Safari",
    "shell": true
  }
}
```

## Identity Management

### Enroll New Identity via API

```bash
# Note: Requires a frame with a face
curl -X POST http://localhost:8000/api/identities \
  -H "Content-Type: application/json" \
  -d '{"name": "alice", "metadata": {"note": "coworker"}}'
```

### Delete Identity

```bash
curl -X DELETE http://localhost:8000/api/identities/alice
```

### List Identities

```bash
curl http://localhost:8000/api/identities
```

## Reset Configuration

To reset all settings to defaults:

```bash
rm ~/.config/cammy/config.json
# Restart Cammy to regenerate defaults
```
