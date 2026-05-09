// @ts-nocheck
import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import NovaLogo from "./components/common/NovaLogo";
import { authAPI } from "./services/api";
import { useAuthStore, useThemeStore } from "./utils/store";

const Chat = lazy(() => import("./pages/Chat"));
const CodeAssistant = lazy(() => import("./pages/CodeAssistant"));
const DocumentAnalyzer = lazy(() => import("./pages/DocumentAnalyzer"));
const ExplainAssistant = lazy(() => import("./pages/ExplainAssistant"));
const ImageGenerator = lazy(() => import("./pages/ImageGenerator"));
const KnowledgeAssistant = lazy(() => import("./pages/KnowledgeAssistant"));
const LearningAssistant = lazy(() => import("./pages/LearningAssistant"));
const Login = lazy(() => import("./pages/Login"));
const MyShares = lazy(() => import("./pages/MyShares"));
const OrchestratorStudio = lazy(() => import("./pages/OrchestratorStudio"));
const ReasoningAssistant = lazy(() => import("./pages/ReasoningAssistant"));
const SearchChat = lazy(() => import("./pages/SearchChat"));
const SharedView = lazy(() => import("./pages/SharedView"));
const Signup = lazy(() => import("./pages/Signup"));

function SessionLoader() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-gray-50 text-sm font-medium text-gray-600 dark:bg-gray-950 dark:text-gray-300">
      <NovaLogo size={44} showText={false} />
      <span>Checking your session...</span>
    </div>
  );
}

function ProtectedRoute({ children, isCheckingSession }) {
  const token = useAuthStore((state) => state.token);
  if (isCheckingSession) {
    return <SessionLoader />;
  }
  return token ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children, isCheckingSession }) {
  const token = useAuthStore((state) => state.token);
  if (isCheckingSession) {
    return <SessionLoader />;
  }
  return token ? <Navigate to="/chat" replace /> : children;
}

function DefaultRoute({ isCheckingSession }) {
  const token = useAuthStore((state) => state.token);
  if (isCheckingSession) {
    return <SessionLoader />;
  }
  return <Navigate to={token ? "/chat" : "/login"} replace />;
}

function App() {
  const isDark = useThemeStore((state) => state.isDark);
  const token = useAuthStore((state) => state.token);
  const setUser = useAuthStore((state) => state.setUser);
  const logout = useAuthStore((state) => state.logout);
  const [isCheckingSession, setIsCheckingSession] = useState(Boolean(token));

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  useEffect(() => {
    let isActive = true;

    if (!token) {
      setIsCheckingSession(false);
      return () => {
        isActive = false;
      };
    }

    setIsCheckingSession(true);
    authAPI.me()
      .then((response) => {
        if (!isActive) {
          return;
        }

        const user = response.data?.user;
        if (user) {
          setUser(user);
        }
      })
      .catch(() => {
        if (isActive) {
          logout();
        }
      })
      .finally(() => {
        if (isActive) {
          setIsCheckingSession(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [logout, setUser, token]);

  return (
    <>
      <Suspense fallback={<SessionLoader />}>
        <Routes>
          <Route path="/" element={<DefaultRoute isCheckingSession={isCheckingSession} />} />
          <Route
            path="/login"
            element={(
              <PublicRoute isCheckingSession={isCheckingSession}>
                <Login />
              </PublicRoute>
            )}
          />
          <Route
            path="/signup"
            element={(
              <PublicRoute isCheckingSession={isCheckingSession}>
                <Signup />
              </PublicRoute>
            )}
          />
          <Route
            path="/chat"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <Chat />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/code"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <CodeAssistant />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/explain"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <ExplainAssistant />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/reasoning"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <ReasoningAssistant />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/knowledge"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <KnowledgeAssistant />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/learning"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <LearningAssistant />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/images"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <ImageGenerator />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/documents"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <DocumentAnalyzer />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/search"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <SearchChat />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/my-shares"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <MyShares />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/orchestrator"
            element={(
              <ProtectedRoute isCheckingSession={isCheckingSession}>
                <OrchestratorStudio />
              </ProtectedRoute>
            )}
          />
          <Route path="/share/:shareId" element={<SharedView />} />
          <Route path="*" element={<DefaultRoute isCheckingSession={isCheckingSession} />} />
        </Routes>
      </Suspense>

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
