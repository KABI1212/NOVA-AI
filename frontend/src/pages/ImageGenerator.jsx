// @ts-nocheck
import { useEffect, useState } from 'react';
import { LazyLoadImage } from 'react-lazy-load-image-component';
import Layout from '../components/common/Layout';
import { useAuthStore, useChatStore } from '../utils/store';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SIZES = [
  { id: '1024x1024', label: 'Square', icon: '⬛', desc: '1024 × 1024' },
  { id: '1792x1024', label: 'Landscape', icon: '▬', desc: '1792 × 1024' },
  { id: '1024x1792', label: 'Portrait', icon: '▮', desc: '1024 × 1792' },
];

const STYLES = [
  { id: 'vivid', label: 'Vivid', desc: 'Hyper-real & dramatic' },
  { id: 'natural', label: 'Natural', desc: 'More subtle & realistic' },
];

const QUALITIES = [
  { id: 'standard', label: 'Standard', desc: 'Faster & cheaper' },
  { id: 'hd', label: 'HD', desc: 'More detail & cost' },
];

const EXAMPLE_PROMPTS = [
  'A futuristic city at sunset with flying cars and neon lights',
  'A cozy coffee shop in a magical forest with glowing mushrooms',
  "An astronaut surfing on Saturn's rings, digital art style",
  'A photorealistic portrait of a robot reading a book',
  'Abstract art representing the feeling of nostalgia',
];

