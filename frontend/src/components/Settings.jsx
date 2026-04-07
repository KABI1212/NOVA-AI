import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

import { authAPI } from "../services/api";
import { useAuthStore, useThemeStore, useVoiceStore } from "../utils/store";
import {
  BROWSER_VOICE_AUTO,
  getSpeechVoiceOptions,
  TTS_VOICE_OPTIONS,
} from "../utils/voices";

function Settings({ open = false, onClose, onNewChat, onExportChat, canExportChat = false }) {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const setUser = useAuthStore((state) => state.setUser);
  const isDark = useThemeStore((state) => state.isDark);
  const toggleTheme = useThemeStore((state) => state.toggleTheme);
  const browserVoice = useVoiceStore((state) => state.browserVoice);
  const setBrowserVoice = useVoiceStore((state) => state.setBrowserVoice);
  const ttsVoice = useVoiceStore((state) => state.ttsVoice);
  const setTtsVoice = useVoiceStore((state) => state.setTtsVoice);

  const [formData, setFormData] = useState({
    full_name: user?.full_name || "",
    username: user?.username || "",
    email: user?.email || "",
  });
  const [speechSupported, setSpeechSupported] = useState(false);
  const [browserVoiceOptions, setBrowserVoiceOptions] = useState([
    { id: BROWSER_VOICE_AUTO, label: "Auto (device default)" },
  ]);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }

    setFormData({
      full_name: user?.full_name || "",
      username: user?.username || "",
      email: user?.email || "",
    });
    setDeleteConfirmation("");
  }, [open, user]);

  useEffect(() => {
    if (!open || typeof window === "undefined") {
      return undefined;
    }

    const syncSpeechVoices = () => {
      const supported = Boolean(window.speechSynthesis);
      setSpeechSupported(supported);
      setBrowserVoiceOptions(getSpeechVoiceOptions());
    };

    syncSpeechVoices();
    window.speechSynthesis?.addEventListener?.("voiceschanged", syncSpeechVoices);

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        onClose?.();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
      window.speechSynthesis?.removeEventListener?.("voiceschanged", syncSpeechVoices);
    };
  }, [onClose, open]);

  const handleSave = async (event) => {
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

  const handleLogout = () => {
    onClose?.();
    logout();
    navigate("/login", { replace: true });
  };

  const handleOpenShares = () => {
    onClose?.();
    navigate("/my-shares");
  };

  const handleStartNewChat = () => {
    onClose?.();
    onNewChat?.();
  };

  const handleExportCurrentChat = () => {
    onClose?.();
    onExportChat?.();
  };

  if (!open) {
    return null;
  }

  return (
    <div
      className="ov open"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose?.();
        }
      }}
    >
      <div className="modal settings-modal" onClick={(event) => event.stopPropagation()}>
        <div className="settings-head">
          <div>
            <h3>Settings</h3>
            <p>Manage your account and personalize the current NOVA AI workspace.</p>
          </div>
          <button className="tb-ghost settings-close" type="button" onClick={onClose} aria-label="Close settings">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="settings-stack">
          <section className="settings-section">
            <div className="settings-section-head">
              <div>
                <h4>Account</h4>
                <span>Update the profile details shown in your workspace and used for login.</span>
              </div>
            </div>

            <form className="settings-form" onSubmit={handleSave}>
              <label className="modal-label" htmlFor="settings-full-name">
                Full name
              </label>
              <input
                id="settings-full-name"
                type="text"
                value={formData.full_name}
                onChange={(event) =>
                  setFormData((current) => ({ ...current, full_name: event.target.value }))
                }
                placeholder="Full name"
                disabled={isSaving}
              />

              <label className="modal-label" htmlFor="settings-username">
                Username
              </label>
              <input
                id="settings-username"
                type="text"
                value={formData.username}
                onChange={(event) =>
                  setFormData((current) => ({ ...current, username: event.target.value }))
                }
                placeholder="Username"
                disabled={isSaving}
              />

              <label className="modal-label" htmlFor="settings-email">
                Email
              </label>
              <input
                id="settings-email"
                type="email"
                value={formData.email}
                onChange={(event) =>
                  setFormData((current) => ({ ...current, email: event.target.value }))
                }
                placeholder="Email"
                disabled={isSaving}
              />

              <div className="mbtns">
                <button className="bok" type="submit" disabled={isSaving}>
                  {isSaving ? "Saving..." : "Save changes"}
                </button>
              </div>
            </form>
          </section>

          <section className="settings-section">
            <div className="settings-section-head">
              <div>
                <h4>Appearance</h4>
                <span>Keep the same interface and switch how NOVA AI feels on this device.</span>
              </div>
            </div>

            <div className="settings-row">
              <div className="settings-copy">
                <strong>{isDark ? "Dark mode" : "Light mode"}</strong>
                <span>Theme preference is saved locally in your browser.</span>
              </div>
              <button className="settings-chip" type="button" onClick={toggleTheme}>
                {isDark ? "Switch to light" : "Switch to dark"}
              </button>
            </div>
          </section>

          <section className="settings-section">
            <div className="settings-section-head">
              <div>
                <h4>Workspace</h4>
                <span>Quick actions and voice preferences for the current NOVA AI workspace.</span>
              </div>
            </div>

            <div className="settings-row">
              <div className="settings-copy">
                <strong>Browser voice</strong>
                <span>{speechSupported ? "Speech playback is available in this browser." : "Speech playback is not available in this browser."}</span>
              </div>
              <span className={`settings-badge${speechSupported ? " ok" : ""}`}>
                {speechSupported ? "Available" : "Unavailable"}
              </span>
            </div>

            <div className="settings-row">
              <div className="settings-copy">
                <strong>Manual playback only</strong>
                <span>NOVA will now speak only when you press a speak button.</span>
              </div>
              <span className="settings-badge ok">Enabled</span>
            </div>

            <div className="settings-row">
              <div className="settings-copy">
                <strong>Browser speak voice</strong>
                <span>Used by speak icons that read answers with your device voice.</span>
              </div>
              <select
                className="input-field max-w-[260px]"
                value={browserVoice}
                onChange={(event) => setBrowserVoice(event.target.value)}
                disabled={!speechSupported}
              >
                {browserVoiceOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="settings-row">
              <div className="settings-copy">
                <strong>AI voice</strong>
                <span>Used by the server-backed read-aloud buttons in assistant replies.</span>
              </div>
              <select
                className="input-field max-w-[260px]"
                value={ttsVoice}
                onChange={(event) => setTtsVoice(event.target.value)}
              >
                {TTS_VOICE_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="settings-action-grid">
              <button className="settings-action-btn" type="button" onClick={handleStartNewChat}>
                New chat
              </button>
              <button
                className="settings-action-btn"
                type="button"
                onClick={handleExportCurrentChat}
                disabled={!canExportChat}
              >
                Export chat
              </button>
              <button className="settings-action-btn" type="button" onClick={handleOpenShares}>
                Shared chats
              </button>
              <button className="settings-action-btn" type="button" onClick={handleLogout}>
                Log out
              </button>
            </div>
          </section>

          <section className="settings-section danger">
            <div className="settings-section-head">
              <div>
                <h4>Danger zone</h4>
                <span>Deleting your account removes conversations and learning history.</span>
              </div>
            </div>

            <label className="modal-label" htmlFor="settings-delete-confirmation">
              Type DELETE to confirm
            </label>
            <input
              id="settings-delete-confirmation"
              type="text"
              value={deleteConfirmation}
              onChange={(event) => setDeleteConfirmation(event.target.value)}
              placeholder='Type "DELETE"'
              disabled={isDeleting}
            />

            <div className="mbtns">
              <button className="bok bok-danger" type="button" onClick={handleDeleteAccount} disabled={isDeleting}>
                {isDeleting ? "Deleting..." : "Delete account"}
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default Settings;
