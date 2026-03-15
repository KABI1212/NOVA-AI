// @ts-nocheck
import { useState, useEffect } from "react";
import { useAuthStore } from "../utils/store";

export default function MyShares() {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copied,  setCopied]  = useState(null);
  const { token } = useAuthStore();

  useEffect(() => { fetchShares(); }, []);

  const fetchShares = async () => {
    try {
      const res = await fetch("/api/share/my-shares", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setShares(data.shares || []);
    } catch {}
    finally { setLoading(false); }
  };

  // @ts-ignore
  const disableShare = async (conversationId, shareId) => {
    try {
      await fetch(`/api/share/disable/${conversationId}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      // @ts-ignore
      setShares(prev => prev.filter(s => s.share_id !== shareId));
    } catch {}
  };

  const copyLink = (/** @type {import("react").SetStateAction<null>} */ shareId) => {
    const url = `${window.location.origin}/share/${shareId}`;
    navigator.clipboard.writeText(url);
    setCopied(shareId);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-3xl mx-auto">

        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">🔗 My Shared Chats</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Manage all your publicly shared conversations
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20 text-gray-500">
            <div className="w-8 h-8 border-4 border-gray-700 border-t-blue-500
                            rounded-full animate-spin mr-3"/>
            Loading...
          </div>
        )}

        {!loading && shares.length === 0 && (
          <div className="text-center py-20 text-gray-600">
            <div className="text-5xl mb-4">🔗</div>
            <p className="text-lg text-gray-500">No shared conversations yet</p>
            <p className="text-sm mt-1">
              Share a chat from the chat page to see it here
            </p>
          </div>
        )}

        {!loading && shares.length > 0 && (
          <div className="space-y-3">
            {shares.map(share => (
              <div
                key={share.share_id}
                className="bg-gray-900 border border-gray-800 rounded-2xl
                           p-5 hover:border-gray-700 transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-white truncate">
                      {share.title}
                    </h3>
                    <div className="flex items-center gap-3 mt-1 flex-wrap">
                      <span className="text-xs text-gray-500">
                        {share.message_count} messages
                      </span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs text-gray-500">
                        👁️ {share.view_count} views
                      </span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs text-gray-500">
                        {new Date(share.shared_at).toLocaleDateString()}
                      </span>
                    </div>

                    {/* Share URL */}
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-xs text-blue-400 font-mono truncate">
                        {window.location.origin}/share/{share.share_id}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => copyLink(share.share_id)}
                      className={`text-xs px-3 py-1.5 rounded-lg transition-all
                                  ${copied === share.share_id
                                    ? "bg-green-700 text-white"
                                    : "bg-gray-800 hover:bg-gray-700 text-gray-300"}`}
                    >
                      {copied === share.share_id ? "✅" : "📋"}
                    </button>

                    
                      <a
                      href={`/share/${share.share_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700
                                 text-gray-300 rounded-lg transition-all"
                    >
                      👁️ View
                    </a>

                    <button
                      onClick={() => disableShare(share.conversation_id, share.share_id)}
                      className="text-xs px-3 py-1.5 bg-red-900/40 hover:bg-red-900/70
                                 text-red-400 hover:text-red-300 border border-red-800/50
                                 rounded-lg transition-all"
                    >
                      Disable
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
