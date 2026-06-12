export interface WsEvent {
  type: string
  [key: string]: unknown
}

export class WsClient {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectDelay = 30000
  private listeners: Map<string, Set<(data: WsEvent) => void>> = new Map()
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null
  public connected = false

  constructor(private url: string) {}

  connect(token: string) {
    this.disconnect()
    const wsUrl = `${this.url}?token=${token}`
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      this.connected = true
      this.reconnectAttempts = 0
      this.startHeartbeat()
      this.emit({ type: 'ws_connected' })
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WsEvent
        this.emit(data)
      } catch { /* ignore */ }
    }

    this.ws.onclose = () => {
      this.connected = false
      this.stopHeartbeat()
      this.emit({ type: 'ws_disconnected' })
      this.scheduleReconnect(token)
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  disconnect() {
    this.stopHeartbeat()
    this.reconnectAttempts = 999 // prevent reconnect
    this.ws?.close()
    this.ws = null
    this.connected = false
  }

  send(data: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  on(type: string, handler: (data: WsEvent) => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set())
    }
    this.listeners.get(type)!.add(handler)
  }

  off(type: string, handler: (data: WsEvent) => void) {
    this.listeners.get(type)?.delete(handler)
  }

  private emit(data: WsEvent) {
    const handlers = this.listeners.get(data.type)
    if (handlers) {
      handlers.forEach(h => h(data))
    }
    // Also notify wildcard listeners
    const wildcardHandlers = this.listeners.get('*')
    if (wildcardHandlers) {
      wildcardHandlers.forEach(h => h(data))
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatInterval = setInterval(() => {
      this.send({ type: 'ping' })
    }, 25000)
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  private scheduleReconnect(token: string) {
    if (this.reconnectAttempts >= 20) return
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay)
    this.reconnectAttempts++
    setTimeout(() => this.connect(token), delay)
  }
}

let instance: WsClient | null = null

export function getWsClient(): WsClient {
  if (!instance) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    instance = new WsClient(`${protocol}//${location.host}/ws`)
  }
  return instance
}
