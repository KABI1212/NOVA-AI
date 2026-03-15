// @ts-nocheck
import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  Code,
  FileText,
  GraduationCap,
  Lightbulb,
  Image,
  ShieldCheck,
  BookOpen,
  Search,
  Link,
  Moon,
  Sun,
  LogOut,
  Menu,
  X
} from 'lucide-react';
import { useAuthStore, useThemeStore, useChatStore } from '../../utils/store';
import NovaLogo from './NovaLogo';

function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { mode, setMode } = useChatStore();
  const { isDark, toggleTheme } = useThemeStore();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const menuItems = [
    { icon: MessageSquare, label: 'Chat', mode: 'chat' },
    { icon: Code, label: 'Code Assistant', mode: 'code' },
    { icon: Lightbulb, label: 'Deep Explain', mode: 'deep' },
    { icon: Image, label: 'Image Generator', mode: 'image' },
    { icon: Search, label: 'Web Search', mode: 'search', path: '/search'},
    { icon: ShieldCheck, label: 'Safe Reasoning', mode: 'safe' },
    { icon: BookOpen, label: 'Knowledge', mode: 'knowledge' },
    { icon: FileText, label: 'Documents', mode: 'documents' },
    { icon: GraduationCap, label: 'Learning', mode: 'learning' },
    { icon: Link, label: 'Shared Chats', mode: 'my-shares', path: '/my-shares'},
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: isSidebarOpen ? 256 : 0 }}
        className="bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-hidden"
      >
        <div className="h-full flex flex-col p-4">
          {/* Logo */}
          <div className="mb-8">
            <NovaLogo size={36} textColor={isDark ? '#ffffff' : '#111111'} />
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-2">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive = item.path ? location.pathname === item.path : mode === item.mode;

              return (
                <button
                  key={item.mode}
                  onClick={() => {
                    if (item.path) {
                      navigate(item.path);
                    } else {
                      setMode(item.mode);
                      navigate(`/chat?mode=${item.mode}`);
                    }
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* User Section */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4 space-y-2">
            <button
              onClick={toggleTheme}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              <span className="font-medium">
                {isDark ? 'Light Mode' : 'Dark Mode'}
              </span>
            </button>

            <div className="px-4 py-2">
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {user?.full_name || user?.username}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {user?.email}
              </p>
            </div>

            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              <LogOut className="w-5 h-5" />
              <span className="font-medium">Logout</span>
            </button>
          </div>
        </div>
      </motion.aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              {isSidebarOpen ? (
                <X className="w-6 h-6 text-gray-600 dark:text-gray-400" />
              ) : (
                <Menu className="w-6 h-6 text-gray-600 dark:text-gray-400" />
              )}
            </button>

            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {menuItems.find((item) => item.mode === mode)?.label || 'NOVA AI'}
            </h2>

            <div className="w-10" />
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}

export default Layout;
