import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  signup: (data) => api.post('/api/auth/signup', data),
  login: (data) => api.post('/api/auth/login', data),
};

// Chat API
export const chatAPI = {
  sendMessage: (data) => api.post('/api/chat', data),
  regenerate: (data) => api.post('/api/chat/regenerate', data),
  getConversations: () => api.get('/api/chat/conversations'),
  getConversation: (id) => api.get(`/api/chat/conversations/${id}`),
  deleteConversation: (id) => api.delete(`/api/chat/conversations/${id}`),
  getProviders: () => api.get('/api/chat/providers'),
};

export const sendMessage = async (message) => {
  try {
    const response = await chatAPI.sendMessage({
      message,
      stream: false,
    });
    return response.data?.answer || response.data?.message || response.data?.response || 'NOVA AI: ...';
  } catch (error) {
    return (
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      'I could not get a reliable answer right now.'
    );
  }
};

// Code API
export const codeAPI = {
  generate: (data) => api.post('/api/code/generate', data),
  explain: (data) => api.post('/api/code/explain', data),
  debug: (data) => api.post('/api/code/debug', data),
  optimize: (data) => api.post('/api/code/optimize', data),
};

// Document API
export const documentAPI = {
  upload: (formData) => {
    const token = localStorage.getItem('token');
    return axios.post(`${API_URL}/api/document/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        Authorization: `Bearer ${token}`,
      },
    });
  },
  getDocuments: () => api.get('/api/document'),
  getDocument: (id) => api.get(`/api/document/${id}`),
  askQuestion: (data) => api.post('/api/document/ask', data),
  deleteDocument: (id) => api.delete(`/api/document/${id}`),
};

// Learning API
export const learningAPI = {
  generateRoadmap: (data) => api.post('/api/learning/roadmap', data),
  getProgress: () => api.get('/api/learning'),
  updateProgress: (data) => api.post('/api/learning/progress', data),
  deleteProgress: (id) => api.delete(`/api/learning/${id}`),
};

// Explain API
export const explainAPI = {
  explain: (data) => api.post('/api/explain', data),
};

// Image API
export const imageAPI = {
  generate: (data) => api.post('/api/image', data),
};

export default api;
