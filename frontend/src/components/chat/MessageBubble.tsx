import React, { useEffect, useState } from "react";
import { Check, Copy, RotateCcw, Volume2, VolumeX } from "lucide-react";
import { motion } from "framer-motion";

import BrandLogo from "./BrandLogo";
import MarkdownAnswer from "../common/MarkdownAnswer";

type Message = {
  id: string;
  role: string;
  content: string;
  images?: string[];
  pending?: boolean;
  streaming?: boolean;
  error?: string | null;
};

interface MessageBubbleProps {
  message: Message;
  canRegenerate?: boolean;
  isSpeaking?: boolean;
  speechSupported?: boolean;
  onRegenerate?: () => void;
  onSpeak?: (message: Message) => void;
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1.5">
      {[0, 1, 2].map((dot) => (
        <motion.span
          key={dot}
          animate={{ opacity: [0.35, 1, 0.35], y: [0, -2, 0] }}
          transition={{
            duration: 0.9,
            repeat: Number.POSITIVE_INFINITY,
            delay: dot * 0.14,
            ease: "easeInOut",
          }}
          className="h-2 w-2 rounded-full bg-[#c8d6dd]"
        />
      ))}
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  return <MarkdownAnswer content={content} />;
}

async function copyTextToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = value;
  textArea.style.position = "fixed";
  textArea.style.left = "-9999px";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  document.execCommand("copy");
  document.body.removeChild(textArea);
}

export default function MessageBubble({
  message,
  canRegenerate = false,
  isSpeaking = false,
  speechSupported = false,
  onRegenerate,
  onSpeak,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const isGenerating = !isUser && (message.pending || message.streaming);

  useEffect(() => {
    if (!copied) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setCopied(false), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [copied]);

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
        className="flex w-full justify-end"
      >
        <div className="max-w-[84%] sm:max-w-[72%]">
          <div className="relative rounded-[18px] rounded-br-[6px] bg-[#144d37] px-4 py-3 text-[14px] leading-6 text-white before:absolute before:-right-1 before:top-3 before:h-3 before:w-3 before:rotate-45 before:bg-[#144d37] before:content-['']">
            <div className="relative whitespace-pre-wrap">{message.content}</div>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="flex w-full justify-start"
    >
      <div className="flex w-full max-w-[920px] items-start gap-2.5">
        <div className="shrink-0 pt-0.5">
          <BrandLogo size={34} animated={isGenerating} />
        </div>

        <div className="max-w-[86%] sm:max-w-[74%]">
          <div
            className={`relative rounded-[18px] rounded-bl-[6px] px-4 py-3 before:absolute before:-left-1 before:top-3 before:h-3 before:w-3 before:rotate-45 before:content-[''] ${
              message.error
                ? "bg-[#4b2429] before:bg-[#4b2429]"
                : "bg-[#202c33] before:bg-[#202c33]"
            }`}
          >
            {message.content ? <MarkdownContent content={message.content} /> : null}

            {Array.isArray(message.images) && message.images.length ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {message.images.map((image, index) => (
                  <img
                    key={`${message.id}-${index}`}
                    src={image}
                    alt={`Generated result ${index + 1}`}
                    className="w-full rounded-2xl"
                  />
                ))}
              </div>
            ) : null}

            {isGenerating ? (
              <div className="mt-2 flex items-center gap-2 text-[12px] text-[#c6d4db]">
                <TypingDots />
                <span>{message.content ? "Generating" : "Thinking"}</span>
              </div>
            ) : null}
          </div>

          {!isGenerating && message.content ? (
            <div className="mt-2 flex flex-wrap items-center gap-2 pl-1">
              <button
                type="button"
                onClick={async () => {
                  try {
                    await copyTextToClipboard(message.content);
                    setCopied(true);
                  } catch {
                    setCopied(false);
                  }
                }}
                className="flex items-center gap-1.5 rounded-full bg-white/[0.06] px-3 py-1.5 text-[12px] text-[#d2dde4] transition hover:bg-white/[0.1]"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-[#25d366]" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>

              <button
                type="button"
                onClick={() => onSpeak?.(message)}
                disabled={!speechSupported}
                className="flex items-center gap-1.5 rounded-full bg-white/[0.06] px-3 py-1.5 text-[12px] text-[#d2dde4] transition hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSpeaking ? <VolumeX className="h-3.5 w-3.5 text-[#25d366]" /> : <Volume2 className="h-3.5 w-3.5" />}
                <span>{isSpeaking ? "Stop" : "Speak"}</span>
              </button>

              <button
                type="button"
                onClick={onRegenerate}
                disabled={!canRegenerate || !onRegenerate}
                className="flex items-center gap-1.5 rounded-full bg-white/[0.06] px-3 py-1.5 text-[12px] text-[#d2dde4] transition hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-45"
                title={canRegenerate ? "Regenerate response" : "Only the latest AI response can be regenerated"}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Regenerate</span>
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
}
