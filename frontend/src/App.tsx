import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ChatPage from './pages/ChatPage'
import Layout from './components/Layout'
import LoadingSpinner from './components/LoadingSpinner'

function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="large" />
      </div>
    )
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route 
        path="/login" 
        element={user ? <Navigate to="/chat" replace /> : <LoginPage />} 
      />
      <Route 
        path="/register" 
        element={user ? <Navigate to="/chat" replace /> : <RegisterPage />} 
      />
      
      {/* Protected routes */}
      <Route 
        path="/chat/*" 
        element={
          user ? (
            <Layout>
              <ChatPage />
            </Layout>
          ) : (
            <Navigate to="/login" replace />
          )
        } 
      />
      
      {/* Default redirect */}
      <Route 
        path="/" 
        element={<Navigate to={user ? "/chat" : "/login"} replace />} 
      />
      
      {/* Catch all */}
      <Route 
        path="*" 
        element={<Navigate to={user ? "/chat" : "/login"} replace />} 
      />
    </Routes>
  )
}

export default App
