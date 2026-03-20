import React from "react";
import { motion } from "framer-motion";

interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
}

export default function SuggestionChips({ suggestions, onSelect }: SuggestionChipsProps) {
  return (
    <div className="mt-6 flex flex-wrap justify-center gap-2.5">
      {suggestions.map((suggestion, index) => (
        <motion.button
          key={suggestion}
          type="button"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.03, duration: 0.28 }}
          whileHover={{ y: -2, scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          onClick={() => onSelect(suggestion)}
          className="rounded-full bg-[#202c33] px-4 py-2 text-[13px] text-[#dce5ea] transition hover:bg-[#233138] hover:text-white"
        >
          {suggestion}
        </motion.button>
      ))}
    </div>
  );
}
