import React, { useMemo, useState } from "react";
import { MessageSquarePlus, Search, User, X } from "lucide-react";
import { motion } from "framer-motion";

type Conversation = {
  id: string;
  title: string;
  preview?: string;
};

interface SidebarProps {
  isOpen: boolean;
  userEmail: string;
  conversations: Conversation[];
  selectedConversationId: string | null;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConversation: (conversationId: string) => void;
}

function initialsFromEmail(email: string) {
  const cleaned = (email || "NOVA").replace(/[^a-zA-Z0-9]/g, "");
  return cleaned.slice(0, 2).toUpperCase() || "NV";
}

function initialsFromConversation(title: string) {
  return (title || "N")
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0] || "")
    .join("")
    .toUpperCase();
}

export default function Sidebar({
  isOpen,
  userEmail,
  conversations,
  selectedConversationId,
  onClose,
  onNewChat,
  onSelectConversation,
}: SidebarProps) {
  const [query, setQuery] = useState("");

  const filteredConversations = useMemo(() => {
    const search = query.trim().toLowerCase();
    if (!search) {
      return conversations;
    }

    return conversations.filter((conversation) =>
      `${conversation.title} ${conversation.preview || ""}`.toLowerCase().includes(search)
    );
  }, [conversations, query]);

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/50 transition-opacity duration-300 lg:hidden ${
          isOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[330px] flex-col border-r border-white/5 bg-[#111b21] transition-transform duration-300 lg:static lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="border-b border-white/5 px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#233138] text-white">
                <User className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold text-white">
                  {initialsFromEmail(userEmail)}
                </div>
                <div className="truncate text-[12px] text-[#8aa0ad]">{userEmail}</div>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-white/[0.05] text-[#b7c6cf] transition hover:bg-white/[0.08] lg:hidden"
              aria-label="Close sidebar"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#144d37] px-4 py-3 text-[14px] font-semibold text-white transition hover:bg-[#176344]"
          >
            <MessageSquarePlus className="h-4 w-4" />
            <span>New chat</span>
          </button>

          <div className="relative mt-4">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6f8692]" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search or start new chat"
              className="w-full rounded-full bg-white/[0.06] py-3 pl-11 pr-4 text-[13px] text-white outline-none placeholder:text-[#6f8692] focus:ring-1 focus:ring-white/15"
            />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {filteredConversations.length ? (
            filteredConversations.map((conversation, index) => {
              const isSelected = selectedConversationId === conversation.id;

              return (
                <motion.button
                  key={conversation.id}
                  type="button"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, delay: index * 0.02 }}
                  onClick={() => {
                    onSelectConversation(conversation.id);
                    onClose();
                  }}
                  className={`flex w-full items-center gap-3 border-b border-white/[0.04] px-4 py-3 text-left transition ${
                    isSelected ? "bg-white/[0.08]" : "hover:bg-white/[0.05]"
                  }`}
                >
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#233138] text-[13px] font-semibold text-[#dce6ea]">
                    {initialsFromConversation(conversation.title)}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] font-medium text-white">
                      {conversation.title}
                    </div>
                    <div className="mt-1 truncate text-[12px] text-[#8aa0ad]">
                      {conversation.preview || "No messages yet"}
                    </div>
                  </div>
                </motion.button>
              );
            })
          ) : (
            <div className="px-4 py-6 text-[13px] text-[#8aa0ad]">
              No matching conversations yet.
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
