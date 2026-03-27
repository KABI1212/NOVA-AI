export const CHAT_COMPOSER_PRESETS = [
  {
    id: "create_image",
    emoji: "âœ¨",
    label: "Create image",
    description: "Generate visuals or remix an attached photo",
    forceMode: "image",
    promptPrefix:
      "[Image mode: create a clear, polished image response that follows the user's visual request closely.]",
    placeholder: "Describe the image you want, or attach a photo to remix",
  },
  {
    id: "thinking",
    emoji: "ðŸ§ ",
    label: "Thinking",
    description: "Take a little more time and reason carefully",
    forceMode: null,
    promptPrefix:
      "[Thinking mode: reason carefully, check assumptions, and explain the answer clearly without unnecessary filler.]",
    placeholder: "Ask a harder question and NOVA will think longer",
  },
  {
    id: "deep_research",
    emoji: "ðŸ”Ž",
    label: "Deep research",
    description: "Search widely, compare sources, and cite clearly",
    forceMode: "search",
    promptPrefix:
      "[Deep research mode: use recent and trustworthy sources, compare findings, include concrete dates when relevant, and return a structured answer with citations or links.]",
    placeholder: "Ask for a sourced report, market brief, or current overview",
  },
  {
    id: "shopping_research",
    emoji: "ðŸ›ï¸",
    label: "Shopping research",
    description: "Compare products, features, and tradeoffs",
    forceMode: "search",
    promptPrefix:
      "[Shopping research mode: compare options by price, features, strengths, weaknesses, and best-fit recommendations. Use recent information and call out tradeoffs clearly.]",
    placeholder: "Ask for the best options by budget, features, or use case",
  },
];

export const DEFAULT_CHAT_PLACEHOLDER = "Ask anything";

export const CHAT_COMPOSER_MENU = [
  {
    id: "attach",
    emoji: "ðŸ“Ž",
    label: "Add photos & files",
    description: "Upload documents now, or attach a photo to remix",
  },
  {
    id: "create_image",
    emoji: "âœ¨",
    label: "Create image",
    description: "Generate original images or edit an uploaded photo",
  },
  {
    id: "thinking",
    emoji: "ðŸ§ ",
    label: "Thinking",
    description: "Slow down a bit for tougher questions",
  },
  {
    id: "deep_research",
    emoji: "ðŸ”Ž",
    label: "Deep research",
    description: "Run a broader, citation-friendly web search",
  },
  {
    id: "shopping_research",
    emoji: "ðŸ›ï¸",
    label: "Shopping research",
    description: "Find best buys, compare specs, and rank choices",
  },
  {
    id: "more",
    emoji: "âž•",
    label: "More",
    description: "Open extra tools and quick settings",
  },
];

export const QUICK_START_CHIPS = [
  { label: "ðŸ¤– Compare top AIs", text: "Compare ChatGPT, Claude, Gemini, and DeepSeek for real work." },
  { label: "ðŸ§  Best Claude features", text: "What are the strongest Claude features right now?" },
  { label: "ðŸ“„ Summarize a document", text: "Summarize this document in simple language and highlight the key points." },
  { label: "ðŸ›ï¸ Best laptop under $1000", text: "Find the best laptops under $1000 and compare them by value." },
  { label: "ðŸŽ¨ Create a hero image", text: "Create a cinematic hero image idea for NOVA AI." },
];
