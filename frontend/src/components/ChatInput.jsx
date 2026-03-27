import React, { useEffect, useMemo, useRef, useState } from "react";

import {
  CHAT_COMPOSER_MENU,
  CHAT_COMPOSER_PRESETS,
  DEFAULT_CHAT_PLACEHOLDER,
} from "../constants/chatExperience";

const PRESET_MAP = Object.fromEntries(CHAT_COMPOSER_PRESETS.map((preset) => [preset.id, preset]));
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"];
const FILE_INPUT_ACCEPT =
  ".pdf,.txt,.docx,.md,.csv,.json,.py,.js,.jsx,.ts,.tsx,.html,.htm,.css,.xml,.yml,.yaml,.png,.jpg,.jpeg,.webp,.gif,.bmp";

const isImageFile = (file) => {
  if (!file) {
    return false;
  }

  const fileType = String(file.type || "").toLowerCase();
  if (fileType.startsWith("image/")) {
    return true;
  }

  const name = String(file.name || "").toLowerCase();
  return IMAGE_EXTENSIONS.some((extension) => name.endsWith(extension));
};

const formatFileSize = (size) => {
  const numericSize = Number(size || 0);
  if (!Number.isFinite(numericSize) || numericSize <= 0) {
    return "0 KB";
  }

  if (numericSize < 1024 * 1024) {
    return `${(numericSize / 1024).toFixed(1)} KB`;
  }

  return `${(numericSize / (1024 * 1024)).toFixed(2)} MB`;
};

