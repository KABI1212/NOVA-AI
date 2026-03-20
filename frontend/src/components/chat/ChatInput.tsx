import React, { useEffect, useRef, useState } from "react";
import { ArrowUp, Image, Mic, Search } from "lucide-react";
import { motion } from "framer-motion";
import TextareaAutosize from "react-textarea-autosize";

type ToolMode = "search" | "image" | null;

interface ChatInputProps {
  value: string;
  status: string;
  disabled: boolean;
  toolMode: ToolMode;
  onChange: (value: string) => void;
  onSend: (payload: { text: string; file: File | null }) => void;
  onToolModeChange: (mode: ToolMode) => void;
}

const toolButtons = [
  { key: "search" as const, label: "Search", icon: Search },
  { key: "image" as const, label: "Image", icon: Image },
];

export default function ChatInput({
  value,
  status,
  disabled,
  toolMode,
  onChange,
  onSend,
  onToolModeChange,
}: ChatInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const speechPrefixRef = useRef("");

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setSpeechSupported(false);
      recognitionRef.current = null;
      return undefined;
    }

    setSpeechSupported(true);
    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let transcript = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index][0]?.transcript || "";
      }

      const prefix = speechPrefixRef.current.trim();
      const fragment = transcript.trim();
      onChange([prefix, fragment].filter(Boolean).join(" ").trim());
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognitionRef.current = recognition;

    return () => {
      recognition.onresult = null;
      recognition.onend = null;
      recognition.onerror = null;
      try {
        recognition.stop();
      } catch {
        // recognition may not have started
      }
      recognitionRef.current = null;
    };
  }, [onChange]);

  useEffect(() => {
    if (!disabled || !isListening || !recognitionRef.current) {
      return;
    }

    recognitionRef.current.stop();
    setIsListening(false);
  }, [disabled, isListening]);

  const handleSend = () => {
    if (disabled || !value.trim()) {
      return;
    }

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }

    onSend({
      text: value.trim(),
      file: null,
    });

    onChange("");
  };

  const handleVoiceToggle = () => {
    if (!speechSupported || !recognitionRef.current || disabled) {
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
      return;
    }

    speechPrefixRef.current = value.trim();
    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch {
      setIsListening(false);
    }
  };

  const helperText = isListening
    ? "Listening..."
    : status || "Enter to send. Shift + Enter for a new line.";

  return (
    <div className="rounded-[26px] border border-white/8 bg-[#202c33]/92 p-3 shadow-[0_12px_32px_rgba(0,0,0,0.22)] backdrop-blur-xl">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {toolButtons.map((button) => {
          const Icon = button.icon;
          const isActive = toolMode === button.key;

          return (
            <motion.button
              key={button.key}
              type="button"
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => onToolModeChange(isActive ? null : button.key)}
              className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-[12px] transition ${
                isActive
                  ? "bg-[#144d37] text-white"
                  : "bg-white/[0.06] text-[#cad6dd] hover:bg-white/[0.1]"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{button.label}</span>
            </motion.button>
          );
        })}
      </div>

      <div className="flex items-end gap-2 rounded-[22px] bg-[#111b21] px-3 py-2.5">
        <div className="flex-1">
          <TextareaAutosize
            minRows={1}
            maxRows={6}
            value={value}
            disabled={disabled}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type a message"
            className="w-full resize-none bg-transparent px-1 py-1.5 text-[15px] leading-6 text-white outline-none placeholder:text-[#748894] disabled:cursor-not-allowed"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleVoiceToggle}
            disabled={!speechSupported || disabled}
            className={`flex h-11 w-11 items-center justify-center rounded-full transition ${
              isListening
                ? "bg-[#144d37] text-white"
                : "bg-white/[0.06] text-[#d9e4ea] hover:bg-white/[0.1]"
            } disabled:cursor-not-allowed disabled:opacity-50`}
            aria-label={isListening ? "Stop voice input" : "Start voice input"}
          >
            <Mic className="h-4 w-4" />
          </button>

          <motion.button
            type="button"
            whileTap={{ scale: 0.97 }}
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            className="flex h-11 w-11 items-center justify-center rounded-full bg-[#25d366] text-[#08131a] transition hover:bg-[#32db72] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Send message"
          >
            <ArrowUp className="h-4 w-4" />
          </motion.button>
        </div>
      </div>

      <div className="mt-2 flex flex-col gap-1 px-1 text-[11px] text-[#8da2ae] sm:flex-row sm:items-center sm:justify-between">
        <span>{helperText}</span>
        <span>
          {toolMode === "search" ? "Search mode on" : toolMode === "image" ? "Image mode on" : "Chat mode"}
        </span>
      </div>
    </div>
  );
}
