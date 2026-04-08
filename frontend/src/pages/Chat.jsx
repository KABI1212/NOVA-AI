// @ts-nocheck
import React, { startTransition, useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate, useSearchParams } from "react-router-dom";

import "../index.css";
import ChatInput from "../components/chat/ChatInput";
import ChatWindow from "../components/ChatWindow";
import MouseSpark from "../components/MouseSpark";
import Sidebar from "../components/chat/Sidebar";
import Settings from "../components/Settings";
import Topbar from "../components/Topbar";
import { chatAPI, fetchApi, fetchApp, imageAPI } from "../services/api";
import { speakText, speechSupported as browserSpeechSupported, stopSpeechPlayback } from "../utils/speech";
import { useAuthStore } from "../utils/store";
const REQUEST_TIMEOUT_MS = 240000;
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
const IMAGE_PROMPT_DETAIL_PATTERN =
  /\b(?:cinematic|photorealistic|hyperrealistic|realistic(?: style)?|highly detailed|ultra detailed|4k(?: quality)?|8k(?: quality)?|shallow depth of field|depth of field|soft natural lighting|natural lighting|studio lighting|golden hour|bokeh|concept art|watercolor|oil painting|digital art|render|matte painting|volumetric lighting|dramatic lighting)\b/gi;
const NON_IMAGE_HELP_PATTERN =
  /\b(?:explain|compare|difference|what|why|how|when|where|who|rewrite|improve|analyze|analysis|summarize)\b/i;
const ACTIVE_NAV_TO_MODE = {
  Chat: "chat",
  Search: "search",
  Code: "code",
  Explain: "chat",
  Reasoning: "chat",
  Knowledge: "chat",
  Learning: "chat",
  Images: "chat",
  Customize: "chat",
  Chats: "chat",
  Projects: "chat",
  Artifacts: "chat",
};
const DEFAULT_CHAT_NAV = "Chat";
const CHAT_NAV_VALUES = new Set([
  DEFAULT_CHAT_NAV,
  "Search",
  "Code",
  "Explain",
  "Reasoning",
  "Knowledge",
  "Learning",
  "Images",
  "Customize",
  "Chats",
  "Projects",
  "Artifacts",
]);

const normalizeChatNav = (value) => {
  const normalized = String(value || "").trim();
  return CHAT_NAV_VALUES.has(normalized) ? normalized : DEFAULT_CHAT_NAV;
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

const MESSAGE_REWRITE_SUFFIX_PATTERN = /(?:\s*\+\s*)?\[(?:File|Photo):\s*[^\]]+\]\s*$/i;

const getEditableQuestionText = (message) => {
  const content = String(message?.content || "").trim();
  const cleaned = content.replace(MESSAGE_REWRITE_SUFFIX_PATTERN, "").trim();
  return cleaned || content;
};

const normalizeConversation = (conversation) => ({
  id: conversation?.id,
  title: conversation?.title?.trim() || "New Chat",
  preview: conversation?.preview?.trim?.() ? conversation.preview.trim() : "",
  created_at: conversation?.created_at || null,
  updated_at: conversation?.updated_at || null,
});

const slugifyConversationTitle = (value) =>
  String(value || "nova-chat")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "nova-chat";

const buildConversationExport = (title, messages) => {
  const exportDate = new Date();
  const lines = [
    `# ${title || "NOVA Chat"}`,
    "",
    `Exported: ${exportDate.toLocaleString()}`,
    "",
  ];

  messages.forEach((message, index) => {
    const role = message?.role === "assistant" ? "NOVA AI" : "User";
    const content = String(message?.content || "").trim() || "(No text)";
    lines.push(`## ${role} ${index + 1}`);
    lines.push("");
    lines.push(content);

    if (Array.isArray(message?.meta?.sources) && message.meta.sources.length) {
      lines.push("");
      lines.push("Sources:");
      message.meta.sources.forEach((source) => {
        const titleText = String(
          source?.title || source?.label || source?.source || source?.url || "Source"
        ).trim();
        const urlText = String(source?.url || "").trim();
        const excerptText = String(source?.excerpt || "").trim();
        if (urlText) {
          lines.push(`- ${titleText}: ${urlText}`);
        } else if (excerptText) {
          lines.push(`- ${titleText}: ${excerptText}`);
        } else {
          lines.push(`- ${titleText}`);
        }
      });
    }

    if (Array.isArray(message?.images) && message.images.length) {
      lines.push("");
      lines.push(`Images attached in app: ${message.images.length}`);
    }

    lines.push("");
  });

  return lines.join("\n").trim();
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
    content: String(message?.content || ""),
    conversation_id: message?.conversation_id || conversationId,
    images: Array.isArray(message?.images) ? message.images : [],
    meta,
  };
};

