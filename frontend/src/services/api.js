import axios from 'axios';

const STATUS_REQUEST_TIMEOUT_MS = 1500;
const RAW_API_URL = String(import.meta.env.VITE_API_URL || '').trim();

const normalizeBaseUrl = (value = '') => String(value || '').trim().replace(/\/$/, '');

const parseApiBaseCandidates = (rawValue = '') =>
  Array.from(
    new Set(
      String(rawValue || '')
        .split(/[,\n]/)
        .map((value) => normalizeBaseUrl(value))
        .filter(Boolean)
    )
  );

const normalizePath = (path = '') => {
  const value = String(path || '').trim();
  if (!value) {
    return '';
  }

  return value.startsWith('/') ? value : `/${value}`;
};

const buildEndpoint = (path = '', baseUrl = '', api = true) => {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
  const normalizedPath = normalizePath(path);

  if (!normalizedBaseUrl) {
    if (!api) {
      return normalizedPath;
    }
    return normalizedPath.startsWith('/api') ? normalizedPath : `/api${normalizedPath}`;
  }

  if (api) {
    if (normalizedBaseUrl.endsWith('/api')) {
      return normalizedPath.startsWith('/api')
        ? `${normalizedBaseUrl}${normalizedPath.slice(4)}`
        : `${normalizedBaseUrl}${normalizedPath}`;
    }

    return normalizedPath.startsWith('/api')
      ? `${normalizedBaseUrl}${normalizedPath}`
      : `${normalizedBaseUrl}/api${normalizedPath}`;
  }

  if (normalizedBaseUrl.endsWith('/api')) {
    const rootBase = normalizedBaseUrl.replace(/\/api$/, '');
    return rootBase ? `${rootBase}${normalizedPath}` : normalizedPath;
  }

  return `${normalizedBaseUrl}${normalizedPath}`;
};

const API_BASE_CANDIDATES = parseApiBaseCandidates(RAW_API_URL);

let preferredApiBaseUrl = API_BASE_CANDIDATES[0] || '';
let preferredApiStatus = null;
let resolveApiBaseUrlPromise = null;

const hasWindow = () => typeof window !== 'undefined';

const safeSetTimeout = (callback, timeout) =>
  hasWindow() ? window.setTimeout(callback, timeout) : setTimeout(callback, timeout);

const safeClearTimeout = (timeoutId) => {
  if (timeoutId == null) {
    return;
  }

  if (hasWindow()) {
    window.clearTimeout(timeoutId);
    return;
  }

  clearTimeout(timeoutId);
};

const buildStatusEndpoint = (baseUrl = '') => buildEndpoint('/status', baseUrl, true);

const findMatchingCandidateBase = (url = '') =>
  API_BASE_CANDIDATES.find(
    (candidate) => url === candidate || url.startsWith(`${candidate}/`)
  );

const probeApiBaseUrl = async (baseUrl) => {
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timeoutId = controller
    ? safeSetTimeout(() => controller.abort(), STATUS_REQUEST_TIMEOUT_MS)
    : null;

  try {
    const response = await fetch(buildStatusEndpoint(baseUrl), {
      headers: {
        Accept: 'application/json',
      },
      ...(controller ? { signal: controller.signal } : {}),
    });

    if (!response.ok) {
      return {
        baseUrl,
        healthy: false,
        score: 0,
        status: null,
      };
    }

    const status = await response.json().catch(() => null);
    const ai = status?.capabilities?.ai || {};
    const auth = status?.capabilities?.auth || {};
    const email = auth?.email || {};
    const availableTextProviders = Array.isArray(ai.available_text_providers)
      ? ai.available_text_providers
      : [];

    return {
      baseUrl,
      healthy: true,
      score:
        100 +
        (ai.text_ready ? 40 : 0) +
        (email.ready ? 20 : 0) +
        (ai.image_ready ? 10 : 0) +
        availableTextProviders.length,
      status,
    };
  } catch {
    return {
      baseUrl,
      healthy: false,
      score: 0,
      status: null,
    };
  } finally {
    safeClearTimeout(timeoutId);
  }
};

const pickBestApiBase = (results = []) => {
  const healthyResults = results.filter((result) => result?.healthy);
  const pool = healthyResults.length ? healthyResults : results;

  return [...pool].sort((left, right) => (right?.score || 0) - (left?.score || 0))[0] || null;
};

export const API_BASE_URL = preferredApiBaseUrl;

export const getApiBaseCandidates = () => [...API_BASE_CANDIDATES];

export const getPreferredApiStatus = () => preferredApiStatus;

export const buildApiEndpoint = (path = '', baseUrl = preferredApiBaseUrl) =>
  buildEndpoint(path, baseUrl, true);

export const buildAppEndpoint = (path = '', baseUrl = preferredApiBaseUrl) =>
  buildEndpoint(path, baseUrl, false);

export const resolveApiBaseUrl = async (force = false) => {
  if (!API_BASE_CANDIDATES.length) {
    return '';
  }

  if (!force && API_BASE_CANDIDATES.length === 1) {
    preferredApiBaseUrl = API_BASE_CANDIDATES[0];
    return preferredApiBaseUrl;
  }

  if (!force && preferredApiStatus) {
    return preferredApiBaseUrl;
  }

  if (!force && resolveApiBaseUrlPromise) {
    return resolveApiBaseUrlPromise;
  }

  resolveApiBaseUrlPromise = (async () => {
    const results = await Promise.all(API_BASE_CANDIDATES.map((baseUrl) => probeApiBaseUrl(baseUrl)));
    const bestMatch = pickBestApiBase(results);

    preferredApiBaseUrl = bestMatch?.baseUrl || API_BASE_CANDIDATES[0];
    preferredApiStatus = bestMatch?.status || null;

    return preferredApiBaseUrl;
  })();

  try {
    return await resolveApiBaseUrlPromise;
  } finally {
    resolveApiBaseUrlPromise = null;
  }
};

