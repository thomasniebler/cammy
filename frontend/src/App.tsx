import { useState, useEffect, useRef, useCallback } from 'react'

interface DetectedFace {
  id: string
  identity: string
  confidence: number
  bbox?: { x: number; y: number; width: number; height: number }
}

interface DetectedHand {
  id: string
  type: string
  confidence: number
  hand: string
}

interface Identity {
  name: string
  enrolled: boolean
}

interface GestureMapping {
  gesture: string
  action: string
}

type Tab = 'main' | 'overview' | 'quickstart' | 'config'

const DOCS = {
  overview: [
    { type: 'h1', content: 'Cammy Overview' },
    { type: 'p', content: 'Cammy is a real-time face detection and hand gesture recognition system.' },
    { type: 'h2', content: 'Features' },
    { type: 'h3', content: 'Face Recognition' },
    { type: 'li', content: 'Real-time face detection using MediaPipe' },
    { type: 'li', content: 'Face identification using DeepFace (ArcFace model)' },
    { type: 'li', content: 'Identity enrollment - add new faces' },
    { type: 'li', content: 'Unknown face detection' },
    { type: 'h3', content: 'Hand Gesture Recognition' },
    { type: 'li', content: '21-point hand tracking with MediaPipe' },
    { type: 'li', content: 'Fist = Pause, Open Palm = Play' },
    { type: 'li', content: 'Thumbs Up/Down = Volume control' },
    { type: 'li', content: 'Peace = Next track' },
    { type: 'h3', content: 'Action System' },
    { type: 'li', content: 'Keyboard automation (pyautogui)' },
    { type: 'li', content: 'Webhook triggers' },
    { type: 'li', content: 'Shell command execution' },
    { type: 'li', content: 'Debouncing to prevent spam' },
    { type: 'h2', content: 'Use Cases' },
    { type: 'li', content: 'Media control without touching keyboard' },
    { type: 'li', content: 'Presentation navigation' },
    { type: 'li', content: 'Touchless computer control' },
    { type: 'li', content: 'Smart home automation via webhooks' },
  ],
  quickstart: [
    { type: 'h1', content: 'Quickstart Guide' },
    { type: 'p', content: 'Get Cammy running in 5 minutes.' },
    { type: 'h2', content: 'Installation' },
    { type: 'code', content: 'git clone <repo-url>' },
    { type: 'code', content: 'cd cammy/backend' },
    { type: 'code', content: 'uv pip install -e ".[dev]"' },
    { type: 'code', content: 'cd ../frontend && npm install' },
    { type: 'h2', content: 'Starting Backend' },
    { type: 'code', content: 'cd backend' },
    { type: 'code', content: 'source .venv/bin/activate' },
    { type: 'code', content: 'python -m cammy.main' },
    { type: 'h2', content: 'Starting Frontend' },
    { type: 'code', content: 'cd frontend' },
    { type: 'code', content: 'npm run dev' },
    { type: 'p', content: 'Then open http://localhost:5173' },
    { type: 'h2', content: 'Default Gestures' },
    { type: 'li', content: '✊ Fist = Pause' },
    { type: 'li', content: '✋ Open Palm = Play' },
    { type: 'li', content: '👍 Thumbs Up = Volume up' },
    { type: 'li', content: '👎 Thumbs Down = Volume down' },
    { type: 'li', content: '✌️ Peace = Next track' },
    { type: 'h2', content: 'Troubleshooting' },
    { type: 'li', content: 'Camera not found: Check webcam connection' },
    { type: 'li', content: 'Low FPS: Set tier to low in config' },
    { type: 'li', content: 'Actions not working: pip install pyautogui' },
  ],
  config: [
    { type: 'h1', content: 'Configuration Guide' },
    { type: 'p', content: 'Config file: ~/.config/cammy/config.json' },
    { type: 'h2', content: 'Performance Settings' },
    { type: 'li', content: 'tier: auto/high/medium/low' },
    { type: 'li', content: 'target_fps: 1-60' },
    { type: 'li', content: 'detection_resolution: [width, height]' },
    { type: 'h2', content: 'Detection Settings' },
    { type: 'li', content: 'face_similarity_threshold: 0.65 (lower = more matches)' },
    { type: 'li', content: 'gesture_confidence_threshold: 0.80' },
    { type: 'li', content: 'max_faces: 5, max_hands: 2' },
    { type: 'h2', content: 'Available Actions' },
    { type: 'li', content: 'media_play, media_pause' },
    { type: 'li', content: 'media_next, media_prev' },
    { type: 'li', content: 'volume_up, volume_down, volume_mute' },
    { type: 'h2', content: 'REST API' },
    { type: 'p', content: 'GET /api/gestures/mapping - List mappings' },
    { type: 'p', content: 'POST /api/gestures/mapping - Update mapping' },
    { type: 'p', content: 'GET /api/identities - List identities' },
    { type: 'p', content: 'DELETE /api/identities/{name} - Delete identity' },
  ],
}

