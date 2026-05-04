import { useState, useEffect, useRef, useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'

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
  pointer?: { x: number; y: number }
}

interface Identity {
  name: string
  enrolled: boolean
}

interface Command {
  name: string
  label: string
  type: 'keypress' | 'shell' | 'webhook'
  payload: Record<string, unknown>
  cooldown_ms: number
}

interface GestureMapping {
  gesture: string
  action: string
  label: string
}

interface LastAction {
  action_name: string
  label: string
  gesture: string
  timestamp: number   // seconds (unix)
  cooldown_ms: number
}

type Tab = 'main' | 'overview'

const GESTURE_EMOJI: Record<string, string> = {
  fist: '✊',
  open_palm: '✋',
  thumbs_up: '👍',
  thumbs_down: '👎',
  peace: '✌️',
  pointing: '☝️',
  ok_sign: '👌',
}

const DOCS_QUICKSTART = [
  { type: 'h1', content: 'Quickstart Guide' },
  { type: 'h2', content: 'Starting Backend' },
  { type: 'code', content: 'task backend:run' },
  { type: 'h2', content: 'Starting Frontend' },
  { type: 'code', content: 'task frontend:dev' },
  { type: 'p', content: 'Then open http://localhost:5173' },
  { type: 'h2', content: 'Default Gestures' },
  { type: 'li', content: '✊ Fist = Pause' },
  { type: 'li', content: '✋ Open Palm = Play' },
  { type: 'li', content: '👍 Thumbs Up = Volume up' },
  { type: 'li', content: '👎 Thumbs Down = Volume down' },
  { type: 'li', content: '✌️ Peace = Next track' },
  { type: 'h2', content: 'Custom Commands' },
  { type: 'li', content: 'Add commands in the Commands panel' },
  { type: 'li', content: 'Types: keypress, shell, webhook' },
  { type: 'li', content: 'Assign any command to any gesture' },
]

