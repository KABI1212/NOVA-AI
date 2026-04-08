import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";

import { fetchApi } from "../../services/api";
import { useAuthStore } from "../../utils/store";

function formatViewCount(value) {
  const count = Number(value || 0);
  if (!Number.isFinite(count) || count <= 0) {
    return "No views yet";
  }
  return `${count} view${count === 1 ? "" : "s"}`;
}

export default function ShareButton({
  conversationId = null,
  conversationTitle = "",
}) {
  const { token } = useAuthStore();

  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [shareTitle, setShareTitle] = useState(conversationTitle || "");

  useEffect(() => {
    setShareTitle(conversationTitle || "");
    setCopied(false);
  }, [conversationId, conversationTitle]);

  useEffect(() => {
    if (!conversationId || !token) {
      setStatus(null);
      return undefined;
    }

    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const response = await fetchApi(`/share/status/${conversationId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          if (!cancelled) {
            setStatus(null);
          }
          return;
        }

        const data = await response.json();
        if (!cancelled) {
          setStatus(data);
          if (data?.share_title) {
            setShareTitle(data.share_title);
          }
        }
      } catch {
        if (!cancelled) {
          setStatus(null);
        }
      }
    };

    fetchStatus();

    return () => {
      cancelled = true;
    };
  }, [conversationId, token]);

  const isShared = Boolean(status?.is_shared);
  const shareUrl = useMemo(() => {
    if (!status?.share_id || typeof window === "undefined") {
      return "";
    }
    return `${window.location.origin}/share/${status.share_id}`;
  }, [status?.share_id]);

  const enableShare = async () => {
    if (!conversationId) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetchApi("/share/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          share_title: shareTitle.trim() || conversationTitle || "",
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || "Could not create a share link.");
      }

      setStatus((previous) => ({ ...(previous || {}), ...data, is_shared: true }));
      if (data?.share_title) {
        setShareTitle(data.share_title);
      }
      toast.success("Share link is ready.");
    } catch (error) {
      toast.error(error?.message || "Could not create a share link right now.");
    } finally {
      setLoading(false);
    }
  };

  const disableShare = async () => {
    if (!conversationId) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetchApi(`/share/disable/${conversationId}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || "Could not disable sharing.");
      }

      setStatus((previous) => ({ ...(previous || {}), is_shared: false }));
      toast.success("Share link disabled.");
    } catch (error) {
      toast.error(error?.message || "Could not disable sharing right now.");
    } finally {
      setLoading(false);
    }
  };

  const copyLink = async () => {
    if (!shareUrl) {
      return;
    }

    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success("Link copied.");
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy the link.");
    }
  };

  const openPreview = () => {
    if (!shareUrl) {
      return;
    }

    window.open(shareUrl, "_blank", "noopener,noreferrer");
  };

  const openNativeShare = async () => {
    if (!shareUrl) {
      return;
    }

    if (navigator.share) {
      try {
        await navigator.share({
          title: shareTitle.trim() || conversationTitle || "NOVA AI conversation",
          url: shareUrl,
        });
        return;
      } catch {
        return;
      }
    }

    await copyLink();
  };

  return (
    <>
      <button
        type="button"
        className={`tb-ghost share-trigger${isShared ? " active" : ""}`}
        onClick={() => setShowModal(true)}
        aria-label="Share conversation"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="19" r="3" />
          <path d="M8.6 13.5 15.4 17.5" />
          <path d="M15.4 6.5 8.6 10.5" />
        </svg>
        <span className="share-trigger-label">{isShared ? "Shared" : "Share"}</span>
      </button>

      {showModal ? (
        <div
          className="ov open"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setShowModal(false);
            }
          }}
        >
          <div className="modal share-modal" onClick={(event) => event.stopPropagation()}>
            <h3>Share Conversation</h3>
            <p>Anyone with the link can view this chat.</p>

            {!conversationId ? (
              <div className="share-empty">
                Send at least one message first. Once the conversation exists, you can create a public link here
                without changing the current layout.
              </div>
            ) : (
              <>
                <label className="modal-label" htmlFor="share-title-input">
                  Share title
                </label>
                <input
                  id="share-title-input"
                  type="text"
                  value={shareTitle}
                  onChange={(event) => setShareTitle(event.target.value)}
                  placeholder={conversationTitle || "My conversation"}
                  disabled={loading}
                />

                <div className="share-panel">
                  <div className="share-toggle-row">
                    <div className="share-toggle-copy">
                      <strong>{isShared ? "Link is active" : "Link sharing"}</strong>
                      <span>{isShared ? formatViewCount(status?.view_count) : "Enable this to create a public link."}</span>
                    </div>
                    <button
                      type="button"
                      className={`share-switch${isShared ? " on" : ""}`}
                      onClick={isShared ? disableShare : enableShare}
                      disabled={loading}
                      aria-label={isShared ? "Disable sharing" : "Enable sharing"}
                    >
                      <span className="share-switch-thumb" />
                    </button>
                  </div>
                </div>

                {isShared && shareUrl ? (
                  <>
                    <div className="share-link-box">
                      <input className="share-link-input" type="text" readOnly value={shareUrl} />
                      <button className="bok share-inline-btn" type="button" onClick={copyLink}>
                        {copied ? "Copied" : "Copy"}
                      </button>
                    </div>

                    <div className="share-action-row">
                      <button className="share-action" type="button" onClick={openPreview}>
                        Open link
                      </button>
                      <button className="share-action" type="button" onClick={openNativeShare}>
                        Share
                      </button>
                    </div>

                    <div className="share-warning">
                      Anyone with the link can read this conversation until you turn sharing off.
                    </div>
                  </>
                ) : (
                  <div className="share-empty">Enable sharing to create a public link for this conversation.</div>
                )}
              </>
            )}

            <div className="mbtns">
              <button className="bcnl" type="button" onClick={() => setShowModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