const NAV_TO_INSTRUCTION = {
  Chat: [],
  Search: ["[Note: reference the most current info available]"],
  Explain: ["[Explain mode: answer step by step, use plain language first, then add detail where it helps.]"],
  Reasoning: ["[Reasoning mode: think carefully about tradeoffs, assumptions, and safer next steps before answering.]"],
  Knowledge: ["[Knowledge mode: answer like a strong tutor, organize ideas clearly, and include examples when useful.]"],
  Learning: ["[Learning mode: structure the answer as a practical learning path with milestones, sequence, and next steps.]"],
  Images: ["[Images mode: help with creating, refining, or remixing visual prompts and image outputs.]"],
  Customize: ["[Personalize the answer to the user's preferences when helpful]"],
  Chats: ["[Answer conversationally and clearly]"],
  Projects: ["[Break complex work into clear practical steps when useful]"],
  Artifacts: ["[Structure outputs so they can be reused as deliverables]"],
  Code: ["[Code mode: use markdown code blocks with language labels for all code]"],
};

const getResponseImages = (payload) => ({
  promptImages: Array.isArray(payload?.prompt_images) ? payload.prompt_images : [],
  answerImages: Array.isArray(payload?.answer_images)
    ? payload.answer_images
    : Array.isArray(payload?.images)
      ? payload.images
      : [],
});

const getResponseSources = (payload) =>
  Array.isArray(payload?.sources)
    ? payload.sources.filter(
        (item) =>
          item &&
          typeof item === "object" &&
          (item.url || item.label || item.title || item.excerpt)
      )
    : [];

const getDocumentReferenceFromMeta = (meta) => {
  if (!meta || typeof meta !== "object") {
    return null;
  }

  const rawDocumentId = meta.document_id;
  const parsedDocumentId = Number.parseInt(String(rawDocumentId ?? ""), 10);
  const documentId = Number.isFinite(parsedDocumentId) ? parsedDocumentId : null;
  const documentName = String(meta.document_name || "").trim() || null;

  if (documentId == null && !documentName) {
    return null;
  }

  return {
    id: documentId,
    name: documentName,
  };
};

const getLatestDocumentReference = (messages = []) => {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const reference = getDocumentReferenceFromMeta(messages[index]?.meta);
    if (reference?.id != null || reference?.name) {
      return reference;
    }
  }

  return null;
};

