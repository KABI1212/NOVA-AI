import React, { useEffect, useRef, useState } from "react";

function ChatInput({ value, onChange, onSend, disabled }) {
  const [attachedFile, setAttachedFile] = useState(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!textareaRef.current) {
      return;
    }
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
  }, [value]);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setAttachedFile(file);
  };

  const clearFile = () => {
    setAttachedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSend = () => {
    if (disabled) {
      return;
    }
    const trimmed = value.trim();
    if (!trimmed && !attachedFile) {
      return;
    }
    const payload = attachedFile
      ? `${trimmed}${trimmed ? " + " : ""}[File: ${attachedFile.name}]`
      : trimmed;
    onSend(payload);
    clearFile();
    onChange("");
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const isSendDisabled = disabled || (!value.trim() && !attachedFile);

  return (
    <div className="input-wrap">
      {attachedFile ? (
        <div className="fp">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          {attachedFile.name} ({(attachedFile.size / 1024).toFixed(1)}KB)
          <button className="frm" type="button" onClick={clearFile}>
            x
          </button>
        </div>
      ) : null}

      <div className="input-pill">
        <button className="input-btn ghost" type="button" onClick={() => fileInputRef.current?.click()}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>

        <textarea
          ref={textareaRef}
          className="input-field"
          placeholder="How can I help you today?"
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />

        <div className="input-actions">
          <button className="input-model" type="button">
            Nova Fast
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          <button className="input-btn ghost" type="button" title="Voice input" disabled>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>
          <button className="input-btn send" type="button" disabled={isSendDisabled} onClick={handleSend}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        style={{ display: "none" }}
        accept="image/*,.pdf,.txt,.csv,.py,.js,.html,.json"
        onChange={handleFileChange}
      />
    </div>
  );
}

export default ChatInput;

