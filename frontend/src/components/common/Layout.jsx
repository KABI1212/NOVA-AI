// @ts-nocheck
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  BookOpen,
  Code,
  GraduationCap,
  Image,
  Lightbulb,
  Link,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  Bot,
  Search,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";

import NovaLogo from "./NovaLogo";
import { useAuthStore, useChatStore, useThemeStore } from "../../utils/store";

const sidebarButtonBase =
  "w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors duration-150";
const sidebarButtonIdle = "text-[#edf2fa] hover:bg-[#2b3748] hover:text-white";
const sidebarButtonActive = "bg-[#18597b] text-[#f7fbff] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]";
const sidebarSectionLabel = "px-4 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-[#8ea1ba]";

function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { mode, setMode } = useChatStore();
  const { isDark, toggleTheme } = useThemeStore();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const primaryItems = useMemo(
    () => [
      { icon: MessageSquare, label: "Main Chat", mode: "chat", path: "/chat" },
    ],
    []
  );

  const assistantItems = useMemo(
    () => [
      { icon: Code, label: "Code Assistant", mode: "code", path: "/code" },
      { icon: Lightbulb, label: "Deep Explain", mode: "deep", path: "/explain" },
      { icon: ShieldCheck, label: "Safe Reasoning", mode: "safe", path: "/reasoning" },
      { icon: BookOpen, label: "Knowledge", mode: "knowledge", path: "/knowledge" },
      { icon: GraduationCap, label: "Learning", mode: "learning", path: "/learning" },
      { icon: Image, label: "Image Generator", mode: "image", path: "/images" },
    ],
    []
  );

  const workspaceItems = useMemo(
    () => [
      { icon: Search, label: "Web Search", mode: "search", path: "/search" },
      { icon: Bot, label: "Orchestrator", mode: "orchestrator", path: "/orchestrator" },
      { icon: Link, label: "Shared Chats", mode: "my-shares", path: "/my-shares" },
    ],
    []
  );

  const menuItems = useMemo(
    () => [...primaryItems, ...assistantItems, ...workspaceItems],
    [assistantItems, primaryItems, workspaceItems]
  );

  useEffect(() => {
    const activeItem = menuItems.find((item) => item.path === location.pathname);
    if (activeItem && activeItem.mode !== mode) {
      setMode(activeItem.mode);
    }
  }, [location.pathname, menuItems, mode, setMode]);

  const activeItem =
    menuItems.find((item) => item.path === location.pathname) ||
    menuItems.find((item) => item.mode === mode);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-[#eef2f7] dark:bg-[#111827]">
      <motion.aside
        initial={false}
        animate={{ width: isSidebarOpen ? 256 : 0 }}
        className="overflow-hidden border-r border-[#314052] bg-[#222d3d]"
      >
        <div className="flex h-full flex-col px-4 pb-4 pt-5">
          <div className="mb-5 border-b border-[#314052] pb-4">
            <NovaLogo size={34} textColor="#f5f8fc" accentColor="#8bd1ff" />
            <p className="mt-3 px-1 text-xs leading-5 text-[#9cafc5]">
              Choose a focused tool and keep your work in one place.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto pr-1">
            <div className={sidebarSectionLabel}>Chat</div>
            <nav className="space-y-2">
              {primaryItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;

                return (
                  <button
                    key={item.path}
                    onClick={() => {
                      setMode(item.mode);
                      navigate(item.path);
                    }}
                    className={`${sidebarButtonBase} ${
                      isActive ? sidebarButtonActive : sidebarButtonIdle
                    }`}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                );
              })}
            </nav>

            <div className={sidebarSectionLabel}>Assistants</div>
            <nav className="space-y-2">
              {assistantItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;

                return (
                  <button
                    key={item.path}
                    onClick={() => {
                      setMode(item.mode);
                      navigate(item.path);
                    }}
                    className={`${sidebarButtonBase} ${
                      isActive ? sidebarButtonActive : sidebarButtonIdle
                    }`}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                );
              })}
            </nav>

            <div className="mt-6">
              <div className={sidebarSectionLabel}>Workspace</div>
              <nav className="space-y-2">
                {workspaceItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;

                  return (
                    <button
                      key={item.path}
                      onClick={() => {
                        setMode(item.mode);
                        navigate(item.path);
                      }}
                      className={`${sidebarButtonBase} ${
                        isActive ? sidebarButtonActive : sidebarButtonIdle
                      }`}
                    >
                      <Icon className="h-5 w-5 shrink-0" />
                      <span className="font-medium">{item.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-[#314052] bg-[#253244] p-3">
            <div className="mb-3 px-2">
              <p className="text-sm font-medium text-[#f5f8fc]">
                {user?.full_name || user?.username || "NOVA User"}
              </p>
              <p className="mt-1 text-xs text-[#a7b4c8]">
                {user?.email || ""}
              </p>
            </div>

            <div className="space-y-2 border-t border-[#314052] pt-3">
              <button
                onClick={toggleTheme}
                className={`${sidebarButtonBase} ${sidebarButtonIdle}`}
              >
                {isDark ? <Sun className="w-5 h-5 shrink-0" /> : <Moon className="w-5 h-5 shrink-0" />}
                <span className="font-medium">
                  {isDark ? "Light Mode" : "Dark Mode"}
                </span>
              </button>

              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-[#f1d4d4] transition-colors duration-150 hover:bg-[#4a2931] hover:text-[#fff1f1]"
              >
                <LogOut className="w-5 h-5 shrink-0" />
                <span className="font-medium">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </motion.aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="border-b border-[#d6dde8] bg-[#f8fafc] px-6 py-4 dark:border-[#243042] dark:bg-[#182230]">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setIsSidebarOpen((previous) => !previous)}
              className="rounded-lg p-2 text-[#475569] transition-colors hover:bg-[#e2e8f0] hover:text-[#0f172a] dark:text-[#c9d5e6] dark:hover:bg-[#253244] dark:hover:text-white"
            >
              {isSidebarOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>

            <h2 className="text-xl font-semibold text-[#0f172a] dark:text-[#f8fafc]">
              {activeItem?.label || "NOVA AI"}
            </h2>

            <div className="w-10" />
          </div>
        </header>

        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}

export default Layout;