export default function ImageGenerator() {
  const [prompt, setPrompt] = useState('');
  const [size, setSize] = useState('1024x1024');
  const [style, setStyle] = useState('vivid');
  const [quality, setQuality] = useState('standard');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const { token } = useAuthStore();
  const { setMode } = useChatStore();

  useEffect(() => {
    setMode('image');
  }, [setMode]);

  const generate = async () => {
    if (!prompt.trim() || loading) return;
    setError(null);
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/api/image/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ prompt, size, style, quality }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Generation failed.');

      const imageResult = {
        id: Date.now(),
        url: data.url,
        prompt,
        revisedPrompt: data.revised_prompt,
        size,
        style,
        quality,
        createdAt: new Date().toLocaleTimeString(),
      };

      setResult(imageResult);
      setHistory((prev) => [imageResult, ...prev.slice(0, 11)]);
    } catch (err) {
      setError(err.message || 'Generation failed.');
    } finally {
      setLoading(false);
    }
  };

  const downloadImage = async (url, filename = 'nova-ai-image.png') => {
    try {
      const proxyUrl = `${API_URL}/api/image/proxy?url=${encodeURIComponent(url)}`;
      const res = await fetch(proxyUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch {
      window.open(url, '_blank');
    }
  };

  return (
    <Layout>
      <div className="h-full w-full bg-gray-950 text-white flex">
        <div className="w-96 border-r border-gray-800 flex flex-col p-6 gap-5 overflow-y-auto">
          <div>
            <h1 className="text-xl font-semibold text-white">🖼️ Image Generator</h1>
            <p className="text-gray-500 text-sm mt-1">Powered by DALL·E 3</p>
          </div>

          <div>
            <label className="text-sm text-gray-400 mb-2 block">Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the image you want to create..."
              rows={4}
              maxLength={4000}
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 text-sm resize-none focus:outline-none focus:border-blue-500 transition-colors"
            />
            <div className="flex justify-between mt-1">
              <span className="text-xs text-gray-600">{prompt.length}/4000</span>
              <button
                onClick={() => setPrompt('')}
                className="text-xs text-gray-600 hover:text-gray-400"
              >
                Clear
              </button>
            </div>
          </div>

          <div>
            <label className="text-sm text-gray-400 mb-2 block">Examples</label>
            <div className="flex flex-col gap-1.5">
              {EXAMPLE_PROMPTS.map((item, i) => (
                <button
                  key={i}
                  onClick={() => setPrompt(item)}
                  className="text-left text-xs text-gray-400 hover:text-blue-400 hover:bg-gray-800 px-3 py-2 rounded-lg transition-colors border border-transparent hover:border-gray-700 truncate"
                >
                  ✨ {item}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm text-gray-400 mb-2 block">Size</label>
            <div className="grid grid-cols-3 gap-2">
              {SIZES.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setSize(option.id)}
                  className={`flex flex-col items-center py-3 px-2 rounded-xl border text-xs transition-all ${
                    size === option.id
                      ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                      : 'border-gray-700 hover:border-gray-600 text-gray-400'
                  }`}
                >
                  <span className="text-lg mb-1">{option.icon}</span>
                  <span className="font-medium">{option.label}</span>
                  <span className="text-gray-600 text-[10px]">{option.desc}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm text-gray-400 mb-2 block">Style</label>
            <div className="grid grid-cols-2 gap-2">
              {STYLES.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setStyle(option.id)}
                  className={`py-3 px-3 rounded-xl border text-left transition-all ${
                    style === option.id
                      ? 'border-purple-500 bg-purple-500/10 text-purple-300'
                      : 'border-gray-700 hover:border-gray-600 text-gray-400'
                  }`}
                >
                  <div className="font-medium text-sm">{option.label}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm text-gray-400 mb-2 block">Quality</label>
            <div className="grid grid-cols-2 gap-2">
              {QUALITIES.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setQuality(option.id)}
                  className={`py-3 px-3 rounded-xl border text-left transition-all ${
                    quality === option.id
                      ? 'border-amber-500 bg-amber-500/10 text-amber-300'
                      : 'border-gray-700 hover:border-gray-600 text-gray-400'
                  }`}
                >
                  <div className="font-medium text-sm">{option.label}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={generate}
            disabled={!prompt.trim() || loading}
            className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Generating...
              </>
            ) : (
              '✨ Generate Image'
            )}
          </button>

          {error && (
            <div className="bg-red-900/40 border border-red-700 rounded-xl px-4 py-3 text-red-300 text-sm flex justify-between items-start">
              <span>⚠️ {error}</span>
              <button onClick={() => setError(null)} className="text-red-500 ml-2">
                ✕
              </button>
            </div>
          )}
        </div>

        <div className="flex-1 flex flex-col overflow-y-auto">
          <div className="flex-1 flex items-center justify-center p-8">
            {loading && (
              <div className="flex flex-col items-center gap-4 text-gray-500">
                <div className="w-16 h-16 border-4 border-gray-700 border-t-blue-500 rounded-full animate-spin" />
                <p className="text-sm">Creating your image...</p>
                <p className="text-xs text-gray-600">This takes about 10-20 seconds</p>
              </div>
            )}

            {!loading && !result && (
              <div className="text-center text-gray-600">
                <div className="text-6xl mb-4">🎨</div>
                <p className="text-lg font-medium text-gray-500">Your image will appear here</p>
                <p className="text-sm mt-1">Enter a prompt and click Generate</p>
              </div>
            )}

            {!loading && result && (
              <div className="max-w-2xl w-full">
                <div className="relative rounded-2xl overflow-hidden border border-gray-700 shadow-2xl">
                  <LazyLoadImage
                    src={result.url}
                    alt={result.prompt}
                    className="w-full object-cover"
                    effect="opacity"
                  />

                  <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent flex gap-2 opacity-0 hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => downloadImage(result.url)}
                      className="flex-1 bg-white/20 hover:bg-white/30 backdrop-blur text-white text-sm py-2 px-4 rounded-lg transition-colors"
                    >
                      ⬇️ Download
                    </button>
                    <button
                      onClick={() => window.open(result.url, '_blank')}
                      className="bg-white/20 hover:bg-white/30 backdrop-blur text-white text-sm py-2 px-4 rounded-lg transition-colors"
                    >
                      🔗 Open
                    </button>
                    <button
                      onClick={() => setPrompt(result.prompt)}
                      className="bg-white/20 hover:bg-white/30 backdrop-blur text-white text-sm py-2 px-4 rounded-lg transition-colors"
                    >
                      🔄 Reuse
                    </button>
                  </div>
                </div>

                {result.revisedPrompt && result.revisedPrompt !== result.prompt && (
                  <div className="mt-3 bg-gray-800/50 border border-gray-700 rounded-xl px-4 py-3">
                    <p className="text-xs text-gray-500 mb-1">DALL·E revised your prompt:</p>
                    <p className="text-sm text-gray-300 italic">"{result.revisedPrompt}"</p>
                  </div>
                )}

                <div className="mt-3 flex gap-2 flex-wrap">
                  {[result.size, result.style, result.quality, result.createdAt].map((tag, i) => (
                    <span
                      key={`${tag}-${i}`}
                      className="text-xs bg-gray-800 border border-gray-700 text-gray-400 px-3 py-1 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {history.length > 1 && (
            <div className="border-t border-gray-800 p-4">
              <p className="text-xs text-gray-500 mb-3">Recent generations</p>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {history.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setResult(item)}
                    className={`flex-shrink-0 w-20 h-20 rounded-xl overflow-hidden border-2 transition-all ${
                      result?.id === item.id
                        ? 'border-blue-500'
                        : 'border-gray-700 hover:border-gray-500'
                    }`}
                  >
                    <LazyLoadImage
                      src={item.url}
                      alt={item.prompt}
                      className="w-full h-full object-cover"
                      effect="opacity"
                    />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
