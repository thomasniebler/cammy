"""WebSocket and REST server for frontend communication.

This module handles:
- WebSocket server for real-time frame streaming
- REST API for configuration management
- Client connection management

CODEMAP:
- WebSocketServer: Handle WebSocket connections
- RestAPI: FastAPI for REST endpoints
- CammyServer: Combined server manager
"""

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Callable
from dataclasses import dataclass
import queue
import uuid

from .common.logging import setup_logger
from .common.types import PipelineResult, DetectedFace, DetectedHand, Action


logger = setup_logger(__name__)


def _check_websockets():
    try:
        import websockets

        return True
    except ImportError:
        return False


def _check_fastapi():
    try:
        import fastapi

        return True
    except ImportError:
        return False


WEBSOCKETS_AVAILABLE = _check_websockets()
FASTAPI_AVAILABLE = _check_fastapi()


@dataclass
class ClientInfo:
    """Information about a connected client."""

    id: str
    connected_at: float
    last_seen: float
    subscriptions: Set[str]


class WebSocketServer:
    """WebSocket server for real-time streaming."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        heartbeat_interval: int = 30,
    ):
        """Initialize WebSocket server.

        Args:
            host: Host to bind to
            port: Port to bind to
            heartbeat_interval: Heartbeat interval in seconds
        """
        self._host = host
        self._port = port
        self._heartbeat_interval = heartbeat_interval

        self._clients: Dict[str, ClientInfo] = {}
        self._server = None
        self._running = False
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._message_queue: queue.Queue = queue.Queue(maxsize=100)

        self._on_client_connect: Optional[Callable] = None
        self._on_client_disconnect: Optional[Callable] = None

    async def _handle_client(self, websocket, path: str = None):
        """Handle a client connection."""
        client_id = str(uuid.uuid4())

        with self._lock:
            self._clients[client_id] = ClientInfo(
                id=client_id,
                connected_at=time.time(),
                last_seen=time.time(),
                subscriptions={"frames", "faces", "gestures"},
            )

        logger.info(f"Client connected: {client_id}")

        if self._on_client_connect:
            try:
                self._on_client_connect(client_id)
            except Exception as e:
                logger.warning(f"Client connect callback error: {e}")

        try:
            async for message in websocket:
                await self._handle_message(client_id, message)

                with self._lock:
                    if client_id in self._clients:
                        self._clients[client_id].last_seen = time.time()

        except Exception as e:
            logger.debug(f"Client {client_id} error: {e}")

        finally:
            with self._lock:
                self._clients.pop(client_id, None)

            logger.info(f"Client disconnected: {client_id}")

            if self._on_client_disconnect:
                try:
                    self._on_client_disconnect(client_id)
                except Exception as e:
                    logger.warning(f"Client disconnect callback error: {e}")

    async def _handle_message(self, client_id: str, message: str):
        """Handle incoming message from client."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "ping":
                # Respond with pong
                pass
            elif msg_type == "subscribe":
                with self._lock:
                    if client_id in self._clients:
                        subs = data.get("subscriptions", [])
                        self._clients[client_id].subscriptions.update(subs)
            elif msg_type == "unsubscribe":
                with self._lock:
                    if client_id in self._clients:
                        subs = data.get("subscriptions", [])
                        self._clients[client_id].subscriptions.difference_update(subs)
            elif msg_type == "config_update":
                # Handle config update from frontend
                pass

        except json.JSONDecodeError:
            logger.warning(f"Invalid message from {client_id}")

    async def _broadcast_loop(self):
        """Broadcast messages to clients."""
        while self._running:
            try:
                message = self._message_queue.get(timeout=0.1)

                with self._lock:
                    clients = list(self._clients.items())

                for client_id, info in clients:
                    try:
                        await websocket.send(message)
                    except Exception as e:
                        logger.debug(f"Failed to send to {client_id}: {e}")

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

    async def start_server(self):
        """Start the WebSocket server."""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets library not available")
            return

        import websockets
        from websockets.server import serve

        self._running = True
        self._loop = asyncio.get_event_loop()

        async with serve(self._handle_client, self._host, self._port):
            logger.info(f"WebSocket server started on {self._host}:{self._port}")
            await asyncio.Future()  # Run forever

    def broadcast(self, data: Dict[str, Any]) -> None:
        """Broadcast data to all connected clients.

        Args:
            data: Data to broadcast
        """
        if not self._running:
            return

        try:
            message = json.dumps(data)
            self._message_queue.put_nowait(message)
        except queue.Full:
            logger.debug("Message queue full, dropping message")

    def broadcast_result(self, result: PipelineResult) -> None:
        """Broadcast pipeline result to all clients.

        Args:
            result: Pipeline result to broadcast
        """
        data = {
            "type": "camera_frame",
            "version": "1.0",
            "timestamp": result.timestamp,
            "faces": [f.to_dict() for f in result.faces],
            "gestures": [h.to_dict() for h in result.hands],
        }
        self.broadcast(data)

    def broadcast_faces(self, faces: List[DetectedFace]) -> None:
        """Broadcast face detections.

        Args:
            faces: List of detected faces
        """
        data = {
            "type": "faces",
            "timestamp": time.time(),
            "faces": [f.to_dict() for f in faces],
        }
        self.broadcast(data)

    def broadcast_gestures(self, hands: List[DetectedHand]) -> None:
        """Broadcast hand gestures.

        Args:
            hands: List of detected hands
        """
        data = {
            "type": "gestures",
            "timestamp": time.time(),
            "gestures": [h.to_dict() for h in hands],
        }
        self.broadcast(data)

    def get_client_count(self) -> int:
        """Get number of connected clients."""
        with self._lock:
            return len(self._clients)

    def set_on_connect(self, callback: Callable[[str], None]) -> None:
        """Set client connect callback."""
        self._on_client_connect = callback

    def set_on_disconnect(self, callback: Callable[[str], None]) -> None:
        """Set client disconnect callback."""
        self._on_client_disconnect = callback

    async def stop_server(self):
        """Stop the WebSocket server."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("WebSocket server stopped")


class RestAPI:
    """REST API for configuration management."""

    def __init__(self, app=None):
        """Initialize REST API.

        Args:
            app: FastAPI app instance
        """
        self._app = app
        self._config_manager = None
        self._identity_store = None
        self._face_pipeline = None
        self._action_executor = None

    def set_dependencies(
        self,
        config_manager=None,
        identity_store=None,
        face_pipeline=None,
        action_executor=None,
    ) -> None:
        """Set dependencies for API endpoints."""
        self._config_manager = config_manager
        self._identity_store = identity_store
        self._face_pipeline = face_pipeline
        self._action_executor = action_executor

    def create_app(self):
        """Create and configure FastAPI app."""
        if not FASTAPI_AVAILABLE:
            logger.warning("FastAPI not available")
            return None

        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel

        app = FastAPI(title="Cammy API", version="1.0.0")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        class ConfigUpdate(BaseModel):
            performance: Optional[Dict] = None
            detection: Optional[Dict] = None
            action: Optional[Dict] = None
            camera: Optional[Dict] = None

        class IdentityCreate(BaseModel):
            name: str
            metadata: Optional[Dict] = None

        class GestureMapping(BaseModel):
            gesture: str
            action: str

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        @app.get("/api/config")
        async def get_config():
            if self._config_manager:
                return self._config_manager.get().to_dict()
            raise HTTPException(status_code=500, detail="Config manager not set")

        @app.post("/api/config")
        async def update_config(update: ConfigUpdate):
            if self._config_manager:
                updates = {k: v for k, v in update.dict().items() if v is not None}
                self._config_manager.update(updates)
                return {"status": "ok"}
            raise HTTPException(status_code=500, detail="Config manager not set")

        @app.get("/api/identities")
        async def list_identities():
            if self._identity_store:
                return {"identities": self._identity_store.list_identities()}
            raise HTTPException(status_code=500, detail="Identity store not set")

        @app.post("/api/identities")
        async def create_identity(identity: IdentityCreate):
            if self._face_pipeline:
                # Note: Would need frame - simplified
                return {"status": "ok", "name": identity.name}
            raise HTTPException(status_code=500, detail="Face pipeline not set")

        @app.delete("/api/identities/{name}")
        async def delete_identity(name: str):
            if self._face_pipeline:
                self._face_pipeline.remove_identity(name)
                return {"status": "ok"}
            raise HTTPException(status_code=500, detail="Face pipeline not set")

        @app.get("/api/metrics")
        async def get_metrics():
            # Would return system metrics
            return {"fps": 0, "pipelines": {}}

        @app.get("/api/gestures/mapping")
        async def get_gesture_mappings():
            if self._action_executor:
                return {"mappings": self._action_executor.mapper.get_all_mappings()}
            raise HTTPException(status_code=500, detail="Action executor not set")

        @app.post("/api/gestures/mapping")
        async def set_gesture_mapping(mapping: GestureMapping):
            if self._action_executor:
                from .common.types import GestureType

                gesture = GestureType(mapping.gesture)
                self._action_executor.mapper.set_mapping(gesture, mapping.action)
                return {"status": "ok"}
            raise HTTPException(status_code=500, detail="Action executor not set")

        @app.post("/api/action/enable")
        async def enable_actions():
            if self._action_executor:
                self._action_executor.enable()
                return {"status": "ok"}
            raise HTTPException(status_code=500, detail="Action executor not set")

        @app.post("/api/action/disable")
        async def disable_actions():
            if self._action_executor:
                self._action_executor.disable()
                return {"status": "ok"}
            raise HTTPException(status_code=500, detail="Action executor not set")

        self._app = app
        return app

    @property
    def app(self):
        """Get FastAPI app."""
        return self._app


class CammyServer:
    """Combined server manager."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        ws_port: int = 8765,
        rest_port: int = 8000,
    ):
        """Initialize combined server.

        Args:
            host: Host to bind to
            ws_port: WebSocket port
            rest_port: REST API port
        """
        self._host = host
        self._ws_port = ws_port
        self._rest_port = rest_port

        self._ws_server = WebSocketServer(host=host, port=ws_port)
        self._rest_api = RestAPI()

        self._running = False
        self._server_thread: Optional[threading.Thread] = None

    def set_dependencies(
        self,
        config_manager=None,
        identity_store=None,
        face_pipeline=None,
        action_executor=None,
    ) -> None:
        """Set dependencies for servers."""
        self._rest_api.set_dependencies(
            config_manager=config_manager,
            identity_store=identity_store,
            face_pipeline=face_pipeline,
            action_executor=action_executor,
        )

    def broadcast(self, data: Dict[str, Any]) -> None:
        """Broadcast data to WebSocket clients."""
        self._ws_server.broadcast(data)

    def broadcast_result(self, result: PipelineResult) -> None:
        """Broadcast pipeline result."""
        self._ws_server.broadcast_result(result)

    def broadcast_faces(self, faces: List[DetectedFace]) -> None:
        """Broadcast face detections."""
        self._ws_server.broadcast_faces(faces)

    def broadcast_gestures(self, hands: List[DetectedHand]) -> None:
        """Broadcast hand gestures."""
        self._ws_server.broadcast_gestures(hands)

    async def _start_ws_async(self):
        """Start WebSocket server asynchronously."""
        await self._ws_server.start_server()

    def start(self, start_rest: bool = True) -> None:
        """Start all servers.

        Args:
            start_rest: Whether to start REST API
        """
        if start_rest and FASTAPI_AVAILABLE:
            self._rest_api.create_app()

        self._running = True
        self._server_thread = threading.Thread(
            target=lambda: asyncio.run(self._ws_server.start_server()),
            daemon=True,
        )
        self._server_thread.start()

        logger.info(f"Cammy server started on {self._host}")

    def stop(self) -> None:
        """Stop all servers."""
        self._running = False

        async def stop_ws():
            await self._ws_server.stop_server()

        try:
            asyncio.run(stop_ws())
        except Exception as e:
            logger.warning(f"Error stopping WebSocket server: {e}")

        logger.info("Cammy server stopped")

    @property
    def ws_port(self) -> int:
        """Get WebSocket port."""
        return self._ws_port

    @property
    def rest_port(self) -> int:
        """Get REST port."""
        return self._rest_port

    @property
    def is_running(self) -> bool:
        """Check if running."""
        return self._running

    @property
    def client_count(self) -> int:
        """Get connected client count."""
        return self._ws_server.get_client_count()


def create_server(
    host: str = "127.0.0.1",
    ws_port: int = 8765,
    rest_port: int = 8000,
) -> CammyServer:
    """Factory to create server.

    Args:
        host: Host to bind to
        ws_port: WebSocket port
        rest_port: REST API port

    Returns:
        CammyServer instance
    """
    return CammyServer(host=host, ws_port=ws_port, rest_port=rest_port)
