import { create } from 'zustand';

import { BROWSER_VOICE_AUTO, DEFAULT_TTS_VOICE } from './voices';

// Auth Store
export const useAuthStore = create((set) => ({
  user: JSON.parse(localStorage.getItem('user')) || null,
  token: localStorage.getItem('token') || null,
  setAuth: (user, token) => {
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('token', token);
    set({ user, token });
  },
  logout: () => {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    set({ user: null, token: null });
  },
  setUser: (user) => {
    localStorage.setItem('user', JSON.stringify(user));
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
  isDark: localStorage.getItem('theme') === 'dark',
  toggleTheme: () => set((state) => {
    const newTheme = !state.isDark;
    localStorage.setItem('theme', newTheme ? 'dark' : 'light');
    if (newTheme) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    return { isDark: newTheme };
  }),
}));

const BROWSER_VOICE_STORAGE_KEY = 'nova_browser_voice';
const TTS_VOICE_STORAGE_KEY = 'nova_tts_voice';

// Voice Store
export const useVoiceStore = create((set) => ({
  browserVoice: localStorage.getItem(BROWSER_VOICE_STORAGE_KEY) || BROWSER_VOICE_AUTO,
  ttsVoice: localStorage.getItem(TTS_VOICE_STORAGE_KEY) || DEFAULT_TTS_VOICE,
  setBrowserVoice: (browserVoice) => {
    localStorage.setItem(BROWSER_VOICE_STORAGE_KEY, browserVoice || BROWSER_VOICE_AUTO);
    set({ browserVoice: browserVoice || BROWSER_VOICE_AUTO });
  },
  setTtsVoice: (ttsVoice) => {
    localStorage.setItem(TTS_VOICE_STORAGE_KEY, ttsVoice || DEFAULT_TTS_VOICE);
    set({ ttsVoice: ttsVoice || DEFAULT_TTS_VOICE });
  },
}));
