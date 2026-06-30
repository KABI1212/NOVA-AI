import { create } from 'zustand';

import { BROWSER_VOICE_AUTO, DEFAULT_TTS_VOICE } from './voices';

const hasLocalStorage = () => typeof window !== 'undefined' && Boolean(window.localStorage);

const getStoredValue = (key, fallback = null) => {
  if (!hasLocalStorage()) {
    return fallback;
  }

  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
};

const setStoredValue = (key, value) => {
  if (!hasLocalStorage()) {
    return;
  }

  try {
    localStorage.setItem(key, value);
  } catch {
    // Ignore quota or privacy-mode storage failures; in-memory state still updates.
  }
};

const removeStoredValue = (key) => {
  if (!hasLocalStorage()) {
    return;
  }

  try {
    localStorage.removeItem(key);
  } catch {
    // Ignore storage failures during logout cleanup.
  }
};

const parseStoredUser = () => {
  const rawUser = getStoredValue('user');
  if (!rawUser) {
    return null;
  }

  try {
    return JSON.parse(rawUser);
  } catch {
    removeStoredValue('user');
    return null;
  }
};

// Auth Store
export const useAuthStore = create((set) => ({
  user: parseStoredUser(),
  token: getStoredValue('token'),
  setAuth: (user, token) => {
    setStoredValue('user', JSON.stringify(user));
    setStoredValue('token', token);
    set({ user, token });
  },
  logout: () => {
    removeStoredValue('user');
    removeStoredValue('token');
    set({ user: null, token: null });
  },
  clearAuth: () => {
    removeStoredValue('user');
    removeStoredValue('token');
    set({ user: null, token: null });
  },
  setUser: (user) => {
    setStoredValue('user', JSON.stringify(user));
    set((state) => ({ ...state, user }));
  },
}));

// Chat Store
export const useChatStore = create((set) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  mode: 'chat',
  isTyping: false,
  setConversations: (conversations) => set({ conversations }),
  setCurrentConversation: (conversation) => set({ currentConversation: conversation }),
  setMessages: (updater) =>
    set((state) => ({
      messages: typeof updater === 'function' ? updater(state.messages) : updater,
    })),
  setMode: (mode) => set({ mode }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setIsTyping: (isTyping) => set({ isTyping }),
}));

// Document Store
export const useDocumentStore = create((set) => ({
  documents: [],
  currentDocument: null,
  setDocuments: (documents) => set({ documents }),
  setCurrentDocument: (currentDocument) => set({ currentDocument }),
  addDocument: (document) =>
    set((state) => ({
      documents: [document, ...state.documents.filter((item) => item.id !== document?.id)],
      currentDocument: document,
    })),
  removeDocument: (documentId) =>
    set((state) => ({
      documents: state.documents.filter((item) => item.id !== documentId),
      currentDocument:
        state.currentDocument?.id === documentId ? null : state.currentDocument,
    })),
}));

// Theme Store
export const useThemeStore = create((set) => ({
  isDark: getStoredValue('theme') === 'dark',
  toggleTheme: () => set((state) => {
    const newTheme = !state.isDark;
    setStoredValue('theme', newTheme ? 'dark' : 'light');
    if (typeof document !== 'undefined') {
      if (newTheme) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
    return { isDark: newTheme };
  }),
}));

const BROWSER_VOICE_STORAGE_KEY = 'nova_browser_voice';
const TTS_VOICE_STORAGE_KEY = 'nova_tts_voice';
const MANUAL_PLAYBACK_STORAGE_KEY = 'nova_manual_playback';

// Voice Store
export const useVoiceStore = create((set) => ({
  browserVoice: getStoredValue(BROWSER_VOICE_STORAGE_KEY, BROWSER_VOICE_AUTO) || BROWSER_VOICE_AUTO,
  ttsVoice: getStoredValue(TTS_VOICE_STORAGE_KEY, DEFAULT_TTS_VOICE) || DEFAULT_TTS_VOICE,
  manualPlayback: getStoredValue(MANUAL_PLAYBACK_STORAGE_KEY, 'true') !== 'false',
  setBrowserVoice: (browserVoice) => {
    setStoredValue(BROWSER_VOICE_STORAGE_KEY, browserVoice || BROWSER_VOICE_AUTO);
    set({ browserVoice: browserVoice || BROWSER_VOICE_AUTO });
  },
  setTtsVoice: (ttsVoice) => {
    setStoredValue(TTS_VOICE_STORAGE_KEY, ttsVoice || DEFAULT_TTS_VOICE);
    set({ ttsVoice: ttsVoice || DEFAULT_TTS_VOICE });
  },
  setManualPlayback: (manualPlayback) => {
    const nextManualPlayback = Boolean(manualPlayback);
    setStoredValue(MANUAL_PLAYBACK_STORAGE_KEY, String(nextManualPlayback));
    set({ manualPlayback: nextManualPlayback });
  },
  toggleManualPlayback: () =>
    set((state) => {
      const manualPlayback = !state.manualPlayback;
      setStoredValue(MANUAL_PLAYBACK_STORAGE_KEY, String(manualPlayback));
      return { manualPlayback };
    }),
}));
