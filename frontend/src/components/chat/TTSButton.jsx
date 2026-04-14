// @ts-nocheck
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, Volume2, VolumeX } from "lucide-react";
import toast from "react-hot-toast";

import { fetchApi } from "../../services/api";
import {
  speechSupported as browserSpeechSupported,
  speakText,
  stopSpeechPlayback,
} from "../../utils/speech";
import { useAuthStore, useVoiceStore } from "../../utils/store";
import { TTS_VOICE_OPTIONS } from "../../utils/voices";

export default function TTSButton({ text }) {
  const [playing, setPlaying] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [playbackMode, setPlaybackMode] = useState(null);
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
    stopSpeechPlayback();
    setPlaybackMode(null);
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

      const res = await fetchApi("/voice/speak", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text, voice: selectedVoice, speed: 1.0 }),
      });

      if (!res.ok) {
        const errorPayload = await res.json().catch(() => null);
        throw new Error(errorPayload?.detail || errorPayload?.message || "TTS failed");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      objectUrlRef.current = url;
      audioRef.current = audio;
      setPlaybackMode("server");

      audio.onended = stopAudio;
      audio.onerror = stopAudio;

      await audio.play();
    } catch (error) {
      stopAudio();

      if (browserSpeechSupported()) {
        const started = speakText(text, {
          onStart: () => {
            setPlaybackMode("browser");
            setPlaying(true);
          },
          onEnd: stopAudio,
          onError: stopAudio,
        });

        if (started) {
          return;
        }
      }

      stopAudio();
      toast.error(error?.message || "Could not play this voice response right now.");
    }
  };

  const selectedVoiceLabel =
    TTS_VOICE_OPTIONS.find((option) => option.id === voice)?.label || "selected voice";

  return (
    <div className="relative inline-flex items-center">
      <button
        onClick={() => speak()}
        title={
          playing
            ? playbackMode === "browser"
              ? "Stop device voice"
              : "Stop"
            : `Read aloud with ${selectedVoiceLabel}`
        }
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
