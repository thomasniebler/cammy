"""Common queue infrastructure for threaded pipeline communication."""

import threading
from queue import Queue, Empty, Full
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class TimestampedFrame:
    """Frame wrapper with timestamp for latency tracking."""

    data: Any
    timestamp: float

    @classmethod
    def create(cls, data: Any) -> "TimestampedFrame":
        """Create a timestamped frame with current time."""
        import time

        return cls(data=data, timestamp=time.time())


class ThreadSafeQueue:
    """Thread-safe queue wrapper with additional utilities."""

    def __init__(self, maxsize: int = 2, name: str = "queue"):
        """Initialize the queue.

        Args:
            maxsize: Maximum queue size (0 = unlimited)
            name: Queue name for logging
        """
        self._queue: Queue = Queue(maxsize=maxsize)
        self._name = name
        self._closed = False
        self._lock = threading.Lock()

    def put(
        self, item: Any, block: bool = True, timeout: Optional[float] = None
    ) -> bool:
        """Put an item on the queue.

        Args:
            item: Item to enqueue
            block: Block if queue is full
            timeout: Timeout in seconds

        Returns:
            True if successful, False if queue is closed or full
        """
        with self._lock:
            if self._closed:
                return False

        try:
            self._queue.put(item, block=block, timeout=timeout)
            return True
        except Full:
            return False

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Get an item from the queue.

        Args:
            block: Block if queue is empty
            timeout: Timeout in seconds

        Returns:
            Item from queue

        Raises:
            Empty: If queue is empty and block=False or timeout exceeded
        """
        return self._queue.get(block=block, timeout=timeout)

    def get_nowait(self) -> Any:
        """Get an item without blocking.

        Returns:
            Item from queue

        Raises:
            Empty: If queue is empty
        """
        return self._queue.get_nowait()

    def put_nowait(self, item: Any) -> bool:
        """Put an item without blocking.

        Args:
            item: Item to enqueue

        Returns:
            True if successful, False if queue is full
        """
        try:
            self._queue.put_nowait(item)
            return True
        except Full:
            return False

    def qsize(self) -> int:
        """Get approximate queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    def full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    def clear(self) -> None:
        """Clear all items from the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break

    def close(self) -> None:
        """Close the queue (prevents new items)."""
        with self._lock:
            self._closed = True

    def is_closed(self) -> bool:
        """Check if queue is closed."""
        return self._closed

    @property
    def name(self) -> str:
        """Get queue name."""
        return self._name


class PipelineQueue:
    """Wrapper for pipeline queues with naming convention."""

    FRAME = "frame"
    FACE = "face"
    HAND = "hand"
    ACTION = "action"

    def __init__(self, frame_maxsize: int = 2, result_maxsize: int = 10):
        """Initialize all pipeline queues.

        Args:
            frame_maxsize: Max size for frame queue
            result_maxsize: Max size for result queue
        """
        self.frames = ThreadSafeQueue(maxsize=frame_maxsize, name=self.FRAME)
        self.faces = ThreadSafeQueue(maxsize=result_maxsize, name=self.FACE)
        self.hands = ThreadSafeQueue(maxsize=result_maxsize, name=self.HAND)
        self.actions = ThreadSafeQueue(maxsize=result_maxsize, name=self.ACTION)

    def close_all(self) -> None:
        """Close all queues."""
        self.frames.close()
        self.faces.close()
        self.hands.close()
        self.actions.close()

    def clear_all(self) -> None:
        """Clear all queues."""
        self.frames.clear()
        self.faces.clear()
        self.hands.clear()
        self.actions.clear()
