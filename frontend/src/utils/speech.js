import { useVoiceStore } from "./store";
import { resolvePreferredSpeechVoice } from "./voices";

export const speechSupported = () =>
  typeof window !== "undefined" && Boolean(window.speechSynthesis);

export const speechTextFromMarkdown = (value) =>
  String(value || "")
    .replace(/```[\s\S]*?```/g, " Code block omitted. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[#>*_~|-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

export const stopSpeechPlayback = () => {
  if (!speechSupported()) {
    return;
  }

  window.speechSynthesis.cancel();
};

export const speakText = (value, options = {}) => {
  if (!speechSupported()) {
    return false;
  }

  const spokenText = speechTextFromMarkdown(value);
  if (!spokenText) {
    return false;
  }

  const { onStart, onEnd, onError, voiceId } = options;
  const synth = window.speechSynthesis;
  synth.cancel();

  const utterance = new SpeechSynthesisUtterance(spokenText);
  utterance.rate = 1;
  utterance.pitch = 1;

  const voices = synth.getVoices?.() || [];
  const selectedVoiceId = voiceId || useVoiceStore.getState().browserVoice;
  const preferredVoice = resolvePreferredSpeechVoice(selectedVoiceId, voices);

  if (preferredVoice) {
    utterance.voice = preferredVoice;
  }

  utterance.onstart = () => {
    onStart?.();
  };

  utterance.onend = () => {
    onEnd?.();
  };

  utterance.onerror = () => {
    onError?.();
  };

  synth.speak(utterance);
  return true;
};
