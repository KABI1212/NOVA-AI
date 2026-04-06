// @ts-nocheck
import { motion } from "framer-motion";
import { Bot, User, Copy, Check } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import TTSButton from "./TTSButton";
import MarkdownAnswer from "../common/MarkdownAnswer";

function TypingCursor() {
  return (
    <span className="inline-block w-2 h-4 bg-blue-400 ml-0.5 animate-pulse rounded-sm"/>
  );
}

function MessageBubble({
  message,
  isTyping,
  isStreaming = false,
  showTts = true,
}) {

  const [copiedMessage, setCopiedMessage] = useState(false);

  const copyMessageToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessage(true);
      toast.success("Copied to clipboard!");
      setTimeout(() => setCopiedMessage(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  };

  if (isTyping) {
    return (
      <motion.div
        initial={{ opacity:0, y:10 }}
        animate={{ opacity:1, y:0 }}
        className="flex items-start gap-4 p-4"
      >
        <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center">
          <Bot className="w-5 h-5 text-white"/>
        </div>

        <div className="flex gap-1 mt-2">
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"/>
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"/>
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"/>
        </div>
      </motion.div>
    );
  }

  const isUser = message?.role === "user";

  return (
    <motion.div
      initial={{ opacity:0, y:10 }}
      animate={{ opacity:1, y:0 }}
      className={`flex items-start p-4 ${isUser ? "justify-end" : "justify-start"}`}
    >

      <div className={`flex items-start gap-4 max-w-4xl w-full ${isUser ? "flex-row-reverse" : ""}`}>

        <div className={`w-8 h-8 rounded-full flex items-center justify-center
          ${isUser ? "bg-gray-300 dark:bg-gray-600" : "bg-primary-600"}`}
        >
          {isUser
            ? <User className="w-5 h-5 text-gray-700 dark:text-gray-300"/>
            : <Bot className="w-5 h-5 text-white"/>}
        </div>

        <div className="flex-1 min-w-0">

          <div className={`rounded-2xl px-4 py-3
            ${isUser
              ? "bg-primary-600 text-white"
              : "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
            }`}
          >

            {isUser ? (
              <p className="whitespace-pre-wrap text-sm">{message.content}</p>
            ) : (
              <div className="max-w-none">
                <MarkdownAnswer content={message.content} />
                {isStreaming && <TypingCursor/>}

                {(message.images || (message.meta && message.meta.images)) && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    {(message.images || message.meta.images).map((img, idx) => (
                      <img
                        key={idx}
                        src={img}
                        alt={`Generated ${idx}`}
                        className="w-full max-w-[300px] rounded-lg border border-gray-700 shadow-lg"
                        loading="lazy"
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {!isUser && showTts && message.content && !isStreaming && (
              <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-700/50">
                <TTSButton text={message.content}/>
                <span className="text-xs text-gray-600">Read aloud</span>
              </div>
            )}

          </div>

          {!isUser && (
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
              <button
                onClick={() => copyMessageToClipboard(message.content)}
                className="flex items-center gap-1"
              >
                {copiedMessage
                  ? <Check className="w-3 h-3"/>
                  : <Copy className="w-3 h-3"/>}
                {copiedMessage ? "Copied!" : "Copy"}
              </button>
            </div>
          )}

        </div>
      </div>
    </motion.div>
  );
}

export default MessageBubble;
