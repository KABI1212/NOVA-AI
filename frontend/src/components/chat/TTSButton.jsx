// @ts-nocheck
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, Volume2, VolumeX } from "lucide-react";
import toast from "react-hot-toast";

import { useAuthStore, useVoiceStore } from "../../utils/store";
import { TTS_VOICE_OPTIONS } from "../../utils/voices";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function TTSButton({ text }) {
  const [playing, setPlaying] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const audioRef = useRef(null);
  const objectUrlRef = useRef(null);
  const { token } = useAuthStore();
  const voice = useVoiceStore((state) => state.ttsVoice);
  const setVoice = useVoiceStore((state) => state.setTtsVoice);

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setPlaying(false);
  }, []);

  useEffect(() => () => {
    stopAudio();
  }, [stopAudio]);

  const speak = async (selectedVoice = voice) => {
    if (!text?.trim()) {
      return;
    }

    const isToggle = selectedVoice === voice;
    if (playing && isToggle) {
      stopAudio();
      return;
    }

    if (playing) {
      stopAudio();
    }

    try {
      setPlaying(true);

      const res = await fetch(`${API_URL}/api/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text, voice: selectedVoice, speed: 1.0 }),
      });

      if (!res.ok) {
        throw new Error("TTS failed");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      objectUrlRef.current = url;
      audioRef.current = audio;

      audio.onended = stopAudio;
      audio.onerror = stopAudio;

      await audio.play();
    } catch {
      stopAudio();
      toast.error("Could not play this voice response right now.");
    }
  };

  const selectedVoiceLabel =
    TTS_VOICE_OPTIONS.find((option) => option.id === voice)?.label || "selected voice";

  return (
    <div className="relative inline-flex items-center">
      <button
        onClick={() => speak()}
        title={playing ? "Stop" : `Read aloud with ${selectedVoiceLabel}`}
        className={`rounded-lg p-1.5 text-xs transition-colors ${
          playing
            ? "bg-blue-500/10 text-blue-400"
            : "text-gray-500 hover:bg-gray-700 hover:text-gray-300"
        }`}
      >
        {playing ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
      </button>

      <button
        onClick={() => setShowMenu((current) => !current)}
        className="p-1 text-xs text-gray-600 hover:text-gray-400"
        title="Choose voice"
      >
        <ChevronDown className="h-3.5 w-3.5" />
      </button>

      {showMenu ? (
        <div className="absolute bottom-8 left-0 z-50 min-w-[180px] overflow-hidden rounded-xl border border-gray-700 bg-gray-900 shadow-xl">
          <div className="border-b border-gray-800 px-3 py-2 text-xs text-gray-500">Voice</div>
          {TTS_VOICE_OPTIONS.map((option) => (
            <button
              key={option.id}
              onClick={() => {
                setVoice(option.id);
                setShowMenu(false);
              }}
              className={`w-full px-4 py-2 text-left text-sm transition-colors hover:bg-gray-800 ${
                voice === option.id ? "text-blue-400" : "text-gray-300"
              }`}
            >
              {voice === option.id ? "* " : "  "}
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
