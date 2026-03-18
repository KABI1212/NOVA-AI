import React, { useCallback, useMemo, useState } from "react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import ChatWindow from "./components/ChatWindow";
import FeatureCards from "./components/FeatureCards";
import ChatInput from "./components/ChatInput";
import MouseSpark from "./components/MouseSpark";

const API_BASE = (import.meta.env.VITE_API_URL || "").trim();
const API_BASE_NORMALIZED = API_BASE.replace(/\/$/, "");
const API_ENDPOINT = API_BASE_NORMALIZED
  ? API_BASE_NORMALIZED.endsWith("/api")
    ? `${API_BASE_NORMALIZED}/chat`
    : `${API_BASE_NORMALIZED}/api/chat`
  : "/api/chat";
const REQUEST_TIMEOUT_MS = 120000;
const TEMPORAL_QUERY_PATTERN = /\b(current|latest|today|recent|news|breaking|updated|2024|2025|2026)\b/i;

const createMessage = (role, content) => ({
  id: typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()),
  role,
  content,
});

function App() {
  const [messages, setMessages] = useState([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeNav, setActiveNav] = useState("Chat");
  const tools = useMemo(
    () => ({
      search: true,
      think: false,
      code: false,
      research: false,
      agent: false,
    }),
    []
  );
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [hiddenHistoryIds, setHiddenHistoryIds] = useState([]);

  const historyItems = useMemo(() => {
    const items = messages.filter((msg) => msg.role === "user" && msg.content);
    return items
      .slice(-8)
      .reverse()
      .map((msg, index) => ({
        id: msg.id,
        text: msg.content.length > 48 ? `${msg.content.slice(0, 48)}...` : msg.content,
      }));
  }, [messages]);

  const visibleHistoryItems = useMemo(
    () => historyItems.filter((item) => !hiddenHistoryIds.includes(item.id)),
    [historyItems, hiddenHistoryIds]
  );

  const handleDeleteHistory = (id) => {
    setHiddenHistoryIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  };

  const toolPrefix = useMemo(() => {
    const lines = [];
    if (tools.think) lines.push("[Think step by step before answering]");
    if (tools.code) lines.push("[Code mode: use markdown code blocks with language labels for all code]");
    if (tools.research) lines.push("[Research mode: give comprehensive, structured, multi-perspective answers]");
    if (tools.agent) lines.push("[Agent mode: break complex tasks into clear numbered steps]");
    if (tools.search) lines.push("[Note: reference the most current info available]");
    return lines.join("\n");
  }, [tools]);

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((prev) => !prev);
  };

  const handleNewChat = () => {
    setMessages([]);
    setInput("");
    setStatus("");
    setActiveNav("Chat");
  };

  const handleSend = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || isTyping) {
        return;
      }

      setMessages((prev) => [...prev, createMessage("user", trimmed)]);
      setIsTyping(true);
      setStatus(
        TEMPORAL_QUERY_PATTERN.test(trimmed)
          ? "NOVA AI is searching recent information..."
          : "Nova AI is thinking..."
      );

      const prompt = toolPrefix ? `${toolPrefix}\n${trimmed}` : trimmed;
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

      try {
        const response = await fetch(API_ENDPOINT, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: prompt,
            stream: false,
          }),
          signal: controller.signal,
        });

        let data = null;
        try {
          data = await response.json();
        } catch (error) {
          data = null;
        }

        if (!response.ok) {
          const detail = data?.detail || data?.message || `Request failed (${response.status})`;
          const fallback = response.status === 401 || response.status === 403 ? "Please log in to continue." : detail;
          setMessages((prev) => [...prev, createMessage("assistant", fallback)]);
        } else {
          const reply = data?.answer || data?.message || data?.response || "NOVA AI: ...";
          setMessages((prev) => [
            ...prev,
            {
              ...createMessage("assistant", reply),
            },
          ]);
        }
      } catch (error) {
        const timeoutMessage =
          error?.name === "AbortError"
            ? "NOVA AI did not finish within 2 minutes. Please try again in a moment."
            : null;
        setMessages((prev) => [
          ...prev,
          createMessage("assistant", timeoutMessage || "NOVA AI encountered an issue but is still running."),
        ]);
      } finally {
        window.clearTimeout(timeoutId);
        setIsTyping(false);
        setStatus("");
      }
    },
    [isTyping, toolPrefix]
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
          history={visibleHistoryItems}
          onDeleteHistory={handleDeleteHistory}
        />
        <main className="chat-container">
          <Topbar
            title={activeNav}
            onToggleSidebar={handleToggleSidebar}
          />
          <ChatWindow messages={messages} isTyping={isTyping} status={status} />
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            disabled={isTyping}
          />
          <FeatureCards visible={!messages.length} onSelect={handleSuggestion} />
        </main>
      </div>
    </>
  );
}

export default App;
