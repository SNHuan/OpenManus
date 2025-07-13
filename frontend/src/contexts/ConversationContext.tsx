import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { conversationApi } from '../services/api'
import { WebSocketService } from '../services/websocket'

interface Conversation {
  id: string
  title: string
  status: string
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}

interface Message {
  event_id: string
  event_type: string
  timestamp: string
  role: 'user' | 'assistant' | 'system' | 'progress'
  content: string
  status: string
  data: Record<string, any>
  isProgress?: boolean  // 标识是否为进度消息
  stepNumber?: number   // Agent步骤编号
  toolName?: string     // 工具名称
}

interface ConversationContextType {
  conversations: Conversation[]
  currentConversation: Conversation | null
  messages: Message[]
  loading: boolean
  isConnected: boolean
  isTyping: boolean
  createConversation: (title?: string) => Promise<Conversation>
  selectConversation: (conversationId: string) => Promise<void>
  sendMessage: (message: string) => Promise<void>
  interruptConversation: () => Promise<void>
  refreshConversations: () => Promise<void>
}

const ConversationContext = createContext<ConversationContextType | undefined>(undefined)

// Export hook separately to fix Fast Refresh compatibility
function useConversation() {
  const context = useContext(ConversationContext)
  if (context === undefined) {
    throw new Error('useConversation must be used within a ConversationProvider')
  }
  return context
}

export { useConversation }

interface ConversationProviderProps {
  children: ReactNode
}