function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
  modelOptions = [],
  selectedModelKey = "auto",
  onSelectModel,
  generatePromptImage = false,
  generateAnswerImage = false,
  answerImageLocked = false,
  onTogglePromptImage,
  onToggleAnswerImage,
}) {
  const [attachedFile, setAttachedFile] = useState(null);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [heardText, setHeardText] = useState("");
  const [showVoiceDraft, setShowVoiceDraft] = useState(false);
  const [launcherView, setLauncherView] = useState("closed");
  const [selectedPresetId, setSelectedPresetId] = useState(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);
  const composerRef = useRef(null);
  const valueRef = useRef(value);
  const attachedFileRef = useRef(attachedFile);
  const disabledRef = useRef(disabled);
  const onChangeRef = useRef(onChange);
  const onSendRef = useRef(onSend);
  const voiceBaseValueRef = useRef("");
  const capturedSpeechRef = useRef("");
  const previewSpeechRef = useRef("");

  const selectedPreset = useMemo(
    () => (selectedPresetId ? PRESET_MAP[selectedPresetId] || null : null),
    [selectedPresetId]
  );
  const attachedImage = isImageFile(attachedFile);
  const placeholder = selectedPreset?.placeholder || DEFAULT_CHAT_PLACEHOLDER;
  const showVoicePanel = isListening || showVoiceDraft;
  const isSendDisabled = disabled || (!value.trim() && !attachedFile);
  const voiceButtonTitle = speechSupported
    ? isListening
      ? "Stop voice input"
      : "Start voice input"
    : "Voice input is not supported in this browser";

  useEffect(() => {
    if (!textareaRef.current) {
      return;
    }
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
  }, [value]);

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  useEffect(() => {
    attachedFileRef.current = attachedFile;
  }, [attachedFile]);

  useEffect(() => {
    disabledRef.current = disabled;
  }, [disabled]);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    onSendRef.current = onSend;
  }, [onSend]);

  useEffect(() => {
    if (launcherView === "closed") {
      return undefined;
    }

    const handlePointerDown = (event) => {
      if (composerRef.current && !composerRef.current.contains(event.target)) {
        setLauncherView("closed");
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setLauncherView("closed");
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [launcherView]);

  const clearFile = () => {
    setAttachedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const resetVoiceDraft = () => {
    voiceBaseValueRef.current = "";
    capturedSpeechRef.current = "";
    previewSpeechRef.current = "";
    setHeardText("");
    setShowVoiceDraft(false);
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const imageFile = isImageFile(file);
    setAttachedFile(file);
    setLauncherView("closed");

    if (imageFile) {
      setSelectedPresetId("create_image");
    } else {
      setSelectedPresetId((current) => (current === "create_image" ? null : current));
    }
  };

  const dispatchMessage = (rawValue) => {
    if (disabledRef.current) {
      return;
    }

    const trimmed = String(rawValue || "").trim();
    const currentFile = attachedFileRef.current;
    const imageAttachment = isImageFile(currentFile);
    if (!trimmed && !currentFile) {
      return;
    }

    const activePreset = selectedPresetId ? PRESET_MAP[selectedPresetId] || null : null;
    const attachmentKind = currentFile ? (imageAttachment ? "image" : "document") : null;
    const attachmentLabel = attachmentKind === "image" ? "Photo" : "File";
    const fallbackText = currentFile
      ? imageAttachment
        ? "Create a polished edit from this uploaded photo."
        : "Summarize this document in simple words."
      : "";
    const text = trimmed || fallbackText;
    const displayText = currentFile
      ? `${trimmed}${trimmed ? " + " : ""}[${attachmentLabel}: ${currentFile.name}]`
      : trimmed;

    onSendRef.current?.({
      text,
      displayText: displayText || text,
      file: currentFile || null,
      attachmentKind,
      presetId: activePreset?.id || null,
      forceMode: activePreset?.forceMode || null,
      promptPrefix: activePreset?.promptPrefix || "",
      presetLabel: activePreset ? `${activePreset.emoji} ${activePreset.label}` : null,
    });

    resetVoiceDraft();
    clearFile();
    onChangeRef.current?.("");
  };

  const handleSend = () => {
    dispatchMessage(valueRef.current);
  };

  const handleVoiceSend = () => {
    dispatchMessage(valueRef.current);
  };

  const handleVoiceEdit = () => {
    textareaRef.current?.focus();
    const cursorPosition = valueRef.current.length;

    try {
      textareaRef.current?.setSelectionRange(cursorPosition, cursorPosition);
    } catch {}
  };

  const handleInputChange = (event) => {
    onChange(event.target.value);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (!disabled || !isListening || !recognitionRef.current) {
      return;
    }

    try {
      recognitionRef.current.stop();
    } catch {}
  }, [disabled, isListening]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return undefined;
    }

    setSpeechSupported(true);

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      let finalChunk = "";
      let interimChunk = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result?.[0]?.transcript?.trim();

        if (!transcript) {
          continue;
        }

        if (result.isFinal) {
          finalChunk = [finalChunk, transcript].filter(Boolean).join(" ").trim();
        } else {
          interimChunk = [interimChunk, transcript].filter(Boolean).join(" ").trim();
        }
      }

      if (finalChunk) {
        capturedSpeechRef.current = [capturedSpeechRef.current, finalChunk].filter(Boolean).join(" ").trim();
      }

      const previewSpoken = [capturedSpeechRef.current, interimChunk].filter(Boolean).join(" ").trim();
      previewSpeechRef.current = previewSpoken;
      setHeardText(previewSpoken);

      const nextValue = [voiceBaseValueRef.current, previewSpoken].filter(Boolean).join(" ").trim();
      onChangeRef.current?.(nextValue);
    };

    recognition.onerror = () => {
      previewSpeechRef.current = "";
      capturedSpeechRef.current = "";
      setHeardText("");
      setShowVoiceDraft(false);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);

      const finalSpoken = (capturedSpeechRef.current || previewSpeechRef.current).trim();
      if (!finalSpoken || disabledRef.current) {
        setHeardText("");
        setShowVoiceDraft(false);
        return;
      }

      capturedSpeechRef.current = finalSpoken;
      previewSpeechRef.current = finalSpoken;
      setHeardText(finalSpoken);
      setShowVoiceDraft(true);

      const nextValue = [voiceBaseValueRef.current, finalSpoken].filter(Boolean).join(" ").trim();
      onChangeRef.current?.(nextValue);

      window.setTimeout(() => {
        textareaRef.current?.focus();
      }, 0);
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.onstart = null;
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      try {
        recognition.stop();
      } catch {}
      recognitionRef.current = null;
    };
  }, []);

  const handleVoiceToggle = () => {
    if (!speechSupported || disabled) {
      return;
    }

    const recognition = recognitionRef.current;
    if (!recognition) {
      return;
    }

    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    if (isListening) {
      recognition.stop();
      return;
    }

    try {
      voiceBaseValueRef.current = valueRef.current.trim();
      capturedSpeechRef.current = "";
      previewSpeechRef.current = "";
      setHeardText("");
      setShowVoiceDraft(false);
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const handlePresetSelect = (presetId) => {
    setSelectedPresetId(presetId);
    setLauncherView("closed");
    textareaRef.current?.focus();
  };

  const clearPreset = () => {
    setSelectedPresetId(null);
  };

  const handleMenuAction = (actionId) => {
    if (actionId === "attach") {
      fileInputRef.current?.click();
      setLauncherView("closed");
      return;
    }

    if (actionId === "more") {
      setLauncherView("more");
      return;
    }

    handlePresetSelect(actionId);
  };

  return (
    <div className="input-wrap">
      {showVoicePanel ? (
        <div className={`voice-capture${isListening ? " live" : ""}`}>
          <div className="voice-capture-head">
            <div className="voice-capture-status">
              <span className="voice-capture-dot" aria-hidden="true" />
              <span>{isListening ? "Listening..." : "Voice draft ready"}</span>
            </div>
            <div className="voice-capture-label">
              {isListening ? "Speak naturally and I will show it here." : "Edit it below or send it directly."}
            </div>
          </div>

          <div className={`voice-capture-text${heardText ? "" : " empty"}`}>
            {heardText || "Start speaking and your words will appear here."}
          </div>

          {!isListening ? (
            <div className="voice-capture-actions">
              <button className="voice-capture-btn secondary" type="button" onClick={handleVoiceEdit}>
                Edit
              </button>
              <button
                className="voice-capture-btn primary"
                type="button"
                disabled={isSendDisabled}
                onClick={handleVoiceSend}
              >
                OK, Send
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {attachedFile ? (
        <div className={`fp${attachedImage ? " photo" : ""}`}>
          <div className="fp-icon" aria-hidden="true">
            {attachedImage ? "🖼️" : "📄"}
          </div>
          <div className="fp-copy">
            <strong>{attachedFile.name}</strong>
            <span>
              {attachedImage ? "Photo ready for image remix" : "Document ready for chat analysis"} •{" "}
              {formatFileSize(attachedFile.size)}
            </span>
          </div>
          <button className="frm" type="button" onClick={clearFile} aria-label="Remove attachment">
            ×
          </button>
        </div>
      ) : null}

      <div className="input-shell" ref={composerRef}>
        {launcherView !== "closed" ? (
          <div className={`launcher-menu${launcherView === "more" ? " more" : ""}`}>
            {launcherView === "main" ? (
              <div className="launcher-panel">
                {CHAT_COMPOSER_MENU.map((item) => {
                  const active = item.id === selectedPresetId;
                  return (
                    <button
                      key={item.id}
                      className={`launcher-action${active ? " active" : ""}`}
                      type="button"
                      onClick={() => handleMenuAction(item.id)}
                    >
                      <span className="launcher-action-icon" aria-hidden="true">
                        {item.emoji}
                      </span>
                      <span className="launcher-action-copy">
                        <strong>{item.label}</strong>
                        <span>{item.description}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="launcher-panel">
                <button className="launcher-back" type="button" onClick={() => setLauncherView("main")}>
                  ← Back
                </button>

                <button
                  className={`launcher-action${!selectedPreset ? " active" : ""}`}
                  type="button"
                  onClick={() => {
                    clearPreset();
                    setLauncherView("closed");
                  }}
                >
                  <span className="launcher-action-icon" aria-hidden="true">
                    💬
                  </span>
                  <span className="launcher-action-copy">
                    <strong>General chat</strong>
                    <span>Clear quick mode and return to a normal conversation</span>
                  </span>
                </button>

                <button
                  className={`launcher-action${generatePromptImage ? " active" : ""}`}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    onTogglePromptImage?.();
                    setLauncherView("closed");
                  }}
                >
                  <span className="launcher-action-icon" aria-hidden="true">
                    🎨
                  </span>
                  <span className="launcher-action-copy">
                    <strong>{generatePromptImage ? "Prompt image on" : "Prompt image"}</strong>
                    <span>Generate a visual from your prompt alongside the answer</span>
                  </span>
                </button>

                <button
                  className={`launcher-action${generateAnswerImage ? " active" : ""}`}
                  type="button"
                  disabled={disabled || answerImageLocked}
                  onClick={() => {
                    if (!answerImageLocked) {
                      onToggleAnswerImage?.();
                    }
                    setLauncherView("closed");
                  }}
                >
                  <span className="launcher-action-icon" aria-hidden="true">
                    🖼️
                  </span>
                  <span className="launcher-action-copy">
                    <strong>{answerImageLocked ? "Answer visuals always on" : "Answer visuals"}</strong>
                    <span>Ask NOVA to add a relevant image to the response when possible</span>
                  </span>
                </button>

                <div className="launcher-note">
                  📌 Photos now flow into the image tool for edits and remixes. Documents still upload into chat for
                  analysis and summarization.
                </div>
              </div>
            )}
          </div>
        ) : null}

        <div className="input-pill">
          <button
            className={`input-btn ghost input-launcher-btn${launcherView !== "closed" ? " active" : ""}`}
            type="button"
            onClick={() => setLauncherView((current) => (current === "closed" ? "main" : "closed"))}
            aria-label="Open tools"
            disabled={disabled}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>

          <textarea
            ref={textareaRef}
            className="input-field"
            placeholder={placeholder}
            rows={1}
            value={value}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            disabled={disabled}
          />

          <div className="input-actions">
            <button
              className={`input-btn ghost${isListening ? " listening" : ""}`}
              type="button"
              title={voiceButtonTitle}
              onClick={handleVoiceToggle}
              disabled={!speechSupported || disabled}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            </button>
            <button className="input-btn send send-circle" type="button" disabled={isSendDisabled} onClick={handleSend}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <div className="input-meta">
        <div className="input-meta-group">
          <div className="input-model input-model-wrap">
            <select
              className="input-model-select"
              value={selectedModelKey}
              onChange={(event) => onSelectModel?.(event.target.value)}
              disabled={disabled || modelOptions.length <= 1}
              title="Choose model"
            >
              {modelOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>

          {selectedPreset ? (
            <button className="input-mode-pill" type="button" onClick={clearPreset}>
              <span aria-hidden="true">{selectedPreset.emoji}</span>
              <span>{selectedPreset.label}</span>
              <span className="input-mode-pill-close" aria-hidden="true">
                ×
              </span>
            </button>
          ) : null}

          {generatePromptImage ? <span className="input-status-pill">🎨 Prompt image on</span> : null}
          {generateAnswerImage || answerImageLocked ? (
            <span className="input-status-pill">🖼️ Answer visuals on</span>
          ) : null}
        </div>

        <div className="input-meta-note">
          {selectedPreset
            ? selectedPreset.description
            : attachedImage
              ? "Photo uploads now go straight into the image tool for edits or remixes."
              : "Use + to attach a file, launch research, or switch into image mode."}
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        style={{ display: "none" }}
        accept={FILE_INPUT_ACCEPT}
        onChange={handleFileChange}
      />
    </div>
  );
}

export default ChatInput;
