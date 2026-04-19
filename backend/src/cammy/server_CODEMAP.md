# Server Module CODEMAP

## Overview

This module handles WebSocket and REST API communication with the frontend.

## Directory

```
src/cammy/server.py
```

## Dependencies

- `websockets` (optional)
- `fastapi` (optional)
- `uvicorn` (optional)
- `json`, `queue` (stdlib)
- `threading` (stdlib)

## Public API

### Functions

| Function | Description | Returns |
|----------|-------------|--------|
| `create_server(host, ws_port, rest_port)` | Factory to create server | `CammyServer` |

### Classes

| Class | Description |
|-------|-------------|
| `CammyServer` | Combined server manager |
| `WebSocketServer` | Real-time streaming server |
| `RestAPI` | Configuration REST API |
| `ClientInfo` | Connected client information |

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/config` | Get configuration |
| POST | `/config` | Update configuration |
| GET | `/identities` | List identities |
| POST | `/identities` | Create identity |
| DELETE | `/identities/{name}` | Delete identity |
| GET | `/metrics` | Get system metrics |
| GET | `/gestures/mapping` | Get gesture mappings |
| POST | `/gestures/mapping` | Set gesture mapping |

## WebSocket Protocol

### Client → Server

```json
{"type": "ping"}
{"type": "subscribe", "subscriptions": ["frames", "faces"]}
{"type": "unsubscribe", "subscriptions": ["gestures"]}
```

### Server → Client

```json
{
  "type": "camera_frame",
  "version": "1.0",
  "timestamp": 1699999999999,
  "faces": [{"id": "...", "identity": "alice", "confidence": 0.92}],
  "gestures": [{"type": "fist", "confidence": 0.85, "hand": "right"}]
}
```

## Usage

```python
from cammy.server import create_server

# Create and start server
server = create_server(host="0.0.0.0", ws_port=8765, rest_port=8000)
server.set_dependencies(
    config_manager=cm,
    identity_store=store,
    face_pipeline=fp,
    action_executor=ae,
)

# Start async
asyncio.run(server.start())

# Broadcast data
server.broadcast({"type": "camera_frame", "faces": [], "gestures": []})

# Stop
asyncio.run(server.stop())
```

## Internal Structure

```
CammyServer
├── _ws_server: WebSocketServer
├── _rest_api: RestAPI
├── broadcast(data)
├── start()
└── stop()

WebSocketServer
├── _clients: Dict[client_id, ClientInfo]
├── _message_queue: Queue
├── _handle_client(websocket)
├── _broadcast_loop()
├── broadcast(data)
└── get_client_count()

RestAPI
├── _app: FastAPI
├── _config_manager
├── _identity_store
├── _face_pipeline
├── _action_executor
└── create_app()
```

## Error Handling

- Missing websockets: Logs warning, WebSocket features disabled
- Missing FastAPI: Logs warning, REST features disabled
- Client disconnect: Automatic cleanup
- Message queue full: Drop oldest message

## Thread Safety

- WebSocket clients dict protected by lock
- Broadcast uses thread-safe queue

## Notes for Future Agents

- To add authentication: Add JWT validation in _handle_client
- To add TLS: Wrap websocket with ssl context
- To scale: Add Redis pub/sub for multi-process broadcasting
- To add compression: Enable websockets per-message deflate