import React, { useEffect, useRef, useState } from "react";

function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
  generatePromptImage = false,
  generateAnswerImage = false,
  onTogglePromptImage,
  onToggleAnswerImage,
}) {
  const [attachedFile, setAttachedFile] = useState(null);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [heardText, setHeardText] = useState("");
  const [showVoiceDraft, setShowVoiceDraft] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);
  const valueRef = useRef(value);
  const attachedFileRef = useRef(attachedFile);
  const disabledRef = useRef(disabled);
  const onChangeRef = useRef(onChange);
  const onSendRef = useRef(onSend);
  const voiceBaseValueRef = useRef("");
  const capturedSpeechRef = useRef("");
  const previewSpeechRef = useRef("");

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

  const resetVoiceDraft = () => {
    voiceBaseValueRef.current = "";
    capturedSpeechRef.current = "";
    previewSpeechRef.current = "";
    setHeardText("");
    setShowVoiceDraft(false);
  };

  const dispatchMessage = (rawValue) => {
    if (disabledRef.current) {
      return;
    }

    const trimmed = String(rawValue || "").trim();
    const currentFile = attachedFileRef.current;
    if (!trimmed && !currentFile) {
      return;
    }

    const payload = currentFile
      ? `${trimmed}${trimmed ? " + " : ""}[File: ${currentFile.name}]`
      : trimmed;

    onSendRef.current?.(payload);
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

  const isSendDisabled = disabled || (!value.trim() && !attachedFile);
  const voiceButtonTitle = speechSupported
    ? isListening
      ? "Stop voice input"
      : "Start voice input"
    : "Voice input is not supported in this browser";
  const showVoicePanel = isListening || showVoiceDraft;

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

      <div className="input-tools">
        <button
          className={`input-chip${generatePromptImage ? " on" : ""}`}
          type="button"
          disabled={disabled}
          onClick={onTogglePromptImage}
        >
          Prompt image
        </button>
        <button
          className={`input-chip${generateAnswerImage ? " on" : ""}`}
          type="button"
          disabled={disabled}
          onClick={onToggleAnswerImage}
        >
          Answer image
        </button>
        <div className="input-tools-hint">Generated visuals appear inline in the chat.</div>
      </div>

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
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
        />

        <div className="input-actions">
          <button className="input-model" type="button">
            Nova Fast
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
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
