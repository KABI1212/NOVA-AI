// @ts-nocheck
import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Send,
  Plus,
  Trash2,
  RefreshCcw,
  Volume2,
  VolumeX,
  Paperclip
} from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import MessageBubble from '../components/chat/MessageBubble';
import VoiceInput from '../components/chat/VoiceInput';
import ShareButton from "../components/chat/ShareButton";
import { chatAPI, documentAPI, explainAPI } from '../services/api';
import { useChatStore } from '../utils/store';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const createLocalId = () => {
  if (crypto?.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

function Chat() {
  const location = useLocation();
  const navigate = useNavigate();
  const {
    conversations,
    currentConversation,
    messages,
    mode,
    isTyping,
    setConversations,
    setCurrentConversation,
    setMessages,
    setMode,
    addMessage,
    setIsTyping,
  } = useChatStore();

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [speakingId, setSpeakingId] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [providers, setProviders] = useState([]);
  const [webSearch, setWebSearch] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState(
    localStorage.getItem('ai_provider') || ''
  );
  const [selectedModel, setSelectedModel] = useState(
    localStorage.getItem('ai_model') || ''
  );
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const canRegenerate = !!currentConversation && messages.some((msg) => msg.role === 'assistant');

  useEffect(() => {
    loadConversations();
    loadProviders();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const nextMode = params.get('mode') || 'chat';
    if (nextMode !== mode) {
      setMode(nextMode);
    }
  }, [location.search, mode, setMode]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);


  useEffect(() => {
    if (mode === 'documents') {
      loadDocuments();
    }
  }, [mode]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadProviders = async () => {
    try {
      const response = await chatAPI.getProviders();
      const list = Array.isArray(response.data) ? response.data : [];
      setProviders(list);

      const storedProvider = localStorage.getItem('ai_provider') || '';
      const storedModel = localStorage.getItem('ai_model') || '';

      const providerId = list.some((p) => p.id === storedProvider)
        ? storedProvider
        : (list[0]?.id || '');
      const provider = list.find((p) => p.id === providerId);
      const models = provider?.models || [];
      const modelId = models.includes(storedModel) ? storedModel : (models[0] || '');

      setSelectedProvider(providerId);
      setSelectedModel(modelId);

      if (providerId) {
        localStorage.setItem('ai_provider', providerId);
      } else {
        localStorage.removeItem('ai_provider');
      }
      if (modelId) {
        localStorage.setItem('ai_model', modelId);
      } else {
        localStorage.removeItem('ai_model');
      }
    } catch (error) {
      toast.error('Failed to load AI providers');
    }
  };

  const streamChat = async (payload, onToken, onFinal, endpoint = '/api/chat') => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: token
        ? {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          }
        : {
            'Content-Type': 'application/json',
          },
      body: JSON.stringify(payload),
    });

    if (response.status === 401 || response.status === 403) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    if (!response.ok || !response.body) {
      const errorText = await response.text();
      throw new Error(errorText || 'Streaming failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data:')) continue;
        const data = line.replace(/^data:\s*/, '');
        if (!data) continue;
        if (data === '[DONE]') {
          onFinal({});
          return;
        }
        const payload = JSON.parse(data);
        if (webSearch) {
          if (payload.type === 'chunk' || payload.type === 'delta') {
            onToken(payload.content || '');
          }
        } else {
          if (payload.type === 'token' || payload.type === 'delta') {
            onToken(payload.content || '');
          }
        }
        
        if (payload.type === 'final') {
          onFinal(payload);
        }
      }
    }
  };

  const loadConversations = async () => {
    try {
      const response = await chatAPI.getConversations();
      setConversations(response.data);
    } catch (error) {
      toast.error('Failed to load conversations');
    }
  };

  const loadDocuments = async () => {
    try {
      const response = await documentAPI.getDocuments();
      setDocuments(response.data);
      if (!selectedDocumentId && response.data.length > 0) {
        setSelectedDocumentId(response.data[0].id);
      }
    } catch (error) {
      toast.error('Failed to load documents');
    }
  };

  const loadConversation = async (conversationId) => {
    try {
      const response = await chatAPI.getConversation(conversationId);
      setCurrentConversation(response.data);
      const mapped = response.data.messages.map((msg) => ({
        ...msg,
        images: msg.meta?.images || msg.images || [],
      }));
      setMessages(mapped);
    } catch (error) {
      if (error.response?.status === 404) {
        toast.error('Conversation not found. Starting a new chat.');
        setCurrentConversation(null);
        setMessages([]);
        loadConversations();
        navigate('/chat');
        return;
      }
      toast.error('Failed to load conversation');
    }
  };

  const deleteConversation = async (conversationId) => {
    try {
      await chatAPI.deleteConversation(conversationId);
      toast.success('Conversation deleted');
      if (currentConversation?.id === conversationId) {
        setCurrentConversation(null);
        setMessages([]);
      }
      loadConversations();
    } catch (error) {
      toast.error('Failed to delete conversation');
    }
  };

  const handleProviderChange = (providerId) => {
    setSelectedProvider(providerId);
    if (providerId) {
      localStorage.setItem('ai_provider', providerId);
    } else {
      localStorage.removeItem('ai_provider');
    }

    const provider = providers.find((p) => p.id === providerId);
    const modelId = provider?.models?.[0] || '';
    setSelectedModel(modelId);
    if (modelId) {
      localStorage.setItem('ai_model', modelId);
    } else {
      localStorage.removeItem('ai_model');
    }
  };

  const handleModelChange = (modelId) => {
    setSelectedModel(modelId);
    if (modelId) {
      localStorage.setItem('ai_model', modelId);
    } else {
      localStorage.removeItem('ai_model');
    }
  };

  const buildChatPayload = (overrides) => {
    const common = {
      model: selectedModel || null,
      ...overrides,
    };

    if (webSearch) {
      return {
        ...common,
        provider: selectedProvider || null,
        message: overrides.message,
        history: messages.filter(m => m.role !== 'system').map(m => ({ role: m.role, content: m.content })),
      };
    }

    return {
      ...common,
      stream: true,
      mode,
      document_id: mode === 'documents' ? selectedDocumentId : null,
      provider: selectedProvider || null,
      conversation_id: currentConversation?.id,
      message: overrides.message,
    };
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    await sendMessage(input);
  };

  const sendMessage = async (messageText) => {
    if (!messageText.trim() || loading) return;
    if (mode === 'documents' && !selectedDocumentId) {
      toast.error('Please upload and select a document first');
      return;
    }

    const userMessage = { id: createLocalId(), role: 'user', content: messageText };
    addMessage(userMessage);
    setInput('');
    setLoading(true);
    setIsTyping(true);

    try {
      const assistantId = createLocalId();
      addMessage({ id: assistantId, role: 'assistant', content: '', images: [] });
      let assistantMessage = '';
      let assistantImages = [];
      
      const endpoint = webSearch ? '/api/search/chat' : '/api/chat';

      await streamChat(
        buildChatPayload({ message: messageText }),
        (token) => {
          assistantMessage += token;
          setIsTyping(false);
          setMessages((prev) => {
            const next = [...prev];
            if (next.length === 0) return next;
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: assistantMessage,
            };
            return next;
          });
        },
        (finalPayload) => {
          assistantMessage = finalPayload.message || assistantMessage;
          assistantImages = finalPayload.images || [];
          setIsTyping(false);
          setMessages((prev) => {
            const next = [...prev];
            if (next.length === 0) return next;
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: assistantMessage,
              images: assistantImages,
            };
            return next;
          });
        },
        endpoint
      );

      if (autoSpeak) {
        speakText(assistantMessage, assistantId);
      }

      loadConversations();
    } catch (error) {
      const fallback = 'NOVA AI encountered an issue but is still running.';
      setIsTyping(false);
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant' && !last.content) {
          next[next.length - 1] = { ...last, content: fallback };
        } else {
          next.push({ id: createLocalId(), role: 'assistant', content: fallback });
        }
        return next;
      });
      toast.error('Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!currentConversation || loading) return;

    setLoading(true);
    setIsTyping(true);

    try {
      setMessages((prev) => {
        const nextMessages = [...prev];
        for (let i = nextMessages.length - 1; i >= 0; i -= 1) {
          if (nextMessages[i].role === 'assistant') {
            nextMessages.splice(i, 1);
            break;
          }
        }
        return nextMessages;
      });

      const assistantId = createLocalId();
      addMessage({ id: assistantId, role: 'assistant', content: '', images: [] });
      let assistantMessage = '';
      let assistantImages = [];
      const endpoint = webSearch ? '/api/search/chat' : '/api/chat';

      await streamChat(
        buildChatPayload({
          conversation_id: currentConversation.id,
        }),
        (token) => {
          assistantMessage += token;
          setIsTyping(false);
          setMessages((prev) => {
            const next = [...prev];
            if (next.length === 0) return next;
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: assistantMessage,
            };
            return next;
          });
        },
        (finalPayload) => {
          assistantMessage = finalPayload.message || assistantMessage;
          assistantImages = finalPayload.images || [];
          setIsTyping(false);
          setMessages((prev) => {
            const next = [...prev];
            if (next.length === 0) return next;
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: assistantMessage,
              images: assistantImages,
            };
            return next;
          });
        },
        endpoint
      );

      if (autoSpeak) {
        speakText(assistantMessage, assistantId);
      }

      loadConversations();
    } catch (error) {
      const fallback = 'NOVA AI encountered an issue but is still running.';
      setIsTyping(false);
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant' && !last.content) {
          next[next.length - 1] = { ...last, content: fallback };
        } else {
          next.push({ id: createLocalId(), role: 'assistant', content: fallback });
        }
        return next;
      });
      toast.error('Failed to regenerate response');
    } finally {
      setLoading(false);
    }
  };

  const startNewChat = () => {
    setCurrentConversation(null);
    setMessages([]);
  };


  const speakText = (text, messageId) => {
    if (!window.speechSynthesis) {
      toast.error('Voice output not supported in this browser');
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onend = () => setSpeakingId(null);
    utterance.onerror = () => setSpeakingId(null);
    setSpeakingId(messageId);
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setSpeakingId(null);
  };

  const handleExplain = async (content) => {
    try {
      const response = await explainAPI.explain({
        prompt: content,
        mode: 'deep',
        audience: 'general',
        detail: 'detailed',
      });
      addMessage({
        id: createLocalId(),
        role: 'assistant',
        content: response.data.explanation,
      });
    } catch (error) {
      toast.error('Failed to explain response');
    }
  };

  const handleSave = (content) => {
    const saved = JSON.parse(localStorage.getItem('savedResponses') || '[]');
    saved.unshift({
      id: createLocalId(),
      content,
      created_at: new Date().toISOString(),
      mode,
    });
    localStorage.setItem('savedResponses', JSON.stringify(saved.slice(0, 50)));
    toast.success('Response saved');
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await documentAPI.upload(formData);
      toast.success('Document uploaded');
      setDocuments((prev) => [response.data, ...prev]);
      setSelectedDocumentId(response.data.id);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const activeProvider = providers.find((provider) => provider.id === selectedProvider);
  const availableModels = activeProvider?.models || [];

  return (
    <Layout>
      <div className="flex h-full">
        {/* Conversation List */}
        <div className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
          <div className="p-4">
            <button
              onClick={startNewChat}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              <Plus className="w-4 h-4" />
              New Chat
            </button>
          </div>

          <div className="space-y-1 p-2">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                  currentConversation?.id === conv.id
                    ? 'bg-primary-100 dark:bg-primary-900'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                onClick={() => loadConversation(conv.id)}
              >
                <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {conv.title}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/20 rounded"
                >
                  <Trash2 className="w-4 h-4 text-red-600" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto">
            {messages.length === 0 && !isTyping ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    Welcome to NOVA AI
                  </h2>
                  <p className="text-gray-600 dark:text-gray-400">
                    Start a conversation and let AI assist you
                  </p>
                </div>
              </div>
            ) : (
              <div className="max-w-4xl mx-auto">
                {messages.map((msg, idx) => (
                  <MessageBubble
                    key={msg.id || idx}
                    message={msg}
                    isStreaming={
                      loading &&
                      idx === messages.length - 1 &&
                      msg.role === 'assistant'
                    }
                    onExplain={handleExplain}
                    onSave={handleSave}
                    onSpeak={(text) => speakText(text, msg.id || idx)}
                    onStopSpeak={stopSpeaking}
                    isSpeaking={speakingId === (msg.id || idx)}
                  />
                ))}
                {isTyping && <MessageBubble isTyping />}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 dark:border-gray-700 p-4">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
                <button
                  onClick={handleRegenerate}
                  disabled={!canRegenerate || loading}
                  className="btn-secondary disabled:opacity-50 flex items-center gap-2"
                >
                  <RefreshCcw className="w-4 h-4" />
                  Regenerate Response
                </button>
                <div className="flex items-center gap-2">
                   <button
                    onClick={() => setWebSearch(!webSearch)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                                border transition-all
                                ${webSearch
                                  ? "border-blue-500 bg-blue-500/10 text-blue-400"
                                  : "border-gray-700 text-gray-500 hover:border-gray-500"}`}
                  >
                    🔍 {webSearch ? "Search ON" : "Search OFF"}
                  </button>
                  {currentConversation?.id && (
                    <ShareButton
                      conversationId={currentConversation?.id}
                      conversationTitle={currentConversation?.title}
                    />
                  )}
                  <button
                    onClick={() => setAutoSpeak(!autoSpeak)}
                    className="btn-secondary flex items-center gap-2"
                  >
                    {autoSpeak ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
                    Voice
                  </button>
                  {providers.length > 0 && (
                    <>
                      <select
                        value={selectedProvider}
                        onChange={(e) => handleProviderChange(e.target.value)}
                        className="input-field w-40 text-sm"
                      >
                        {providers.map((provider) => (
                          <option key={provider.id} value={provider.id}>
                            {provider.name}
                          </option>
                        ))}
                      </select>
                      <select
                        value={selectedModel}
                        onChange={(e) => handleModelChange(e.target.value)}
                        className="input-field w-56 text-sm"
                        disabled={availableModels.length === 0}
                      >
                        {availableModels.map((model) => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>
                    </>
                  )}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn-secondary flex items-center gap-2"
                    disabled={uploading}
                  >
                    <Paperclip className="w-4 h-4" />
                    {uploading ? 'Uploading...' : 'Upload'}
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.txt,.docx"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                </div>
              </div>

              {mode === 'documents' && (
                <div className="mb-3">
                  <select
                    value={selectedDocumentId || ''}
                    onChange={(e) => setSelectedDocumentId(Number(e.target.value))}
                    className="input-field"
                  >
                    <option value="" disabled>Select a document</option>
                    {documents.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.filename}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex gap-2 items-end">
                <VoiceInput
                  onTranscript={(transcript) => {
                    setInput(transcript);
                  }}
                  disabled={loading}
                />
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Type your message..."
                  className="input-field flex-1 resize-none"
                  rows={2}
                  disabled={loading}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || loading}
                  className="btn-primary disabled:opacity-50 px-6"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default Chat;