const buildProgressStatus = ({
  text,
  isSearch = false,
  isImage = false,
  isDocument = false,
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

  if (isDocument) {
    return regenerate
      ? "NOVA AI is revisiting your document..."
      : "NOVA AI is analyzing your document...";
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

const looksLikeImageRequest = (value) => {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return false;
  }

  if (IMAGE_INTENT_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return true;
  }

  if (NON_IMAGE_HELP_PATTERN.test(normalized)) {
    return false;
  }

  const detailMatches = normalized.match(IMAGE_PROMPT_DETAIL_PATTERN) || [];
  const commaCount = (normalized.match(/,/g) || []).length;
  return normalized.split(/\s+/).length >= 8 && commaCount >= 2 && detailMatches.length >= 2;
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

const IMAGE_ATTACHMENT_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"];

const isImageAttachment = (file) => {
  if (!file) {
    return false;
  }

  const fileType = String(file.type || "").toLowerCase();
  if (fileType.startsWith("image/")) {
    return true;
  }

  const fileName = String(file.name || "").toLowerCase();
  return IMAGE_ATTACHMENT_EXTENSIONS.some((extension) => fileName.endsWith(extension));
};

const readFileAsDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => {
      resolve(String(reader.result || ""));
    };

    reader.onerror = () => {
      reject(new Error(`Could not read ${file?.name || "the selected file"}.`));
    };

    reader.readAsDataURL(file);
  });

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

  for (;;) {
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
  const [searchParams, setSearchParams] = useSearchParams();
  const logout = useAuthStore((state) => state.logout);
  const requestedNav = searchParams.get("nav");
  const requestedPresetId = searchParams.get("preset");
  const initialActiveNav = normalizeChatNav(requestedNav);

  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeNav, setActiveNav] = useState(initialActiveNav);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isConversationLoading, setIsConversationLoading] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);
  const [generatePromptImage, setGeneratePromptImage] = useState(false);
  const [generateAnswerImage, setGenerateAnswerImage] = useState(false);
  const [imageGenerationAvailable, setImageGenerationAvailable] = useState(true);
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
  const activeDocumentReference = useMemo(
    () => getLatestDocumentReference(messages),
    [messages]
  );
  const currentConversationTitle = useMemo(() => {
    const activeConversation = conversations.find(
      (conversation) => conversation.id === currentConversationId
    );
    if (activeConversation?.title) {
      return activeConversation.title;
    }

    const firstUserMessage = messages.find((message) => message.role === "user")?.content?.trim() || "";
    if (!firstUserMessage) {
      return "New Chat";
    }

    return firstUserMessage.length > 60
      ? `${firstUserMessage.slice(0, 57)}...`
      : firstUserMessage;
  }, [conversations, currentConversationId, messages]);
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
    const nextNav = normalizeChatNav(requestedNav);
    setActiveNav((current) => (current === nextNav ? current : nextNav));
  }, [requestedNav]);

  const handleNavChange = useCallback(
    (nextNav) => {
      const normalizedNav = normalizeChatNav(nextNav);
      setActiveNav(normalizedNav);

      const nextParams = new URLSearchParams(searchParams);
      if (normalizedNav === DEFAULT_CHAT_NAV) {
        nextParams.delete("nav");
      } else {
        nextParams.set("nav", normalizedNav);
      }

      setSearchParams(nextParams, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    setSpeechSupported(browserSpeechSupported());

    return () => {
      stopSpeechPlayback();
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

    window.localStorage.removeItem(PROMPT_IMAGE_STORAGE_KEY);
    window.localStorage.removeItem(ANSWER_IMAGE_STORAGE_KEY);
  }, []);

  useEffect(() => {
    if (!modelOptions.some((option) => option.id === selectedModelKey)) {
      setSelectedModelKey(modelOptions[0]?.id || AUTO_MODEL_KEY);
    }
  }, [modelOptions, selectedModelKey]);

  const stopSpeaking = useCallback(() => {
    stopSpeechPlayback();
    setSpeakingMessageId(null);
  }, []);

  const speakAssistantMessage = useCallback(
    (message) => {
      if (!message?.content) {
        return false;
      }

      const started = speakText(message.content, {
        onStart: () => {
          setSpeakingMessageId(message.id);
        },
        onEnd: () => {
          setSpeakingMessageId((current) => (current === message.id ? null : current));
        },
        onError: () => {
          setSpeakingMessageId((current) => (current === message.id ? null : current));
        },
      });

      if (!started) {
        setSpeakingMessageId(null);
      }

      return started;
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

  const loadImageProviders = useCallback(async () => {
    try {
      const response = await imageAPI.getProviders();
      const providers = Array.isArray(response?.data?.providers) ? response.data.providers : [];
      const hasWorkingImageProvider = providers.some(
        (provider) => provider?.id && provider.id !== "auto" && provider.available
      );

      startTransition(() => {
        setImageGenerationAvailable(hasWorkingImageProvider);
      });
    } catch (error) {
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        handleUnauthorized();
      }
    }
  }, [handleUnauthorized]);

  const uploadDocument = useCallback(
    async (file) => {
      const formData = new FormData();
      formData.append("file", file);

      const token = localStorage.getItem("token");
      const uploadTargets = [
        { path: "/document/upload", request: fetchApi },
        { path: "/upload-document", request: fetchApp },
      ];

      let lastError = null;

      for (const target of uploadTargets) {
        const response = await target.request(target.path, {
          method: "POST",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: formData,
        });

        if (response.status === 401 || response.status === 403) {
          handleUnauthorized();
          return null;
        }

        let payload = null;
        try {
          payload = await response.json();
        } catch {
          payload = null;
        }

        if (response.ok) {
          return payload;
        }

        if (response.status === 404 || response.status === 405) {
          lastError =
            payload?.detail || payload?.message || `Document upload failed (${response.status})`;
          continue;
        }

        throw new Error(
          payload?.detail || payload?.message || `Document upload failed (${response.status})`
        );
      }

      throw new Error(lastError || "Document upload failed.");
    },
    [handleUnauthorized]
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
          setCurrentConversationId(conversation?.id || conversationId);
          setMessages(loadedMessages);
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

  useEffect(() => {
    loadImageProviders();
  }, [loadImageProviders]);

  useEffect(() => {
    if (imageGenerationAvailable) {
      return;
    }

    setGeneratePromptImage(false);
    setGenerateAnswerImage(false);
  }, [imageGenerationAvailable]);

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((previous) => !previous);
  };

  const handleNewChat = () => {
    stopSpeaking();
    setMessages([]);
    setInput("");
    setStatus("");
    setCurrentConversationId(null);
    handleNavChange(DEFAULT_CHAT_NAV);
  };

  const handleOpenSettings = () => {
    setIsSettingsOpen(true);
  };

  const handleCloseSettings = () => {
    setIsSettingsOpen(false);
  };

  const handleExportChat = useCallback(() => {
    const exportableMessages = messages.filter(
      (message) =>
        String(message?.content || "").trim() ||
        (Array.isArray(message?.images) && message.images.length)
    );

    if (!exportableMessages.length) {
      toast.error("There is no chat to export yet.");
      return;
    }

    if (typeof window === "undefined") {
      toast.error("Chat export is only available in the browser.");
      return;
    }

    const exportTitle = currentConversationTitle || "NOVA Chat";
    const fileName = `${slugifyConversationTitle(exportTitle)}.md`;
    const exportContent = buildConversationExport(exportTitle, exportableMessages);
    const blob = new Blob([exportContent], { type: "text/markdown;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    toast.success("Chat exported successfully.");
  }, [currentConversationTitle, messages]);

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

  const handleRenameConversation = useCallback(
    async (conversationId, nextTitle) => {
      if (!conversationId) {
        return;
      }

      const title = String(nextTitle || "").trim();
      if (!title) {
        toast.error("Conversation title cannot be empty.");
        return;
      }

      try {
        const response = await chatAPI.updateConversation(conversationId, { title });
        const updatedConversation = normalizeConversation(response?.data || { id: conversationId, title });

        startTransition(() => {
          setConversations((previous) => {
            const found = previous.some((conversation) => conversation.id === conversationId);
            if (!found) {
              return [updatedConversation, ...previous];
            }

            return previous.map((conversation) =>
              conversation.id === conversationId
                ? { ...conversation, ...updatedConversation }
                : conversation
            );
          });
        });

        toast.success(response?.data?.message || "Conversation renamed.");
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
          return;
        }

        toast.error(
          error?.response?.data?.detail || "Could not rename this conversation right now."
        );
      }
    },
    [handleUnauthorized]
  );

  const handleSend = useCallback(
    async (payload) => {
      const isStructuredPayload = payload && typeof payload === "object" && !Array.isArray(payload);
      const text = isStructuredPayload ? payload.text : payload;
      const displayText = isStructuredPayload ? payload.displayText : payload;
      const attachedFile = isStructuredPayload ? payload.file : null;
      const attachmentKind = isStructuredPayload ? payload.attachmentKind : null;
      const forceMode = isStructuredPayload ? payload.forceMode : null;
      const promptPrefix = isStructuredPayload ? payload.promptPrefix : "";
      const presetLabel = isStructuredPayload ? payload.presetLabel : null;
      let trimmed = String(text || "").trim();
      const hasImageAttachment = attachmentKind === "image" || isImageAttachment(attachedFile);
      const hasDocumentAttachment = Boolean(attachedFile && !hasImageAttachment);
      const predictedImageRequest =
        !hasDocumentAttachment &&
        (forceMode === "image" || (resolvedMode === "chat" && looksLikeImageRequest(trimmed)));
      const shouldContinueDocumentConversation =
        !hasDocumentAttachment &&
        !predictedImageRequest &&
        !forceMode &&
        resolvedMode === "chat" &&
        Boolean(activeDocumentReference?.id);
      if (!trimmed && hasImageAttachment && attachedFile && !predictedImageRequest) {
        trimmed = "Describe this image clearly.";
      }
      if (!trimmed && hasDocumentAttachment) {
        trimmed = "Summarize this document.";
      }
      const displayValue = String(displayText || trimmed).trim();
      const effectiveGeneratePromptImage = imageGenerationAvailable && generatePromptImage;
      const effectiveGenerateAnswerImage = imageGenerationAvailable && generateAnswerImage;
      let attachedImageDataUrl = null;

      if (!trimmed || isTyping || isConversationLoading) {
        return;
      }

      if (hasImageAttachment && attachedFile && !predictedImageRequest) {
        attachedImageDataUrl = await readFileAsDataUrl(attachedFile);
      }

      const initialDocumentReference = shouldContinueDocumentConversation
        ? activeDocumentReference
        : null;

      stopSpeaking();
      const optimisticUserMessage = createMessage("user", displayValue || trimmed, currentConversationId, {
        images: attachedImageDataUrl ? [attachedImageDataUrl] : [],
        meta: {
          generate_prompt_image: effectiveGeneratePromptImage,
          generate_answer_image: effectiveGenerateAnswerImage,
          ...(presetLabel ? { quick_mode: presetLabel } : {}),
          ...(hasImageAttachment ? { attachment_kind: "image" } : {}),
          ...(hasDocumentAttachment ? { attachment_kind: "document" } : {}),
          ...(attachedImageDataUrl ? { image_origin: "upload" } : {}),
          ...(initialDocumentReference?.id != null ? { document_id: initialDocumentReference.id } : {}),
          ...(initialDocumentReference?.name ? { document_name: initialDocumentReference.name } : {}),
        },
      });
      setMessages((previous) => [...previous, optimisticUserMessage]);
      setIsTyping(true);
      if (attachedFile?.name) {
        setStatus(
          hasImageAttachment
            ? `Preparing ${attachedFile.name}...`
            : hasDocumentAttachment
              ? `Uploading ${attachedFile.name}...`
              : `Reading ${attachedFile.name}...`
        );
      } else {
        setStatus(
          buildProgressStatus({
            text: trimmed,
            isSearch: forceMode === "search" || activeNav === "Search",
            isImage: predictedImageRequest,
            isDocument: shouldContinueDocumentConversation,
            generatePromptImage: effectiveGeneratePromptImage,
            generateAnswerImage: effectiveGenerateAnswerImage,
          })
        );
      }

      let controller = null;
      let timeoutId = null;

      try {
        if (predictedImageRequest && !attachedFile) {
          setStatus("NOVA AI is generating your image...");
          const response = await imageAPI.generate({
            prompt: trimmed,
            size: "1024x1024",
            quality: "standard",
            style: "vivid",
          });
          const images = Array.isArray(response?.data?.images)
            ? response.data.images
            : response?.data?.url
              ? [response.data.url]
              : [];
          const imageError = response?.data?.error || null;

          if (!images.length) {
            throw new Error(imageError || "Image generation returned no images.");
          }

          const assistantMessage = createMessage(
            "assistant",
            "## **✨ Image Ready**\nHere is the image generated from your prompt.",
            currentConversationId,
            { images }
          );
          setMessages((previous) => [...previous, assistantMessage]);
          return;
        }

        if (hasImageAttachment && attachedFile && predictedImageRequest) {
          setStatus(`Remixing ${attachedFile.name || "photo"}...`);
          const imageDataUrl = attachedImageDataUrl || (await readFileAsDataUrl(attachedFile));
          const imageBase64 = imageDataUrl.includes(",") ? imageDataUrl.split(",")[1] : imageDataUrl;
          const response = await imageAPI.variation({
            prompt: trimmed,
            image_b64: imageBase64,
            mime_type: attachedFile.type || "image/png",
          });
          const images = Array.isArray(response?.data?.images)
            ? response.data.images
            : response?.data?.url
              ? [response.data.url]
              : [];

          if (!images.length) {
            throw new Error("Image editing returned no images.");
          }

          const assistantMessage = createMessage(
            "assistant",
            trimmed
              ? "## **✨ Image Remix Ready**\nI used your uploaded photo and prompt to create a fresh visual."
              : "## **✨ Image Remix Ready**\nI created a fresh visual from your uploaded photo.",
            currentConversationId,
            {
              images,
            }
          );

          setMessages((previous) => {
            const updated = previous.map((message) =>
              message.id === optimisticUserMessage.id
                ? {
                    ...message,
                    images: [imageDataUrl],
                    meta: {
                      ...(message.meta || {}),
                      attachment_kind: "image",
                      image_origin: "upload",
                    },
                  }
                : message
            );

            updated.push(assistantMessage);

            return updated;
          });

          return;
        }

        let documentReference = initialDocumentReference;

        if (hasDocumentAttachment && attachedFile) {
          setStatus(`Uploading ${attachedFile.name || "document"}...`);
          const uploadedDocument = await uploadDocument(attachedFile);

          if (!uploadedDocument) {
            return;
          }

          documentReference = {
            id: uploadedDocument?.id ?? null,
            name: uploadedDocument?.filename || attachedFile.name || null,
          };

          setMessages((previous) =>
            previous.map((message) =>
              message.id === optimisticUserMessage.id
                ? {
                    ...message,
                    meta: {
                      ...(message.meta || {}),
                      attachment_kind: "document",
                      ...(documentReference?.id != null ? { document_id: documentReference.id } : {}),
                      ...(documentReference?.name ? { document_name: documentReference.name } : {}),
                    },
                  }
                : message
            )
          );

          if (documentReference?.id == null) {
            throw new Error("Document upload did not return a document id.");
          }

          if (!uploadedDocument?.is_processed) {
            const detail =
              uploadedDocument?.summary ||
              "The document uploaded, but no readable text could be extracted.";
            setMessages((previous) => [
              ...previous,
              createMessage("assistant", detail, currentConversationId),
            ]);
            return;
          }
        }

        const requestMode = hasDocumentAttachment
          ? "documents"
          : forceMode || (shouldContinueDocumentConversation ? "documents" : predictedImageRequest ? "image" : resolvedMode);
        setStatus(
          buildProgressStatus({
            text: trimmed,
            isSearch: requestMode === "search",
            isImage: requestMode === "image",
            isDocument: requestMode === "documents",
            generatePromptImage: effectiveGeneratePromptImage,
            generateAnswerImage: effectiveGenerateAnswerImage,
          })
        );

        const trimmedPromptPrefix = String(promptPrefix || "").trim();
        const combinedPromptPrefix = [toolPrefix, trimmedPromptPrefix].filter(Boolean).join("\n");
        const prompt = combinedPromptPrefix
          ? `${combinedPromptPrefix}\n${trimmed}`
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
        const response = await fetchApi("/chat", {
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
            ...selectedProvider,
            generate_prompt_image: effectiveGeneratePromptImage,
            generate_answer_image: effectiveGenerateAnswerImage,
            ...(requestMode === "documents" && documentReference?.id != null
              ? { document_id: documentReference.id }
              : {}),
            ...(attachedImageDataUrl
              ? {
                  image_b64: attachedImageDataUrl.includes(",")
                    ? attachedImageDataUrl.split(",")[1]
                    : attachedImageDataUrl,
                  image_mime_type: attachedFile?.type || "image/png",
                }
              : {}),
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
          const answerSources = getResponseSources(data);
          const assistantMessage =
            reply || answerImages.length
              ? createMessage("assistant", reply, nextConversationId, {
                  id: assistantMessageId,
                  images: answerImages,
                  meta: answerSources.length ? { sources: answerSources } : null,
                })
              : null;

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
                      ...(requestMode === "documents" && documentReference?.id != null
                        ? { document_id: documentReference.id }
                        : {}),
                      ...(requestMode === "documents" && documentReference?.name
                        ? { document_name: documentReference.name }
                        : {}),
                    },
                  }
                : message
            );

            if (assistantMessage) {
              updated.push(assistantMessage);
            }

            return updated;
          });

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
        const answerSources = getResponseSources(finalPayload);
        const assistantMessage =
          reply || answerImages.length
            ? createMessage("assistant", reply, nextConversationId, {
                id: assistantMessageId,
                images: answerImages,
                meta: answerSources.length ? { sources: answerSources } : null,
              })
            : null;

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
                      ...(requestMode === "documents" && documentReference?.id != null
                        ? { document_id: documentReference.id }
                        : {}),
                      ...(requestMode === "documents" && documentReference?.name
                        ? { document_name: documentReference.name }
                        : {}),
                    },
                  }
                : message
          );

          const assistantIndex = updated.findIndex(
            (message) => message.id === assistantMessageId
          );
          if (assistantIndex === -1) {
            if (assistantMessage) {
              updated.push(assistantMessage);
            }
          } else if (assistantMessage) {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              ...assistantMessage,
            };
          }

          return updated;
        });

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
      currentConversationId,
      handleUnauthorized,
      activeNav,
      activeDocumentReference,
      imageGenerationAvailable,
      isConversationLoading,
      isTyping,
      loadConversations,
      selectedModelOption,
      resolvedMode,
      stopSpeaking,
      toolPrefix,
      uploadDocument,
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
      const targetMessage = messages.find((message) => message.id === messageId) || null;
      const lastUserContent = [...messages]
        .reverse()
        .find((message) => message.role === "user")?.content || "";
      const effectiveGenerateAnswerImage = imageGenerationAvailable && generateAnswerImage;
      const shouldUseDocumentMode =
        resolvedMode === "chat" &&
        Boolean(activeDocumentReference?.id) &&
        !looksLikeImageRequest(lastUserContent);
      const requestMode = shouldUseDocumentMode
        ? "documents"
        : resolvedMode === "chat" && looksLikeImageRequest(lastUserContent)
          ? "image"
          : resolvedMode;
      setIsTyping(true);
      setStatus(
        buildProgressStatus({
          isSearch: requestMode === "search",
          isImage: requestMode === "image",
          isDocument: requestMode === "documents",
          generateAnswerImage: effectiveGenerateAnswerImage,
          regenerate: true,
        })
      );

      try {
        const response = await chatAPI.regenerate({
          conversation_id: currentConversationId,
          mode: requestMode,
          stream: false,
          previous_answer: targetMessage?.content || "",
          ...(selectedModelOption?.provider && selectedModelOption?.model
            ? {
                provider: selectedModelOption.provider,
                model: selectedModelOption.model,
              }
            : {}),
          ...(requestMode === "documents" && activeDocumentReference?.id != null
            ? { document_id: activeDocumentReference.id }
            : {}),
          generate_answer_image: effectiveGenerateAnswerImage,
        });
        const data = response?.data || {};
        const nextConversationId = data?.conversation_id || currentConversationId;
        const reply = data?.answer || data?.message || data?.response || "";
        const { promptImages, answerImages } = getResponseImages(data);
        const answerSources = getResponseSources(data);
        const assistantMessage =
          reply || answerImages.length
            ? createMessage("assistant", reply, nextConversationId, {
                images: answerImages,
                meta: {
                  ...(answerSources.length ? { sources: answerSources } : {}),
                },
              })
            : null;

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

            if (assistantMessage) {
              updated.push(assistantMessage);
            }

            return updated;
          });
        });

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
      currentConversationId,
      handleUnauthorized,
      imageGenerationAvailable,
      isConversationLoading,
      isTyping,
      loadConversations,
      messages,
      activeDocumentReference,
      regeneratableMessageId,
      selectedModelOption,
      resolvedMode,
      stopSpeaking,
      generateAnswerImage,
    ]
  );

  const handleRewriteQuestion = useCallback(
    (message) => {
      const rewrittenInput = getEditableQuestionText(message);
      if (!rewrittenInput) {
        toast.error("That question could not be loaded for editing.");
        return;
      }

      stopSpeaking();
      setInput(rewrittenInput);

      setStatus("");
      window.setTimeout(() => {
        const textarea = document.querySelector(".input-field");
        if (!(textarea instanceof HTMLTextAreaElement)) {
          return;
        }

        textarea.focus();
        const cursorPosition = textarea.value.length;
        try {
          textarea.setSelectionRange(cursorPosition, cursorPosition);
        } catch {
          // Ignore cursor placement issues from browser-specific textarea implementations.
        }
      }, 0);

      toast.success("Question added back to the input. Edit it and send.");
    },
    [stopSpeaking]
  );

  return (
    <>
      <MouseSpark />
      <div className="app">
        <Sidebar
          collapsed={isSidebarCollapsed}
          activeNav={activeNav}
          onNavChange={handleNavChange}
          onNewChat={handleNewChat}
          conversations={conversations}
          selectedConversationId={currentConversationId}
          onSelectConversation={loadConversation}
          onRenameConversation={handleRenameConversation}
          onDeleteConversation={handleDeleteConversation}
        />
        <main className="chat-container">
          <Topbar
            title={activeNav}
            onToggleSidebar={handleToggleSidebar}
            conversationId={currentConversationId}
            conversationTitle={currentConversationTitle}
            onProfileClick={handleOpenSettings}
            profileActive={isSettingsOpen}
          />
          <ChatWindow
            messages={messages}
            activeNav={activeNav}
            isTyping={isTyping}
            status={status}
            regeneratableMessageId={regeneratableMessageId}
            onRegenerate={handleRegenerate}
            onRewriteQuestion={handleRewriteQuestion}
            speechSupported={speechSupported}
            speakingMessageId={speakingMessageId}
            onSpeak={handleSpeak}
          />
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            disabled={isTyping || isConversationLoading}
            requestedPresetId={requestedPresetId}
            modelOptions={modelOptions}
            selectedModelKey={selectedModelOption?.id || AUTO_MODEL_KEY}
            onSelectModel={setSelectedModelKey}
            generatePromptImage={imageGenerationAvailable && generatePromptImage}
            generateAnswerImage={imageGenerationAvailable && generateAnswerImage}
            onTogglePromptImage={() => {
              if (!imageGenerationAvailable) {
                return;
              }
              setGeneratePromptImage((previous) => !previous);
            }}
            onToggleAnswerImage={() => {
              if (!imageGenerationAvailable) {
                return;
              }
              setGenerateAnswerImage((previous) => !previous);
            }}
          />
          <Settings
            open={isSettingsOpen}
            onClose={handleCloseSettings}
            onNewChat={handleNewChat}
            onExportChat={handleExportChat}
            canExportChat={Boolean(messages.length)}
          />
        </main>
      </div>
    </>
  );
}

export default Chat;

