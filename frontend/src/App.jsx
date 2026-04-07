// @ts-nocheck
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import Chat from "./pages/Chat";
import CodeAssistant from "./pages/CodeAssistant";
import ExplainAssistant from "./pages/ExplainAssistant";
import ImageGenerator from "./pages/ImageGenerator";
import KnowledgeAssistant from "./pages/KnowledgeAssistant";
import LearningAssistant from "./pages/LearningAssistant";
import Login from "./pages/Login";
import MyShares from "./pages/MyShares";
import ReasoningAssistant from "./pages/ReasoningAssistant";
import SearchChat from "./pages/SearchChat";
import SharedView from "./pages/SharedView";
import Signup from "./pages/Signup";
import { useAuthStore, useThemeStore } from "./utils/store";

function ProtectedRoute({ children }) {
  const token = useAuthStore((state) => state.token);
  return token ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const token = useAuthStore((state) => state.token);
  return token ? <Navigate to="/chat" replace /> : children;
}

function DefaultRoute() {
  const token = useAuthStore((state) => state.token);
  return <Navigate to={token ? "/chat" : "/login"} replace />;
}

function App() {
  const isDark = useThemeStore((state) => state.isDark);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  return (
    <>
      <Routes>
        <Route path="/" element={<DefaultRoute />} />
        <Route
          path="/login"
          element={(
            <PublicRoute>
              <Login />
            </PublicRoute>
          )}
        />
        <Route
          path="/signup"
          element={(
            <PublicRoute>
              <Signup />
            </PublicRoute>
          )}
        />
        <Route
          path="/chat"
          element={(
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/code"
          element={(
            <ProtectedRoute>
              <CodeAssistant />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/explain"
          element={(
            <ProtectedRoute>
              <ExplainAssistant />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/reasoning"
          element={(
            <ProtectedRoute>
              <ReasoningAssistant />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/knowledge"
          element={(
            <ProtectedRoute>
              <KnowledgeAssistant />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/learning"
          element={(
            <ProtectedRoute>
              <LearningAssistant />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/images"
          element={(
            <ProtectedRoute>
              <ImageGenerator />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/search"
          element={(
            <ProtectedRoute>
              <SearchChat />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/my-shares"
          element={(
            <ProtectedRoute>
              <MyShares />
            </ProtectedRoute>
          )}
        />
        <Route path="/share/:shareId" element={<SharedView />} />
        <Route path="*" element={<DefaultRoute />} />
      </Routes>

      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: isDark ? "#1f2937" : "#ffffff",
            color: isDark ? "#f9fafb" : "#111827",
            border: `1px solid ${isDark ? "#374151" : "#e5e7eb"}`,
          },
        }}
      />
    </>
  );
}

export default App;
