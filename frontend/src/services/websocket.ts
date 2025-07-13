export class WebSocketService {
  private ws: WebSocket | null = null
  private conversationId: string
  private token: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 3  // Reduced from 5 to 3
  private reconnectDelay = 2000     // Increased from 1000 to 2000ms
  private isConnecting = false

  // Event handlers
  public onConnect: (() => void) | null = null
  public onDisconnect: (() => void) | null = null
  public onMessage: ((data: any) => void) | null = null
  public onError: ((error: Event) => void) | null = null

  constructor(conversationId: string, token: string) {
    this.conversationId = conversationId
    this.token = token
  }

  async connect(): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return
    }

    this.isConnecting = true

    try {
      const wsUrl = this.getWebSocketUrl()
      console.log('Attempting WebSocket connection to:', wsUrl)
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.isConnecting = false
        this.reconnectAttempts = 0
        if (this.onConnect) {
          this.onConnect()
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (this.onMessage) {
            this.onMessage(data)
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        this.isConnecting = false

        if (this.onDisconnect) {
          this.onDisconnect()
        }

        // Only attempt to reconnect for specific error codes and if not manually disconnected
        // 1006 = abnormal closure (but limit attempts), 1011 = server error, 1012 = service restart
        const shouldReconnect = this.reconnectAttempts < this.maxReconnectAttempts &&
          event.code !== 1000 && // Don't reconnect on normal closure
          event.code !== 1001 && // Don't reconnect on going away
          event.code !== 1005    // Don't reconnect on no status

        if (shouldReconnect) {
          // For 1006 errors, add extra delay to avoid rapid reconnection
          if (event.code === 1006) {
            console.log(`WebSocket closed abnormally (1006), scheduling delayed reconnect...`)
            setTimeout(() => this.scheduleReconnect(), 3000) // Extra 3 second delay for 1006
          } else {
            console.log(`WebSocket closed with code ${event.code}, scheduling reconnect...`)
            this.scheduleReconnect()
          }
        } else {
          console.log(`WebSocket closed with code ${event.code}, not reconnecting (attempts: ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.isConnecting = false

        if (this.onError) {
          this.onError(error)
        }
      }

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      this.isConnecting = false
      throw error
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }
    this.reconnectAttempts = this.maxReconnectAttempts // Prevent reconnection
  }

  sendMessage(content: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'send_message',
        content: content
      }
      this.ws.send(JSON.stringify(message))
    } else {
      console.error('WebSocket is not connected')
      throw new Error('WebSocket is not connected')
    }
  }

  interrupt(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'interrupt'
      }
      this.ws.send(JSON.stringify(message))
    } else {
      console.error('WebSocket is not connected')
      throw new Error('WebSocket is not connected')
    }
  }

  ping(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'ping'
      }
      this.ws.send(JSON.stringify(message))
    }
  }

  getHistory(limit = 50, offset = 0): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'get_history',
        limit,
        offset
      }
      this.ws.send(JSON.stringify(message))
    }
  }

  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // Use backend port (8000) instead of frontend port (3000)
    const host = window.location.hostname
    const port = '8000'  // Backend port
    return `${protocol}//${host}:${port}/api/v1/ws/conversations/${this.conversationId}?token=${this.token}`
  }

  private scheduleReconnect(): void {
    // Don't schedule reconnect if we're already at max attempts or manually disconnected
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnect attempts reached, giving up')
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000) // Cap at 30 seconds

    console.log(`Scheduling WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`)

    setTimeout(() => {
      // Double-check we still want to reconnect
      if (this.reconnectAttempts <= this.maxReconnectAttempts &&
        (!this.ws || this.ws.readyState === WebSocket.CLOSED)) {
        console.log(`Attempting WebSocket reconnect ${this.reconnectAttempts}/${this.maxReconnectAttempts}`)
        this.connect().catch(error => {
          console.error('Reconnect attempt failed:', error)
        })
      } else {
        console.log('Skipping reconnect - already connected or max attempts reached')
      }
    }, delay)
  }

  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  get readyState(): number {
    return this.ws ? this.ws.readyState : WebSocket.CLOSED
  }
}
