import React, { useEffect, useRef, useState } from "react";
import { Check, Copy, ExternalLink, Pencil, RotateCcw, Volume2, VolumeX } from "lucide-react";

import MarkdownAnswer from "./common/MarkdownAnswer";
import NovaLogo from "./common/NovaLogo";
import TypingIndicator from "./TypingIndicator";

const USER_MESSAGE_SUFFIX_PATTERN = /(?:\s*\+\s*)?\[(?:File|Photo):\s*[^\]]+\]\s*$/i;

async function copyTextToClipboard(value) {
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

function getUserQuestionText(message) {
  const content = String(message?.content || "").trim();
  const cleaned = content.replace(USER_MESSAGE_SUFFIX_PATTERN, "").trim();
  return cleaned || content;
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

function formatSourceDate(value) {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getSourceHostname(url) {
  try {
    const hostname = new URL(url).hostname || "";
    return hostname.replace(/^www\./i, "");
  } catch {
    return "";
  }
}

function getMessageSources(message) {
  const metaSources = Array.isArray(message?.meta?.sources) ? message.meta.sources : [];
  return metaSources
    .filter(
      (item) =>
        item &&
        typeof item === "object" &&
        (item.url || item.label || item.title || item.excerpt)
    )
    .slice(0, 3);
}

function MessageSources({ message }) {
  const sources = getMessageSources(message);
  if (!sources.length) {
    return null;
  }

  return (
    <div className="message-sources" aria-label="Sources">
      {sources.map((item, index) => {
        const sourceName = String(item?.source || item?.kind || "").trim() || getSourceHostname(item?.url || "");
        const sourceMeta = [formatSourceDate(item?.date), sourceName].filter(Boolean).join(" | ");
        const sourceTitle = String(item?.title || item?.label || sourceName || "Source").trim() || "Source";
        const excerpt = String(item?.excerpt || "").trim();

        if (!item?.url) {
          return (
            <div
              key={`${message.id}-source-${index}`}
              className="message-source-chip"
              title={sourceTitle}
            >
              <span className="message-source-copy">
                <strong>{sourceTitle}</strong>
                {sourceMeta ? <span>{sourceMeta}</span> : null}
                {excerpt ? <span>{excerpt}</span> : null}
              </span>
            </div>
          );
        }

        return (
          <a
            key={`${message.id}-source-${index}`}
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="message-source-chip"
            title={sourceTitle}
          >
            <span className="message-source-copy">
              <strong>{sourceTitle}</strong>
              {sourceMeta ? <span>{sourceMeta}</span> : null}
            </span>
            <ExternalLink />
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
  onRewriteQuestion,
  speechSupported = false,
  speakingMessageId = null,
  onSpeak,
}) {
  const chatRef = useRef(null);
  const [copiedKey, setCopiedKey] = useState(null);

  useEffect(() => {
    if (!copiedKey) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setCopiedKey(null);
    }, 1800);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [copiedKey]);

  useEffect(() => {
    if (!chatRef.current) {
      return;
    }
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, isTyping]);

  if (!messages.length) {
    return (
      <div className="hero-wrap">
        <div className="hero-ai-icon">
          <NovaLogo size={38} showText={false} className="hero-logo" />
        </div>
        <div className="hero-title">
          Hello, Kabilesh
        </div>
        <div className="hero-sub">How can I help you today?</div>
        <div className="sts">{status}</div>
      </div>
    );
  }

  return (
    <>
      <div className="chat messages-wrapper" ref={chatRef}>
        <div className="chat-inner">
          {messages.map((message) => {
            const isUser = message.role === "user";
            const isSpeaking = !isUser && speakingMessageId === message.id;
            const canSpeak = !isUser && speechSupported && Boolean(String(message?.content || "").trim());
            const isAssistantComplete = !isUser && !message.streaming;
            const copyStateKey = `${isUser ? "question" : "answer"}:${message.id}`;
            const isCopied = copiedKey === copyStateKey;
            const canRegenerate = !isUser && regeneratableMessageId === message.id && typeof onRegenerate === "function";
            const handleCopy = async () => {
              const textToCopy = isUser ? getUserQuestionText(message) : String(message?.content || "").trim();
              if (!textToCopy) {
                return;
              }

              try {
                await copyTextToClipboard(textToCopy);
                setCopiedKey(copyStateKey);
              } catch {
                setCopiedKey(null);
              }
            };

            return (
              <div key={message.id} className={`message msg ${isUser ? "u" : "a"}`}>
                <div className="mlb">{isUser ? "You" : "Nova AI"}</div>
                <div className={`message-content bb ${isUser ? "user-message" : "ai-message"}`}>
                  {isUser ? (
                    <>
                      {message.content}
                      <MessageImages message={message} />
                    </>
                  ) : (
                    <>
                      <MarkdownAnswer content={message.content} streaming={Boolean(message.streaming)} />
                      <MessageImages message={message} />
                    </>
                  )}
                </div>

                {!isUser ? <MessageSources message={message} /> : null}

                {isUser ? (
                  <div className="message-actions user" aria-label="Question actions">
                    <button
                      className={`message-action${isCopied ? " active" : ""}`}
                      type="button"
                      title={isCopied ? "Question copied" : "Copy question"}
                      aria-label={isCopied ? "Question copied" : "Copy question"}
                      onClick={handleCopy}
                    >
                      {isCopied ? <Check /> : <Copy />}
                    </button>
                    <button
                      className="message-action"
                      type="button"
                      title="Rewrite question"
                      aria-label="Rewrite question"
                      onClick={() => onRewriteQuestion?.(message)}
                    >
                      <Pencil />
                    </button>
                  </div>
                ) : isAssistantComplete ? (
                  <div className="message-footer">
                    <div className="message-line" aria-hidden="true" />
                    <div className="message-actions assistant" aria-label="Answer actions">
                      <button
                        className={`message-action${isCopied ? " active" : ""}`}
                        type="button"
                        title={isCopied ? "Answer copied" : "Copy answer"}
                        aria-label={isCopied ? "Answer copied" : "Copy answer"}
                        onClick={handleCopy}
                      >
                        {isCopied ? <Check /> : <Copy />}
                      </button>
                      <button
                        className={`message-action${isSpeaking ? " active negative speaking" : ""}${canSpeak ? "" : " disabled"}`}
                        type="button"
                        title={isSpeaking ? "Stop reading answer" : "Read answer aloud"}
                        aria-label={isSpeaking ? "Stop reading answer" : "Read answer aloud"}
                        onClick={() => onSpeak?.(message)}
                        disabled={!canSpeak}
                      >
                        {isSpeaking ? <VolumeX /> : <Volume2 />}
                      </button>
                      <button
                        className={`message-action${canRegenerate ? "" : " disabled"}`}
                        type="button"
                        title={canRegenerate ? "Regenerate answer" : "Only the latest AI answer can be regenerated"}
                        aria-label={canRegenerate ? "Regenerate answer" : "Only the latest AI answer can be regenerated"}
                        onClick={() => onRegenerate?.(message.id)}
                        disabled={!canRegenerate}
                      >
                        <RotateCcw />
                      </button>
                    </div>
                  </div>
                ) : null}

                {!isUser ? (
                  <>
                    {isSpeaking ? (
                      <div className="assistant-speaking" aria-live="polite">
                        <span className="assistant-speaking-bars" aria-hidden="true">
                          <span />
                          <span />
                          <span />
                        </span>
                        <span>Reading answer</span>
                      </div>
                    ) : null}
                    <div className="assistant-brand" aria-hidden="true">
                      <NovaLogo size={22} showText={false} className="assistant-logo" />
                    </div>
                  </>
                ) : null}
              </div>
            );
          })}
          {isTyping ? (
            <div className="message msg a">
              <div className="mlb">Nova AI</div>
              <div className="message-content bb ai-message">
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
