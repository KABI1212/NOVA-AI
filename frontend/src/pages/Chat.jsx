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
import DragDropUploader from "../components/uploads/DragDropUploader";
import FilePreviewModal from "../components/uploads/FilePreviewModal";
import UploadedFilesPanel from "../components/uploads/UploadedFilesPanel";
import { chatAPI, fetchApi, filesAPI, imageAPI } from "../services/api";
import { speakText, speechSupported as browserSpeechSupported, stopSpeechPlayback } from "../utils/speech";
import { useAuthStore } from "../utils/store";
const REQUEST_TIMEOUT_MS = 600000;
const STREAM_RENDER_INTERVAL_MS = 32;
const SESSION_STORAGE_KEY = "nova_session_id";
const MODEL_STORAGE_KEY = "nova_selected_model";
const PROMPT_IMAGE_STORAGE_KEY = "nova_generate_prompt_image";
const ANSWER_IMAGE_STORAGE_KEY = "nova_generate_answer_image";
const AUTO_MODEL_KEY = "auto";
const TEMPORAL_QUERY_PATTERN = /\b(current|latest|today|recent|news|breaking|updated|2024|2025|2026)\b/i;
const FILE_POLL_INTERVAL_MS = 1500;
const READY_FILE_STATUSES = new Set(["ready"]);
const PENDING_FILE_STATUSES = new Set(["uploaded", "queued", "analyzing"]);
const FAILED_FILE_STATUSES = new Set(["failed", "failed-upload"]);
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
      : "NOVA AI is refining the answer...";
  }

  if (withImages) {
    return isSearch
      ? "NOVA AI is searching and generating images..."
      : "NOVA AI is preparing the answer and images...";
  }

  return isSearch
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

