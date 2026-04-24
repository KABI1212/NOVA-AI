// @ts-nocheck
import { useRef, useState } from 'react';
import { useAuthStore } from '../../utils/store';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const VOICES = [
  { id: 'nova', label: 'Nova (default)' },
  { id: 'alloy', label: 'Alloy' },
  { id: 'echo', label: 'Echo' },
  { id: 'fable', label: 'Fable' },
  { id: 'onyx', label: 'Onyx' },
  { id: 'shimmer', label: 'Shimmer' },
];

export default function TTSButton({ text }) {
  const [playing, setPlaying] = useState(false);
  const [voice, setVoice] = useState('nova');
  const [showMenu, setShowMenu] = useState(false);
  const audioRef = useRef(null);
  const { token } = useAuthStore();

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlaying(false);
  };

  const speak = async (selectedVoice = voice) => {
    if (!text?.trim()) return;
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
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text, voice: selectedVoice, speed: 1.0 }),
      });

      if (!res.ok) throw new Error('TTS failed');

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        setPlaying(false);
        URL.revokeObjectURL(url);
      };

      audio.play();
    } catch {
      setPlaying(false);
    }
  };

  return (
    <div className="relative inline-flex items-center">
      <button
        onClick={() => speak()}
        title={playing ? 'Stop' : 'Read aloud'}
        className={`p-1.5 rounded-lg text-xs transition-colors ${
          playing
            ? 'text-blue-400 bg-blue-500/10'
            : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700'
        }`}
      >
        {playing ? '⏹️' : '🔊'}
      </button>

      <button
        onClick={() => setShowMenu(!showMenu)}
        className="p-1 text-gray-600 hover:text-gray-400 text-xs"
        title="Choose voice"
      >
        ▾
      </button>

      {showMenu && (
        <div className="absolute bottom-8 left-0 bg-gray-900 border border-gray-700 rounded-xl shadow-xl z-50 min-w-[160px] overflow-hidden">
          <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-800">
            Voice
          </div>
          {VOICES.map((option) => (
            <button
              key={option.id}
              onClick={() => {
                setVoice(option.id);
                setShowMenu(false);
                speak(option.id);
              }}
              className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-800 transition-colors ${
                voice === option.id ? 'text-blue-400' : 'text-gray-300'
              }`}
            >
              {voice === option.id ? '✓ ' : '  '}
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
