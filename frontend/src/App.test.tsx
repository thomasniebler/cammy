import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import App from './App'

// No real WebSocket in tests
vi.mock('./hooks/useWebSocket', () => ({
  useWebSocket: () => ({ lastMessage: null, wsConnected: true }),
}))

type Handler = (init?: RequestInit) => { status?: number; body?: unknown } | Promise<never>

const CAMERAS = {
  current: 0,
  cameras: [
    { index: 0, name: 'Cam A (/dev/video0)' },
    { index: 2, name: 'Cam B (/dev/video2)' },
  ],
}

let identities: string[]
let handlers: Record<string, Handler>
let calls: { url: string; method: string; body?: string }[]

function installFetch() {
  calls = []
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    calls.push({ url, method, body: init?.body as string | undefined })
    const key = `${method} ${url}`
    const handler = handlers[key]
    if (!handler) return new Response(JSON.stringify({}), { status: 200 })
    const out = await handler(init)
    return new Response(JSON.stringify(out.body ?? {}), { status: out.status ?? 200 })
  }) as unknown as typeof fetch
}

beforeEach(() => {
  // jsdom has no canvas; App draws detection overlays on one
  HTMLCanvasElement.prototype.getContext = (() =>
    new Proxy({}, { get: () => () => undefined, set: () => true })) as never
  identities = []
  handlers = {
    'GET /api/cameras': () => ({ body: CAMERAS }),
    'GET /api/identities': () => ({ body: { identities } }),
    'GET /api/commands': () => ({ body: { commands: [] } }),
    'GET /api/gestures/mapping': () => ({ body: { mappings: [] } }),
  }
  installFetch()
})

afterEach(() => cleanup())

const cameraSelect = () => screen.getByLabelText('Camera') as HTMLSelectElement
const streamSrc = () => (screen.getByAltText('Camera feed') as HTMLImageElement).getAttribute('src')

describe('camera selection', () => {
  it('lists cameras and selects the current one (fetchCameras)', async () => {
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))
    expect(cameraSelect().value).toBe('0')
    expect(screen.getByText('Cam B (/dev/video2)')).toBeTruthy()
  })

  it('survives an unreachable API when listing cameras', async () => {
    handlers['GET /api/cameras'] = () => Promise.reject(new Error('down')) as never
    render(<App />)
    await waitFor(() => expect(calls.some(c => c.url === '/api/cameras')).toBe(true))
    expect(cameraSelect().options.length).toBe(0)
  })

  it('POSTs the chosen device, refreshes the list and reconnects the stream', async () => {
    handlers['POST /api/camera'] = () => {
      handlers['GET /api/cameras'] = () => ({ body: { ...CAMERAS, current: 2 } })
      return { body: { status: 'ok', current: 2 } }
    }
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))
    expect(streamSrc()).toBe('/api/video/stream?k=0')

    fireEvent.change(cameraSelect(), { target: { value: '2' } })

    await waitFor(() => expect(streamSrc()).toBe('/api/video/stream?k=1'))
    const post = calls.find(c => c.method === 'POST' && c.url === '/api/camera')!
    expect(JSON.parse(post.body!)).toEqual({ device_index: 2 })
    await waitFor(() => expect(cameraSelect().value).toBe('2'))
  })

  it('shows the server error when the camera cannot be opened', async () => {
    handlers['POST /api/camera'] = () => ({ status: 422, body: { detail: 'Cannot open camera 2' } })
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))

    fireEvent.change(cameraSelect(), { target: { value: '2' } })

    expect(await screen.findByText('Cannot open camera 2')).toBeTruthy()
    // still reconnects so the picture shows whichever camera the server kept
    await waitFor(() => expect(streamSrc()).toBe('/api/video/stream?k=1'))
  })

  it('shows "API not available" when the switch request fails', async () => {
    handlers['POST /api/camera'] = () => Promise.reject(new Error('down')) as never
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))

    fireEvent.change(cameraSelect(), { target: { value: '2' } })

    expect(await screen.findByText('API not available')).toBeTruthy()
  })
})

describe('identity enrollment', () => {
  const nameInput = () => screen.getByPlaceholderText('Name, then face the camera') as HTMLInputElement
  const enrollButton = () => screen.getByRole('button', { name: /Enroll from camera/ }) as HTMLButtonElement

  it('disables enrolling for a blank name', async () => {
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))
    expect(enrollButton().disabled).toBe(true)
    fireEvent.change(nameInput(), { target: { value: '   ' } })
    expect(enrollButton().disabled).toBe(true)
    fireEvent.change(nameInput(), { target: { value: 'Alice' } })
    expect(enrollButton().disabled).toBe(false)
  })

  it('enrolls, reports success, clears the input and refreshes identities', async () => {
    handlers['POST /api/identities'] = () => {
      identities = ['Alice']
      return { body: { status: 'ok', name: 'Alice' } }
    }
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))

    fireEvent.change(nameInput(), { target: { value: ' Alice ' } })
    fireEvent.click(enrollButton())

    expect(await screen.findByText('Enrolled "Alice"')).toBeTruthy()
    const post = calls.find(c => c.method === 'POST' && c.url === '/api/identities')!
    expect(JSON.parse(post.body!)).toEqual({ name: 'Alice' }) // trimmed
    expect(nameInput().value).toBe('')
    expect(await screen.findByText('Alice')).toBeTruthy() // list refreshed
  })

  it('shows the server error and keeps the name when enrollment fails', async () => {
    handlers['POST /api/identities'] = () => ({ status: 422, body: { detail: 'Could not enroll: no face detected' } })
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))

    fireEvent.change(nameInput(), { target: { value: 'Bob' } })
    fireEvent.click(enrollButton())

    expect(await screen.findByText('Could not enroll: no face detected')).toBeTruthy()
    expect(nameInput().value).toBe('Bob')
  })

  it('shows "API not available" when the request itself fails', async () => {
    handlers['POST /api/identities'] = () => Promise.reject(new Error('down')) as never
    render(<App />)
    await waitFor(() => expect(cameraSelect().options.length).toBe(2))

    fireEvent.change(nameInput(), { target: { value: 'Bob' } })
    fireEvent.click(enrollButton())

    expect(await screen.findByText('API not available')).toBeTruthy()
    expect(enrollButton().disabled).toBe(false) // enrolling flag reset
  })
})
