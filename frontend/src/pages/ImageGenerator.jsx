// @ts-nocheck
import { useEffect, useMemo, useState } from 'react';
import { LazyLoadImage } from 'react-lazy-load-image-component';
import Layout from '../components/common/Layout';
import { imageAPI } from '../services/api';
import { useAuthStore, useChatStore } from '../utils/store';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SIZES = [
  { id: '1024x1024', label: 'Square', desc: '1024 x 1024' },
  { id: '1792x1024', label: 'Landscape', desc: '1792 x 1024' },
  { id: '1024x1792', label: 'Portrait', desc: '1024 x 1792' },
];

const STYLES = [
  { id: 'vivid', label: 'Vivid', desc: 'Cinematic and punchy' },
  { id: 'natural', label: 'Natural', desc: 'Balanced and realistic' },
];

const QUALITIES = [
  { id: 'standard', label: 'Standard', desc: 'Faster generation' },
  { id: 'hd', label: 'HD', desc: 'Higher detail output' },
];

const DEFAULT_PROVIDER_OPTIONS = [
  { id: 'auto', name: 'Auto', available: true, description: 'Pick the best configured image model.' },
  { id: 'google', name: 'Gemini', available: true, description: 'Google image generation.' },
  { id: 'openrouter', name: 'OpenRouter', available: true, description: 'OpenRouter image generation fallback.' },
  { id: 'openai', name: 'ChatGPT', available: true, description: 'OpenAI image generation.' },
];

const PROMPT_TARGETS = [
  { id: 'auto', label: 'Auto', desc: 'General prompt polishing' },
  { id: 'chatgpt', label: 'ChatGPT', desc: 'Tune for OpenAI image prompts' },
  { id: 'gemini', label: 'Gemini', desc: 'Tune for Gemini image prompts' },
  { id: 'canva', label: 'Canva', desc: 'Tune for design-focused prompts' },
];

const EXAMPLE_PROMPTS = [
  'A futuristic city at sunset with flying cars and reflective wet streets',
  'A cozy coffee shop hidden in a glowing forest filled with fireflies',
  'An astronaut surfing on Saturn rings in a cinematic digital art style',
  'A photorealistic portrait of a robot reading near a rain-covered window',
  'A premium skincare product photo on stone with soft studio lighting',
];

function optionLabelById(options, id, fallback = '') {
  const match = options.find((option) => option.id === id);
  return match?.name || match?.label || fallback;
}

