import React from "react";

import NovaLogo from "./common/NovaLogo";

function TypingIndicator() {
  return (
    <div className="typing-indicator">
      <NovaLogo size={22} showText={false} className="typing-logo" />
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
