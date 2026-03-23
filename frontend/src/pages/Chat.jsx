// @ts-nocheck
import React, { startTransition, useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

import "../index.css";
import ChatInput from "../components/ChatInput";
import ChatWindow from "../components/ChatWindow";
import FeatureCards from "../components/FeatureCards";
import MouseSpark from "../components/MouseSpark";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import { chatAPI, documentAPI } from "../services/api";
import { useAuthStore } from "../utils/store";

const API_BASE = (import.meta.env.VITE_API_URL || "").trim();
const API_BASE_NORMALIZED = API_BASE.replace(/\/$/, "");
const API_ENDPOINT = API_BASE_NORMALIZED
  ? API_BASE_NORMALIZED.endsWith("/api")
    ? `${API_BASE_NORMALIZED}/chat`
    : `${API_BASE_NORMALIZED}/api/chat`
  : "/api/chat";
const REQUEST_TIMEOUT_MS = 120000;
const SESSION_STORAGE_KEY = "nova_session_id";
const MODEL_STORAGE_KEY = "nova_selected_model";
const PROMPT_IMAGE_STORAGE_KEY = "nova_generate_prompt_image";
const ANSWER_IMAGE_STORAGE_KEY = "nova_generate_answer_image";
const AUTO_MODEL_KEY = "auto";
const TEMPORAL_QUERY_PATTERN = /\b(current|latest|today|recent|news|breaking|updated|2024|2025|2026)\b/i;
const IMAGE_INTENT_PATTERNS = [
  /\b(?:generate|create|make|draw|design|illustrate|paint|render|show me|give me)\b[\s\S]{0,80}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|cover art|sticker|icon|mascot|avatar)\b/i,
  /\b(?:need|want)\b[\s\S]{0,24}\b(?:an?|some)\b[\s\S]{0,12}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|cover art|sticker|icon|mascot|avatar)\b(?:[\s\S]{0,24}\b(?:of|for|showing|with)\b|[.!?]?$)/i,
  /\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|sticker|icon|mascot|avatar)\b[\s\S]{0,40}\b(?:of|for|showing|with)\b/i,
  /^(?:show me|give me|make me)\b[\s\S]{0,60}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|sticker|icon|mascot|avatar)\b/i,
  /^(?:can you|could you|please)\b[\s\S]{0,40}\b(?:generate|create|make|draw|design|illustrate|paint|render|show|give|send)\b[\s\S]{0,90}\b(?:image|picture|photo|art|artwork|illustration|poster|logo|portrait|wallpaper|banner|thumbnail|cover art|sticker|icon|mascot|avatar)\b/i,
  /^(?:paint|illustrate|sketch)\b[\s\S]{0,220}$/i,
];
const ACTIVE_NAV_TO_MODE = {
  Chat: "chat",
  Search: "search",
  Code: "code",
  Customize: "chat",
  Chats: "chat",
  Projects: "chat",
  Artifacts: "chat",
};

const createMessage = (role, content, conversationId = null, extra = {}) => ({
  id:
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : String(Date.now() + Math.random()),
  role,
  content,
  conversation_id: conversationId,
  ...extra,
});

const normalizeConversation = (conversation) => ({
  id: conversation?.id,
  title: conversation?.title?.trim() || "New Chat",
  created_at: conversation?.created_at || null,
  updated_at: conversation?.updated_at || null,
});

const resolveDocumentContext = (meta) => {
  const rawId = meta?.document_id;
  const numericId = Number(rawId);
  const id = Number.isFinite(numericId) ? numericId : null;
  const name = typeof meta?.document_name === "string" && meta.document_name.trim()
    ? meta.document_name.trim()
    : null;

  return id ? { id, name } : null;
};

const withDocumentLabel = (content, role, meta) => {
  if (role !== "user") {
    return content || "";
  }

  const documentContext = resolveDocumentContext(meta);
  if (!documentContext?.name || String(content || "").includes("[File:")) {
    return content || "";
  }

  const base = String(content || "").trim();
  return `${base}${base ? " + " : ""}[File: ${documentContext.name}]`;
};

