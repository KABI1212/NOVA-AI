import React, { useEffect, useState } from "react";
import { useAuthStore } from "../utils/store";

function Topbar({
  onToggleSidebar,
  onProfileClick,
  profileActive = false,
}) {
  const user = useAuthStore((state) => state.user);
  const [userLabel, setUserLabel] = useState("");

  useEffect(() => {
    setUserLabel(String(user?.username || user?.email || "").trim());
  }, [user]);

  return (
    <div className="topbar minimal">
      <button className="hbtn" type="button" onClick={onToggleSidebar} aria-label="Toggle sidebar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>
      <div className="ttl" aria-hidden="true" />
      <div className="tb-right">
        <button className="model-inline" type="button" aria-label="Current model">
          <span aria-hidden="true">⚡</span>
          <span>NOVA Fast</span>
          <span aria-hidden="true">▼</span>
        </button>
        <button
          className={`tb-ghost user-profile${profileActive ? " active" : ""}`}
          type="button"
          aria-label={userLabel ? `Profile: ${userLabel}` : "Profile"}
          onClick={onProfileClick}
        >
          {userLabel ? <span className="tb-user-label">{userLabel}</span> : null}
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