const resetSessionId = () => {
  if (typeof window === "undefined") {
    return "anonymous";
  }
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
  return getOrCreateSessionId();
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

const normalizeUploadedFile = (file) => ({
  ...file,
  id: file?.id || null,
  clientId:
    file?.clientId ||
    (typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `file-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`),
  original_name: file?.original_name || file?.name || file?.filename || "Uploaded file",
  status: String(file?.status || "uploaded").toLowerCase(),
  progress:
    file?.progress && typeof file.progress === "object"
      ? {
          ...file.progress,
          progress: Number(file.progress.progress || 0),
        }
      : {
          progress: file?.status === "ready" ? 100 : 0,
          stage: file?.status || "uploaded",
          message: file?.status === "ready" ? "Ready to chat" : "Uploading...",
        },
});

const mergeUploadedFiles = (previousFiles, nextFiles) => {
  const merged = [...previousFiles];

  nextFiles.forEach((file) => {
    const normalized = normalizeUploadedFile(file);
    const matchIndex = merged.findIndex(
      (item) =>
        (normalized.id && item.id === normalized.id) ||
        (!normalized.id && normalized.clientId && item.clientId === normalized.clientId)
    );

    if (matchIndex === -1) {
      merged.unshift(normalized);
      return;
    }

    merged[matchIndex] = {
      ...merged[matchIndex],
      ...normalized,
      progress: {
        ...(merged[matchIndex]?.progress || {}),
        ...(normalized.progress || {}),
      },
    };
  });

  return merged;
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

const scheduleStreamRender = (() => {
  if (typeof window === "undefined") {
    return (callback) => setTimeout(callback, STREAM_RENDER_INTERVAL_MS);
  }

  return (callback) => {
    const timeoutId = window.setTimeout(() => {
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(callback);
      } else {
        callback();
      }
    }, STREAM_RENDER_INTERVAL_MS);
    return timeoutId;
  };
})();

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
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [previewFile, setPreviewFile] = useState(null);
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
  const readySessionFiles = useMemo(
    () => uploadedFiles.filter((file) => READY_FILE_STATUSES.has(String(file?.status || "").toLowerCase())),
    [uploadedFiles]
  );
  const pendingSessionFiles = useMemo(
    () => uploadedFiles.filter((file) => PENDING_FILE_STATUSES.has(String(file?.status || "").toLowerCase())),
    [uploadedFiles]
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

  const loadUploadedFiles = useCallback(
    async (options = {}) => {
      const sessionId = getOrCreateSessionId();
      try {
        const response = await filesAPI.list({
          session_id: sessionId,
          ...(options?.conversationId ? { conversation_id: options.conversationId } : {}),
          page: 1,
          page_size: 50,
        });
        const items = Array.isArray(response?.data?.items)
          ? response.data.items.map(normalizeUploadedFile)
          : [];
        startTransition(() => {
          setUploadedFiles((previous) => {
            const retainedPrevious = previous.filter(
              (file) =>
                !file.id ||
                FAILED_FILE_STATUSES.has(String(file?.status || "").toLowerCase()) ||
                items.some((item) => item.id && item.id === file.id)
            );
            return mergeUploadedFiles(retainedPrevious, items);
          });
        });
        return items;
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
          return [];
        }
        return [];
      }
    },
    [handleUnauthorized]
  );

  const waitForFilesReady = useCallback(
    async (fileIds, timeoutMs = 90000) => {
      const targetIds = fileIds.filter(Boolean);
      if (!targetIds.length) {
        return [];
      }

      const startedAt = Date.now();
      for (;;) {
        const latestFiles = await loadUploadedFiles({ conversationId: currentConversationId });
        const targetFiles = latestFiles.filter((file) => targetIds.includes(file.id));
        if (targetFiles.length && targetFiles.every((file) => READY_FILE_STATUSES.has(file.status))) {
          return targetFiles;
        }
        if (targetFiles.some((file) => FAILED_FILE_STATUSES.has(file.status))) {
          return targetFiles;
        }
        if (Date.now() - startedAt > timeoutMs) {
          return targetFiles;
        }
        await new Promise((resolve) => window.setTimeout(resolve, FILE_POLL_INTERVAL_MS));
      }
    },
    [currentConversationId, loadUploadedFiles]
  );

  const uploadFilesToSession = useCallback(
    async (files) => {
      const sessionId = getOrCreateSessionId();
      const uploadedServerFiles = [];

      for (const file of files) {
        const clientId =
          typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : `local-file-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

        setUploadedFiles((previous) =>
          mergeUploadedFiles(previous, [
            {
              clientId,
              localFile: file,
              original_name: file.name,
              size: file.size,
              mime_type: file.type,
              status: "uploading",
              preview_text: "",
              progress: {
                progress: 0,
                stage: "uploading",
                message: "Uploading...",
              },
            },
          ])
        );

        try {
          const formData = new FormData();
          formData.append("files", file);
          formData.append("session_id", sessionId);
          if (currentConversationId) {
            formData.append("conversation_id", currentConversationId);
          }

          const response = await filesAPI.upload(formData, {
            onUploadProgress: (event) => {
              const total = Number(event?.total || file.size || 1);
              const loaded = Number(event?.loaded || 0);
              const progress = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
              setUploadedFiles((previous) =>
                mergeUploadedFiles(previous, [
                  {
                    clientId,
                    progress: {
                      progress,
                      stage: "uploading",
                      message: progress >= 100 ? "Upload complete" : `Uploading... ${progress}%`,
                    },
                    status: "uploading",
                  },
                ])
              );
            },
          });

          const serverFile = Array.isArray(response?.data?.files) ? response.data.files[0] : null;
          if (!serverFile?.id) {
            throw new Error("Upload succeeded, but the file record was missing.");
          }

          uploadedServerFiles.push(serverFile);
          setUploadedFiles((previous) =>
            mergeUploadedFiles(
              previous.filter((item) => item.clientId !== clientId),
              [{ ...serverFile, localFile: file }]
            )
          );
        } catch (error) {
          if (error?.response?.status === 401 || error?.response?.status === 403) {
            handleUnauthorized();
            return uploadedServerFiles;
          }
          setUploadedFiles((previous) =>
            mergeUploadedFiles(previous, [
              {
                clientId,
                localFile: file,
                original_name: file.name,
                size: file.size,
                mime_type: file.type,
                status: "failed-upload",
                error:
                  error?.response?.data?.detail ||
                  error?.message ||
                  "The file could not be uploaded.",
                progress: {
                  progress: 100,
                  stage: "failed",
                  message: "Upload failed",
                },
              },
            ])
          );
        }
      }

      if (uploadedServerFiles.length) {
        await loadUploadedFiles({ conversationId: currentConversationId });
      }
      return uploadedServerFiles;
    },
    [currentConversationId, handleUnauthorized, loadUploadedFiles]
  );

  const handleSelectFiles = useCallback(
    async (files) => {
      const selectedFiles = Array.isArray(files) ? files : Array.from(files || []);
      if (!selectedFiles.length) {
        return;
      }
      const uploaded = await uploadFilesToSession(selectedFiles);
      if (uploaded.length) {
        toast.success(
          uploaded.length === 1
            ? `${uploaded[0].original_name || uploaded[0].filename} is being analyzed.`
            : `${uploaded.length} files are being analyzed.`
        );
      }
    },
    [uploadFilesToSession]
  );

  const handleRetryUploadedFile = useCallback(
    async (file) => {
      if (!file) {
        return;
      }
      if (file.localFile instanceof File && !file.id) {
        await uploadFilesToSession([file.localFile]);
        setUploadedFiles((previous) => previous.filter((item) => item.clientId !== file.clientId));
        return;
      }
      try {
        await filesAPI.process(file.id);
        await loadUploadedFiles({ conversationId: currentConversationId });
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
          return;
        }
        toast.error(error?.response?.data?.detail || "Could not retry file analysis.");
      }
    },
    [currentConversationId, handleUnauthorized, loadUploadedFiles, uploadFilesToSession]
  );

  const handleRemoveUploadedFile = useCallback(
    async (file) => {
      if (!file) {
        return;
      }
      if (!file.id) {
        setUploadedFiles((previous) => previous.filter((item) => item.clientId !== file.clientId));
        return;
      }
      try {
        await filesAPI.remove(file.id);
        setUploadedFiles((previous) => previous.filter((item) => item.id !== file.id));
      } catch (error) {
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          handleUnauthorized();
          return;
        }
        toast.error(error?.response?.data?.detail || "Could not remove that file right now.");
      }
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
    loadUploadedFiles({ conversationId: currentConversationId });
  }, [currentConversationId, loadUploadedFiles]);

  useEffect(() => {
    if (!pendingSessionFiles.length) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      loadUploadedFiles({ conversationId: currentConversationId });
    }, FILE_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [currentConversationId, loadUploadedFiles, pendingSessionFiles.length]);

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
    resetSessionId();
    setMessages([]);
    setInput("");
    setStatus("");
    setCurrentConversationId(null);
    setUploadedFiles([]);
    setPreviewFile(null);
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
      const readyFileIds = readySessionFiles.map((file) => file.id).filter(Boolean);
      const predictedImageRequest =
        !hasDocumentAttachment &&
        (forceMode === "image" || (resolvedMode === "chat" && looksLikeImageRequest(trimmed)));
      const shouldContinueDocumentConversation =
        !hasDocumentAttachment &&
        !predictedImageRequest &&
        !forceMode &&
        resolvedMode === "chat" &&
        Boolean(activeDocumentReference?.id);
      const shouldUseSessionFiles =
        !predictedImageRequest &&
        (hasDocumentAttachment || readyFileIds.length > 0);
      if (!trimmed && hasImageAttachment && attachedFile && !predictedImageRequest) {
        trimmed = "Describe this image clearly.";
      }
      if (!trimmed && hasDocumentAttachment) {
        trimmed = "Summarize these files.";
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
          ...(readyFileIds.length ? { file_ids: readyFileIds } : {}),
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
          shouldUseSessionFiles
            ? "NOVA AI is analyzing your uploaded files..."
            :
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
        let activeFileIds = readyFileIds;

        if (!hasDocumentAttachment && pendingSessionFiles.length && !readySessionFiles.length && !predictedImageRequest) {
          setMessages((previous) => [
            ...previous,
            createMessage(
              "assistant",
              "Your files are still being analyzed. Give me a moment and ask again as soon as they show Ready to chat.",
              currentConversationId
            ),
          ]);
          return;
        }

        if (hasDocumentAttachment && attachedFile) {
          setStatus(`Uploading ${attachedFile.name || "document"}...`);
          const uploadedFiles = await uploadFilesToSession([attachedFile]);

          if (!uploadedFiles.length) {
            return;
          }

          const processedFiles = await waitForFilesReady(
            uploadedFiles.map((file) => file.id).filter(Boolean),
            90000
          );

          const failedProcessedFile = processedFiles.find((file) =>
            FAILED_FILE_STATUSES.has(String(file?.status || "").toLowerCase())
          );
          if (failedProcessedFile) {
            setMessages((previous) => [
              ...previous,
              createMessage(
                "assistant",
                failedProcessedFile?.error || "That file uploaded, but NOVA AI could not extract readable text from it.",
                currentConversationId
              ),
            ]);
            return;
          }

          const readyProcessedFiles = processedFiles.filter((file) =>
            READY_FILE_STATUSES.has(String(file?.status || "").toLowerCase())
          );

          if (!readyProcessedFiles.length) {
            setMessages((previous) => [
              ...previous,
              createMessage(
                "assistant",
                "The file is still analyzing. Ask again in a moment once it shows Ready to chat.",
                currentConversationId
              ),
            ]);
            return;
          }

          activeFileIds = readyProcessedFiles.map((file) => file.id).filter(Boolean);
          documentReference = {
            id: readyProcessedFiles[0]?.id ?? null,
            name: readyProcessedFiles[0]?.original_name || attachedFile.name || null,
          };

          setMessages((previous) =>
            previous.map((message) =>
              message.id === optimisticUserMessage.id
                ? {
                    ...message,
                    meta: {
                      ...(message.meta || {}),
                      attachment_kind: "document",
                      file_ids: activeFileIds,
                      ...(documentReference?.id != null ? { document_id: documentReference.id } : {}),
                      ...(documentReference?.name ? { document_name: documentReference.name } : {}),
                    },
                  }
                : message
            )
          );
        }

        const hasActiveUploadedFiles = activeFileIds.length > 0 && !predictedImageRequest;
        const requestMode = hasActiveUploadedFiles
          ? "files"
          : hasDocumentAttachment
            ? "documents"
            : forceMode || (shouldContinueDocumentConversation ? "documents" : predictedImageRequest ? "image" : resolvedMode);
        setStatus(
          hasActiveUploadedFiles
            ? "NOVA AI is answering from your uploaded files first..."
            : buildProgressStatus({
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
        const response = await fetchApi(hasActiveUploadedFiles ? "/chat/with-files" : "/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Session-ID": getOrCreateSessionId(),
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(
            hasActiveUploadedFiles
              ? {
                  message: prompt,
                  stream: true,
                  conversation_id: currentConversationId,
                  session_id: getOrCreateSessionId(),
                  file_ids: activeFileIds,
                  ...selectedProvider,
                }
              : {
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
                }
          ),
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
                      ...(requestMode === "files" && activeFileIds.length
                        ? { file_ids: activeFileIds }
                        : {}),
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
          await loadUploadedFiles({ conversationId: nextConversationId });
          return;
        }

        let streamedReply = "";
        let finalPayload = null;
        let pendingStreamRender = "";
        let streamRenderTimer = null;

        const flushStreamRender = () => {
          streamRenderTimer = null;
          const nextContent = pendingStreamRender;
          if (!nextContent) {
            return;
          }

          startTransition(() => {
            setMessages((previous) => {
              const updated = [...previous];
              const assistantIndex = updated.findIndex(
                (message) => message.id === assistantMessageId
              );
              const assistantMessage = createMessage(
                "assistant",
                nextContent,
                currentConversationId,
                { id: assistantMessageId, streaming: true }
              );

              if (assistantIndex === -1) {
                updated.push(assistantMessage);
              } else {
                updated[assistantIndex] = {
                  ...updated[assistantIndex],
                  content: nextContent,
                  streaming: true,
                };
              }

              return updated;
            });
          });
        };

        const queueStreamRender = () => {
          pendingStreamRender = streamedReply;
          if (streamRenderTimer != null) {
            return;
          }
          streamRenderTimer = scheduleStreamRender(flushStreamRender);
        };

        await readSseEvents(response, (parsed) => {
          if (!parsed || typeof parsed !== "object") {
            return;
          }

          if (parsed.type === "start") {
            setIsTyping(false);
            return;
          }

          if (parsed.type === "delta" && parsed.content) {
            streamedReply += parsed.content;
            setIsTyping(false);
            queueStreamRender();
          }

          if (parsed.type === "final") {
            finalPayload = parsed;
            setIsTyping(false);
          }
        });

        if (streamRenderTimer != null) {
          window.clearTimeout(streamRenderTimer);
          streamRenderTimer = null;
        }
        pendingStreamRender = streamedReply;
        flushStreamRender();

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
        if (finalPayload?.error === "retry" || finalPayload?.error === "partial") {
          toast.error("NOVA AI had to recover the stream. The answer shown is the safest completed text available.");
        }
        const assistantMessage =
          reply || answerImages.length
            ? createMessage("assistant", reply, nextConversationId, {
                id: assistantMessageId,
                images: answerImages,
                meta: {
                  ...(answerSources.length ? { sources: answerSources } : {}),
                  ...(finalPayload?.error ? { stream_recovered: true } : {}),
                },
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
                      ...(requestMode === "files" && activeFileIds.length
                        ? { file_ids: activeFileIds }
                        : {}),
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
        await loadUploadedFiles({ conversationId: nextConversationId });
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
      loadUploadedFiles,
      selectedModelOption,
      resolvedMode,
      stopSpeaking,
      toolPrefix,
      uploadFilesToSession,
      waitForFilesReady,
      generateAnswerImage,
      generatePromptImage,
      pendingSessionFiles,
      readySessionFiles,
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
      const readyFileIds = readySessionFiles.map((file) => file.id).filter(Boolean);
      const shouldUseFileMode =
        resolvedMode === "chat" &&
        readyFileIds.length > 0 &&
        !looksLikeImageRequest(lastUserContent);
      const shouldUseDocumentMode =
        !shouldUseFileMode &&
        resolvedMode === "chat" &&
        Boolean(activeDocumentReference?.id) &&
        !looksLikeImageRequest(lastUserContent);
      const requestMode = shouldUseFileMode
        ? "files"
        : shouldUseDocumentMode
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
        const response = shouldUseFileMode
          ? await chatAPI.sendMessageWithFiles({
              message: lastUserContent,
              conversation_id: currentConversationId,
              session_id: getOrCreateSessionId(),
              file_ids: readyFileIds,
              stream: false,
              ...(selectedModelOption?.provider && selectedModelOption?.model
                ? {
                    provider: selectedModelOption.provider,
                    model: selectedModelOption.model,
                  }
                : {}),
            })
          : await chatAPI.regenerate({
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
        await loadUploadedFiles({ conversationId: nextConversationId });
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
      readySessionFiles,
      regeneratableMessageId,
      selectedModelOption,
      resolvedMode,
      stopSpeaking,
      generateAnswerImage,
      loadUploadedFiles,
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
          <DragDropUploader
            onFilesSelected={handleSelectFiles}
            disabled={isTyping || isConversationLoading}
            className="mx-auto w-full max-w-[980px]"
          >
            <div className="space-y-4 px-4 pb-4 md:px-5">
              <UploadedFilesPanel
                files={uploadedFiles}
                onPreview={setPreviewFile}
                onRetry={handleRetryUploadedFile}
                onRemove={handleRemoveUploadedFile}
                disabled={isTyping || isConversationLoading}
              />
              <ChatInput
                value={input}
                onChange={setInput}
                onSend={handleSend}
                onSelectFiles={handleSelectFiles}
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
            </div>
          </DragDropUploader>
          <Settings
            open={isSettingsOpen}
            onClose={handleCloseSettings}
            onNewChat={handleNewChat}
            onExportChat={handleExportChat}
            canExportChat={Boolean(messages.length)}
          />
          <FilePreviewModal file={previewFile} open={Boolean(previewFile)} onClose={() => setPreviewFile(null)} />
        </main>
      </div>
    </>
  );
}

export default Chat;

