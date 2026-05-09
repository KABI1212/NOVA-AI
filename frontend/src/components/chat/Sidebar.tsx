import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, MouseEvent as ReactMouseEvent, ReactNode } from "react";
import toast from "react-hot-toast";
import { useLocation, useNavigate } from "react-router-dom";

import { authAPI } from "../../services/api";
import NovaLogo from "../common/NovaLogo";
import { formatApiError } from "../../utils/apiErrors";
import { useAuthStore } from "../../utils/store";

type Conversation = {
  id: string;
  title: string;
  preview?: string;
};

type UserFormState = {
  full_name: string;
  username: string;
  email: string;
};

interface SidebarProps {
  collapsed?: boolean;
  activeNav?: string;
  onNavChange?: (value: string) => void;
  onNewChat?: () => void;
  conversations?: Conversation[];
  selectedConversationId?: string | null;
  onSelectConversation?: (conversationId: string) => void;
  onRenameConversation?: (conversationId: string, title: string) => Promise<void> | void;
  onDeleteConversation?: (conversationId: string) => void;
  isOpen?: boolean;
  userEmail?: string;
  onClose?: () => void;
}

type SidebarItem = {
  key: string;
  label: string;
  icon: ReactNode;
  route?: string;
  navValue?: string;
};

const CHAT_ROUTE = "/chat";

const chatItems: SidebarItem[] = [
  {
    key: "new",
    label: "New chat",
    route: CHAT_ROUTE,
    navValue: "Chat",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </svg>
    ),
  },
  {
    key: "chat",
    label: "Main chat",
    route: CHAT_ROUTE,
    navValue: "Chat",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
];

function getUserInfo(user: Record<string, unknown> | null | undefined, fallbackEmail?: string) {
  const name = String(user?.full_name || user?.username || "Guest");
  const email = String(user?.email || fallbackEmail || "guest@nova.ai");
  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return { name, email, initials: initials || "G" };
}