export const ConversationProvider: React.FC<ConversationProviderProps> = ({ children }) => {
  const { user, token } = useAuth()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const wsServiceRef = useRef<WebSocketService | null>(null)
  const isSelectingRef = useRef<boolean>(false)

  const refreshConversations = useCallback(async () => {
    if (!user || !token) return

    try {
      setLoading(true)
      const userConversations = await conversationApi.getUserConversations(user.id, token)
      console.log('Raw API response:', userConversations)
      console.log('Response data:', userConversations.data)

      // The users API returns data directly, not wrapped in a data field
      const conversationsData = Array.isArray(userConversations.data) ? userConversations.data : (Array.isArray(userConversations) ? userConversations : [])
      console.log('Processed conversations data:', conversationsData)
      setConversations(conversationsData)
    } catch (error) {
      console.error('Failed to fetch conversations:', error)
    } finally {
      setLoading(false)
    }
  }, [user, token])

  const createConversation = useCallback(async (title?: string): Promise<Conversation> => {
    if (!token) throw new Error('Not authenticated')

    try {
      const response = await conversationApi.create({ title }, token)
      console.log('Create conversation response:', response)
      console.log('Create conversation data:', response.data)

      // Handle different response formats
      const conversationData = response.data || response

      if (!conversationData || !conversationData.id) {
        console.error('Invalid conversation data received:', conversationData)
        throw new Error('Invalid conversation data received from server')
      }

      setConversations(prev => [conversationData, ...prev])
      return conversationData
    } catch (error) {
      console.error('Failed to create conversation:', error)
      throw error
    }
  }, [token])

  const selectConversation = useCallback(async (conversationId: string) => {
    if (!token) return

    // Prevent concurrent selections
    if (isSelectingRef.current) {
      console.log('⚠️ Already selecting a conversation, skipping:', conversationId)
      return
    }

    isSelectingRef.current = true

    try {
      setLoading(true)

      // Disconnect from previous WebSocket
      if (wsServiceRef.current) {
        wsServiceRef.current.disconnect()
      }

      // Get conversation details
      console.log('📡 Fetching conversation details for:', conversationId)
      const conversation = await conversationApi.get(conversationId, token)
      console.log('📡 Raw conversation response:', conversation)
      console.log('📡 Conversation data:', conversation.data)

      // Check if conversation data exists
      const conversationData = conversation.data || conversation
      if (!conversationData || !conversationData.id) {
        console.error('❌ Invalid conversation data received:', conversationData)
        throw new Error('Invalid conversation data')
      }

      console.log('📡 Setting current conversation:', conversationData)
      setCurrentConversation(conversationData)

      // Get conversation history
      console.log('📡 Fetching conversation history for:', conversationId)
      const history = await conversationApi.getHistory(conversationId, token)
      console.log('📡 Raw history response:', history)

      // Check if history data exists
      const historyData = Array.isArray(history.data) ? history.data : (Array.isArray(history) ? history : [])
      console.log('📡 Setting messages:', historyData.length, 'messages')
      setMessages(historyData)

      // Connect to WebSocket for real-time updates
      console.log('🔌 Connecting to WebSocket for conversation:', conversationId)
      const ws = new WebSocketService(conversationId, token)

      ws.onConnect = () => {
        setIsConnected(true)
        console.log('✅ WebSocket connected')
      }

      ws.onDisconnect = () => {
        setIsConnected(false)
        console.log('❌ WebSocket disconnected')
      }

      ws.onMessage = (message) => {
        handleWebSocketMessage(message)
      }

      ws.onError = (error) => {
        console.error('❌ WebSocket error:', error)
        setIsConnected(false)
      }

      await ws.connect()
      wsServiceRef.current = ws

    } catch (error) {
      console.error('Failed to select conversation:', error)
    } finally {
      setLoading(false)
      isSelectingRef.current = false
    }
  }, [token]) // Removed currentConversation to prevent dependency loop

  const handleLLMStreamMessage = (data: any) => {
    const { content, is_complete, agent_name } = data

    setMessages(prev => {
      // Find existing streaming message or create new one
      const lastMessage = prev[prev.length - 1]

      if (lastMessage && lastMessage.status === 'streaming' && lastMessage.role === 'assistant') {
        // Update existing streaming message
        const updatedMessage = {
          ...lastMessage,
          content: lastMessage.content + content,
          status: is_complete ? 'complete' : 'streaming'
        }
        return [...prev.slice(0, -1), updatedMessage]
      } else {
        // Create new streaming message
        const streamingMessage: Message = {
          event_id: data.event_id,
          event_type: 'message.assistant',
          timestamp: data.timestamp,
          role: 'assistant',
          content: content,
          status: is_complete ? 'complete' : 'streaming',
          data: { agent_name }
        }
        return [...prev, streamingMessage]
      }
    })

    if (is_complete) {
      setIsTyping(false)
    } else {
      setIsTyping(true)
    }
  }

  const handleToolResultMessage = (data: any) => {
    const { tool_name, result, truncated } = data

    // Filter out terminate tool results - they're not needed for display
    if (tool_name === 'terminate') {
      return
    }

    const toolResultMessage: Message = {
      event_id: data.event_id,
      event_type: 'tool.result',
      timestamp: data.timestamp,
      role: 'system',
      content: `🔧 Tool: ${tool_name}\n${result}${truncated ? '\n(Result truncated for display)' : ''}`,
      status: 'complete',
      data: { tool_name, truncated }
    }

    setMessages(prev => [...prev, toolResultMessage])
  }

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'message.user':
      case 'message.assistant':
        const newMessage: Message = {
          event_id: data.event_id,
          event_type: data.type,
          timestamp: data.timestamp,
          role: data.role,
          content: data.content,
          status: 'complete',
          data: data.data || {}
        }
        setMessages(prev => [...prev, newMessage])
        setIsTyping(false)
        break

      case 'llm.stream':
        handleLLMStreamMessage(data)
        break

      case 'tool.result':
        handleToolResultMessage(data)
        break

      case 'agent.step_start':
        // Show simple step start indicator
        const stepStartMessage: Message = {
          event_id: data.event_id,
          event_type: data.type,
          timestamp: data.timestamp,
          role: 'progress',
          content: `🤔 Thinking... (Step ${data.step}/${data.total_steps})`,
          status: 'running',
          data: data,
          isProgress: true,
          stepNumber: data.step
        }
        setMessages(prev => [...prev, stepStartMessage])
        setIsTyping(true)
        break

      case 'agent.step_complete':
        // Update the last step start message to show completion
        setMessages(prev => {
          const newMessages = [...prev]
          // Find the last step start message and update it
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'progress' && newMessages[i].stepNumber === data.step) {
              newMessages[i] = {
                ...newMessages[i],
                content: `✅ Step ${data.step} completed`,
                status: 'complete'
              }
              break
            }
          }
          return newMessages
        })
        setIsTyping(false)
        break

      case 'tool.execution':
        // Don't show tool execution details to user
        // Just keep typing indicator active
        break

      case 'conversation.interrupted':
        setIsTyping(false)
        const interruptMessage: Message = {
          event_id: data.event_id,
          event_type: data.type,
          timestamp: data.timestamp,
          role: 'system',
          content: 'Conversation was interrupted',
          status: 'complete',
          data: data.data || {}
        }
        setMessages(prev => [...prev, interruptMessage])
        break

      case 'error':
        console.error('WebSocket error message:', data)
        setIsTyping(false)
        break

      case 'interrupt_result':
        console.log('Conversation interrupted:', data)
        setIsTyping(false)
        // Optionally show a message that the conversation was interrupted
        if (data.success) {
          console.log('Conversation successfully interrupted')
        }
        break

      default:
        console.log('Unknown WebSocket message type:', data.type)
    }
  }

  const sendMessage = useCallback(async (message: string) => {
    if (!currentConversation || !token) return

    try {
      // Prefer WebSocket for real-time response, fallback to API
      if (wsServiceRef.current && isConnected) {
        wsServiceRef.current.sendMessage(message)
      } else {
        // Fallback to API if WebSocket is not available
        await conversationApi.sendMessage(currentConversation.id, { message }, token)
      }

    } catch (error) {
      console.error('Failed to send message:', error)
      throw error
    }
  }, [currentConversation, token, isConnected])

  const interruptConversation = useCallback(async () => {
    if (!currentConversation || !token) return

    try {
      if (wsServiceRef.current) {
        wsServiceRef.current.interrupt()
      }
      await conversationApi.interrupt(currentConversation.id, token)
    } catch (error) {
      console.error('Failed to interrupt conversation:', error)
      throw error
    }
  }, [currentConversation, token])

  // Effects
  useEffect(() => {
    if (user && token) {
      refreshConversations()
    }
  }, [user, token, refreshConversations])

  useEffect(() => {
    // Cleanup WebSocket on unmount
    return () => {
      if (wsServiceRef.current) {
        wsServiceRef.current.disconnect()
      }
    }
  }, [])

  const value: ConversationContextType = {
    conversations,
    currentConversation,
    messages,
    loading,
    isConnected,
    isTyping,
    createConversation,
    selectConversation,
    sendMessage,
    interruptConversation,
    refreshConversations,
  }

  return (
    <ConversationContext.Provider value={value}>
      {children}
    </ConversationContext.Provider>
  )
}
