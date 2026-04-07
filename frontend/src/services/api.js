import axios from 'axios';

const API_URL = (import.meta.env.VITE_API_URL || '').trim();

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
    const token = localStorage.getItem('token');
    if (error.response?.status === 401 && token) {
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
  verifyLoginOtp: (data) => api.post('/api/auth/login/otp/verify', data),
  resendLoginOtp: (data) => api.post('/api/auth/login/otp/resend', data),
  sendTestEmail: () => api.post('/api/auth/email-test'),
  me: () => api.get('/api/auth/me'),
  updateMe: (data) => api.put('/api/auth/me', data),
  deleteMe: () => api.delete('/api/auth/me'),
};

// Chat API
export const chatAPI = {
  sendMessage: (data) => api.post('/api/chat', data),
  regenerate: (data) => api.post('/api/chat/regenerate', data),
  getConversations: () => api.get('/api/chat/conversations'),
  getConversation: (id) => api.get(`/api/chat/conversations/${id}`),
  updateConversation: (id, data) => api.put(`/api/chat/conversations/${id}`, data),
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
  generate: (data) => api.post('/api/image/generate', data, { timeout: 240000 }),
  optimizePrompt: (data) => api.post('/api/image/prompt', data, { timeout: 120000 }),
  getProviders: () => api.get('/api/image/providers'),
  variation: (data) => api.post('/api/image/variations', data, { timeout: 240000 }),
};

export const generateImage = async (prompt, options = {}) => {
  const response = await imageAPI.generate({ prompt, ...options });
  return response.data?.url || response.data?.images?.[0] || '';
};

export const optimizeImagePrompt = async (data) => {
  const response = await imageAPI.optimizePrompt(data);
  return response.data?.revised_prompt || response.data?.prompt || '';
};

export default api;