function renderDoc(doc: typeof DOCS_QUICKSTART) {
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

// ── Blank command template ────────────────────────────────────────────────────
function blankCommand(): Omit<Command, 'name'> & { name: string } {
  return { name: '', label: '', type: 'keypress', payload: { key: '' }, cooldown_ms: 1000 }
}

// ── CommandForm ───────────────────────────────────────────────────────────────
function CommandForm({
  initial,
  isNew,
  onSave,
  onCancel,
}: {
  initial: Command
  isNew: boolean
  onSave: (cmd: Command) => void
  onCancel: () => void
}) {
  const [cmd, setCmd] = useState<Command>({ ...initial })

  function setPayloadField(key: string, value: unknown) {
    setCmd(c => ({ ...c, payload: { ...c.payload, [key]: value } }))
  }

  function handleTypeChange(t: Command['type']) {
    const defaults: Record<Command['type'], Record<string, unknown>> = {
      keypress: { key: '' },
      shell:    { command: '' },
      webhook:  { url: '', method: 'POST', body: '{}' },
    }
    setCmd(c => ({ ...c, type: t, payload: defaults[t] }))
  }

  return (
    <div className="cmd-form">
      {isNew && (
        <div className="cmd-form-row">
          <label>ID</label>
          <input
            type="text"
            placeholder="my_command"
            value={cmd.name}
            onChange={e => setCmd(c => ({ ...c, name: e.target.value.replace(/\s/g, '_').toLowerCase() }))}
          />
        </div>
      )}
      <div className="cmd-form-row">
        <label>Label</label>
        <input
          type="text"
          placeholder="My Command"
          value={cmd.label}
          onChange={e => setCmd(c => ({ ...c, label: e.target.value }))}
        />
      </div>
      <div className="cmd-form-row">
        <label>Type</label>
        <select value={cmd.type} onChange={e => handleTypeChange(e.target.value as Command['type'])}>
          <option value="keypress">Keypress</option>
          <option value="shell">Shell</option>
          <option value="webhook">Webhook</option>
        </select>
      </div>

      {cmd.type === 'keypress' && (
        <>
          <div className="cmd-form-row">
            <label>Key</label>
            <input
              type="text"
              placeholder="e.g. play, volumeup, ctrl+c"
              value={String(cmd.payload.key ?? '')}
              onChange={e => setPayloadField('key', e.target.value)}
            />
          </div>
          <div className="cmd-form-row">
            <label>Count</label>
            <input
              type="number"
              min={1}
              max={20}
              value={Number(cmd.payload.count ?? 1)}
              onChange={e => setPayloadField('count', parseInt(e.target.value, 10) || 1)}
            />
          </div>
        </>
      )}

      {cmd.type === 'shell' && (
        <div className="cmd-form-row">
          <label>Command</label>
          <input
            type="text"
            placeholder="e.g. notify-send 'hello'"
            value={String(cmd.payload.command ?? '')}
            onChange={e => setPayloadField('command', e.target.value)}
          />
        </div>
      )}

      {cmd.type === 'webhook' && (
        <>
          <div className="cmd-form-row">
            <label>URL</label>
            <input
              type="text"
              placeholder="https://..."
              value={String(cmd.payload.url ?? '')}
              onChange={e => setPayloadField('url', e.target.value)}
            />
          </div>
          <div className="cmd-form-row">
            <label>Method</label>
            <select
              value={String(cmd.payload.method ?? 'POST')}
              onChange={e => setPayloadField('method', e.target.value)}
            >
              <option>GET</option>
              <option>POST</option>
              <option>PUT</option>
            </select>
          </div>
          <div className="cmd-form-row">
            <label>Body JSON</label>
            <input
              type="text"
              placeholder='{}'
              value={String(cmd.payload.body ?? '{}')}
              onChange={e => setPayloadField('body', e.target.value)}
            />
          </div>
        </>
      )}

      <div className="cmd-form-row">
        <label>Cooldown (ms)</label>
        <input
          type="number"
          min={100}
          step={100}
          value={cmd.cooldown_ms}
          onChange={e => setCmd(c => ({ ...c, cooldown_ms: parseInt(e.target.value, 10) || 1000 }))}
        />
      </div>

      <div className="cmd-form-actions">
        <button className="button button-primary" onClick={() => onSave(cmd)}>Save</button>
        <button className="button button-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

// ── CooldownBar ───────────────────────────────────────────────────────────────
function CooldownBar({ lastAction }: { lastAction: LastAction | null }) {
  const [progress, setProgress] = useState(0)  // 0–1, 1 = full (just fired)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (!lastAction) { setProgress(0); return }

    function tick() {
      const elapsed = Date.now() / 1000 - lastAction!.timestamp
      const fraction = Math.max(0, 1 - elapsed / (lastAction!.cooldown_ms / 1000))
      setProgress(fraction)
      if (fraction > 0) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [lastAction])

  if (!lastAction) {
    return (
      <div className="last-action last-action-empty">
        <span>No action yet</span>
      </div>
    )
  }

  const emoji = GESTURE_EMOJI[lastAction.gesture] ?? '🖐️'
  const ready = progress === 0

  return (
    <div className="last-action">
      <div className="last-action-info">
        <span className="last-action-emoji">{emoji}</span>
        <div>
          <div className="last-action-label">{lastAction.label || lastAction.action_name}</div>
          <div className="last-action-gesture">{lastAction.gesture}</div>
        </div>
        <span className={`last-action-status ${ready ? 'ready' : 'cooling'}`}>
          {ready ? '✓ Ready' : '⏳ Cooling'}
        </span>
      </div>
      <div className="cooldown-bar-container">
        <div
          className="cooldown-bar"
          style={{ width: `${(progress * 100).toFixed(1)}%` }}
        />
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────
function App() {
  const [activeTab, setActiveTab] = useState<Tab>('main')
  const [faces, setFaces] = useState<DetectedFace[]>([])
  const [hands, setHands] = useState<DetectedHand[]>([])
  const [identities, setIdentities] = useState<Identity[]>([])
  const [commands, setCommands] = useState<Command[]>([])
  const [gestureMappings, setGestureMappings] = useState<GestureMapping[]>([])
  const [actionsEnabled, setActionsEnabled] = useState(true)
  const [lastAction, setLastAction] = useState<LastAction | null>(null)

  // Command editor state
  const [editingCmd, setEditingCmd] = useState<Command | null>(null)
  const [isNewCmd, setIsNewCmd] = useState(false)

  const overlayCanvasRef = useRef<HTMLCanvasElement>(null)

  const wsUrl = `${window.location.protocol.replace('http', 'ws')}//${window.location.host}/ws`
  const { lastMessage, wsConnected } = useWebSocket(wsUrl)

  // ── WebSocket messages ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!lastMessage) return
    try {
      const data = JSON.parse(lastMessage)
      if (data.type === 'faces' || data.type === 'camera_frame') {
        setFaces(data.faces || [])
      }
      if (data.type === 'gestures' || data.type === 'camera_frame') {
        setHands(data.gestures || [])
      }
      if (data.type === 'action_executed') {
        setLastAction({
          action_name: data.action_name,
          label: data.label,
          gesture: data.gesture,
          timestamp: data.timestamp,
          cooldown_ms: data.cooldown_ms,
        })
      }
    } catch {
      // ignore malformed messages
    }
  }, [lastMessage])

  // ── Initial fetches ─────────────────────────────────────────────────────────
  useEffect(() => {
    fetchIdentities()
    fetchCommands()
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

  async function fetchCommands() {
    try {
      const res = await fetch('/api/commands')
      const data = await res.json()
      setCommands(data.commands || [])
    } catch {
      setCommands([])
    }
  }

  async function fetchGestureMappings() {
    try {
      const res = await fetch('/api/gestures/mapping')
      const data = await res.json()
      const mappings = data.mappings || {}
      setGestureMappings(
        Object.entries(mappings).map(([gesture, val]) => {
          const v = val as { action: string; label: string } | string
          if (typeof v === 'string') return { gesture, action: v, label: v }
          return { gesture, action: v.action, label: v.label }
        })
      )
    } catch {
      setGestureMappings([
        { gesture: 'fist',        action: 'media_pause', label: 'Pause' },
        { gesture: 'open_palm',   action: 'media_play',  label: 'Play' },
        { gesture: 'thumbs_up',   action: 'volume_up',   label: 'Volume Up' },
        { gesture: 'thumbs_down', action: 'volume_down', label: 'Volume Down' },
        { gesture: 'peace',       action: 'media_next',  label: 'Next Track' },
      ])
    }
  }

  // ── Identities ──────────────────────────────────────────────────────────────
  async function handleDeleteIdentity(name: string) {
    try {
      await fetch(`/api/identities/${name}`, { method: 'DELETE' })
      setIdentities(prev => prev.filter(i => i.name !== name))
    } catch { /* API not available */ }
  }

  // ── Gesture mapping ─────────────────────────────────────────────────────────
  async function handleMappingChange(gesture: string, action: string) {
    try {
      await fetch('/api/gestures/mapping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gesture, action }),
      })
      const cmd = commands.find(c => c.name === action)
      setGestureMappings(prev =>
        prev.map(m => m.gesture === gesture ? { ...m, action, label: cmd?.label ?? action } : m)
      )
    } catch { /* API not available */ }
  }

  // ── Commands CRUD ───────────────────────────────────────────────────────────
  async function handleSaveCommand(cmd: Command) {
    try {
      if (isNewCmd) {
        const res = await fetch('/api/commands', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cmd),
        })
        if (res.ok) {
          const saved: Command = await res.json()
          setCommands(prev => [...prev, saved])
        }
      } else {
        const { name, ...body } = cmd
        const res = await fetch(`/api/commands/${name}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (res.ok) {
          const saved: Command = await res.json()
          setCommands(prev => prev.map(c => c.name === saved.name ? saved : c))
        }
      }
    } catch { /* API not available */ }
    setEditingCmd(null)
  }

  async function handleDeleteCommand(name: string) {
    try {
      await fetch(`/api/commands/${name}`, { method: 'DELETE' })
      setCommands(prev => prev.filter(c => c.name !== name))
    } catch { /* API not available */ }
  }

  // ── Toggle actions ──────────────────────────────────────────────────────────
  async function toggleActions() {
    const endpoint = actionsEnabled ? '/api/action/disable' : '/api/action/enable'
    try {
      await fetch(endpoint, { method: 'POST' })
      setActionsEnabled(!actionsEnabled)
    } catch { /* API not available */ }
  }

  // ── Canvas overlay ──────────────────────────────────────────────────────────
  const drawDetections = useCallback(() => {
    const canvas = overlayCanvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    canvas.width = 640
    canvas.height = 480
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    faces.forEach(face => {
      if (!face.bbox) return
      const { x, y, width, height } = face.bbox
      ctx.strokeStyle = '#22c55e'
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, width, height)
      ctx.fillStyle = '#22c55e'
      ctx.font = '12px sans-serif'
      ctx.fillText(`${face.identity ?? 'unknown'} (${(face.confidence * 100).toFixed(0)}%)`, x, y - 5)
    })

    if (hands.length > 0) {
      const gestureText = hands.map(h => `${h.type} (${(h.confidence * 100).toFixed(0)}%)`).join(', ')
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
      ctx.fillRect(10, canvas.height - 30, Math.min(gestureText.length * 7, 300), 20)
      ctx.fillStyle = 'white'
      ctx.font = '12px sans-serif'
      ctx.fillText(gestureText, 15, canvas.height - 15)
    }

    // Draw red dot for pointing gesture (index fingertip position)
    hands.forEach(hand => {
      if (hand.type === 'pointing' && hand.pointer) {
        // Mirror X to match the typical mirrored camera preview
        const dotX = (1 - hand.pointer.x) * canvas.width
        const dotY = hand.pointer.y * canvas.height

        // Outer glow ring
        ctx.beginPath()
        ctx.arc(dotX, dotY, 14, 0, Math.PI * 2)
        ctx.fillStyle = 'rgba(239, 68, 68, 0.25)'
        ctx.fill()

        // Solid red dot
        ctx.beginPath()
        ctx.arc(dotX, dotY, 8, 0, Math.PI * 2)
        ctx.fillStyle = 'rgba(239, 68, 68, 0.9)'
        ctx.fill()
        ctx.strokeStyle = 'white'
        ctx.lineWidth = 2
        ctx.stroke()
      }
    })
  }, [faces, hands])

  useEffect(() => { drawDetections() }, [drawDetections])

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      <header>
        <h1>Cammy</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div className="status">
            <div className={`status-dot ${wsConnected ? 'status-connected' : 'status-disconnected'}`} />
            <span>{wsConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <nav className="nav-tabs">
            <button className={activeTab === 'main' ? 'active' : ''} onClick={() => setActiveTab('main')}>Main</button>
            <button className={activeTab === 'overview' ? 'active' : ''} onClick={() => setActiveTab('overview')}>Help</button>
          </nav>
        </div>
      </header>

      {activeTab === 'main' && (
        <div className="main-content">
          {/* ── Camera ── */}
          <div className="card camera-container">
            <img src="/api/video/stream" alt="Camera feed" />
            <canvas ref={overlayCanvasRef} className="camera-overlay" />
          </div>

          {/* ── Sidebar ── */}
          <div className="sidebar">

            {/* Last Action */}
            <div className="card">
              <h2>Last Action</h2>
              <CooldownBar lastAction={lastAction} />
            </div>

            {/* Commands */}
            <div className="card">
              <div className="card-header-row">
                <h2>Commands</h2>
                {!editingCmd && (
                  <button
                    className="button button-primary btn-sm"
                    onClick={() => { setEditingCmd(blankCommand() as Command); setIsNewCmd(true) }}
                  >
                    + New
                  </button>
                )}
              </div>

              {editingCmd && isNewCmd && (
                <CommandForm
                  initial={editingCmd}
                  isNew
                  onSave={handleSaveCommand}
                  onCancel={() => setEditingCmd(null)}
                />
              )}

              <div className="cmd-list">
                {commands.length === 0 && <p className="empty-hint">No commands yet</p>}
                {commands.map(cmd => (
                  <div key={cmd.name} className="cmd-item">
                    {editingCmd?.name === cmd.name && !isNewCmd ? (
                      <CommandForm
                        initial={cmd}
                        isNew={false}
                        onSave={handleSaveCommand}
                        onCancel={() => setEditingCmd(null)}
                      />
                    ) : (
                      <div className="cmd-item-row">
                        <div>
                          <span className="cmd-label">{cmd.label || cmd.name}</span>
                          <span className="cmd-type">{cmd.type}</span>
                        </div>
                        <div className="cmd-item-actions">
                          <button
                            className="btn-icon"
                            title="Edit"
                            onClick={() => { setEditingCmd(cmd); setIsNewCmd(false) }}
                          >✏️</button>
                          <button
                            className="btn-icon btn-danger"
                            title="Delete"
                            onClick={() => handleDeleteCommand(cmd.name)}
                          >🗑️</button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Gesture Mappings */}
            <div className="card">
              <h2>Gesture Mappings</h2>
              <div className="gesture-mapping">
                {gestureMappings.map(mapping => (
                  <div key={mapping.gesture} className="mapping-item">
                    <span>{GESTURE_EMOJI[mapping.gesture] ?? '🤚'} {mapping.gesture}</span>
                    <select
                      value={mapping.action}
                      onChange={(e) => handleMappingChange(mapping.gesture, e.target.value)}
                    >
                      {commands.map(cmd => (
                        <option key={cmd.name} value={cmd.name}>{cmd.label || cmd.name}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>

            {/* Identities */}
            <div className="card">
              <h2>Identities</h2>
              <div className="identity-list">
                {identities.length === 0 ? (
                  <p className="empty-hint">No identities enrolled</p>
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

            {/* Metrics */}
            <div className="card">
              <h2>Metrics</h2>
              <div className="metrics">
                <div className="metric-row"><span>Faces</span><span>{faces.length}</span></div>
                <div className="metric-row"><span>Hands</span><span>{hands.length}</span></div>
                <div className="metric-row"><span>Backend</span><span>{wsConnected ? '🟢' : '🔴'}</span></div>
              </div>
            </div>

            {/* Toggle actions */}
            <div className="card">
              <button
                className={`button ${actionsEnabled ? 'button-secondary' : 'button-primary'}`}
                onClick={toggleActions}
                style={{ width: '100%' }}
              >
                {actionsEnabled ? 'Disable Actions' : 'Enable Actions'}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'overview' && (
        <div className="doc-content">
          <div className="card">
            <ul>{renderDoc(DOCS_QUICKSTART)}</ul>
          </div>
          <div className="card">
            <button className="button button-secondary" onClick={() => setActiveTab('main')}>
              Back to Main
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
