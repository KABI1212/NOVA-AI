import React, { useCallback, useMemo, useState } from "react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import ChatWindow from "./components/ChatWindow";
import FeatureCards from "./components/FeatureCards";
import ChatInput from "./components/ChatInput";

const API_ENDPOINT = "http://127.0.0.1:8000/api/chat";
const DEFAULT_MODEL = "gpt-4o-mini";

const createMessage = (role, content) => ({
  id: typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()),
  role,
  content,
});

function App() {
  const [messages, setMessages] = useState([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeNav, setActiveNav] = useState("Chat");
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [tools, setTools] = useState({
    search: true,
    think: false,
    code: false,
    research: false,
    agent: false,
    memory: false,
  });
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("");
  const [isTyping, setIsTyping] = useState(false);

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

  const handleToggleTool = (tool) => {
    setTools((prev) => ({ ...prev, [tool]: !prev[tool] }));
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
      setStatus("Nova AI is thinking...");

      const prompt = toolPrefix ? `${toolPrefix}\n${trimmed}` : trimmed;

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
          }),
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
          const reply = data?.message || data?.answer || "NOVA AI: ...";
          setMessages((prev) => [...prev, createMessage("assistant", reply)]);
        }
      } catch (error) {
        setMessages((prev) => [
          ...prev,
          createMessage("assistant", "NOVA AI encountered an issue but is still running."),
        ]);
      } finally {
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
    <div className="app">
      <Sidebar
        collapsed={isSidebarCollapsed}
        activeNav={activeNav}
        onNavChange={setActiveNav}
        onNewChat={handleNewChat}
      />
      <main className="chat-container">
        <Topbar
          title={activeNav}
          model={model}
          onModelChange={setModel}
          onToggleSidebar={handleToggleSidebar}
          tools={tools}
          onToggleTool={handleToggleTool}
        />
        <ChatWindow messages={messages} isTyping={isTyping} status={status} />
        <FeatureCards visible={!messages.length} onSelect={handleSuggestion} />
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          disabled={isTyping}
          tools={tools}
          onToggleTool={handleToggleTool}
        />
      </main>
    </div>
  );
}

export default App;
