import React, { useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

import { authAPI } from "../services/api";
import { useAuthStore } from "../utils/store";

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

function getUserInfo(user) {
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
  const navigate = useNavigate();
  const authUser = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const setUser = useAuthStore((state) => state.setUser);

  const user = useMemo(() => getUserInfo(authUser), [authUser]);
  const menuRef = useRef(null);

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [formData, setFormData] = useState({
    full_name: authUser?.full_name || "",
    username: authUser?.username || "",
    email: authUser?.email || "",
  });

  useEffect(() => {
    setFormData({
      full_name: authUser?.full_name || "",
      username: authUser?.username || "",
      email: authUser?.email || "",
    });
  }, [authUser]);

  useEffect(() => {
    if (!isMenuOpen) {
      return undefined;
    }

    const handlePointerDown = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [isMenuOpen]);

  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key !== "Escape") {
        return;
      }

      setIsMenuOpen(false);
      setIsEditOpen(false);
      setIsDeleteOpen(false);
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  const handleClick = (item) => {
    if (item.key === "new") {
      onNewChat?.();
      onNavChange?.("Chat");
      return;
    }
    onNavChange?.(item.label);
  };

  const handleLogout = () => {
    setIsMenuOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const handleEditSubmit = async (event) => {
    event.preventDefault();

    const payload = {
      full_name: formData.full_name.trim(),
      username: formData.username.trim(),
      email: formData.email.trim(),
    };

    if (!payload.username || !payload.email) {
      toast.error("Username and email are required.");
      return;
    }

    setIsSaving(true);
    try {
      const response = await authAPI.updateMe(payload);
      const nextUser = response?.data?.user;
      if (nextUser) {
        setUser(nextUser);
      }
      setIsEditOpen(false);
      toast.success(response?.data?.message || "Account updated successfully.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Could not update your account right now."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmation.trim().toUpperCase() !== "DELETE") {
      toast.error('Type "DELETE" to confirm account removal.');
      return;
    }

    setIsDeleting(true);
    try {
      const response = await authAPI.deleteMe();
      logout();
      navigate("/signup", { replace: true });
      toast.success(response?.data?.message || "Account deleted successfully.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Could not delete your account right now."
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const openEditModal = () => {
    setIsMenuOpen(false);
    setIsEditOpen(true);
  };

  const openDeleteModal = () => {
    setIsMenuOpen(false);
    setDeleteConfirmation("");
    setIsDeleteOpen(true);
  };

  return (
    <>
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
          <div className="acct-wrap" ref={menuRef}>
            <button
              className="ur ur-btn"
              type="button"
              onClick={() => setIsMenuOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={isMenuOpen}
            >
              <div className="av">{user.initials}</div>
              <div className="ui">
                <div className="un">{user.name}</div>
                <div className="ue">Free plan</div>
              </div>
              <svg className="ur-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="m6 9 6 6 6-6" />
              </svg>
            </button>

            {isMenuOpen ? (
              <div className="acct-menu" role="menu">
                <button className="acct-action" type="button" onClick={openEditModal}>
                  Edit account
                </button>
                <button className="acct-action" type="button" onClick={handleLogout}>
                  Log out
                </button>
                <button className="acct-action danger" type="button" onClick={openDeleteModal}>
                  Delete account
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </aside>

      {isEditOpen ? (
        <div className="ov open" onClick={() => setIsEditOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h3>Edit Account</h3>
            <p>Update the profile details shown in your sidebar and used for login.</p>
            <form className="acct-form" onSubmit={handleEditSubmit}>
              <label className="modal-label" htmlFor="account-full-name">
                Full name
              </label>
              <input
                id="account-full-name"
                type="text"
                value={formData.full_name}
                onChange={(event) =>
                  setFormData((current) => ({ ...current, full_name: event.target.value }))
                }
                placeholder="Full name"
                disabled={isSaving}
              />

              <label className="modal-label" htmlFor="account-username">
                Username
              </label>
              <input
                id="account-username"
                type="text"
                value={formData.username}
                onChange={(event) =>
                  setFormData((current) => ({ ...current, username: event.target.value }))
                }
                placeholder="Username"
                disabled={isSaving}
              />

              <label className="modal-label" htmlFor="account-email">
                Email
              </label>
              <input
                id="account-email"
                type="email"
                value={formData.email}
                onChange={(event) =>
                  setFormData((current) => ({ ...current, email: event.target.value }))
                }
                placeholder="Email"
                disabled={isSaving}
              />

              <div className="mbtns">
                <button
                  className="bcnl"
                  type="button"
                  onClick={() => setIsEditOpen(false)}
                  disabled={isSaving}
                >
                  Cancel
                </button>
                <button className="bok" type="submit" disabled={isSaving}>
                  {isSaving ? "Saving..." : "Save changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {isDeleteOpen ? (
        <div className="ov open" onClick={() => setIsDeleteOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h3>Delete Account</h3>
            <p>
              This removes your profile, conversations, uploaded documents, and learning history.
              Type <strong>DELETE</strong> to continue.
            </p>
            <label className="modal-label" htmlFor="delete-account-confirmation">
              Confirmation
            </label>
            <input
              id="delete-account-confirmation"
              type="text"
              value={deleteConfirmation}
              onChange={(event) => setDeleteConfirmation(event.target.value)}
              placeholder='Type "DELETE"'
              disabled={isDeleting}
            />
            <div className="mbtns">
              <button
                className="bcnl"
                type="button"
                onClick={() => setIsDeleteOpen(false)}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button className="bok bok-danger" type="button" onClick={handleDeleteAccount} disabled={isDeleting}>
                {isDeleting ? "Deleting..." : "Delete account"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

export default Sidebar;
