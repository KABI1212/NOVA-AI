import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuthStore, useThemeStore } from './utils/store';
import { useEffect } from 'react';

// Pages
import Login from './pages/Login';
import Signup from './pages/Signup';
import Chat from './pages/Chat';

function App() {
  const { user } = useAuthStore();
  const { isDark } = useThemeStore();

  useEffect(() => {
    // Apply dark mode on mount
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: isDark ? '#1f2937' : '#ffffff',
            color: isDark ? '#f3f4f6' : '#1f2937',
          },
        }}
      />
      <Routes>
        <Route path="/login" element={!user ? <Login /> : <Navigate to="/chat" />} />
        <Route path="/signup" element={!user ? <Signup /> : <Navigate to="/chat" />} />
        <Route path="/chat" element={user ? <Chat /> : <Navigate to="/login" />} />
        <Route path="/chat/:id" element={user ? <Chat /> : <Navigate to="/login" />} />
        <Route path="/code" element={user ? <Navigate to="/chat?mode=code" /> : <Navigate to="/login" />} />
        <Route path="/explain" element={user ? <Navigate to="/chat?mode=deep" /> : <Navigate to="/login" />} />
        <Route path="/image" element={user ? <Navigate to="/chat?mode=image" /> : <Navigate to="/login" />} />
        <Route path="/reasoning" element={user ? <Navigate to="/chat?mode=safe" /> : <Navigate to="/login" />} />
        <Route path="/knowledge" element={user ? <Navigate to="/chat?mode=knowledge" /> : <Navigate to="/login" />} />
        <Route path="/documents" element={user ? <Navigate to="/chat?mode=documents" /> : <Navigate to="/login" />} />
        <Route path="/learning" element={user ? <Navigate to="/chat?mode=learning" /> : <Navigate to="/login" />} />
        <Route path="/" element={<Navigate to={user ? "/chat" : "/login"} />} />
      </Routes>
    </>
  );
}

export default App;
