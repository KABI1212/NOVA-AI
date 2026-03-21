import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import TypingIndicator from "./TypingIndicator";

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Evening";
}

function getName() {
  try {
    const raw = localStorage.getItem("user");
    const user = raw ? JSON.parse(raw) : null;
    return user?.full_name || user?.username || "there";
  } catch {
    return "there";
  }
}

async function copyToClipboard(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = value;
  textArea.style.position = "fixed";
  textArea.style.left = "-9999px";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  document.execCommand("copy");
  document.body.removeChild(textArea);
}

async function shareMessage(value) {
  if (navigator.share) {
    await navigator.share({ text: value });
    return true;
  }

  await copyToClipboard(value);
  return false;
}

function Icon({ children }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

function resolveImageSource(value) {
  if (!value) {
    return "";
  }
  return value.startsWith("data:") || value.startsWith("http://") || value.startsWith("https://")
    ? value
    : `data:image/png;base64,${value}`;
}

function MessageImages({ message }) {
  if (!Array.isArray(message?.images) || !message.images.length) {
    return null;
  }

  const isUser = message.role === "user";

  return (
    <div className={`bb-images${isUser ? " user" : ""}`}>
      {message.images.map((image, index) => {
        const imageSrc = resolveImageSource(image);

        return (
        <a
          key={`${message.id}-image-${index}`}
          href={imageSrc}
          target="_blank"
          rel="noreferrer"
          className="bb-image-link"
        >
          <img
            src={imageSrc}
            alt={`${isUser ? "Prompt" : "Answer"} visual ${index + 1}`}
            className="bb-image"
            loading="lazy"
          />
        </a>
        );
      })}
    </div>
  );
}

function ChatWindow({
  messages,
  isTyping,
  status,
  regeneratableMessageId = null,
  onRegenerate,
  speechSupported = false,
  speakingMessageId = null,
  onSpeak,
}) {
  const chatRef = useRef(null);
  const [copiedMessageId, setCopiedMessageId] = useState(null);
  const [feedbackById, setFeedbackById] = useState({});
  const [menuMessageId, setMenuMessageId] = useState(null);

  const hero = useMemo(() => {
    return {
      greeting: `${getGreeting()}, ${getName()}`,
    };
  }, []);

  useEffect(() => {
    if (!chatRef.current) {
      return;
    }
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, isTyping]);

  useEffect(() => {
    if (!copiedMessageId) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setCopiedMessageId(null), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [copiedMessageId]);

  useEffect(() => {
    setMenuMessageId(null);
  }, [messages, isTyping]);

  const handleCopy = async (message) => {
    try {
      await copyToClipboard(message.content || "");
      setCopiedMessageId(message.id);
    } catch {
      setCopiedMessageId(null);
    }
  };

  const handleShare = async (message) => {
    try {
      const usedNativeShare = await shareMessage(message.content || "");
      if (!usedNativeShare) {
        setCopiedMessageId(message.id);
      }
    } catch {
      setCopiedMessageId(null);
    }
  };

  const handleFeedback = (messageId, value) => {
    setFeedbackById((previous) => ({
      ...previous,
      [messageId]: previous[messageId] === value ? null : value,
    }));
  };

  if (!messages.length) {
    return (
      <div className="hero-wrap">
        <div className="plan-pill">Free plan - Upgrade</div>
        <div className="hero-title">
          <svg className="hero-logo" viewBox="0 0 80 80" fill="none" aria-hidden="true">
            <g transform="translate(40,40)">
              <path
                d="M0,-28 C2,-10 10,-2 28,0 C10,2 2,10 0,28 C-2,10 -10,2 -28,0 C-10,-2 -2,-10 0,-28 Z"
                fill="none"
                stroke="#1B8FE8"
                strokeWidth="4.5"
                strokeLinejoin="round"
              />
              <g transform="translate(-22,-23)">
                <path
                  d="M0,-7.5 C0.5,-3 3,-0.5 7.5,0 C3,0.5 0.5,3 0,7.5 C-0.5,3 -3,0.5 -7.5,0 C-3,-0.5 -0.5,-3 0,-7.5 Z"
                  fill="#1B8FE8"
                />
              </g>
              <g transform="translate(22,22)">
                <path
                  d="M0,-6 C0.4,-2.5 2.5,-0.4 6,0 C2.5,0.4 0.4,2.5 0,6 C-0.4,2.5 -2.5,0.4 -6,0 C-2.5,-0.4 -0.4,-2.5 0,-6 Z"
                  fill="#1B8FE8"
                />
              </g>
            </g>
          </svg>
          {hero.greeting}
        </div>
        <div className="hero-sub">How can I help you today?</div>
        <div className="sts">{status}</div>
      </div>
    );
  }

  return (
    <>
      <div className="chat" ref={chatRef}>
        <div className="chat-inner">
          {messages.map((message) => {
            const isUser = message.role === "user";
            const feedback = feedbackById[message.id] || null;
            const canRegenerate = !isUser && message.id === regeneratableMessageId;
            const isSpeaking = speakingMessageId === message.id;

            return (
              <div key={message.id} className={`msg ${isUser ? "u" : "a"}`}>
                <div className="mlb">{isUser ? "You" : "Nova AI"}</div>
                <div className="bb">
                  {isUser ? (
                    <>
                      {message.content}
                      <MessageImages message={message} />
                    </>
                  ) : (
                    <>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkBreaks]}
                        components={{
                          code({ inline, children, ...props }) {
                            if (inline) {
                              return (
                                <code className="inline-code" {...props}>
                                  {children}
                                </code>
                              );
                            }
                            return (
                              <pre className="code-block" {...props}>
                                <code>{children}</code>
                              </pre>
                            );
                          },
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                      <MessageImages message={message} />
                    </>
                  )}
                </div>

                {!isUser ? (
                  <>
                    <div className="assistant-brand" aria-hidden="true">
                      <svg className="assistant-logo" viewBox="0 0 80 80" fill="none">
                        <g transform="translate(40,40)">
                          <path
                            d="M0,-28 C2,-10 10,-2 28,0 C10,2 2,10 0,28 C-2,10 -10,2 -28,0 C-10,-2 -2,-10 0,-28 Z"
                            fill="none"
                            stroke="#1B8FE8"
                            strokeWidth="3.5"
                            strokeLinejoin="round"
                          />
                          <g transform="translate(-22,-23)">
                            <path
                              d="M0,-7.5 C0.5,-3 3,-0.5 7.5,0 C3,0.5 0.5,3 0,7.5 C-0.5,3 -3,0.5 -7.5,0 C-3,-0.5 -0.5,-3 0,-7.5 Z"
                              fill="#1B8FE8"
                            />
                          </g>
                          <g transform="translate(22,22)">
                            <path
                              d="M0,-6 C0.4,-2.5 2.5,-0.4 6,0 C2.5,0.4 0.4,2.5 0,6 C-0.4,2.5 -2.5,0.4 -6,0 C-2.5,-0.4 -0.4,-2.5 0,-6 Z"
                              fill="#1B8FE8"
                            />
                          </g>
                        </g>
                      </svg>
                    </div>

                    {message.content ? (
                      <div className="message-actions">
                        <button
                          type="button"
                          className={`message-action${copiedMessageId === message.id ? " active" : ""}`}
                          onClick={() => handleCopy(message)}
                          title={copiedMessageId === message.id ? "Copied" : "Copy answer"}
                        >
                          <Icon>
                            <rect x="9" y="9" width="11" height="11" rx="2" />
                            <path d="M5 15V6a2 2 0 0 1 2-2h9" />
                          </Icon>
                        </button>

                        <button
                          type="button"
                          className={`message-action${feedback === "up" ? " active" : ""}`}
                          onClick={() => handleFeedback(message.id, "up")}
                          title="Helpful"
                        >
                          <Icon>
                            <path d="M7 10v10" />
                            <path d="M15 5l-4 5v10h7.2a2 2 0 0 0 2-1.64l1.1-7A2 2 0 0 0 19.32 9H15V5z" />
                            <path d="M7 20H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h2" />
                          </Icon>
                        </button>

                        <button
                          type="button"
                          className={`message-action${feedback === "down" ? " active negative" : ""}`}
                          onClick={() => handleFeedback(message.id, "down")}
                          title="Not helpful"
                        >
                          <Icon>
                            <path d="M7 14V4" />
                            <path d="M15 19l-4-5V4h7.2a2 2 0 0 1 2 1.64l1.1 7A2 2 0 0 1 19.32 15H15v4z" />
                            <path d="M7 4H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" />
                          </Icon>
                        </button>

                        <button
                          type="button"
                          className="message-action"
                          onClick={() => handleShare(message)}
                          title="Share answer"
                        >
                          <Icon>
                            <path d="M12 16V4" />
                            <path d="M7 9l5-5 5 5" />
                            <path d="M5 20h14" />
                          </Icon>
                        </button>

                        <button
                          type="button"
                          className={`message-action${isSpeaking ? " active speaking" : ""}`}
                          onClick={() => onSpeak?.(message)}
                          disabled={!speechSupported}
                          title={
                            speechSupported
                              ? isSpeaking
                                ? "Stop reading"
                                : "Read answer aloud"
                              : "Speech output is not supported in this browser"
                          }
                        >
                          <Icon>
                            <path d="M11 5L6 9H3v6h3l5 4V5z" />
                            {isSpeaking ? (
                              <path d="M17 9a4 4 0 0 1 0 6" />
                            ) : (
                              <>
                                <path d="M16 8a6 6 0 0 1 0 8" />
                                <path d="M18.8 5.8a9.5 9.5 0 0 1 0 12.4" />
                              </>
                            )}
                          </Icon>
                        </button>

                        {isSpeaking ? (
                          <div className="assistant-speaking" aria-live="polite">
                            <div className="assistant-speaking-bars" aria-hidden="true">
                              <span />
                              <span />
                              <span />
                            </div>
                            <span>Nova is speaking</span>
                          </div>
                        ) : null}

                        <button
                          type="button"
                          className={`message-action${canRegenerate ? "" : " disabled"}`}
                          onClick={() => onRegenerate?.(message.id)}
                          disabled={!canRegenerate}
                          title={canRegenerate ? "Regenerate answer" : "Only the latest AI answer can be regenerated"}
                        >
                          <Icon>
                            <path d="M3 12a9 9 0 0 1 15.3-6.36" />
                            <path d="M21 4v6h-6" />
                            <path d="M21 12a9 9 0 0 1-15.3 6.36" />
                            <path d="M3 20v-6h6" />
                          </Icon>
                        </button>

                        <div className="message-action-more">
                          <button
                            type="button"
                            className={`message-action${menuMessageId === message.id ? " active" : ""}`}
                            onClick={() => setMenuMessageId((previous) => (previous === message.id ? null : message.id))}
                            title="More actions"
                          >
                            <Icon>
                              <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
                              <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
                              <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
                            </Icon>
                          </button>

                          {menuMessageId === message.id ? (
                            <div className="message-action-menu">
                              <button
                                type="button"
                                onClick={async () => {
                                  await handleCopy(message);
                                  setMenuMessageId(null);
                                }}
                              >
                                Copy answer
                              </button>
                              <button
                                type="button"
                                onClick={async () => {
                                  await handleShare(message);
                                  setMenuMessageId(null);
                                }}
                              >
                                Share answer
                              </button>
                              <button
                                type="button"
                                disabled={!speechSupported}
                                onClick={() => {
                                  onSpeak?.(message);
                                  setMenuMessageId(null);
                                }}
                              >
                                {isSpeaking ? "Stop reading" : "Read aloud"}
                              </button>
                              <button
                                type="button"
                                disabled={!canRegenerate}
                                onClick={() => {
                                  onRegenerate?.(message.id);
                                  setMenuMessageId(null);
                                }}
                              >
                                Regenerate
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            );
          })}
          {isTyping ? (
            <div className="msg a">
              <div className="mlb">Nova AI</div>
              <div className="bb">
                <TypingIndicator />
              </div>
            </div>
          ) : null}
        </div>
      </div>
      <div className="sts">{status}</div>
    </>
  );
}

export default ChatWindow;
