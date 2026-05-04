"""Common types for cammy pipeline."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class HandType(str, Enum):
    """Hand type enumeration."""

    LEFT = "left"
    RIGHT = "right"
    UNKNOWN = "unknown"


class GestureType(str, Enum):
    """Gesture type enumeration."""

    FIST = "fist"
    OPEN_PALM = "open_palm"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    PEACE = "peace"
    POINTING = "pointing"
    OK_SIGN = "ok_sign"
    L_SHAPE = "l_shape"
    ROCK = "rock"
    UNKNOWN = "unknown"
    NONE = "none"


class ActionType(str, Enum):
    """Action type enumeration."""

    MEDIA_PLAY = "media_play"
    MEDIA_PAUSE = "media_pause"
    MEDIA_NEXT = "media_next"
    MEDIA_PREV = "media_prev"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_MUTE = "volume_mute"
    KEY_PRESS = "key_press"
    WEBHOOK = "webhook"
    SHELL = "shell"
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    CUSTOM = "custom"


@dataclass
class BoundingBox:
    """Bounding box for detected objects."""

    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "BoundingBox":
        return cls(x=data["x"], y=data["y"], width=data["width"], height=data["height"])


@dataclass
class DetectedFace:
    """Detected face result."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity: Optional[str] = None
    confidence: float = 0.0
    embedding: Optional[List[float]] = None
    bbox: Optional[BoundingBox] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id}
        if self.identity is not None:
            result["identity"] = self.identity
        if self.confidence > 0:
            result["confidence"] = round(self.confidence, 2)
        if self.bbox is not None:
            result["bbox"] = self.bbox.to_dict()
        return result


@dataclass
class DetectedHand:
    """Detected hand result."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    gesture: GestureType = GestureType.UNKNOWN
    gesture_confidence: float = 0.0
    hand_type: HandType = HandType.UNKNOWN
    landmarks: Optional[List[List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id": self.id,
            "type": self.gesture.value if self.gesture else GestureType.UNKNOWN.value,
            "confidence": round(self.gesture_confidence, 2),
            "hand": self.hand_type.value,
        }
        if self.gesture == GestureType.POINTING and self.landmarks and len(self.landmarks) > 8:
            result["pointer"] = {
                "x": round(self.landmarks[8][0], 4),
                "y": round(self.landmarks[8][1], 4),
            }
        return result


@dataclass
class Action:
    """Action to execute."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType = ActionType.CUSTOM
    action_name: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.action_type.value,
            "name": self.action_name,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


@dataclass
class CameraFrame:
    """Camera frame data."""

    frame: Any  # numpy array
    timestamp: float
    width: int = 0
    height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class PipelineResult:
    """Combined pipeline result."""

    timestamp: float
    faces: List[DetectedFace] = field(default_factory=list)
    hands: List[DetectedHand] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "faces": [f.to_dict() for f in self.faces],
            "hands": [h.to_dict() for h in self.hands],
            "actions": [a.to_dict() for a in self.actions],
        }


# Registry for gesture action mappings
GESTURE_ACTION_MAPPING: Dict[GestureType, ActionType] = {
    GestureType.FIST: ActionType.MEDIA_PAUSE,
    GestureType.OPEN_PALM: ActionType.MEDIA_PLAY,
    GestureType.THUMBS_UP: ActionType.VOLUME_UP,
    GestureType.THUMBS_DOWN: ActionType.VOLUME_DOWN,
    GestureType.PEACE: ActionType.MEDIA_NEXT,
}