export default function Sidebar({
  collapsed,
  activeNav = "Chat",
  onNavChange,
  onNewChat,
  conversations = [],
  selectedConversationId = null,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
  isOpen,
  userEmail,
  onClose,
}: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const authUser = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const setUser = useAuthStore((state) => state.setUser);

  const resolvedCollapsed = typeof collapsed === "boolean" ? collapsed : typeof isOpen === "boolean" ? !isOpen : false;
  const user = useMemo(() => getUserInfo(authUser as Record<string, unknown> | null | undefined, userEmail), [authUser, userEmail]);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [conversationQuery, setConversationQuery] = useState("");
  const [renameConversationId, setRenameConversationId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [isRenamingConversation, setIsRenamingConversation] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [formData, setFormData] = useState<UserFormState>({
    full_name: String(authUser?.full_name || ""),
    username: String(authUser?.username || ""),
    email: String(authUser?.email || userEmail || ""),
  });

  useEffect(() => {
    setFormData({
      full_name: String(authUser?.full_name || ""),
      username: String(authUser?.username || ""),
      email: String(authUser?.email || userEmail || ""),
    });
  }, [authUser, userEmail]);

  useEffect(() => {
    if (!isMenuOpen) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (menuRef.current && target instanceof Node && !menuRef.current.contains(target)) {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [isMenuOpen]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }

      setIsMenuOpen(false);
      setIsEditOpen(false);
      setIsDeleteOpen(false);
      setRenameConversationId(null);
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  const filteredConversations = useMemo(() => {
    const query = conversationQuery.trim().toLowerCase();
    if (!query) {
      return conversations;
    }

    return conversations.filter((conversation) =>
      `${conversation.title || ""} ${conversation.preview || ""}`.toLowerCase().includes(query)
    );
  }, [conversationQuery, conversations]);

  const handleClick = (item: SidebarItem) => {
    if (item.key === "new") {
      if (location.pathname === CHAT_ROUTE) {
        onNewChat?.();
      } else {
        navigate(CHAT_ROUTE);
      }
      onClose?.();
      return;
    }

    if (item.navValue && location.pathname === CHAT_ROUTE) {
      onNavChange?.(item.navValue);
    }

    if (item.route && `${location.pathname}${location.search}` !== item.route) {
      navigate(item.route);
    }

    onClose?.();
  };

  const isItemActive = (item: SidebarItem) => {
    if (item.key === "new") {
      return false;
    }

    if (item.navValue) {
      return location.pathname === CHAT_ROUTE && activeNav === item.navValue;
    }

    return Boolean(item.route) && location.pathname === item.route;
  };

  const handleLogout = () => {
    setIsMenuOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const handleEditSubmit = async (event: FormEvent<HTMLFormElement>) => {
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
    } catch (error: any) {
      toast.error(formatApiError(error, "Could not update your account right now."));
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
    } catch (error: any) {
      toast.error(formatApiError(error, "Could not delete your account right now."));
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

  const openRenameModal = (conversation: Conversation) => {
    setRenameConversationId(conversation?.id || null);
    setRenameTitle(conversation?.title || "");
  };

  const handleRenameConversationSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!renameConversationId) {
      return;
    }

    const title = renameTitle.trim();
    if (!title) {
      toast.error("Conversation title cannot be empty.");
      return;
    }

    setIsRenamingConversation(true);
    try {
      await onRenameConversation?.(renameConversationId, title);
      setRenameConversationId(null);
      setRenameTitle("");
    } finally {
      setIsRenamingConversation(false);
    }
  };

  return (
    <>
      <aside className={`sb claude${resolvedCollapsed ? " col" : ""}`}>
        <div className="logo">
          <NovaLogo size={30} showText={false} className="li" />
          <span className="lt">
            NOVA <span>AI</span>
          </span>
        </div>

        <div className="sb-scroll">
          <div className="sl">Chat</div>
          <div className="slist">
            {chatItems.map((item) => (
              <button
                key={item.key}
                className={`sitem${isItemActive(item) ? " active" : ""}`}
                type="button"
                onClick={() => handleClick(item)}
              >
                {item.icon}
                <span className="slabel">{item.label}</span>
              </button>
            ))}
          </div>

          <div className="sl">Conversations</div>
          <div className="ssearch">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              value={conversationQuery}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setConversationQuery(event.target.value)}
              placeholder="Search conversations"
              aria-label="Search conversations"
            />
          </div>
          <div className="hst">
            {filteredConversations.length ? (
              filteredConversations.map((conversation) => (
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
                      onClose?.();
                    }}
                  >
                    <span className="hst-copy">
                      <span className="hst-text">{conversation.title}</span>
                      {conversation.preview ? <span className="hst-preview">{conversation.preview}</span> : null}
                    </span>
                  </button>
                  <button
                    className="hst-ren"
                    type="button"
                    onClick={(event: ReactMouseEvent<HTMLButtonElement>) => {
                      event.stopPropagation();
                      openRenameModal(conversation);
                    }}
                    aria-label="Rename chat"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 20h9" />
                      <path d="M16.5 3.5a2.12 2.12 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
                    </svg>
                  </button>
                  <button
                    className="hst-del"
                    type="button"
                    onClick={(event: ReactMouseEvent<HTMLButtonElement>) => {
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
              <div className="hst-empty">
                {conversationQuery.trim() ? "No matching chats" : "No chats yet"}
              </div>
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
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
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
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
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
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setFormData((current) => ({ ...current, email: event.target.value }))
                }
                placeholder="Email"
                disabled={isSaving}
              />

              <div className="mbtns">
                <button className="bcnl" type="button" onClick={() => setIsEditOpen(false)} disabled={isSaving}>
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
              This removes your profile, conversations, and learning history. Type{" "}
              <strong>DELETE</strong> to continue.
            </p>
            <label className="modal-label" htmlFor="delete-account-confirmation">
              Confirmation
            </label>
            <input
              id="delete-account-confirmation"
              type="text"
              value={deleteConfirmation}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setDeleteConfirmation(event.target.value)}
              placeholder='Type "DELETE"'
              disabled={isDeleting}
            />
            <div className="mbtns">
              <button className="bcnl" type="button" onClick={() => setIsDeleteOpen(false)} disabled={isDeleting}>
                Cancel
              </button>
              <button className="bok bok-danger" type="button" onClick={handleDeleteAccount} disabled={isDeleting}>
                {isDeleting ? "Deleting..." : "Delete account"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {renameConversationId ? (
        <div className="ov open" onClick={() => setRenameConversationId(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h3>Rename Chat</h3>
            <p>Choose a clearer title so this conversation is easier to find later.</p>
            <form className="acct-form" onSubmit={handleRenameConversationSubmit}>
              <label className="modal-label" htmlFor="rename-conversation-title">
                Conversation title
              </label>
              <input
                id="rename-conversation-title"
                type="text"
                value={renameTitle}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setRenameTitle(event.target.value)}
                placeholder="Conversation title"
                maxLength={120}
                disabled={isRenamingConversation}
              />
              <div className="mbtns">
                <button
                  className="bcnl"
                  type="button"
                  onClick={() => setRenameConversationId(null)}
                  disabled={isRenamingConversation}
                >
                  Cancel
                </button>
                <button className="bok" type="submit" disabled={isRenamingConversation}>
                  {isRenamingConversation ? "Saving..." : "Save title"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}
