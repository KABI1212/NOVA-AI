// @ts-nocheck
import React, { startTransition, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import "../index.css";
import ChatInput from "../components/ChatInput";
import ChatWindow from "../components/ChatWindow";
import FeatureCards from "../components/FeatureCards";
import MouseSpark from "../components/MouseSpark";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import { chatAPI } from "../services/api";
import { useAuthStore } from "../utils/store";

const API_BASE = (import.meta.env.VITE_API_URL || "").trim();
const API_BASE_NORMALIZED = API_BASE.replace(/\/$/, "");
const API_ENDPOINT = API_BASE_NORMALIZED
  ? API_BASE_NORMALIZED.endsWith("/api")
    ? `${API_BASE_NORMALIZED}/chat`
    : `${API_BASE_NORMALIZED}/api/chat`
  : "/api/chat";
const REQUEST_TIMEOUT_MS = 120000;
const TEMPORAL_QUERY_PATTERN = /\b(current|latest|today|recent|news|breaking|updated|2024|2025|2026)\b/i;
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

const normalizeMessage = (message, conversationId = null) => ({
  id:
    message?.id ??
    (typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : String(Date.now() + Math.random())),
  role: message?.role || "assistant",
  content: message?.content || "",
  conversation_id: message?.conversation_id || conversationId,
  images: Array.isArray(message?.images) ? message.images : [],
  meta: message?.meta || null,
});

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
  generatePromptImage = false,
  generateAnswerImage = false,
  regenerate = false,
}) => {
  const withImages = generatePromptImage || generateAnswerImage;

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
  const [generatePromptImage, setGeneratePromptImage] = useState(false);
  const [generateAnswerImage, setGenerateAnswerImage] = useState(true);

  const toolPrefix = useMemo(
    () => (NAV_TO_INSTRUCTION[activeNav] || []).join("\n"),
    [activeNav]
  );
  const resolvedMode = useMemo(() => ACTIVE_NAV_TO_MODE[activeNav] || "chat", [activeNav]);
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
          setActiveNav("Chat");
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

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((previous) => !previous);
  };

  const handleNewChat = () => {
    stopSpeaking();
    setMessages([]);
    setInput("");
    setStatus("");
    setCurrentConversationId(null);
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
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || isTyping || isConversationLoading) {
        return;
      }

      stopSpeaking();
      const optimisticUserMessage = createMessage("user", trimmed, currentConversationId, {
        images: [],
        meta: {
          generate_prompt_image: generatePromptImage,
          generate_answer_image: generateAnswerImage,
        },
      });
      setMessages((previous) => [...previous, optimisticUserMessage]);
      setIsTyping(true);
      setStatus(
        buildProgressStatus({
          text: trimmed,
          isSearch: activeNav === "Search",
          generatePromptImage,
          generateAnswerImage,
        })
      );

      const prompt = toolPrefix ? `${toolPrefix}\n${trimmed}` : trimmed;
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

      try {
        const token = localStorage.getItem("token");
        const response = await fetch(API_ENDPOINT, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: prompt,
            stream: false,
            mode: resolvedMode,
            conversation_id: currentConversationId,
            generate_prompt_image: generatePromptImage,
            generate_answer_image: generateAnswerImage,
          }),
          signal: controller.signal,
        });

        if (response.status === 401 || response.status === 403) {
          handleUnauthorized();
          return;
        }

        let data = null;
        try {
          data = await response.json();
        } catch {
          data = null;
        }

        if (!response.ok) {
          const detail = data?.detail || data?.message || `Request failed (${response.status})`;
          setMessages((previous) => [...previous, createMessage("assistant", detail, currentConversationId)]);
          return;
        }

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
                }
              : message
          );

          if (reply || answerImages.length) {
            updated.push(
              createMessage("assistant", reply, nextConversationId, {
                images: answerImages,
              })
            );
          }

          return updated;
        });

        await loadConversations(nextConversationId);
      } catch (error) {
        const timeoutMessage =
          error?.name === "AbortError"
            ? "NOVA AI did not finish within 2 minutes. Please try again in a moment."
            : "NOVA AI encountered an issue but is still running.";

        setMessages((previous) => [
          ...previous,
          createMessage("assistant", timeoutMessage, currentConversationId),
        ]);
      } finally {
        window.clearTimeout(timeoutId);
        setIsTyping(false);
        setStatus("");
      }
    },
    [
      activeNav,
      currentConversationId,
      handleUnauthorized,
      isConversationLoading,
      isTyping,
      loadConversations,
      resolvedMode,
      stopSpeaking,
      toolPrefix,
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
      setIsTyping(true);
      setStatus(
        buildProgressStatus({
          isSearch: resolvedMode === "search",
          generateAnswerImage,
          regenerate: true,
        })
      );

      try {
        const response = await chatAPI.regenerate({
          conversation_id: currentConversationId,
          mode: resolvedMode,
          stream: false,
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
                })
              );
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
        setMessages((previous) => [...previous, createMessage("assistant", detail, currentConversationId)]);
      } finally {
        setIsTyping(false);
        setStatus("");
      }
    },
    [
      currentConversationId,
      handleUnauthorized,
      isConversationLoading,
      isTyping,
      loadConversations,
      regeneratableMessageId,
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
