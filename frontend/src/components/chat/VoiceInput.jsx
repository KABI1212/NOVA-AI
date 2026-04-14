import { useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2, Mic, Square, X } from "lucide-react";

import { fetchApi } from "../../services/api";
import { useAuthStore } from "../../utils/store";

const RECORDING_LIMIT_MS = 60000;

export default function VoiceInput({ onTranscript, disabled, compact = false }) {
  const [state, setState] = useState("idle"); // idle | recording | processing
  const [error, setError] = useState(null);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);
  const timerRef = useRef(null);
  const { token } = useAuthStore();

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      if (mediaRecorder.current?.state === "recording") {
        mediaRecorder.current.stop();
      }
    };
  }, []);

  const transcribeAudio = async () => {
    try {
      const mimeType = audioChunks.current[0]?.type || "audio/webm";
      const audioBlob = new Blob(audioChunks.current, { type: mimeType });

      if (audioBlob.size < 1000) {
        setError("Recording too short. Try again.");
        setState("idle");
        return;
      }

      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");

      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetchApi("/voice/transcribe", {
        method: "POST",
        headers,
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Transcription failed.");
      }

      const data = await res.json();
      const transcript = data.transcript?.trim();

      if (transcript) {
        onTranscript?.(transcript);
      } else {
        setError("Could not understand audio. Try again.");
      }
    } catch (err) {
      setError(err?.message || "Transcription failed.");
    } finally {
      setState("idle");
    }
  };

  const stopRecording = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    if (mediaRecorder.current?.state === "recording") {
      mediaRecorder.current.stop();
      setState("processing");
    }
  };

  const startRecording = async () => {
    setError(null);
    audioChunks.current = [];

    if (typeof MediaRecorder === "undefined") {
      setError("Your browser does not support audio recording.");
      return;
    }

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Microphone not supported.");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/ogg";

      mediaRecorder.current = new MediaRecorder(stream, { mimeType });

      mediaRecorder.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.current.push(event.data);
        }
      };

      mediaRecorder.current.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        await transcribeAudio();
      };

      mediaRecorder.current.start(250);
      setState("recording");
      timerRef.current = setTimeout(stopRecording, RECORDING_LIMIT_MS);
    } catch (err) {
      if (err?.name === "NotAllowedError") {
        setError("Microphone permission denied.");
      } else {
        setError("Could not access microphone.");
      }
      setState("idle");
    }
  };

  const handleClick = () => {
    if (state === "idle") {
      startRecording();
      return;
    }

    if (state === "recording") {
      stopRecording();
    }
  };

  const title =
    state === "idle"
      ? compact
        ? "Record voice input"
        : "Click to record"
      : state === "recording"
        ? compact
          ? "Stop recording"
          : "Click to stop"
        : "Transcribing...";

  const buttonClassName = compact
    ? `input-btn ghost${state === "recording" ? " listening" : ""}`
    : `w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200 text-base ${
        state === "idle"
          ? "bg-gray-700 hover:bg-gray-600 text-gray-300"
          : state === "recording"
            ? "bg-red-500 hover:bg-red-400 text-white animate-pulse shadow-lg shadow-red-500/40"
            : "bg-yellow-600 text-white cursor-wait"
      } disabled:opacity-40 disabled:cursor-not-allowed`;

  return (
    <div className="relative flex flex-col items-center">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || state === "processing"}
        title={title}
        aria-label={title}
        className={buttonClassName}
      >
        {state === "idle" ? <Mic className="h-4 w-4" /> : null}
        {state === "recording" ? <Square className="h-4 w-4" /> : null}
        {state === "processing" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      </button>

      {error ? (
        <div className="absolute bottom-16 left-1/2 z-20 flex items-center gap-2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-red-900 px-3 py-1.5 text-xs text-red-200 shadow-lg">
          <AlertCircle className="h-3.5 w-3.5" />
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-red-300 hover:text-red-100"
            aria-label="Dismiss voice error"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : null}
    </div>
  );
}