export default function ImageGenerator() {
  const [prompt, setPrompt] = useState('');
  const [size, setSize] = useState('1024x1024');
  const [style, setStyle] = useState('vivid');
  const [quality, setQuality] = useState('standard');
  const [provider, setProvider] = useState('auto');
  const [promptTarget, setPromptTarget] = useState('auto');
  const [enhancePrompt, setEnhancePrompt] = useState(true);
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [providerOptions, setProviderOptions] = useState(DEFAULT_PROVIDER_OPTIONS);
  const { token } = useAuthStore();
  const { setMode } = useChatStore();

  useEffect(() => {
    setMode('image');
  }, [setMode]);

  useEffect(() => {
    let active = true;

    const loadProviders = async () => {
      try {
        const response = await imageAPI.getProviders();
        if (!active) {
          return;
        }
        const nextProviders = Array.isArray(response.data?.providers) && response.data.providers.length
          ? response.data.providers
          : DEFAULT_PROVIDER_OPTIONS;
        setProviderOptions(nextProviders);
      } catch {
        if (active) {
          setProviderOptions(DEFAULT_PROVIDER_OPTIONS);
        }
      }
    };

    loadProviders();
    return () => {
      active = false;
    };
  }, []);

  const availableProviders = useMemo(
    () => providerOptions.filter((option) => option.id === 'auto' || option.available),
    [providerOptions],
  );

  const optimizePrompt = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || optimizing) {
      return;
    }

    setError(null);
    setOptimizing(true);
    try {
      const response = await imageAPI.optimizePrompt({
        prompt: trimmed,
        size,
        style,
        quality,
        provider,
        prompt_target: promptTarget,
      });
      const revisedPrompt = response.data?.revised_prompt?.trim();
      if (!revisedPrompt) {
        throw new Error('Prompt optimization returned no text.');
      }
      setPrompt(revisedPrompt);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Prompt optimization failed.');
    } finally {
      setOptimizing(false);
    }
  };

  const generate = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || loading) {
      return;
    }

    setError(null);
    setLoading(true);
    setResult(null);

    try {
      const response = await imageAPI.generate({
        prompt: trimmed,
        size,
        style,
        quality,
        n: 1,
        provider,
        enhance_prompt: enhancePrompt,
        prompt_target: promptTarget,
      });
      const data = response.data || {};
      const url = data.url || data.images?.[0];
      if (!url) {
        throw new Error('Generation returned no image.');
      }

      const nextResult = {
        id: Date.now(),
        url,
        prompt: data.prompt || trimmed,
        revisedPrompt: data.revised_prompt || trimmed,
        size: data.size || size,
        style: data.style || style,
        quality: data.quality || quality,
        provider: data.provider || provider,
        providerLabel: data.provider_label || optionLabelById(providerOptions, data.provider || provider, 'Auto'),
        promptTarget,
        createdAt: new Date().toLocaleTimeString(),
      };

      setResult(nextResult);
      setHistory((prev) => [nextResult, ...prev.filter((item) => item.url !== nextResult.url).slice(0, 11)]);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Generation failed.');
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
      <div className="flex h-full w-full bg-gray-950 text-white">
        <div className="flex w-96 flex-col gap-5 overflow-y-auto border-r border-gray-800 p-6">
          <div>
            <h1 className="text-xl font-semibold text-white">Image Generator</h1>
            <p className="mt-1 text-sm text-gray-500">Generate with Gemini, OpenRouter, or ChatGPT and polish prompts for Canva, Gemini, or ChatGPT.</p>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-sm text-gray-400">Prompt</label>
              <button
                onClick={optimizePrompt}
                disabled={!prompt.trim() || optimizing || loading}
                className="rounded-lg border border-gray-700 px-3 py-1 text-xs text-gray-300 transition-colors hover:border-blue-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {optimizing ? 'Optimizing...' : 'Improve Prompt'}
              </button>
            </div>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Describe the image you want to create..."
              rows={5}
              maxLength={4000}
              className="w-full resize-none rounded-xl border border-gray-700 bg-gray-800 px-4 py-3 text-sm text-white placeholder-gray-500 transition-colors focus:border-blue-500 focus:outline-none"
            />
            <div className="mt-1 flex justify-between">
              <span className="text-xs text-gray-600">{prompt.length}/4000</span>
              <button
                onClick={() => setPrompt('')}
                className="text-xs text-gray-600 transition-colors hover:text-gray-400"
              >
                Clear
              </button>
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm text-gray-400">Prompt Target</label>
            <div className="grid grid-cols-2 gap-2">
              {PROMPT_TARGETS.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setPromptTarget(option.id)}
                  className={`rounded-xl border px-3 py-3 text-left transition-all ${
                    promptTarget === option.id
                      ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300'
                      : 'border-gray-700 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  <div className="text-sm font-medium">{option.label}</div>
                  <div className="mt-0.5 text-xs text-gray-500">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm text-gray-400">Generate With</label>
            <div className="grid gap-2">
              {providerOptions.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setProvider(option.id)}
                  disabled={option.id !== 'auto' && !option.available}
                  className={`rounded-xl border px-3 py-3 text-left transition-all ${
                    provider === option.id
                      ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                      : 'border-gray-700 text-gray-400 hover:border-gray-600'
                  } ${option.id !== 'auto' && !option.available ? 'cursor-not-allowed opacity-40' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{option.name}</span>
                    <span className="text-[10px] uppercase tracking-[0.2em] text-gray-500">
                      {option.available || option.id === 'auto' ? 'Ready' : 'Not set'}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">{option.description}</div>
                </button>
              ))}
            </div>
            {availableProviders.length <= 1 && (
              <p className="mt-2 text-xs text-amber-300">No dedicated image provider key is configured yet. Prompt optimization can still help, but image generation will stay unavailable until Gemini, OpenRouter, or ChatGPT credentials are set.</p>
            )}
          </div>

          <div className="flex items-center justify-between rounded-xl border border-gray-800 bg-gray-900/70 px-4 py-3">
            <div>
              <div className="text-sm font-medium text-white">Auto-enhance before generate</div>
              <div className="text-xs text-gray-500">Use the selected prompt target each time you render.</div>
            </div>
            <button
              onClick={() => setEnhancePrompt((value) => !value)}
              className={`h-7 w-14 rounded-full transition-colors ${enhancePrompt ? 'bg-blue-500' : 'bg-gray-700'}`}
            >
              <span
                className={`block h-6 w-6 rounded-full bg-white transition-transform ${enhancePrompt ? 'translate-x-7' : 'translate-x-0.5'}`}
              />
            </button>
          </div>

          <div>
            <label className="mb-2 block text-sm text-gray-400">Examples</label>
            <div className="flex flex-col gap-1.5">
              {EXAMPLE_PROMPTS.map((item) => (
                <button
                  key={item}
                  onClick={() => setPrompt(item)}
                  className="truncate rounded-lg border border-transparent px-3 py-2 text-left text-xs text-gray-400 transition-colors hover:border-gray-700 hover:bg-gray-800 hover:text-blue-400"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm text-gray-400">Size</label>
            <div className="grid grid-cols-3 gap-2">
              {SIZES.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setSize(option.id)}
                  className={`rounded-xl border px-2 py-3 text-center text-xs transition-all ${
                    size === option.id
                      ? 'border-blue-500 bg-blue-500/10 text-blue-300'
                      : 'border-gray-700 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  <div className="font-medium">{option.label}</div>
                  <div className="mt-1 text-[10px] text-gray-500">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm text-gray-400">Style</label>
            <div className="grid grid-cols-2 gap-2">
              {STYLES.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setStyle(option.id)}
                  className={`rounded-xl border px-3 py-3 text-left transition-all ${
                    style === option.id
                      ? 'border-purple-500 bg-purple-500/10 text-purple-300'
                      : 'border-gray-700 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  <div className="text-sm font-medium">{option.label}</div>
                  <div className="mt-0.5 text-xs text-gray-500">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm text-gray-400">Quality</label>
            <div className="grid grid-cols-2 gap-2">
              {QUALITIES.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setQuality(option.id)}
                  className={`rounded-xl border px-3 py-3 text-left transition-all ${
                    quality === option.id
                      ? 'border-amber-500 bg-amber-500/10 text-amber-300'
                      : 'border-gray-700 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  <div className="text-sm font-medium">{option.label}</div>
                  <div className="mt-0.5 text-xs text-gray-500">{option.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={generate}
            disabled={!prompt.trim() || loading}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 py-3 text-sm font-semibold transition-all hover:from-blue-500 hover:to-cyan-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? 'Generating...' : 'Generate Image'}
          </button>

          {error && (
            <div className="flex items-start justify-between rounded-xl border border-red-700 bg-red-900/30 px-4 py-3 text-sm text-red-300">
              <span className="break-words">{error}</span>
              <button onClick={() => setError(null)} className="ml-3 text-red-400 transition-colors hover:text-red-200">
                x
              </button>
            </div>
          )}
        </div>

        <div className="flex flex-1 flex-col overflow-y-auto">
          <div className="flex flex-1 items-center justify-center p-8">
            {loading && (
              <div className="flex flex-col items-center gap-4 text-gray-500">
                <div className="h-16 w-16 animate-spin rounded-full border-4 border-gray-700 border-t-blue-500" />
                <p className="text-sm">Creating your image...</p>
                <p className="text-xs text-gray-600">This can take 10 to 20 seconds.</p>
              </div>
            )}

            {!loading && !result && (
              <div className="text-center text-gray-600">
                <div className="mb-4 text-5xl font-semibold text-gray-700">NOVA</div>
                <p className="text-lg font-medium text-gray-500">Your image will appear here</p>
                <p className="mt-1 text-sm">Optimize the prompt, choose a provider, and generate.</p>
              </div>
            )}

            {!loading && result && (
              <div className="w-full max-w-2xl">
                <div className="relative overflow-hidden rounded-2xl border border-gray-700 shadow-2xl">
                  <LazyLoadImage
                    src={result.url}
                    alt={result.prompt}
                    className="w-full object-cover"
                    effect="opacity"
                  />

                  <div className="absolute bottom-0 left-0 right-0 flex gap-2 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 transition-opacity hover:opacity-100">
                    <button
                      onClick={() => downloadImage(result.url)}
                      className="flex-1 rounded-lg bg-white/20 px-4 py-2 text-sm text-white transition-colors hover:bg-white/30"
                    >
                      Download
                    </button>
                    <button
                      onClick={() => window.open(result.url, '_blank')}
                      className="rounded-lg bg-white/20 px-4 py-2 text-sm text-white transition-colors hover:bg-white/30"
                    >
                      Open
                    </button>
                    <button
                      onClick={() => setPrompt(result.revisedPrompt || result.prompt)}
                      className="rounded-lg bg-white/20 px-4 py-2 text-sm text-white transition-colors hover:bg-white/30"
                    >
                      Reuse
                    </button>
                  </div>
                </div>

                {result.revisedPrompt && result.revisedPrompt !== result.prompt && (
                  <div className="mt-3 rounded-xl border border-gray-700 bg-gray-800/50 px-4 py-3">
                    <p className="mb-1 text-xs text-gray-500">Optimized prompt</p>
                    <p className="text-sm italic text-gray-300">&quot;{result.revisedPrompt}&quot;</p>
                  </div>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  {[
                    result.size,
                    result.style,
                    result.quality,
                    result.providerLabel || optionLabelById(providerOptions, result.provider, 'Auto'),
                    optionLabelById(PROMPT_TARGETS, result.promptTarget, 'Auto'),
                    result.createdAt,
                  ].map((tag) => (
                    <span
                      key={`${result.id}-${tag}`}
                      className="rounded-full border border-gray-700 bg-gray-800 px-3 py-1 text-xs text-gray-400"
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
              <p className="mb-3 text-xs text-gray-500">Recent generations</p>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {history.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setResult(item)}
                    className={`h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl border-2 transition-all ${
                      result?.id === item.id ? 'border-blue-500' : 'border-gray-700 hover:border-gray-500'
                    }`}
                  >
                    <LazyLoadImage
                      src={item.url}
                      alt={item.prompt}
                      className="h-full w-full object-cover"
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
