import React from "react";

import ShareButton from "./chat/ShareButton";

function Topbar({
  title,
  onToggleSidebar,
  conversationId = null,
  conversationTitle = "",
  onProfileClick,
  profileActive = false,
}) {
  return (
    <div className="topbar minimal">
      <button className="hbtn" type="button" onClick={onToggleSidebar} aria-label="Toggle sidebar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>
      <div className="ttl">{title}</div>
      <div className="tb-right">
        <ShareButton conversationId={conversationId} conversationTitle={conversationTitle} />
        <button
          className={`tb-ghost${profileActive ? " active" : ""}`}
          type="button"
          aria-label="Profile"
          onClick={onProfileClick}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="7" r="4" />
            <path d="M5.5 21a6.5 6.5 0 0 1 13 0" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default Topbar;
