import React, { useState, useRef, useEffect } from 'react'
import { useConversation } from '../contexts/ConversationContext'

interface Conversation {
  id: string
  title: string
  status: string
  created_at: string
  updated_at: string
}

interface Message {
  event_id: string
  event_type: string
  timestamp: string
  role: 'user' | 'assistant' | 'system' | 'progress'
  content: string
  status: string
  data: Record<string, any>
  isProgress?: boolean
  stepNumber?: number
  toolName?: string
}

interface ChatWindowProps {
  conversation: Conversation
}

const ChatWindow: React.FC<ChatWindowProps> = ({ conversation }) => {
  const {
    messages,
    isConnected,
    isTyping,
    sendMessage,
    interruptConversation
  } = useConversation()

  const [inputMessage, setInputMessage] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  // Focus input when conversation changes
  useEffect(() => {
    inputRef.current?.focus()
  }, [conversation.id])

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || sending || !isConnected) return

    const message = inputMessage.trim()
    setInputMessage('')
    setSending(true)

    try {
      await sendMessage(message)
    } catch (error) {
      console.error('Failed to send message:', error)
      // Restore message on error
      setInputMessage(message)
    } finally {
      setSending(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleInterrupt = async () => {
    try {
      await interruptConversation()
    } catch (error) {
      console.error('Failed to interrupt conversation:', error)
    }
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const renderMessage = (message: Message) => {
    const baseClasses = "mb-4 flex"

    if (message.role === 'user') {
      return (
        <div key={message.event_id} className={`${baseClasses} justify-end`}>
          <div className="max-w-xs lg:max-w-md">
            <div className="message-user">
              {message.content}
            </div>
            <div className="text-xs text-gray-500 mt-1 text-right">
              {formatTime(message.timestamp)}
            </div>
          </div>
        </div>
      )
    } else if (message.role === 'assistant') {
      return (
        <div key={message.event_id} className={`${baseClasses} justify-start`}>
          <div className="max-w-xs lg:max-w-md">
            <div className="message-assistant">
              <div className="whitespace-pre-wrap">
                {message.content}
                {message.status === 'streaming' && (
                  <span className="inline-block w-2 h-4 bg-blue-500 ml-1 animate-pulse"></span>
                )}
              </div>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {formatTime(message.timestamp)}
              {message.status === 'streaming' && (
                <span className="ml-2 text-blue-500">Streaming...</span>
              )}
            </div>
          </div>
        </div>
      )
    } else if (message.role === 'progress') {
      const isRunning = message.status === 'running'
      const isComplete = message.status === 'complete'

      return (
        <div key={message.event_id} className={`${baseClasses} justify-center`}>
          <div className="max-w-2xl lg:max-w-4xl w-full">
            <div className={`message-progress rounded-lg px-4 py-3 text-sm ${isRunning
              ? 'bg-blue-50 border border-blue-200 text-blue-700'
              : 'bg-green-50 border border-green-200 text-green-700'
              }`}>
              <div className="flex items-start space-x-3">
                <div className={`mt-1 w-2 h-2 rounded-full ${isRunning
                  ? 'animate-pulse bg-blue-500'
                  : 'bg-green-500'
                  }`}></div>
                <div className="flex-1 min-w-0">
                  {/* Main content with markdown support */}
                  <div className="whitespace-pre-wrap">
                    {message.content.split('\n').map((line, index) => {
                      // Simple markdown parsing for bold text
                      if (line.includes('**')) {
                        const parts = line.split('**')
                        return (
                          <div key={index} className="mb-1">
                            {parts.map((part, partIndex) =>
                              partIndex % 2 === 1 ?
                                <strong key={partIndex}>{part}</strong> :
                                <span key={partIndex}>{part}</span>
                            )}
                          </div>
                        )
                      }
                      return <div key={index} className="mb-1">{line}</div>
                    })}
                  </div>

                  {/* Step and tool information */}
                  {message.stepNumber && (
                    <div className={`text-xs mt-2 ${isRunning ? 'text-blue-500' : 'text-green-500'
                      }`}>
                      Step {message.stepNumber}
                      {message.data?.total_steps && ` of ${message.data.total_steps}`}
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-1 text-center">
              {formatTime(message.timestamp)}
            </div>
          </div>
        </div>
      )
    } else {
      // Special handling for tool results
      if (message.event_type === 'tool.result') {
        // Filter out terminate tool results - they're not needed for display
        if (message.data.tool_name === 'terminate') {
          return null
        }

        return (
          <div key={message.event_id} className={`${baseClasses} justify-center`}>
            <div className="max-w-xs lg:max-w-md">
              <div className="bg-gray-100 border border-gray-200 rounded-lg p-3 text-sm">
                <div className="font-medium text-gray-700 mb-1">
                  🔧 {message.data.tool_name || 'Tool'} Result
                </div>
                <div className="text-gray-600 whitespace-pre-wrap font-mono text-xs">
                  {message.content.replace(/^🔧 Tool: .*\n/, '')}
                </div>
                {message.data.truncated && (
                  <div className="text-xs text-gray-500 mt-1 italic">
                    Result truncated for display
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-500 mt-1 text-center">
                {formatTime(message.timestamp)}
              </div>
            </div>
          </div>
        )
      }

      return (
        <div key={message.event_id} className={`${baseClasses} justify-center`}>
          <div className="message-system">
            {message.content}
          </div>
        </div>
      )
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {conversation.title || 'Untitled Conversation'}
            </h3>
            <div className="flex items-center mt-1">
              <div className={`w-2 h-2 rounded-full mr-2 ${isConnected ? 'bg-green-400' : 'bg-red-400'
                }`} />
              <span className="text-sm text-gray-600">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
              {isTyping && (
                <>
                  <span className="mx-2 text-gray-300">•</span>
                  <span className="text-sm text-gray-600">AI is thinking...</span>
                </>
              )}
            </div>
          </div>

          {isTyping && (
            <button
              onClick={handleInterrupt}
              className="btn btn-danger text-sm"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <div className="mb-4">
                <svg className="w-12 h-12 mx-auto text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <p>Start the conversation by sending a message</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map(renderMessage)}

            {/* Typing indicator */}
            {isTyping && (
              <div className="flex justify-start mb-4">
                <div className="max-w-xs lg:max-w-md">
                  <div className="message-assistant">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex space-x-3">
          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={isConnected ? "Type your message..." : "Connecting..."}
              disabled={!isConnected || sending}
              className="input resize-none"
              rows={1}
              style={{
                minHeight: '2.5rem',
                maxHeight: '8rem',
                height: 'auto'
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = target.scrollHeight + 'px'
              }}
            />
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || !isConnected || sending}
            className="btn btn-primary px-6"
          >
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>

        <div className="mt-2 text-xs text-gray-500">
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  )
}

export default ChatWindow
