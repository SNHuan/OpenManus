import axios from 'axios'

// Use backend port (8000) instead of frontend port (3000)
const API_BASE_URL = 'http://localhost:8000/api/v1'

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (username: string, password: string) => {
    const response = await api.post('/auth/login', { username, password })
    return response
  },

  register: async (username: string, email: string, password: string) => {
    const response = await api.post('/auth/register', { username, email, password })
    return response
  },

  verify: async (token: string) => {
    const response = await api.get('/auth/verify', {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  logout: async () => {
    const response = await api.post('/auth/logout')
    return response
  },
}

// User API
export const userApi = {
  getProfile: async (token: string) => {
    const response = await api.get('/users/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  updateProfile: async (data: any, token: string) => {
    const response = await api.put('/users/me', data, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  deleteAccount: async (token: string) => {
    const response = await api.delete('/users/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },
}

// Conversation API
export const conversationApi = {
  create: async (data: { title?: string; metadata?: any }, token: string) => {
    const response = await api.post('/conversations', data, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  get: async (conversationId: string, token: string) => {
    const response = await api.get(`/conversations/${conversationId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  update: async (conversationId: string, data: any, token: string) => {
    const response = await api.put(`/conversations/${conversationId}`, data, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  delete: async (conversationId: string, token: string) => {
    const response = await api.delete(`/conversations/${conversationId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  getUserConversations: async (userId: string, token: string, limit = 50, offset = 0) => {
    const response = await api.get(`/users/${userId}/conversations`, {
      params: { limit, offset },
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  sendMessage: async (conversationId: string, data: { message: string; parent_event_id?: string }, token: string) => {
    const response = await api.post(`/conversations/${conversationId}/messages`, data, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  interrupt: async (conversationId: string, token: string) => {
    const response = await api.post(`/conversations/${conversationId}/interrupt`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  getHistory: async (conversationId: string, token: string, limit = 100, offset = 0) => {
    const response = await api.get(`/conversations/${conversationId}/history`, {
      params: { limit, offset },
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },
}

// Events API
export const eventsApi = {
  get: async (eventId: string, token: string) => {
    const response = await api.get(`/events/${eventId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  getTrace: async (eventId: string, token: string) => {
    const response = await api.get(`/events/${eventId}/trace`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },

  getRelated: async (eventId: string, token: string) => {
    const response = await api.get(`/events/${eventId}/related`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response
  },
}

export default api