const normalizeMessage = (message, conversationId = null) => {
  const role = message?.role || "assistant";
  const meta = message?.meta || null;

  return {
    id:
      message?.id ??
      (typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : String(Date.now() + Math.random())),
    role,
    content: withDocumentLabel(message?.content || "", role, meta),
    conversation_id: message?.conversation_id || conversationId,
    images: Array.isArray(message?.images) ? message.images : [],
    meta,
  };
};

const extractDocumentContextFromMessages = (messageList = []) => {
  for (let index = messageList.length - 1; index >= 0; index -= 1) {
    const documentContext = resolveDocumentContext(messageList[index]?.meta);
    if (documentContext?.id) {
      return documentContext;
    }
  }
  return null;
};

const NAV_TO_INSTRUCTION = {
  Chat: [],
  Search: ["[Note: reference the most current info available]"],
  Customize: ["[Personalize the answer to the user's preferences when helpful]"],
  Chats: ["[Answer conversationally and clearly]"],
  Projects: ["[Break complex work into clear practical steps when useful]"],
  Artifacts: ["[Structure outputs so they can be reused as deliverables]"],
  Code: ["[Code mode: use markdown code blocks with language labels for all code]"],
};

const markdownToSpeechText = (value) =>
  String(value || "")
    .replace(/```[\s\S]*?```/g, " Code block omitted. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[#>*_~|-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const getResponseImages = (payload) => ({
  promptImages: Array.isArray(payload?.prompt_images) ? payload.prompt_images : [],
  answerImages: Array.isArray(payload?.answer_images)
    ? payload.answer_images
    : Array.isArray(payload?.images)
      ? payload.images
      : [],
});

const buildProgressStatus = ({
  text,
  isSearch = false,
  isImage = false,
  generatePromptImage = false,
  generateAnswerImage = false,
  regenerate = false,
}) => {
  const withImages = generatePromptImage || generateAnswerImage;

  if (isImage) {
    return regenerate
      ? "NOVA AI is regenerating your image..."
      : "NOVA AI is generating your image...";
  }

  if (regenerate) {
    if (withImages) {
      return isSearch
        ? "NOVA AI is re-checking the answer and refreshing the image..."
        : "NOVA AI is refining the answer and refreshing the image...";
    }
    return isSearch
      ? "NOVA AI is re-checking the latest information..."
      : "NOVA AI is refining the latest answer...";
  }

  if (withImages) {
    return isSearch || TEMPORAL_QUERY_PATTERN.test(text)
      ? "NOVA AI is searching and generating images..."
      : "NOVA AI is preparing the answer and images...";
  }

  return isSearch || TEMPORAL_QUERY_PATTERN.test(text)
    ? "NOVA AI is searching recent information..."
    : "Nova AI is thinking...";
};

const buildModelOptions = (providers = []) => {
  const seen = new Set([AUTO_MODEL_KEY]);
  const options = [
    {
      id: AUTO_MODEL_KEY,
      label: "Nova Fast",
      provider: null,
      model: null,
    },
  ];

  providers.forEach((provider) => {
    const providerId = String(provider?.id || "").trim();
    const providerName = String(provider?.name || providerId || "").trim();
    const models = Array.isArray(provider?.models) ? provider.models : [];

    models.forEach((modelName) => {
      const model = String(modelName || "").trim();
      const optionId = `${providerId}:${model}`;
      if (!providerId || !model || seen.has(optionId)) {
        return;
      }

      seen.add(optionId);
      options.push({
        id: optionId,
        label: `${providerName} - ${model}`,
        provider: providerId,
        model,
      });
    });
  });

  return options;
};

const getStoredModelKey = () => {
  if (typeof window === "undefined") {
    return AUTO_MODEL_KEY;
  }

  return window.localStorage.getItem(MODEL_STORAGE_KEY)?.trim() || AUTO_MODEL_KEY;
};

const getStoredToggle = (key, fallback = false) => {
  if (typeof window === "undefined") {
    return fallback;
  }

  const value = window.localStorage.getItem(key);
  if (value === null) {
    return fallback;
  }

  return value === "true";
};

const looksLikeImageRequest = (value) => {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return false;
  }

  return IMAGE_INTENT_PATTERNS.some((pattern) => pattern.test(normalized));
};

