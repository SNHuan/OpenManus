import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import './index.css'
import { AuthProvider } from './contexts/AuthContext'
import { ConversationProvider } from './contexts/ConversationContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ConversationProvider>
          <App />
        </ConversationProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
