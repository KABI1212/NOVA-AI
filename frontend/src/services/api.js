import axios from 'axios';

const RAW_API_URL = (import.meta.env.VITE_API_URL || '').trim();

export const API_BASE_URL = RAW_API_URL.replace(/\/$/, '');

const normalizePath = (path = '') => {
  const value = String(path || '').trim();
  if (!value) {
    return '';
  }

  return value.startsWith('/') ? value : `/${value}`;
};

export const buildApiEndpoint = (path = '') => {
  const normalizedPath = normalizePath(path);

  if (!API_BASE_URL) {
    return normalizedPath.startsWith('/api') ? normalizedPath : `/api${normalizedPath}`;
  }

  if (API_BASE_URL.endsWith('/api')) {
    return normalizedPath.startsWith('/api')
      ? `${API_BASE_URL}${normalizedPath.slice(4)}`
      : `${API_BASE_URL}${normalizedPath}`;
  }

  return normalizedPath.startsWith('/api')
    ? `${API_BASE_URL}${normalizedPath}`
    : `${API_BASE_URL}/api${normalizedPath}`;
};

export const buildAppEndpoint = (path = '') => {
  const normalizedPath = normalizePath(path);

  if (!API_BASE_URL) {
    return normalizedPath;
  }

  if (API_BASE_URL.endsWith('/api')) {
    const rootBase = API_BASE_URL.replace(/\/api$/, '');
    return rootBase ? `${rootBase}${normalizedPath}` : normalizedPath;
  }

  return `${API_BASE_URL}${normalizedPath}`;
};

export const fetchApi = (path, options = {}) => fetch(buildApiEndpoint(path), options);

const api = axios.create({
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
  signup: (data) => api.post(buildApiEndpoint('/auth/signup'), data),
  login: (data) => api.post(buildApiEndpoint('/auth/login'), data),
  verifyLoginOtp: (data) => api.post(buildApiEndpoint('/auth/login/otp/verify'), data),
  resendLoginOtp: (data) => api.post(buildApiEndpoint('/auth/login/otp/resend'), data),
  sendTestEmail: () => api.post(buildApiEndpoint('/auth/email-test')),
  me: () => api.get(buildApiEndpoint('/auth/me')),
  updateMe: (data) => api.put(buildApiEndpoint('/auth/me'), data),
  deleteMe: () => api.delete(buildApiEndpoint('/auth/me')),
};

// Chat API
export const chatAPI = {
  sendMessage: (data) => api.post(buildApiEndpoint('/chat'), data),
  regenerate: (data) => api.post(buildApiEndpoint('/chat/regenerate'), data),
  getConversations: () => api.get(buildApiEndpoint('/chat/conversations')),
  getConversation: (id) => api.get(buildApiEndpoint(`/chat/conversations/${id}`)),
  updateConversation: (id, data) => api.put(buildApiEndpoint(`/chat/conversations/${id}`), data),
  deleteConversation: (id) => api.delete(buildApiEndpoint(`/chat/conversations/${id}`)),
  getProviders: () => api.get(buildApiEndpoint('/chat/providers')),
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
  generate: (data) => api.post(buildApiEndpoint('/code/generate'), data),
  explain: (data) => api.post(buildApiEndpoint('/code/explain'), data),
  debug: (data) => api.post(buildApiEndpoint('/code/debug'), data),
  optimize: (data) => api.post(buildApiEndpoint('/code/optimize'), data),
};

// Learning API
export const learningAPI = {
  generateRoadmap: (data) => api.post(buildApiEndpoint('/learning/roadmap'), data),
  getProgress: () => api.get(buildApiEndpoint('/learning')),
  updateProgress: (data) => api.post(buildApiEndpoint('/learning/progress'), data),
  deleteProgress: (id) => api.delete(buildApiEndpoint(`/learning/${id}`)),
};

// Explain API
export const explainAPI = {
  explain: (data) => api.post(buildApiEndpoint('/explain'), data),
};

// Image API
export const imageAPI = {
  generate: (data) => api.post(buildApiEndpoint('/image/generate'), data, { timeout: 240000 }),
  optimizePrompt: (data) => api.post(buildApiEndpoint('/image/prompt'), data, { timeout: 120000 }),
  getProviders: () => api.get(buildApiEndpoint('/image/providers')),
  variation: (data) => api.post(buildApiEndpoint('/image/variations'), data, { timeout: 240000 }),
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