export const fetchApi = async (path, options = {}) => {
  const baseUrl = await resolveApiBaseUrl();
  return fetch(buildApiEndpoint(path, baseUrl), options);
};

export const fetchApp = async (path, options = {}) => {
  const baseUrl = await resolveApiBaseUrl();
  return fetch(buildAppEndpoint(path, baseUrl), options);
};

if (hasWindow() && API_BASE_CANDIDATES.length > 1) {
  void resolveApiBaseUrl();
}

const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
});

const PUBLIC_AUTH_401_PATHS = [
  '/auth/login',
  '/auth/signup',
  '/auth/login/otp/verify',
  '/auth/login/otp/resend',
  '/auth/password/forgot',
  '/auth/password/reset',
];

const shouldHandle401AsExpiredSession = (requestUrl = '') => {
  const normalizedUrl = String(requestUrl || '').trim();

  if (!normalizedUrl) {
    return true;
  }

  return !PUBLIC_AUTH_401_PATHS.some((path) => normalizedUrl.includes(path));
};

api.interceptors.request.use(async (config) => {
  const resolvedBaseUrl = await resolveApiBaseUrl();
  const originalUrl = String(config.url || '').trim();
  const matchedCandidateBase = findMatchingCandidateBase(originalUrl);

  if (originalUrl) {
    if (!/^https?:\/\//i.test(originalUrl)) {
      config.url = buildApiEndpoint(originalUrl, resolvedBaseUrl);
    } else if (matchedCandidateBase) {
      const remainder = originalUrl.slice(matchedCandidateBase.length) || '/';
      config.url = remainder.startsWith('/api')
        ? buildApiEndpoint(remainder, resolvedBaseUrl)
        : buildAppEndpoint(remainder, resolvedBaseUrl);
    }
  }

  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const token = localStorage.getItem('token');
    const requestUrl = String(error?.config?.url || '').trim();
    if (
      error.response?.status === 401 &&
      token &&
      shouldHandle401AsExpiredSession(requestUrl)
    ) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  signup: (data) => api.post('/auth/signup', data),
  login: (data) => api.post('/auth/login', data),
  verifyLoginOtp: (data) => api.post('/auth/login/otp/verify', data),
  resendLoginOtp: (data) => api.post('/auth/login/otp/resend', data),
  forgotPassword: (data) => api.post('/auth/password/forgot', data),
  resetPassword: (data) => api.post('/auth/password/reset', data),
  sendTestEmail: () => api.post('/auth/email-test'),
  me: () => api.get('/auth/me'),
  updateMe: (data) => api.put('/auth/me', data),
  deleteMe: () => api.delete('/auth/me'),
};

export const chatAPI = {
  sendMessage: (data) => api.post('/chat', data),
  sendMessageWithFiles: (data) => api.post('/chat/with-files', data),
  regenerate: (data) => api.post('/chat/regenerate', data),
  getConversations: () => api.get('/chat/conversations'),
  getConversation: (id) => api.get(`/chat/conversations/${id}`),
  updateConversation: (id, data) => api.put(`/chat/conversations/${id}`, data),
  deleteConversation: (id) => api.delete(`/chat/conversations/${id}`),
  getProviders: () => api.get('/chat/providers'),
};

export const filesAPI = {
  upload: (formData, config = {}) =>
    api.post('/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 240000,
      ...config,
    }),
  process: (fileId) => api.post(`/files/process/${fileId}`),
  list: (params = {}) => api.get('/files/list', { params }),
  remove: (fileId) => api.delete(`/files/${fileId}`),
};

export const documentAPI = {
  upload: (formData, config = {}) =>
    api.post('/document/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 240000,
      ...config,
    }),
  getDocuments: () => api.get('/document'),
  getDocument: (documentId) => api.get(`/document/${documentId}`),
  askQuestion: (data) => api.post('/document/ask', data, { timeout: 120000 }),
  rewriteQuestion: (data) => api.post('/document/rewrite-question', data),
  deleteDocument: (documentId) => api.delete(`/document/${documentId}`),
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

export const codeAPI = {
  generate: (data) => api.post('/code/generate', data),
  explain: (data) => api.post('/code/explain', data),
  debug: (data) => api.post('/code/debug', data),
  optimize: (data) => api.post('/code/optimize', data),
};

export const learningAPI = {
  generateRoadmap: (data) => api.post('/learning/roadmap', data),
  getProgress: () => api.get('/learning'),
  updateProgress: (data) => api.post('/learning/progress', data),
  deleteProgress: (id) => api.delete(`/learning/${id}`),
};

export const explainAPI = {
  explain: (data) => api.post('/explain', data),
};

export const orchestratorAPI = {
  compose: (data) => api.post('/orchestrator/compose', data, { timeout: 120000 }),
  agent: (data) => api.post('/orchestrator/agent', data, { timeout: 120000 }),
};

export const imageAPI = {
  generate: (data) => api.post('/image/generate', data, { timeout: 240000 }),
  optimizePrompt: (data) => api.post('/image/prompt', data, { timeout: 120000 }),
  getProviders: () => api.get('/image/providers'),
  variation: (data) => api.post('/image/variations', data, { timeout: 240000 }),
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
