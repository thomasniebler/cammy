"""Common metrics infrastructure for performance monitoring."""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import deque


@dataclass
class PipelineMetrics:
    """Metrics for a single pipeline stage."""

    name: str
    count: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        if self.count == 0:
            return 0.0
        return self.total_latency_ms / self.count

    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        self.count += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    def record_error(self) -> None:
        """Record an error."""
        self.errors += 1

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "count": self.count,
            "errors": self.errors,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2)
            if self.min_latency_ms != float("inf")
            else 0,
            "max_latency_ms": round(self.max_latency_ms, 2),
        }


@dataclass
class SystemMetrics:
    """System-wide metrics aggregator."""

    pipelines: Dict[str, PipelineMetrics] = field(default_factory=dict)
    fps_window: int = 30

    def __post_init__(self) -> None:
        """Initialize default pipelines."""
        self._fps_timestamps: deque = deque(maxlen=self.fps_window)
        self._lock = threading.Lock()

    def get_or_create_pipeline(self, name: str) -> PipelineMetrics:
        """Get or create a pipeline metrics."""
        with self._lock:
            if name not in self.pipelines:
                self.pipelines[name] = PipelineMetrics(name=name)
            return self.pipelines[name]

    def record_fps(self) -> None:
        """Record an FPS frame."""
        with self._lock:
            self._fps_timestamps.append(time.time())

    def get_fps(self) -> float:
        """Calculate current FPS based on window."""
        with self._lock:
            if len(self._fps_timestamps) < 2:
                return 0.0
            elapsed = self._fps_timestamps[-1] - self._fps_timestamps[0]
            if elapsed <= 0:
                return 0.0
            return (len(self._fps_timestamps) - 1) / elapsed

    def record_pipeline_latency(self, pipeline: str, latency_ms: float) -> None:
        """Record pipeline latency."""
        metrics = self.get_or_create_pipeline(pipeline)
        metrics.record_latency(latency_ms)

    def record_pipeline_error(self, pipeline: str) -> None:
        """Record pipeline error."""
        metrics = self.get_or_create_pipeline(pipeline)
        metrics.record_error()

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        with self._lock:
            return {
                "fps": round(self.get_fps(), 2),
                "pipelines": {
                    name: metrics.to_dict() for name, metrics in self.pipelines.items()
                },
            }


class LatencyTracker:
    """Context manager for tracking operation latency."""

    def __init__(self, metrics: SystemMetrics, pipeline: str):
        """Initialize the tracker.

        Args:
            metrics: System metrics instance
            pipeline: Pipeline name to track
        """
        self._metrics = metrics
        self._pipeline = pipeline
        self._start_time: Optional[float] = None

    def __enter__(self) -> "LatencyTracker":
        """Start tracking."""
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End tracking and record latency."""
        if self._start_time is not None:
            latency_ms = (time.perf_counter() - self._start_time) * 1000
            self._metrics.record_pipeline_latency(self._pipeline, latency_ms)
            if exc_type is not None:
                self._metrics.record_pipeline_error(self._pipeline)


class Timer:
    """Simple timer for measuring elapsed time."""

    def __init__(self) -> None:
        """Initialize timer."""
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self) -> None:
        """Start the timer."""
        self._start_time = time.perf_counter()

    def stop(self) -> float:
        """Stop the timer and return elapsed time in milliseconds."""
        self._end_time = time.perf_counter()
        return self.elapsed_ms()

    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._start_time is None:
            return 0.0
        end = self._end_time if self._end_time is not None else time.perf_counter()
        return (end - self._start_time) * 1000

    def reset(self) -> None:
        """Reset the timer."""
        self._start_time = None
        self._end_time = None
