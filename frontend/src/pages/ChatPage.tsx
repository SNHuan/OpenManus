import React, { useState, useEffect } from 'react'
import { useConversation } from '../contexts/ConversationContext'
import ConversationList from '../components/ConversationList'
import ChatWindow from '../components/ChatWindow'
import LoadingSpinner from '../components/LoadingSpinner'

const ChatPage: React.FC = () => {
  const {
    conversations,
    currentConversation,
    loading,
    createConversation,
    selectConversation
  } = useConversation()

  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Auto-select first conversation or create one if none exist
  useEffect(() => {
    if (!loading && conversations.length > 0 && !currentConversation) {
      selectConversation(conversations[0].id)
    }
  }, [conversations, currentConversation, loading]) // Removed selectConversation from deps

  const handleNewConversation = async () => {
    try {
      const conversation = await createConversation()
      console.log('Created conversation:', conversation)

      if (!conversation || !conversation.id) {
        throw new Error('Invalid conversation data received')
      }

      await selectConversation(conversation.id)
    } catch (error) {
      console.error('Failed to create conversation:', error)
      // TODO: Show user-friendly error message
    }
  }

  const handleSelectConversation = async (conversationId: string) => {
    try {
      await selectConversation(conversationId)
    } catch (error) {
      console.error('Failed to select conversation:', error)
    }
  }

  if (loading && conversations.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="large" />
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-80' : 'w-0'} transition-all duration-300 overflow-hidden border-r border-gray-200`}>
        <ConversationList
          conversations={conversations}
          currentConversation={currentConversation}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          loading={loading}
        />
      </div>

      {/* Sidebar toggle button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute top-4 left-4 z-10 p-2 bg-white border border-gray-200 rounded-lg shadow-sm hover:bg-gray-50 transition-colors"
        title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
      >
        <svg
          className="w-5 h-5 text-gray-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          {sidebarOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          )}
        </svg>
      </button>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {currentConversation ? (
          <ChatWindow conversation={currentConversation} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="text-gray-400 mb-4">
                <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Welcome to OpenManus
              </h3>
              <p className="text-gray-600 mb-4">
                {conversations.length === 0
                  ? "Start a new conversation to begin chatting with AI"
                  : "Select a conversation from the sidebar to continue"
                }
              </p>
              {conversations.length === 0 && (
                <button
                  onClick={handleNewConversation}
                  className="btn btn-primary"
                >
                  Start New Conversation
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatPage
