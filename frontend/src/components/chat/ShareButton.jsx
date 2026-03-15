import { useState, useEffect } from "react";
import { useAuthStore } from "../../utils/store";

export default function ShareButton({ conversationId, conversationTitle }) {
  const [status,    setStatus]    = useState(null);  // share status from API
  const [loading,   setLoading]   = useState(false);
  const [copied,    setCopied]    = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [shareTitle, setShareTitle] = useState(conversationTitle || "");
  const { token } = useAuthStore();

  // Load share status on mount
  useEffect(() => {
    if (conversationId) fetchStatus();
  }, [conversationId]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/share/status/${conversationId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch {}
  };

  const enableShare = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/share/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization:  `Bearer ${token}`,
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          share_title:     shareTitle,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail);
      }

      const data = await res.json();
      setStatus(prev => ({ ...prev, ...data }));
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const disableShare = async () => {
    setLoading(true);
    try {
      await fetch(`/api/share/disable/${conversationId}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setStatus(prev => ({ ...prev, is_shared: false }));
    } catch {}
    finally {
      setLoading(false);
    }
  };

  const copyLink = () => {
    const url = `${window.location.origin}/share/${status.share_id}`;
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const shareUrl = status?.share_id
    ? `${window.location.origin}/share/${status.share_id}`
    : null;

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setShowModal(true)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                    border transition-all
                    ${status?.is_shared
                      ? "border-green-600 bg-green-600/10 text-green-400"
                      : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"}`}
        title="Share conversation"
      >
        {status?.is_shared ? "🔗 Shared" : "🔗 Share"}
      </button>

      {/* Modal */}
      {showModal && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50
                     flex items-center justify-center p-4"
          onClick={e => { if (e.target === e.currentTarget) setShowModal(false); }}
        >
          <div className="bg-gray-900 border border-gray-700 rounded-2xl
                          shadow-2xl w-full max-w-md p-6">

            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Share Conversation
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Anyone with the link can view this chat
                </p>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-600 hover:text-white transition-colors text-xl"
              >
                ✕
              </button>
            </div>

            {/* Share title input */}
            <div className="mb-4">
              <label className="text-sm text-gray-400 mb-1.5 block">
                Share title (optional)
              </label>
              <input
                value={shareTitle}
                onChange={e => setShareTitle(e.target.value)}
                placeholder={conversationTitle || "My conversation"}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl
                           px-4 py-2.5 text-white text-sm placeholder-gray-500
                           focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Toggle share */}
            <div className="flex items-center justify-between bg-gray-800
                            border border-gray-700 rounded-xl px-4 py-3 mb-4">
              <div>
                <p className="text-sm font-medium text-white">
                  {status?.is_shared ? "Link is active" : "Link sharing"}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {status?.is_shared
                    ? `${status.view_count || 0} views`
                    : "Enable to create a public link"}
                </p>
              </div>

              {/* Toggle switch */}
              <button
                onClick={status?.is_shared ? disableShare : enableShare}
                disabled={loading}
                className={`relative w-12 h-6 rounded-full transition-all duration-200
                            ${status?.is_shared ? "bg-green-500" : "bg-gray-600"}
                            disabled:opacity-50`}
              >
                <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full
                                  shadow transition-all duration-200
                                  ${status?.is_shared ? "left-6" : "left-0.5"}`}
                />
              </button>
            </div>

            {/* Share link display */}
            {status?.is_shared && shareUrl && (
              <div className="space-y-3">
                {/* Link box */}
                <div className="flex items-center gap-2 bg-gray-800 border
                                border-gray-700 rounded-xl px-3 py-2.5">
                  <span className="flex-1 text-sm text-blue-400 truncate font-mono">
                    {shareUrl}
                  </span>
                  <button
                    onClick={copyLink}
                    className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-lg
                                font-medium transition-all
                                ${copied
                                  ? "bg-green-600 text-white"
                                  : "bg-gray-700 hover:bg-gray-600 text-gray-300"}`}
                  >
                    {copied ? "✅ Copied!" : "📋 Copy"}
                  </button>
                </div>

                {/* Share actions */}
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={copyLink}
                    className="flex flex-col items-center gap-1.5 py-3 bg-gray-800
                               hover:bg-gray-700 border border-gray-700 rounded-xl
                               text-xs text-gray-400 hover:text-white transition-all"
                  >
                    <span className="text-lg">📋</span>
                    Copy link
                  </button>

                  <button
                    onClick={() => window.open(shareUrl, "_blank")}
                    className="flex flex-col items-center gap-1.5 py-3 bg-gray-800
                               hover:bg-gray-700 border border-gray-700 rounded-xl
                               text-xs text-gray-400 hover:text-white transition-all"
                  >
                    <span className="text-lg">👁️</span>
                    Preview
                  </button>

                  <button
                    onClick={() => {
                      const text = `Check out this AI conversation: ${shareUrl}`;
                      window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`, "_blank");
                    }}
                    className="flex flex-col items-center gap-1.5 py-3 bg-gray-800
                               hover:bg-gray-700 border border-gray-700 rounded-xl
                               text-xs text-gray-400 hover:text-white transition-all"
                  >
                    <span className="text-lg">𝕏</span>
                    Tweet
                  </button>
                </div>

                {/* Warning */}
                <div className="flex items-start gap-2 bg-amber-900/20 border
                                border-amber-700/30 rounded-xl px-3 py-2.5">
                  <span className="text-amber-500 flex-shrink-0">⚠️</span>
                  <p className="text-xs text-amber-500/80">
                    Anyone with the link can view this conversation.
                    Disable sharing to revoke access.
                  </p>
                </div>
              </div>
            )}

            {/* Footer */}
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="px-5 py-2 bg-gray-800 hover:bg-gray-700 text-white
                           text-sm rounded-xl transition-colors border border-gray-700"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
