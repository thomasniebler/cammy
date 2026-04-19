# Face Pipeline Module CODEMAP

## Overview

This module handles face detection, embedding extraction, and identity recognition.

## Directory

```
src/cammy/face_pipeline.py
```

## Dependencies

- `mediapipe` - Face detection
- `deepface` - Face embeddings (ArcFace)
- `opencv-python` - Image processing
- `numpy`
- `json`, `threading` (stdlib)
- `pathlib` (stdlib)

## Public API

### Functions

| Function | Description | Returns |
|----------|-------------|--------|
| `create_face_pipeline(threshold, max_faces, identity_store)` | Factory to create pipeline | `FacePipeline` |

### Classes

| Class | Description |
|-------|-------------|
| `FacePipeline` | Combined detection + recognition |
| `FaceDetector` | Detect faces in frames |
| `FaceEmbedder` | Extract face embeddings |
| `FaceRecognizer` | Match embeddings to identities |
| `IdentityStore` | Store/retrieve identity embeddings |

## Data Flow

```
[Frame]
     │
     ▼
[FaceDetector.detect()]
     │
     ▼ (bounding boxes)
[FaceEmbedder.extract_embedding()]
     │
     ▼ (embedding vector)
[FaceRecognizer.recognize()]
     │
     ▼
[IdentityStore] ←── compare against stored embeddings
     │
     ▼
[DetectedFace] + confidence
```

## Internal Structure

```
FacePipeline
├── _detector: FaceDetector
├── _recognizer: FaceRecognizer
├── _identity_store: IdentityStore
├── _input_queue: ThreadSafeQueue
├── _output_queue: ThreadSafeQueue
└── process(frame) → List[DetectedFace]

FaceDetector
├── _detector: mp.solutions.face_detection (or None)
└── detect(frame) → List[bbox, confidence]

FaceRecognizer
├── _embedder: FaceEmbedder
├── _identity_store: IdentityStore
├── _threshold: float
├── recognize(embedding) → identity
└── enroll(name, embedding, metadata)

IdentityStore
├── _identities: Dict[str, data]
├── save_identity(name, data)
├── delete_identity(name)
├── get_identity(name)
└── list_identities() → List[str]
```

## Usage

```python
from cammy.face_pipeline import FacePipeline, create_face_pipeline

# Create pipeline
pipeline = create_face_pipeline(threshold=0.65)

# Process a frame
faces = pipeline.process(frame)
for face in faces:
    print(f"{face.identity}: {face.confidence}")

# Enroll a new identity
pipeline.enroll_identity("john", face_frame, {"note": " coworker"})

# List identities
print(pipeline.get_identities())
```

## Error Handling

- No MediaPipe: Falls back to no face detection
- No DeepFace: Returns dummy embeddings for compatibility
- Identity load failure: Logs warning, continues with empty store
- Detection failure: Returns empty list

## Metrics Tracked

- Face detection latency
- Recognition latency

## Thread Safety

- IdentityStore uses in-memory dict (assumes single-threaded enrollment)
- FacePipeline.process() can be called from multiple threads

## Notes for Future Agents

- To improve detection: Add histogram equalization preprocessing
- To add alignment: Use MTCNN for face landmarks alignment
- To improve recognition: Store multiple embeddings per identity, use averaging
- To add liveness detection: Add blink/dot tracking to prevent spoofing