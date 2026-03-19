import React from "react";

const mainItems = [
  {
    key: "new",
    label: "New chat",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </svg>
    ),
  },
  {
    key: "search",
    label: "Search",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
  },
  {
    key: "customize",
    label: "Customize",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 1v4" />
        <path d="M12 19v4" />
        <path d="M4.22 4.22l2.83 2.83" />
        <path d="M16.95 16.95l2.83 2.83" />
        <path d="M1 12h4" />
        <path d="M19 12h4" />
        <path d="M4.22 19.78l2.83-2.83" />
        <path d="M16.95 7.05l2.83-2.83" />
      </svg>
    ),
  },
  {
    key: "chats",
    label: "Chats",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    key: "projects",
    label: "Projects",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M3 7h6l2 2h10v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
      </svg>
    ),
  },
  {
    key: "artifacts",
    label: "Artifacts",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M9 9h6M9 12h6M9 15h4" />
      </svg>
    ),
  },
  {
    key: "code",
    label: "Code",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    ),
  },
];

function getUserInfo() {
  if (typeof window === "undefined") {
    return { name: "Guest", email: "guest@nova.ai", initials: "G" };
  }

  try {
    const raw = localStorage.getItem("user");
    const user = raw ? JSON.parse(raw) : null;
    const name = user?.full_name || user?.username || "Guest";
    const email = user?.email || "guest@nova.ai";
    const initials = name
      .split(" ")
      .filter(Boolean)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();
    return { name, email, initials: initials || "G" };
  } catch {
    return { name: "Guest", email: "guest@nova.ai", initials: "G" };
  }
}

function Sidebar({
  collapsed,
  activeNav,
  onNavChange,
  onNewChat,
  conversations = [],
  selectedConversationId = null,
  onSelectConversation,
  onDeleteConversation,
}) {
  const user = getUserInfo();

  const handleClick = (item) => {
    if (item.key === "new") {
      onNewChat?.();
      onNavChange?.("Chat");
      return;
    }
    onNavChange?.(item.label);
  };

  return (
    <aside className={`sb claude${collapsed ? " col" : ""}`}>
      <div className="logo">
        <svg className="li" viewBox="0 0 80 80" fill="none" aria-hidden="true">
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
        <span className="lt">
          NOVA <span>AI</span>
        </span>
      </div>

      <div className="sb-scroll">
        <div className="slist">
          {mainItems.map((item) => (
            <button
              key={item.key}
              className={`sitem${activeNav === item.label ? " active" : ""}`}
              type="button"
              onClick={() => handleClick(item)}
            >
              {item.icon}
              <span className="slabel">{item.label}</span>
            </button>
          ))}
        </div>

        <div className="sl">Conversations</div>
        <div className="hst">
          {conversations.length ? (
            conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`hst-item${selectedConversationId === conversation.id ? " active" : ""}`}
                title={conversation.title}
              >
                <button
                  className="hst-main"
                  type="button"
                  onClick={() => {
                    onNavChange?.("Chat");
                    onSelectConversation?.(conversation.id);
                  }}
                >
                  <span className="hst-text">{conversation.title}</span>
                </button>
                <button
                  className="hst-del"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeleteConversation?.(conversation.id);
                  }}
                  aria-label="Delete chat"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 6h18" />
                    <path d="M8 6V4h8v2" />
                    <path d="M6 6l1 14h10l1-14" />
                  </svg>
                </button>
              </div>
            ))
          ) : (
            <div className="hst-empty">No chats yet</div>
          )}
        </div>
      </div>

      <div className="sftr">
        <div className="ur">
          <div className="av">{user.initials}</div>
          <div className="ui">
            <div className="un">{user.name}</div>
            <div className="ue">Free plan</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
