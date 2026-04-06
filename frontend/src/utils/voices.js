export const BROWSER_VOICE_AUTO = "auto";
export const DEFAULT_TTS_VOICE = "nova";

export const TTS_VOICE_OPTIONS = [
  { id: "nova", label: "Nova" },
  { id: "alloy", label: "Alloy" },
  { id: "echo", label: "Echo" },
  { id: "fable", label: "Fable" },
  { id: "onyx", label: "Onyx" },
  { id: "shimmer", label: "Shimmer" },
];

export const getSpeechSynthesisVoices = () => {
  if (typeof window === "undefined" || !window.speechSynthesis?.getVoices) {
    return [];
  }

  return window.speechSynthesis.getVoices() || [];
};

export const getSpeechVoiceOptions = () => {
  const voices = getSpeechSynthesisVoices();
  const seen = new Set();
  const options = [
    {
      id: BROWSER_VOICE_AUTO,
      label: "Auto (device default)",
    },
  ];

  voices
    .slice()
    .sort((first, second) => {
      if (first.default && !second.default) {
        return -1;
      }
      if (!first.default && second.default) {
        return 1;
      }
      return String(first.name || "").localeCompare(String(second.name || ""));
    })
    .forEach((voice) => {
      const name = String(voice?.name || "").trim();
      if (!name || seen.has(name)) {
        return;
      }

      seen.add(name);
      const parts = [name];
      if (voice?.lang) {
        parts.push(voice.lang);
      }
      if (voice?.default) {
        parts.push("default");
      }

      options.push({
        id: name,
        label: parts.join(" | "),
      });
    });

  return options;
};

export const resolvePreferredSpeechVoice = (selectedVoiceId, voices = getSpeechSynthesisVoices()) => {
  const selected = String(selectedVoiceId || "").trim();
  if (selected && selected !== BROWSER_VOICE_AUTO) {
    const explicitMatch = voices.find((voice) => String(voice?.name || "").trim() === selected);
    if (explicitMatch) {
      return explicitMatch;
    }
  }

  return (
    voices.find((voice) => voice?.default) ||
    voices.find((voice) => voice?.lang?.toLowerCase().startsWith("en-in")) ||
    voices.find((voice) => voice?.lang?.toLowerCase().startsWith("en")) ||
    voices[0] ||
    null
  );
};
