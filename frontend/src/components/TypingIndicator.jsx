import React from "react";

function TypingIndicator() {
  return (
    <div className="typing-indicator">
      <svg className="typing-logo" viewBox="0 0 80 80" fill="none" aria-hidden="true">
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
      <span className="typing-text">NOVA is thinking</span>
      <span className="typing-dots">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

export default TypingIndicator;
