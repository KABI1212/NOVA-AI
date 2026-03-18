// @ts-nocheck
import { useEffect, useState } from "react";
import { useParams }           from "react-router-dom";
import MessageBubble           from "../components/chat/MessageBubble";
import NovaLogo                from "../components/common/NovaLogo";

export default function SharedView() {
  const { shareId }              = useParams();
  const [convo,  setConvo]       = useState(null);
  const [loading, setLoading]    = useState(true);
  const [error,   setError]      = useState(null);

  useEffect(() => {
    fetchShared();
  }, [shareId]);

  const fetchShared = async () => {
    try {
      const res = await fetch(`/api/share/view/${shareId}`);

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Not found");
      }

      const data = await res.json();
      setConvo(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-gray-500">
        <div className="w-10 h-10 border-4 border-gray-700 border-t-blue-500
                        rounded-full animate-spin"/>
        <p className="text-sm">Loading conversation...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="text-center max-w-md px-6">
        <div className="text-6xl mb-4">🔒</div>
        <h1 className="text-xl font-semibold text-white mb-2">
          Conversation Not Found
        </h1>
        <p className="text-gray-500 text-sm mb-6">{error}</p>
        
        <a
          href="/"
          className="inline-block bg-blue-600 hover:bg-blue-500 text-white
                     px-6 py-2.5 rounded-xl text-sm font-medium transition-colors"
        >
          Go to NOVA-AI
        </a>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* Top bar */}
      <div className="border-b border-gray-800 px-6 py-4
                      flex items-center justify-between sticky top-0
                      bg-gray-950/95 backdrop-blur z-10">
        <div className="flex items-center gap-3">
          {/* NOVA-AI logo */}
          <NovaLogo size={32} textColor="#ffffff" />
          <div>
            <h1 className="font-semibold text-white text-sm">
              {convo.title}
            </h1>
            <p className="text-xs text-gray-500">
              Shared via NOVA-AI ·{" "}
              {convo.message_count || convo.messages?.length} messages ·{" "}
              {convo.view_count} views
            </p>
          </div>
        </div>

        <a
          href="/"
          className="text-sm bg-blue-600 hover:bg-blue-500 text-white
                     px-4 py-2 rounded-lg transition-colors font-medium"
        >
          Try NOVA-AI →
        </a>
      </div>

      {/* Shared at banner */}
      {convo.shared_at && (
        <div className="bg-blue-900/20 border-b border-blue-800/30 px-6 py-2">
          <p className="text-xs text-blue-400 text-center">
            🔗 Shared on{" "}
            {new Date(convo.shared_at).toLocaleDateString("en-US", {
              year: "numeric", month: "long", day: "numeric"
            })}
            {" · "}Model: <span className="font-medium">{convo.model}</span>
          </p>
        </div>
      )}

      {/* Messages */}
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-4">
        {convo.messages?.map((msg, i) => (
          <MessageBubble
            key={i}
            message={msg}
            isStreaming={false}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-gray-800 px-6 py-8 text-center">
        <p className="text-gray-600 text-sm mb-4">
          This conversation was shared from NOVA-AI
        </p>
        
        <a
          href="/"
          className="inline-flex items-center gap-2 bg-gradient-to-r
                     from-blue-600 to-purple-600 hover:from-blue-500
                     hover:to-purple-500 text-white px-6 py-3 rounded-xl
                     text-sm font-semibold transition-all shadow-lg"
        >
          ✨ Start your own conversation on NOVA-AI
        </a>
      </div>
    </div>
  );
}
