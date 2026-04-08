// @ts-nocheck
import { useEffect, useRef, useState } from "react";

import Layout from "../components/common/Layout";
import MessageBubble from "../components/chat/MessageBubble";
import SearchResults from "../components/chat/SearchResults";
import { fetchApi } from "../services/api";
import { stopSpeechPlayback } from "../utils/speech";
import { useAuthStore } from "../utils/store";

export default function SearchChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const bottomRef = useRef(null);
  const { token } = useAuthStore();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => () => {
    stopSpeechPlayback();
  }, []);

  const search = async (query) => {
    if (!query || !query.trim() || loading) {
      return;
    }

    setError(null);
    setInput("");
    stopSpeechPlayback();

    const userMsg = { role: "user", content: query };
    const history = messages
      .filter((message) => message.role !== "system")
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));

    setMessages((previous) => [
      ...previous,
      userMsg,
      { role: "assistant", content: "", searchResults: null, isSearching: true },
    ]);

    setLoading(true);

    try {
      let finalReply = "";
      const response = await fetchApi("/search/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: query,
          history,
        }),
      });

      if (!response.ok) {
        let detail = `Server error: ${response.status}`;
        try {
          const payload = await response.json();
          detail = payload?.detail || payload?.message || detail;
        } catch {
          // Ignore non-JSON error bodies.
        }
        throw new Error(detail);
      }

      if (!response.body) {
        throw new Error("Search response did not include a stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      for (;;) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        const lines = decoder.decode(value, { stream: true }).split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ") || line === "data: [DONE]") {
            continue;
          }

          try {
            const parsed = JSON.parse(line.slice(6));

            if (parsed.type === "search_results") {
              setMessages((previous) => {
                const updated = [...previous];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  searchResults: parsed.results,
                  searchQuery: parsed.query,
                  isSearching: false,
                };
                return updated;
              });
            }

            if ((parsed.type === "chunk" || parsed.type === "delta") && parsed.content) {
              finalReply += parsed.content;
              setMessages((previous) => {
                const updated = [...previous];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = {
                  ...last,
                  content: (last.content || "") + parsed.content,
                };
                return updated;
              });
            }

            if (parsed.type === "final" && parsed.message) {
              finalReply = parsed.message;
              setMessages((previous) => {
                const updated = [...previous];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = {
                  ...last,
                  content: parsed.message,
                  searchResults: last.searchResults || parsed.results || [],
                  isSearching: false,
                };
                return updated;
              });
            }

            if (parsed.error || parsed.type === "error") {
              const detail = parsed.error || parsed.content || "An error occurred";
              setMessages((previous) => {
                const updated = [...previous];
                const lastIndex = updated.length - 1;
                if (lastIndex >= 0 && updated[lastIndex]?.role === "assistant") {
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    isSearching: false,
                  };
                }
                return updated;
              });
              setError(detail);
            }
          } catch {
            // Ignore malformed stream chunks.
          }
        }
      }

    } catch (err) {
      setError(err?.message || "Search request failed.");
      setMessages((previous) => previous.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="flex flex-col h-full bg-gray-950 text-white">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h1 className="text-xl font-semibold">Web Search</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              AI answers backed by real-time web results
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-2">
          {messages.length === 0 && (
            <div className="text-center text-gray-600 mt-24">
              <div className="text-5xl mb-4">Search</div>

              <p className="text-lg font-medium text-gray-500">
                Ask anything and I&apos;ll search the web
              </p>

              <p className="text-sm mt-1 mb-8">
                Like Perplexity, powered by your AI models
              </p>

              <div className="flex flex-wrap gap-2 justify-center max-w-lg mx-auto">
                {[
                  "Latest AI news today",
                  "Best Python frameworks 2025",
                  "How does React 19 differ from 18",
                  "Top free APIs for developers",
                  "What is DeepSeek R1",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => search(suggestion)}
                    className="text-sm bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-gray-500 text-gray-400 hover:text-white px-4 py-2 rounded-full transition-all"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`}>
              {message.role === "assistant" && message.searchResults && (
                <SearchResults
                  results={message.searchResults}
                  query={message.searchQuery}
                />
              )}

              {message.role === "assistant" && message.isSearching && (
                <div className="flex items-center gap-2 px-4 py-2 text-gray-500 text-sm">
                  <svg className="animate-spin w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v8H4z"
                    />
                  </svg>
                  Searching the web...
                </div>
              )}

              <MessageBubble
                message={message}
                isStreaming={loading && index === messages.length - 1 && message.role === "assistant"}
              />
            </div>
          ))}

          {error && (
            <div className="mx-2 bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-red-300 text-sm flex justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)}>Dismiss</button>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="px-4 pb-6 pt-2 border-t border-gray-800">
          <div className="flex items-center gap-3 bg-gray-800 rounded-xl px-4 py-3 border border-gray-700 focus-within:border-blue-500 transition-colors">
            <span className="text-gray-500 text-lg">/</span>

            <input
              className="flex-1 bg-transparent outline-none text-white placeholder-gray-500 text-sm"
              placeholder="Search anything..."
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  search(input);
                }
              }}
            />

            <button
              onClick={() => search(input)}
              disabled={loading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? "..." : "Search"}
            </button>
          </div>

          <p className="text-center text-gray-700 text-xs mt-2">
            Results from DuckDuckGo. AI answers may not be 100% accurate.
          </p>
        </div>
      </div>
    </Layout>
  );
}
