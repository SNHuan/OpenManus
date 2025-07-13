import React from 'react'
import LoadingSpinner from './LoadingSpinner'

interface Conversation {
  id: string
  title: string
  status: string
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}

interface ConversationListProps {
  conversations: Conversation[]
  currentConversation: Conversation | null
  onSelectConversation: (conversationId: string) => void
  onNewConversation: () => void
  loading: boolean
}

const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  currentConversation,
  onSelectConversation,
  onNewConversation,
  loading
}) => {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)

    if (diffInHours < 24) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } else if (diffInHours < 24 * 7) {
      return date.toLocaleDateString([], { weekday: 'short' })
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
    }
  }

  const truncateTitle = (title: string, maxLength = 30) => {
    if (title.length <= maxLength) return title
    return title.substring(0, maxLength) + '...'
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">Conversations</h2>
          <button
            onClick={onNewConversation}
            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            title="New conversation"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {loading && conversations.length === 0 ? (
          <div className="flex items-center justify-center p-8">
            <LoadingSpinner size="medium" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <div className="mb-4">
              <svg className="w-12 h-12 mx-auto text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="text-sm">No conversations yet</p>
            <p className="text-xs text-gray-400 mt-1">Start a new conversation to begin</p>
          </div>
        ) : (
          <div className="p-2">
            {conversations.filter(conversation => conversation && conversation.id).map((conversation) => (
              <div
                key={conversation.id}
                onClick={() => onSelectConversation(conversation.id)}
                className={`p-3 mb-2 rounded-lg cursor-pointer transition-colors ${currentConversation?.id === conversation.id
                    ? 'bg-primary-50 border border-primary-200'
                    : 'bg-white hover:bg-gray-50 border border-transparent'
                  }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium text-gray-900 truncate">
                      {truncateTitle(conversation.title || 'Untitled Conversation')}
                    </h3>
                    <div className="flex items-center mt-1">
                      <span
                        className={`inline-block w-2 h-2 rounded-full mr-2 ${conversation.status === 'active'
                            ? 'bg-green-400'
                            : conversation.status === 'paused'
                              ? 'bg-yellow-400'
                              : 'bg-gray-400'
                          }`}
                      />
                      <span className="text-xs text-gray-500 capitalize">
                        {conversation.status}
                      </span>
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 ml-2">
                    {formatDate(conversation.updated_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="text-xs text-gray-500 text-center">
          {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
        </div>
      </div>
    </div>
  )
}

export default ConversationList
