import React, { useEffect, useRef, useState } from "react";
import { ChevronDown, Menu } from "lucide-react";
import { motion } from "framer-motion";

import BrandLogo from "./BrandLogo";

interface NavbarProps {
  model: string;
  models: string[];
  conversationTitle: string;
  isTyping: boolean;
  onModelChange: (model: string) => void;
  onToggleSidebar: () => void;
}

export default function Navbar({
  model,
  models,
  conversationTitle,
  isTyping,
  onModelChange,
  onToggleSidebar,
}: NavbarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (!dropdownRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  return (
    <header className="relative z-10 flex items-center justify-between border-b border-white/5 bg-[#202c33]/88 px-3 py-3 backdrop-blur-xl sm:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-white/[0.06] text-[#dbe5eb] transition hover:bg-white/[0.1] lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#111b21]">
          <BrandLogo size={30} animated={isTyping} />
        </div>

        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold text-white">{conversationTitle}</div>
          <div className="mt-0.5 flex items-center gap-2 text-[12px] text-[#97abb7]">
            <motion.span
              className={`h-2 w-2 rounded-full ${isTyping ? "bg-[#25d366]" : "bg-[#7a8e99]"}`}
              animate={isTyping ? { opacity: [0.4, 1, 0.4], scale: [0.9, 1.15, 0.9] } : { opacity: 1, scale: 1 }}
              transition={isTyping ? { duration: 1, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" } : { duration: 0.2 }}
            />
            <span>{isTyping ? "typing..." : "online"}</span>
          </div>
        </div>
      </div>

      <div className="relative ml-4" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setIsOpen((previous) => !previous)}
          className="flex items-center gap-2 rounded-full bg-white/[0.06] px-3 py-2 text-[12px] font-medium text-[#e1eaef] transition hover:bg-white/[0.1]"
        >
          <span className="hidden sm:inline">{model}</span>
          <span className="sm:hidden">Model</span>
          <ChevronDown className="h-3.5 w-3.5 text-[#a9bbc6]" />
        </button>

        {isOpen ? (
          <div className="absolute right-0 mt-2 w-48 rounded-2xl border border-white/10 bg-[#182229] p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.3)]">
            {models.map((option) => {
              const isSelected = option === model;

              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    onModelChange(option);
                    setIsOpen(false);
                  }}
                  className={`w-full rounded-[14px] px-3 py-2.5 text-left text-[13px] transition ${
                    isSelected ? "bg-[#233138] text-white" : "text-[#c9d6de] hover:bg-white/[0.05]"
                  }`}
                >
                  {option}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    </header>
  );
}
