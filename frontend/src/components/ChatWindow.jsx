import React, { useEffect, useRef } from "react";

function ChatWindow({ messages, isTyping, status }) {
  const chatRef = useRef(null);

  useEffect(() => {
    if (!chatRef.current) {
      return;
    }
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, isTyping]);

  if (!messages.length) {
    return (
      <>
        <div className="wlc">
          <svg style={{ opacity: 0.18 }} width="60" height="60" viewBox="0 0 80 80" fill="none" aria-hidden="true">
            <g transform="translate(40,40)">
              <path
                d="M0,-28 C2,-10 10,-2 28,0 C10,2 2,10 0,28 C-2,10 -10,2 -28,0 C-10,-2 -2,-10 0,-28 Z"
                fill="#1B8FE8"
                stroke="#1B8FE8"
                strokeWidth="2.5"
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
          <div className="free-tag">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            100% Free - No API Key Needed
          </div>
          <h2>Hello, how can I help?</h2>
          <p>
            Nova AI - powered by GPT-4o, Claude, Gemini, Llama and more. Connect to your NOVA AI backend to begin.
          </p>
        </div>
        <div className="sts">{status}</div>
      </>
    );
  }

  return (
    <>
      <div className="chat" ref={chatRef}>
        {messages.map((message) => (
          <div key={message.id} className={`msg ${message.role === "user" ? "u" : "a"}`}>
            <div className="mlb">{message.role === "user" ? "You" : "Nova AI"}</div>
            <div className="bb">{message.content}</div>
          </div>
        ))}
        {isTyping ? (
          <div className="msg a">
            <div className="mlb">Nova AI</div>
            <div className="bb">
              <div className="typing">
                <div className="dot" />
                <div className="dot" />
                <div className="dot" />
              </div>
            </div>
          </div>
        ) : null}
      </div>
      <div className="sts">{status}</div>
    </>
  );
}

export default ChatWindow;