function renderDoc(doc: typeof DOCS['overview']) {
  return doc.map((item, i) => {
    switch (item.type) {
      case 'h1': return <h1 key={i}>{item.content}</h1>
      case 'h2': return <h2 key={i}>{item.content}</h2>
      case 'h3': return <h3 key={i}>{item.content}</h3>
      case 'li': return <li key={i}>{item.content}</li>
      case 'p': return <p key={i}>{item.content}</p>
      case 'code': return <code key={i}>{item.content}</code>
      default: return null
    }
  })
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('main')
  const [faces, setFaces] = useState<DetectedFace[]>([])
  const [hands, setHands] = useState<DetectedHand[]>([])
  const [identities, setIdentities] = useState<Identity[]>([])
  const [gestureMappings, setGestureMappings] = useState<GestureMapping[]>([])
  const [metrics] = useState({ fps: 0, faces: 0, hands: 0 })
  const [actionsEnabled, setActionsEnabled] = useState(true)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [cameraError, setCameraError] = useState<string | null>(null)

  const videoRef = useRef<HTMLVideoElement>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (stream && videoRef.current) {
      videoRef.current.srcObject = stream
    }
  }, [stream])

  useEffect(() => {
    async function initCamera() {
      try {
        const mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        })
        setStream(mediaStream)
      } catch (err) {
        setCameraError(err instanceof Error ? err.message : 'Camera error')
      }
    }
    initCamera()

    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop())
      }
    }
  }, [])

  useEffect(() => {
    fetchIdentities()
    fetchGestureMappings()
  }, [])

  async function fetchIdentities() {
    try {
      const res = await fetch('/api/identities')
      const data = await res.json()
      setIdentities((data.identities || []).map((name: string) => ({ name, enrolled: true })))
    } catch {
      setIdentities([])
    }
  }

  async function fetchGestureMappings() {
    try {
      const res = await fetch('/api/gestures/mapping')
      const data = await res.json()
      const mappings = data.mappings || {}
      setGestureMappings(
        Object.entries(mappings).map(([gesture, action]) => ({
          gesture,
          action: action as string,
        }))
      )
    } catch {
      setGestureMappings([
        { gesture: 'fist', action: 'media_pause' },
        { gesture: 'open_palm', action: 'media_play' },
        { gesture: 'thumbs_up', action: 'volume_up' },
        { gesture: 'thumbs_down', action: 'volume_down' },
        { gesture: 'peace', action: 'media_next' },
      ])
    }
  }

  async function handleDeleteIdentity(name: string) {
    try {
      await fetch(`/api/identities/${name}`, { method: 'DELETE' })
      setIdentities(prev => prev.filter(i => i.name !== name))
    } catch {
      // API not available
    }
  }

  async function handleMappingChange(gesture: string, action: string) {
    try {
      await fetch('/api/gestures/mapping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gesture, action }),
      })
      setGestureMappings(prev =>
        prev.map(m => (m.gesture === gesture ? { ...m, action } : m))
      )
    } catch {
      // API not available
    }
  }

  async function toggleActions() {
    const endpoint = actionsEnabled ? '/api/action/disable' : '/api/action/enable'
    try {
      await fetch(endpoint, { method: 'POST' })
      setActionsEnabled(!actionsEnabled)
    } catch {
      // API not available
    }
  }

  const drawDetections = useCallback(() => {
    const canvas = overlayCanvasRef.current
    const video = videoRef.current
    if (!canvas || !video) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    faces.forEach(face => {
      if (!face.bbox) return
      const { x, y, width, height } = face.bbox
      
      ctx.strokeStyle = '#22c55e'
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, width, height)
      
      ctx.fillStyle = '#22c55e'
      ctx.font = '12px sans-serif'
      ctx.fillText(`${face.identity} (${(face.confidence * 100).toFixed(0)}%)`, x, y - 5)
    })

    hands.forEach(hand => {
      const gestureText = `${hand.type} (${(hand.confidence * 100).toFixed(0)}%)`
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
      ctx.fillRect(10, canvas.height - 30, 120, 20)
      ctx.fillStyle = 'white'
      ctx.font = '12px sans-serif'
      ctx.fillText(gestureText, 15, canvas.height - 15)
    })
  }, [faces, hands])

  useEffect(() => {
    drawDetections()
  }, [drawDetections])

  return (
    <div className="app">
      <header>
        <h1>Cammy</h1>
        <nav className="nav-tabs">
          <button 
            className={activeTab === 'main' ? 'active' : ''} 
            onClick={() => setActiveTab('main')}
          >
            Main
          </button>
          <button 
            className={activeTab === 'overview' ? 'active' : ''} 
            onClick={() => setActiveTab('overview')}
          >
            Help
          </button>
        </nav>
      </header>

      {activeTab === 'main' && (
        <div className="main-content">
          <div className="card camera-container">
            {cameraError ? (
              <div className="no-camera">{cameraError}</div>
            ) : (
              <>
                <video ref={videoRef} autoPlay playsInline muted />
                <canvas ref={overlayCanvasRef} className="camera-overlay" />
              </>
            )}
          </div>

          <div className="sidebar">
            <div className="card">
              <h2>Identities</h2>
              <div className="identity-list">
                {identities.length === 0 ? (
                  <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>No identities enrolled</p>
                ) : (
                  identities.map(identity => (
                    <div key={identity.name} className="identity-item">
                      <span>{identity.name}</span>
                      <button onClick={() => handleDeleteIdentity(identity.name)}>Delete</button>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="card">
              <h2>Gesture Mappings</h2>
              <div className="gesture-mapping">
                {gestureMappings.map(mapping => (
                  <div key={mapping.gesture} className="mapping-item">
                    <span>{mapping.gesture}</span>
                    <select
                      value={mapping.action}
                      onChange={(e) => handleMappingChange(mapping.gesture, e.target.value)}
                    >
                      <option value="media_play">Play</option>
                      <option value="media_pause">Pause</option>
                      <option value="media_next">Next</option>
                      <option value="media_prev">Previous</option>
                      <option value="volume_up">Volume Up</option>
                      <option value="volume_down">Volume Down</option>
                      <option value="volume_mute">Mute</option>
                    </select>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <h2>Metrics</h2>
              <div className="metrics">
                <div className="metric-row">
                  <span>FPS</span>
                  <span>{metrics.fps}</span>
                </div>
                <div className="metric-row">
                  <span>Faces</span>
                  <span>{metrics.faces}</span>
                </div>
                <div className="metric-row">
                  <span>Hands</span>
                  <span>{metrics.hands}</span>
                </div>
              </div>
            </div>

            <div className="card">
              <button
                className={`button ${actionsEnabled ? 'button-secondary' : 'button-primary'}`}
                onClick={toggleActions}
              >
                {actionsEnabled ? 'Disable Actions' : 'Enable Actions'}
              </button>
            </div>

            <div className="card">
              <button
                className="button button-secondary"
                onClick={() => setActiveTab('overview')}
              >
                View Help & Docs
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'overview' && (
        <div className="doc-content">
          <div className="card">
            <ul>{renderDoc(DOCS.quickstart)}</ul>
            <hr />
            <ul>{renderDoc(DOCS.config)}</ul>
          </div>
          <div className="card">
            <button
              className="button button-secondary"
              onClick={() => setActiveTab('main')}
            >
              Back to Main
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default App