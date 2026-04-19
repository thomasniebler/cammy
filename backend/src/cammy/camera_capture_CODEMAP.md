# Camera Capture Module CODEMAP

## Overview

This module handles video frame capture from camera devices with threading support for continuous, non-blocking frame reading.

## Directory

```
src/cammy/camera_capture.py
```

## Dependencies

- `cv2` (opencv-python)
- `numpy`
- `threading` (stdlib)
- `time` (stdlib)
- `dataclasses` (stdlib)

## Public API

### Functions

| Function | Description | Returns |
|----------|-------------|--------|
| `get_available_cameras()` | Discover available camera devices | `List[CameraInfo]` |
| `create_camera_capture(device_index, target_fps)` | Factory to create CameraCapture | `CameraCapture` |

### Classes

| Class | Description |
|-------|-------------|
| `CameraCapture` | Main interface for camera capture |
| `CameraReader` | Thread-based frame reader |
| `CameraInfo` | Camera device information |
| `CameraFrame` | Wrapped frame with metadata |

## Internal Structure

```
CameraCapture
├── _reader: CameraReader (thread)
├── _frame_queue: ThreadSafeQueue
├── _metrics: SystemMetrics
└── _config: CameraConfig

CameraReader (threading.Thread)
├── run() → captures frames continuously
├── _frame_queue → output queue
└── _cap → cv2.VideoCapture
```

## Data Flow

```
[Camera Device]
     │
     ▼ (cv2.VideoCapture)
[CameraReader Thread]
     │
     ▼ (ThreadSafeQueue)
[CameraCapture.get_frame()]
     │
     ▼
[Pipeline]
```

## Usage

```python
from cammy.camera_capture import CameraCapture, create_camera_capture

# Method 1: Direct usage
capture = create_camera_capture(device_index=0, target_fps=30)
capture.start()

# Get frames
while True:
    frame = capture.get_frame(timeout=1.0)
    if frame:
        process(frame.frame)

capture.stop()

# Method 2: With custom config
from cammy.common import CameraConfig
config = CameraConfig(device_index=0, width=1280, height=720, fps=30)
capture = CameraCapture(config)
capture.start()
```

## Error Handling

- Camera device not found: Logs error, sets `_error` attribute
- Frame read failure: Logs warning, retries
- Queue full: Drops frame, logs debug

## Metrics Tracked

- Capture FPS (moving average)
- Capture latency

## Thread Safety

- CameraReader is a daemon thread
- Frame queue is thread-safe (ThreadSafeQueue)
- CameraCapture methods are thread-safe for start/stop

## Notes for Future Agents

- When modifying frame processing, add preprocessing to CameraCapture or create a separate preprocessor module
- To add camera settings (brightness, contrast), add to CameraConfig and apply in CameraReader.run()
- For camera switching, implement in CameraCapture with proper thread cleanup