const getOrCreateSessionId = () => {
  if (typeof window === "undefined") {
    return "anonymous";
  }

  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY)?.trim();
  if (existing) {
    return existing;
  }

  const sessionId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  return sessionId;
};

const readSseEvents = async (response, onEvent) => {
  if (!response.body) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const processEventBlock = (rawEvent) => {
    const payload = rawEvent
      .split("\n")
      .filter((line) => line.startsWith("data: "))
      .map((line) => line.slice(6))
      .join("\n")
      .trim();

    if (!payload || payload === "[DONE]") {
      return;
    }

    try {
      onEvent(JSON.parse(payload));
    } catch {
      // Ignore malformed stream payloads.
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    events.forEach(processEventBlock);
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    processEventBlock(buffer);
  }
};

function Chat() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeNav, setActiveNav] = useState("Chat");
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isConversationLoading, setIsConversationLoading] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);
  const [generatePromptImage, setGeneratePromptImage] = useState(() =>
    getStoredToggle(PROMPT_IMAGE_STORAGE_KEY, false)
  );
  const [generateAnswerImage, setGenerateAnswerImage] = useState(() =>
    getStoredToggle(ANSWER_IMAGE_STORAGE_KEY, false)
  );
  const [activeDocumentContext, setActiveDocumentContext] = useState(null);
  const [availableProviders, setAvailableProviders] = useState([]);
  const [selectedModelKey, setSelectedModelKey] = useState(getStoredModelKey);

  const toolPrefix = useMemo(
    () => (NAV_TO_INSTRUCTION[activeNav] || []).join("\n"),
    [activeNav]
  );
  const resolvedMode = useMemo(() => ACTIVE_NAV_TO_MODE[activeNav] || "chat", [activeNav]);
  const modelOptions = useMemo(() => buildModelOptions(availableProviders), [availableProviders]);
  const selectedModelOption = useMemo(
    () => modelOptions.find((option) => option.id === selectedModelKey) || modelOptions[0],
    [modelOptions, selectedModelKey]
  );
  const regeneratableMessageId = useMemo(() => {
    if (!currentConversationId) {
      return null;
    }

    const lastAssistantMessage = [...messages].reverse().find((message) => message.role === "assistant");
    return lastAssistantMessage?.id || null;
  }, [currentConversationId, messages]);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login", { replace: true });
  }, [logout, navigate]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    setSpeechSupported(Boolean(window.speechSynthesis));

    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(MODEL_STORAGE_KEY, selectedModelKey);
  }, [selectedModelKey]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(PROMPT_IMAGE_STORAGE_KEY, String(generatePromptImage));
  }, [generatePromptImage]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(ANSWER_IMAGE_STORAGE_KEY, String(generateAnswerImage));
  }, [generateAnswerImage]);

  useEffect(() => {
    if (!modelOptions.some((option) => option.id === selectedModelKey)) {
      setSelectedModelKey(modelOptions[0]?.id || AUTO_MODEL_KEY);
    }
  }, [modelOptions, selectedModelKey]);

  const stopSpeaking = useCallback(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      return;
    }

    window.speechSynthesis.cancel();
    setSpeakingMessageId(null);
  }, []);

  const speakAssistantMessage = useCallback(
    (message) => {
      if (typeof window === "undefined" || !window.speechSynthesis || !message?.content) {
        return false;
      }

      const spokenText = markdownToSpeechText(message.content);
      if (!spokenText) {
        return false;
      }

      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(spokenText);
      utterance.rate = 1;
      utterance.pitch = 1;

      const voices = window.speechSynthesis.getVoices?.() || [];
      const preferredVoice =
        voices.find((voice) => voice.lang?.toLowerCase().startsWith("en-in")) ||
        voices.find((voice) => voice.lang?.toLowerCase().startsWith("en")) ||
        voices[0];

      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      setSpeakingMessageId(message.id);

      utterance.onend = () => {
        setSpeakingMessageId((current) => (current === message.id ? null : current));
      };

      utterance.onerror = () => {
        setSpeakingMessageId((current) => (current === message.id ? null : current));
      };

      window.speechSynthesis.speak(utterance);
      return true;
    },
    []
  );

  const handleSpeak = useCallback(
    (message) => {
      if (!message || !speechSupported) {
        return;
      }

      if (speakingMessageId === message.id) {
        stopSpeaking();
        return;
      }

      speakAssistantMessage(message);
    },
    [speakAssistantMessage, speakingMessageId, speechSupported, stopSpeaking]
  );

  const loadProviders = useCallback(async () => {
    try {
      const response = await chatAPI.getProviders();
      const providers = Array.isArray(response?.data) ? response.data : [];

      startTransition(() => {
        setAvailableProviders(providers);
      });
    } catch (error) {
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        handleUnauthorized();
        return;
      }

      startTransition(() => {
        setAvailableProviders([]);
      });
    }
  }, [handleUnauthorized]);

  const uploadDocumentForChat = useCallback(
    async (file) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await documentAPI.upload(formData, {
        onUploadProgress: (event) => {
          const total = event.total || file?.size || 0;
          if (!total) {
            setStatus(`Uploading ${file?.name || "document"}...`);
            return;
          }

          const progress = Math.min(100, Math.round((event.loaded / total) * 100));
          setStatus(`Uploading ${file?.name || "document"}... ${progress}%`);
        },
      });
      return {
        id: response?.data?.id,
        name: response?.data?.filename || file?.name || "document",
      };
    },
    []
  );

  const loadConversations = useCallback(
    async (selectedId = null) => {
      try {
        const response = await chatAPI.getConversations();
        const items = Array.isArray(response?.data)
          ? response.data.map(normalizeConversation).filter((conversation) => conversation.id)
          : [];

        startTransition(() => {
          setConversations(items);
        });

        if (selectedId && !items.some((conversation) => conversation.id === selectedId)) {
          startTransition(() => {
            setCurrentConversationId(null);
            setMessages([]);
            setActiveDocumentContext(null);
          });
        }
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
        }
      }
    },
    [handleUnauthorized]
  );

  const loadConversation = useCallback(
    async (conversationId) => {
      if (!conversationId) {
        return;
      }

      stopSpeaking();
      setIsConversationLoading(true);
      setStatus("Loading conversation...");

      try {
        const response = await chatAPI.getConversation(conversationId);
        const conversation = response?.data;
        const loadedMessages = Array.isArray(conversation?.messages)
          ? conversation.messages.map((message) => normalizeMessage(message, conversationId))
          : [];

        startTransition(() => {
          setActiveNav("Chat");
          setCurrentConversationId(conversation?.id || conversationId);
          setMessages(loadedMessages);
          setActiveDocumentContext(extractDocumentContextFromMessages(loadedMessages));
        });
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
        }
      } finally {
        setIsConversationLoading(false);
        setStatus("");
      }
    },
    [handleUnauthorized, stopSpeaking]
  );

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((previous) => !previous);
  };

  const handleNewChat = () => {
    stopSpeaking();
    setMessages([]);
    setInput("");
    setStatus("");
    setCurrentConversationId(null);
    setActiveDocumentContext(null);
    setActiveNav("Chat");
  };

  const handleDeleteConversation = useCallback(
    async (conversationId) => {
      if (!conversationId) {
        return;
      }

      try {
        await chatAPI.deleteConversation(conversationId);
        startTransition(() => {
          setConversations((previous) =>
            previous.filter((conversation) => conversation.id !== conversationId)
          );
        });

        if (conversationId === currentConversationId) {
          stopSpeaking();
          startTransition(() => {
            setCurrentConversationId(null);
            setMessages([]);
            setStatus("");
            setActiveDocumentContext(null);
          });
        }
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
        }
      }
    },
    [currentConversationId, handleUnauthorized, stopSpeaking]
  );

  const handleSend = useCallback(
    async (payload) => {
      const isStructuredPayload = payload && typeof payload === "object" && !Array.isArray(payload);
      const text = isStructuredPayload ? payload.text : payload;
      const displayText = isStructuredPayload ? payload.displayText : payload;
      const attachedFile = isStructuredPayload ? payload.file : null;
      const trimmed = String(text || "").trim();
      const displayValue = String(displayText || trimmed).trim();

      if (!trimmed || isTyping || isConversationLoading) {
        return;
      }

      stopSpeaking();
      const optimisticUserMessage = createMessage("user", displayValue || trimmed, currentConversationId, {
        images: [],
        meta: {
          generate_prompt_image: generatePromptImage,
          generate_answer_image: generateAnswerImage,
          ...(attachedFile?.name ? { document_name: attachedFile.name } : {}),
          ...(activeDocumentContext?.id && !attachedFile
            ? {
                document_id: activeDocumentContext.id,
                document_name: activeDocumentContext.name,
              }
            : {}),
        },
      });
      setMessages((previous) => [...previous, optimisticUserMessage]);
      setIsTyping(true);
      if (attachedFile?.name) {
        setStatus(`Reading ${attachedFile.name}...`);
      } else {
        const predictedImageRequest = resolvedMode === "chat" && looksLikeImageRequest(trimmed);
        setStatus(
          buildProgressStatus({
            text: trimmed,
            isSearch: activeNav === "Search",
            isImage: predictedImageRequest,
            generatePromptImage,
            generateAnswerImage,
          })
        );
      }

      let controller = null;
      let timeoutId = null;

      try {
        let documentContext = attachedFile ? null : activeDocumentContext;

        if (attachedFile) {
          const uploadedDocument = await uploadDocumentForChat(attachedFile);
          if (!uploadedDocument?.id) {
            throw new Error("Document upload did not return an id.");
          }
          documentContext = uploadedDocument;
          setActiveDocumentContext(uploadedDocument);
        }

        const requestMode = documentContext?.id
          ? "documents"
          : resolvedMode === "chat" && looksLikeImageRequest(trimmed)
            ? "image"
            : resolvedMode;
        setStatus(
          buildProgressStatus({
            text: trimmed,
            isSearch: requestMode === "search",
            isImage: requestMode === "image",
            generatePromptImage,
            generateAnswerImage,
          })
        );

        const prompt = requestMode === "documents"
          ? trimmed
          : toolPrefix
            ? `${toolPrefix}\n${trimmed}`
            : trimmed;
        const selectedProvider =
          selectedModelOption?.provider && selectedModelOption?.model
            ? {
                provider: selectedModelOption.provider,
                model: selectedModelOption.model,
              }
            : {};

        controller = new AbortController();
        timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        const token = localStorage.getItem("token");
        const assistantMessageId =
          typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : String(Date.now() + Math.random());
        const response = await fetch(API_ENDPOINT, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Session-ID": getOrCreateSessionId(),
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: prompt,
            stream: true,
            mode: requestMode,
            conversation_id: currentConversationId,
            ...(documentContext?.id ? { document_id: documentContext.id } : {}),
            ...selectedProvider,
            generate_prompt_image: generatePromptImage,
            generate_answer_image: generateAnswerImage,
          }),
          signal: controller.signal,
        });

        if (response.status === 401 || response.status === 403) {
          handleUnauthorized();
          return;
        }

        const contentType = response.headers.get("content-type") || "";
        const readJsonPayload = async () => {
          try {
            return await response.json();
          } catch {
            return null;
          }
        };

        if (!response.ok) {
          const data = await readJsonPayload();
          const detail = data?.detail || data?.message || `Request failed (${response.status})`;
          setMessages((previous) => [...previous, createMessage("assistant", detail, currentConversationId)]);
          return;
        }

        if (contentType.includes("application/json")) {
          const data = await readJsonPayload();
          const nextConversationId = data?.conversation_id || currentConversationId;
          const reply = data?.answer || data?.message || data?.response || "NOVA AI: ...";
          const { promptImages, answerImages } = getResponseImages(data);

          if (nextConversationId) {
            setCurrentConversationId(nextConversationId);
          }

          setMessages((previous) => {
            const updated = previous.map((message) =>
              message.id === optimisticUserMessage.id
                ? {
                    ...message,
                    conversation_id: nextConversationId,
                    images: promptImages,
                    meta: {
                      ...(message.meta || {}),
                      ...(documentContext?.id
                        ? {
                            document_id: documentContext.id,
                            document_name: documentContext.name,
                          }
                        : {}),
                    },
                  }
                : message
            );

            if (reply || answerImages.length) {
              updated.push(
                createMessage("assistant", reply, nextConversationId, {
                  id: assistantMessageId,
                  images: answerImages,
                })
              );
            }

            return updated;
          });

          if (documentContext?.id) {
            setActiveDocumentContext(documentContext);
          }

          await loadConversations(nextConversationId);
          return;
        }

        let streamedReply = "";
        let finalPayload = null;

        await readSseEvents(response, (parsed) => {
          if (!parsed || typeof parsed !== "object") {
            return;
          }

          if (parsed.type === "delta" && parsed.content) {
            streamedReply += parsed.content;
            setIsTyping(false);
            setMessages((previous) => {
              const updated = [...previous];
              const assistantIndex = updated.findIndex(
                (message) => message.id === assistantMessageId
              );
              const assistantMessage = createMessage(
                "assistant",
                streamedReply,
                currentConversationId,
                { id: assistantMessageId }
              );

              if (assistantIndex === -1) {
                updated.push(assistantMessage);
              } else {
                updated[assistantIndex] = {
                  ...updated[assistantIndex],
                  content: streamedReply,
                };
              }

              return updated;
            });
          }

          if (parsed.type === "final") {
            finalPayload = parsed;
            setIsTyping(false);
          }
        });

        const nextConversationId =
          finalPayload?.conversation_id || currentConversationId;
        const reply =
          finalPayload?.answer ||
          finalPayload?.message ||
          finalPayload?.response ||
          streamedReply ||
          "NOVA AI: ...";
        const { promptImages, answerImages } = getResponseImages(finalPayload);

        if (nextConversationId) {
          setCurrentConversationId(nextConversationId);
        }

        setMessages((previous) => {
          const updated = previous.map((message) =>
            message.id === optimisticUserMessage.id
              ? {
                  ...message,
                  conversation_id: nextConversationId,
                  images: promptImages,
                  meta: {
                    ...(message.meta || {}),
                    ...(documentContext?.id
                      ? {
                          document_id: documentContext.id,
                          document_name: documentContext.name,
                        }
                      : {}),
                  },
                }
              : message
          );

          const assistantIndex = updated.findIndex(
            (message) => message.id === assistantMessageId
          );
          if (assistantIndex === -1) {
            if (reply || answerImages.length) {
              updated.push(
                createMessage("assistant", reply, nextConversationId, {
                  id: assistantMessageId,
                  images: answerImages,
                })
              );
            }
          } else {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              conversation_id: nextConversationId,
              content: reply,
              images: answerImages,
            };
          }

          return updated;
        });

        if (documentContext?.id) {
          setActiveDocumentContext(documentContext);
        }

        await loadConversations(nextConversationId);
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
          return;
        }

        const uploadError =
          error?.response?.data?.detail ||
          error?.message ||
          null;
        if (uploadError && attachedFile) {
          toast.error(uploadError);
        }

        const timeoutMessage =
          error?.name === "AbortError"
            ? "NOVA AI did not finish within 2 minutes. Please try again in a moment."
            : uploadError || "NOVA AI encountered an issue but is still running.";

        setMessages((previous) => [
          ...previous,
          createMessage("assistant", timeoutMessage, currentConversationId),
        ]);
      } finally {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
        setIsTyping(false);
        setStatus("");
      }
    },
    [
      activeNav,
      activeDocumentContext,
      currentConversationId,
      handleUnauthorized,
      isConversationLoading,
      isTyping,
      loadConversations,
      selectedModelOption,
      resolvedMode,
      stopSpeaking,
      toolPrefix,
      uploadDocumentForChat,
      generateAnswerImage,
      generatePromptImage,
    ]
  );

  const handleRegenerate = useCallback(
    async (messageId) => {
      if (
        !currentConversationId ||
        !messageId ||
        messageId !== regeneratableMessageId ||
        isTyping ||
        isConversationLoading
      ) {
        return;
      }

      stopSpeaking();
      const documentContext = activeDocumentContext || extractDocumentContextFromMessages(messages);
      const targetMessage = messages.find((message) => message.id === messageId) || null;
      const lastUserContent = [...messages]
        .reverse()
        .find((message) => message.role === "user")?.content || "";
      const requestMode = documentContext?.id
        ? "documents"
        : resolvedMode === "chat" && looksLikeImageRequest(lastUserContent)
          ? "image"
          : resolvedMode;
      setIsTyping(true);
      setStatus(
        buildProgressStatus({
          isSearch: requestMode === "search",
          isImage: requestMode === "image",
          generateAnswerImage,
          regenerate: true,
        })
      );

      try {
        const response = await chatAPI.regenerate({
          conversation_id: currentConversationId,
          mode: requestMode,
          stream: false,
          previous_answer: targetMessage?.content || "",
          ...(documentContext?.id ? { document_id: documentContext.id } : {}),
          ...(selectedModelOption?.provider && selectedModelOption?.model
            ? {
                provider: selectedModelOption.provider,
                model: selectedModelOption.model,
              }
            : {}),
          generate_answer_image: generateAnswerImage,
        });
        const data = response?.data || {};
        const nextConversationId = data?.conversation_id || currentConversationId;
        const reply = data?.answer || data?.message || data?.response || "";
        const { promptImages, answerImages } = getResponseImages(data);

        if (nextConversationId) {
          setCurrentConversationId(nextConversationId);
        }

        startTransition(() => {
          setMessages((previous) => {
            const updated = [...previous];
            for (let index = updated.length - 1; index >= 0; index -= 1) {
              if (updated[index]?.role === "assistant") {
                updated.splice(index, 1);
                break;
              }
            }

            for (let index = updated.length - 1; index >= 0; index -= 1) {
              if (updated[index]?.role === "user") {
                updated[index] = {
                  ...updated[index],
                  conversation_id: nextConversationId,
                  images: promptImages.length ? promptImages : updated[index]?.images || [],
                };
                break;
              }
            }

            if (reply || answerImages.length) {
              updated.push(
                createMessage("assistant", reply, nextConversationId, {
                  images: answerImages,
                  meta: documentContext?.id
                    ? {
                        document_id: documentContext.id,
                        document_name: documentContext.name,
                      }
                    : null,
                })
              );
            }

            return updated;
          });
        });

        if (documentContext?.id) {
          setActiveDocumentContext(documentContext);
        }

        await loadConversations(nextConversationId);
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
          return;
        }

        const detail =
          error?.response?.data?.detail ||
          error?.response?.data?.message ||
          "NOVA AI could not regenerate that answer right now.";
        toast.error(detail);
      } finally {
        setIsTyping(false);
        setStatus("");
      }
    },
    [
      activeDocumentContext,
      currentConversationId,
      handleUnauthorized,
      isConversationLoading,
      isTyping,
      loadConversations,
      messages,
      regeneratableMessageId,
      selectedModelOption,
      resolvedMode,
      stopSpeaking,
      generateAnswerImage,
    ]
  );

  const handleSuggestion = (text) => {
    setInput(text);
    handleSend(text);
  };

  return (
    <>
      <MouseSpark />
      <div className="app">
        <Sidebar
          collapsed={isSidebarCollapsed}
          activeNav={activeNav}
          onNavChange={setActiveNav}
          onNewChat={handleNewChat}
          conversations={conversations}
          selectedConversationId={currentConversationId}
          onSelectConversation={loadConversation}
          onDeleteConversation={handleDeleteConversation}
        />
        <main className="chat-container">
          <Topbar title={activeNav} onToggleSidebar={handleToggleSidebar} />
          <ChatWindow
            messages={messages}
            isTyping={isTyping}
            status={status}
            regeneratableMessageId={regeneratableMessageId}
            onRegenerate={handleRegenerate}
            speechSupported={speechSupported}
            speakingMessageId={speakingMessageId}
            onSpeak={handleSpeak}
          />
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            disabled={isTyping || isConversationLoading}
            modelOptions={modelOptions}
            selectedModelKey={selectedModelOption?.id || AUTO_MODEL_KEY}
            onSelectModel={setSelectedModelKey}
            generatePromptImage={generatePromptImage}
            generateAnswerImage={generateAnswerImage}
            onTogglePromptImage={() => setGeneratePromptImage((previous) => !previous)}
            onToggleAnswerImage={() => setGenerateAnswerImage((previous) => !previous)}
          />
          <FeatureCards visible={!messages.length} onSelect={handleSuggestion} />
        </main>
      </div>
    </>
  );
}

export default Chat;
