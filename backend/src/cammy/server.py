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
from .common.commands import CommandDef, CommandsManager


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
        self._websockets: Dict[str, Any] = {}  # client_id -> websocket connection
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
            self._websockets[client_id] = websocket

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
                self._websockets.pop(client_id, None)

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
                message = self._message_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue
            except Exception as e:
                logger.error(f"Broadcast queue error: {e}")
                await asyncio.sleep(0.01)
                continue

            with self._lock:
                websockets_snapshot = dict(self._websockets)

            dead_clients = []
            for client_id, ws in websockets_snapshot.items():
                try:
                    await ws.send(message)
                except Exception as e:
                    logger.debug(f"Failed to send to {client_id}: {e}")
                    dead_clients.append(client_id)

            if dead_clients:
                with self._lock:
                    for client_id in dead_clients:
                        self._websockets.pop(client_id, None)
                        self._clients.pop(client_id, None)

    async def start_server(self):
        """Start the WebSocket server."""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets library not available")
            return

        from websockets.server import serve

        self._running = True
        self._loop = asyncio.get_event_loop()

        async with serve(self._handle_client, self._host, self._port):
            logger.info(f"WebSocket server started on {self._host}:{self._port}")
            asyncio.create_task(self._broadcast_loop())
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
        self._camera = None
        self._commands_manager: Optional[CommandsManager] = None

    def set_dependencies(
        self,
        config_manager=None,
        identity_store=None,
        face_pipeline=None,
        action_executor=None,
        camera=None,
        commands_manager: Optional[CommandsManager] = None,
    ) -> None:
        """Set dependencies for API endpoints."""
        self._config_manager = config_manager
        self._identity_store = identity_store
        self._face_pipeline = face_pipeline
        self._action_executor = action_executor
        self._camera = camera
        self._commands_manager = commands_manager

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

        class CommandCreate(BaseModel):
            name: str
            label: str
            type: str  # keypress | shell | webhook
            payload: Dict
            cooldown_ms: int = 1000

        class CommandUpdate(BaseModel):
            label: Optional[str] = None
            type: Optional[str] = None
            payload: Optional[Dict] = None
            cooldown_ms: Optional[int] = None

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
                raw = self._action_executor.mapper.get_all_mappings()
                # Return gesture_name -> {action, label}
                result = {}
                all_actions = self._action_executor.mapper.get_all_actions()
                for gesture, action_name in raw.items():
                    label = ""
                    ac = all_actions.get(action_name)
                    if ac:
                        label = ac.label or action_name
                    result[gesture.name.lower() if hasattr(gesture, "name") else str(gesture)] = {
                        "action": action_name,
                        "label": label,
                    }
                return {"mappings": result}
            raise HTTPException(status_code=500, detail="Action executor not set")

        @app.post("/api/gestures/mapping")
        async def set_gesture_mapping(mapping: GestureMapping):
            if self._action_executor:
                from .common.types import GestureType

                try:
                    gesture = GestureType[mapping.gesture.upper()]
                except KeyError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid gesture: {mapping.gesture}",
                    )
                self._action_executor.mapper.set_mapping(gesture, mapping.action)
                return {"status": "ok"}
            raise HTTPException(status_code=500, detail="Action executor not set")

        # ── Commands CRUD ────────────────────────────────────────────────────

        @app.get("/api/commands")
        async def list_commands():
            if self._commands_manager:
                cmds = self._commands_manager.get_commands()
                return {"commands": [c.to_dict() for c in cmds.values()]}
            raise HTTPException(status_code=500, detail="Commands manager not set")

        @app.post("/api/commands", status_code=201)
        async def create_command(cmd: CommandCreate):
            if not self._commands_manager:
                raise HTTPException(status_code=500, detail="Commands manager not set")
            existing = self._commands_manager.get_command(cmd.name)
            if existing:
                raise HTTPException(status_code=409, detail=f"Command '{cmd.name}' already exists")
            new_cmd = CommandDef(
                name=cmd.name,
                label=cmd.label,
                type=cmd.type,
                payload=cmd.payload,
                cooldown_ms=cmd.cooldown_ms,
            )
            self._commands_manager.upsert_command(new_cmd)
            return new_cmd.to_dict()

        @app.put("/api/commands/{name}")
        async def update_command(name: str, update: CommandUpdate):
            if not self._commands_manager:
                raise HTTPException(status_code=500, detail="Commands manager not set")
            existing = self._commands_manager.get_command(name)
            if not existing:
                raise HTTPException(status_code=404, detail=f"Command '{name}' not found")
            updated = CommandDef(
                name=existing.name,
                label=update.label if update.label is not None else existing.label,
                type=update.type if update.type is not None else existing.type,
                payload=update.payload if update.payload is not None else existing.payload,
                cooldown_ms=update.cooldown_ms if update.cooldown_ms is not None else existing.cooldown_ms,
            )
            self._commands_manager.upsert_command(updated)
            return updated.to_dict()

        @app.delete("/api/commands/{name}", status_code=204)
        async def delete_command(name: str):
            if not self._commands_manager:
                raise HTTPException(status_code=500, detail="Commands manager not set")
            if not self._commands_manager.delete_command(name):
                raise HTTPException(status_code=404, detail=f"Command '{name}' not found")
            return None

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

        @app.get("/api/video/stream")
        async def video_stream():
            if not self._camera:
                raise HTTPException(status_code=503, detail="Camera not available")

            import cv2 as _cv2
            import concurrent.futures
            from fastapi.responses import StreamingResponse

            _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            def encode_frame(frame_data):
                ret, jpeg = _cv2.imencode(
                    ".jpg", frame_data, [_cv2.IMWRITE_JPEG_QUALITY, 70]
                )
                return jpeg.tobytes() if ret else None

            async def generate():
                loop = asyncio.get_event_loop()
                last_timestamp = 0.0
                while True:
                    frame = self._camera.get_latest_frame()
                    if frame is None or frame.timestamp == last_timestamp:
                        await asyncio.sleep(0.01)
                        continue
                    last_timestamp = frame.timestamp
                    jpeg_bytes = await loop.run_in_executor(
                        _executor, encode_frame, frame.frame
                    )
                    if jpeg_bytes:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n"
                            + jpeg_bytes
                            + b"\r\n"
                        )

            return StreamingResponse(
                generate(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

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
        camera=None,
        commands_manager: Optional[CommandsManager] = None,
    ) -> None:
        """Set dependencies for servers."""
        self._rest_api.set_dependencies(
            config_manager=config_manager,
            identity_store=identity_store,
            face_pipeline=face_pipeline,
            action_executor=action_executor,
            camera=camera,
            commands_manager=commands_manager,
        )
        # Wire action_executed callback so the executor broadcasts over WS
        if action_executor is not None:
            action_executor.set_on_action_executed(self._ws_server.broadcast)

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
            app = self._rest_api.create_app()
            if app is not None:
                try:
                    import uvicorn

                    rest_thread = threading.Thread(
                        target=uvicorn.run,
                        args=(app,),
                        kwargs={
                            "host": self._host,
                            "port": self._rest_port,
                            "log_level": "error",
                        },
                        daemon=True,
                        name="RestAPIServer",
                    )
                    rest_thread.start()
                    logger.info(f"REST API started on {self._host}:{self._rest_port}")
                except ImportError:
                    logger.warning("uvicorn not available, REST API disabled")

        self._running = True
        self._server_thread = threading.Thread(
            target=lambda: asyncio.run(self._ws_server.start_server()),
            daemon=True,
            name="WebSocketServer",
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
