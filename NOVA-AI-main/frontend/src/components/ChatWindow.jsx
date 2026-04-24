import React, { useEffect, useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
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

function ChatWindow({ messages, isTyping, status }) {
  const chatRef = useRef(null);

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
            return (
              <div key={message.id} className={`msg ${isUser ? "u" : "a"}`}>
                <div className="mlb">{isUser ? "You" : "Nova AI"}</div>
                <div className="bb">
                  {isUser ? (
                    message.content
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkBreaks]}
                      components={{
                        code({ inline, className, children, ...props }) {
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
                  )}
                </div>
                {!isUser ? (
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
