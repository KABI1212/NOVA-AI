import React, { useEffect, useMemo, useRef } from "react";

import BrandLogo from "./BrandLogo";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import SuggestionChips from "./SuggestionChips";

type ToolMode = "search" | "image" | null;

type Message = {
  id: string;
  role: string;
  content: string;
  images?: string[];
  pending?: boolean;
  streaming?: boolean;
  error?: string | null;
};

type Conversation = {
  id: string;
  title: string;
  preview?: string;
};

interface ChatLayoutProps {
  userEmail: string;
  messages: Message[];
  conversations: Conversation[];
  selectedConversationId: string | null;
  currentConversationTitle: string;
  speakingMessageId: string | null;
  speechSupported: boolean;
  input: string;
  status: string;
  isSidebarOpen: boolean;
  isTyping: boolean;
  disabled: boolean;
  model: string;
  models: string[];
  toolMode: ToolMode;
  onToggleSidebar: () => void;
  onCloseSidebar: () => void;
  onNewChat: () => void;
  onSelectConversation: (conversationId: string) => void;
  onModelChange: (model: string) => void;
  onInputChange: (value: string) => void;
  onSend: (payload: { text: string; file: File | null }) => void;
  onRegenerate: () => void;
  onSpeakMessage: (message: Message) => void;
  onToolModeChange: (mode: ToolMode) => void;
  onSuggestionSelect: (suggestion: string) => void;
}

const suggestions = [
  "Summarize this topic",
  "Help me write a reply",
  "Explain it simply",
  "Research this for me",
  "Give me code help",
  "Brainstorm ideas",
];

export default function ChatLayout({
  userEmail,
  messages,
  conversations,
  selectedConversationId,
  currentConversationTitle,
  speakingMessageId,
  speechSupported,
  input,
  status,
  isSidebarOpen,
  isTyping,
  disabled,
  model,
  models,
  toolMode,
  onToggleSidebar,
  onCloseSidebar,
  onNewChat,
  onSelectConversation,
  onModelChange,
  onInputChange,
  onSend,
  onRegenerate,
  onSpeakMessage,
  onToolModeChange,
  onSuggestionSelect,
}: ChatLayoutProps) {
  const scrollAreaRef = useRef<HTMLDivElement | null>(null);
  const hasMessages = messages.length > 0;

  const lastAssistantId = useMemo(
    () => [...messages].reverse().find((message) => message.role !== "user")?.id || null,
    [messages]
  );

  const isStreaming = useMemo(
    () => messages.some((message) => message.streaming),
    [messages]
  );

  useEffect(() => {
    if (!scrollAreaRef.current || !hasMessages) {
      return undefined;
    }

    const frame = window.requestAnimationFrame(() => {
      scrollAreaRef.current?.scrollTo({
        top: scrollAreaRef.current.scrollHeight,
        behavior: isStreaming ? "auto" : "smooth",
      });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [hasMessages, isStreaming, isTyping, messages]);

  return (
    <div className="min-h-screen bg-[#08131a] font-sans text-white">
      <div className="flex min-h-screen">
        <Sidebar
          isOpen={isSidebarOpen}
          userEmail={userEmail}
          conversations={conversations}
          selectedConversationId={selectedConversationId}
          onClose={onCloseSidebar}
          onNewChat={onNewChat}
          onSelectConversation={onSelectConversation}
        />

        <div className="relative flex min-h-screen min-w-0 flex-1 flex-col bg-[#0b141a]">
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(6,18,24,0.96),rgba(11,20,26,0.98))]" />
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.06]"
            style={{
              backgroundImage:
                "radial-gradient(circle at center, rgba(255,255,255,0.9) 1px, transparent 1.5px)",
              backgroundSize: "28px 28px",
            }}
          />

          <div className="relative flex min-h-screen flex-col">
            <Navbar
              model={model}
              models={models}
              conversationTitle={currentConversationTitle}
              isTyping={isTyping}
              onModelChange={onModelChange}
              onToggleSidebar={onToggleSidebar}
            />

            <div className="relative flex min-h-0 flex-1 flex-col">
              {hasMessages ? (
                <div ref={scrollAreaRef} className="min-h-0 flex-1 overflow-y-auto px-3 pb-40 pt-4 sm:px-6">
                  <div className="mx-auto flex w-full max-w-[980px] flex-col gap-4">
                    {messages.map((message) => (
                      <MessageBubble
                        key={message.id}
                        message={message}
                        canRegenerate={message.id === lastAssistantId}
                        isSpeaking={speakingMessageId === message.id}
                        speechSupported={speechSupported}
                        onRegenerate={onRegenerate}
                        onSpeak={onSpeakMessage}
                      />
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex flex-1 items-center justify-center px-4 py-8 sm:px-6">
                  <div className="w-full max-w-[680px] text-center">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#1f2c34] shadow-[0_8px_24px_rgba(0,0,0,0.2)]">
                      <BrandLogo size={38} />
                    </div>
                    <h1 className="mt-5 font-display text-3xl font-semibold text-white sm:text-4xl">
                      Start a chat with NOVA AI
                    </h1>
                    <p className="mx-auto mt-3 max-w-[520px] text-[14px] leading-7 text-[#93a8b4]">
                      A more natural, messenger-style AI workspace with live responses, clean bubbles, and quick reply actions.
                    </p>
                    <SuggestionChips suggestions={suggestions} onSelect={onSuggestionSelect} />
                  </div>
                </div>
              )}

              <div className="sticky bottom-0 z-20 px-3 pb-3 pt-5 sm:px-6 sm:pb-5">
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[#0b141a] via-[#0b141a]/92 to-transparent" />
                <div className="relative mx-auto w-full max-w-[980px]">
                  <ChatInput
                    value={input}
                    status={status}
                    disabled={disabled}
                    toolMode={toolMode}
                    onChange={onInputChange}
                    onSend={onSend}
                    onToolModeChange={onToolModeChange}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
