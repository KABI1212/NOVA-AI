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

  const toolPrefix = useMemo(
    () => (NAV_TO_INSTRUCTION[activeNav] || []).join("\n"),
    [activeNav]
  );

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login", { replace: true });
  }, [logout, navigate]);

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
    [handleUnauthorized]
  );

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((previous) => !previous);
  };

  const handleNewChat = () => {
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
    [currentConversationId, handleUnauthorized]
  );

  const handleSend = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || isTyping || isConversationLoading) {
        return;
      }

      const optimisticUserMessage = createMessage("user", trimmed, currentConversationId);
      setMessages((previous) => [...previous, optimisticUserMessage]);
      setIsTyping(true);
      setStatus(
        activeNav === "Search" || TEMPORAL_QUERY_PATTERN.test(trimmed)
          ? "NOVA AI is searching recent information..."
          : "Nova AI is thinking..."
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
            conversation_id: currentConversationId,
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

        if (nextConversationId) {
          setCurrentConversationId(nextConversationId);
        }

        setMessages((previous) => [
          ...previous,
          createMessage("assistant", reply, nextConversationId),
        ]);

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
      toolPrefix,
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
          <ChatWindow messages={messages} isTyping={isTyping} status={status} />
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            disabled={isTyping || isConversationLoading}
          />
          <FeatureCards visible={!messages.length} onSelect={handleSuggestion} />
        </main>
      </div>
    </>
  );
}

export default Chat;
