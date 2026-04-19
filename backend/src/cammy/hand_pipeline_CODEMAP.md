# Hand Pipeline Module CODEMAP

## Overview

This module handles hand landmark detection and gesture classification using MediaPipe.

## Directory

```
src/cammy/hand_pipeline.py
```

## Dependencies

- `mediapipe` (optional)
- `numpy`
- `dataclasses` (stdlib)

## Public API

### Functions

| Function | Description | Returns |
|----------|-------------|--------|
| `create_hand_pipeline(max_hands, min_confidence)` | Factory to create pipeline | `HandPipeline` |

### Classes

| Class | Description |
|-------|-------------|
| `HandPipeline` | Combined detection + classification |
| `HandDetector` | Detect hands and landmarks |
| `GestureClassifier` | Classify gestures from landmarks |

## Data Flow

```
[Frame]
     │
     ▼
[HandDetector.detect()]
     │
     ▼ (21 landmarks per hand)
[GestureClassifier.classify()]
     │
     ▼
[DetectedHand] + gesture type
```

## Gesture Types Supported

| Gesture | Fingers Extended | Confidence |
|---------|-----------------|------------|
| FIST | 0 | 0.85 |
| OPEN_PALM | 5 | 0.85 |
| PEACE | 2 (index + middle) | 0.80 |
| POINTING | 1 (index) | 0.75 |
| THUMBS_UP | 1 (thumb up) | 0.80 |
| THUMBS_DOWN | 1 (thumb down) | 0.80 |

## Usage

```python
from cammy.hand_pipeline import HandPipeline, create_hand_pipeline

# Create pipeline
pipeline = create_hand_pipeline(max_hands=2)

# Process a frame
hands = pipeline.process(frame)
for hand in hands:
    print(f"{hand.hand_type}: {hand.gesture} ({hand.gesture_confidence})")
```

## Internal Structure

```
HandPipeline
├── _detector: HandDetector
├── _classifier: GestureClassifier
├── _input_queue: ThreadSafeQueue
├── _output_queue: ThreadSafeQueue
└── process(frame) → List[DetectedHand]

HandDetector
├── _detector: mp.solutions.hands.Hands
├── _drawing: mp.solutions.drawing_utils
└── detect(frame) → List[landmarks, hand_type]

GestureClassifier
├── _recognizer: mp.tasks.vision.GestureRecognizer (optional)
├── classify(landmarks, hand_type) → gesture
└── _classify_rule_based(landmarks) → gesture (fallback)
```

## Error Handling

- No MediaPipe: Returns empty hand list
- Gesture init failure: Falls back to rule-based
- Low confidence: Filters out with threshold

## Metrics Tracked

- Hand detection latency

## Notes for Future Agents

- To add custom gestures: Train MLP on landmark data
- To improve classification: Add temporal smoothing (gesture shouldn't flicker)
- To detect pinch gesture: Calculate distance between thumb and index tip
- To support left-hand users: Add config option to mirror