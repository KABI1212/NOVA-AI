import { useState } from 'react';
import { Image as ImageIcon, Download, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import { imageAPI } from '../services/api';

function ImageGenerator() {
  const [prompt, setPrompt] = useState('');
  const [size, setSize] = useState('1024x1024');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  const suggestions = [
    'Cinematic city skyline at dusk with teal lights',
    'Minimalist desk setup with warm sunlight and plants',
    'Futuristic lab interior with glass and soft glow',
    'Abstract waves in deep blue and gold tones',
  ];

  const handleGenerate = async () => {
    if (!prompt.trim() || loading) return;
    setLoading(true);
    const promptText = prompt.trim();
    setPrompt('');
    try {
      const response = await imageAPI.generate({
        prompt: promptText,
        size,
        n: 1,
      });

      const images = response.data.images.map(
        (img) => `data:image/png;base64,${img}`
      );

      setHistory((prev) => [
        {
          id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          prompt: promptText,
          images,
          createdAt: new Date().toISOString(),
        },
        ...prev,
      ]);
    } catch (error) {
      toast.error('Failed to generate image');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="h-full flex flex-col p-6">
        <div className="max-w-6xl mx-auto w-full flex-1 flex flex-col">
          <div className="card p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Image Generator</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe the image you want to generate..."
                  className="input-field"
                />
              </div>
              <select
                value={size}
                onChange={(e) => setSize(e.target.value)}
                className="input-field"
              >
                <option value="512x512">512x512</option>
                <option value="1024x1024">1024x1024</option>
              </select>
            </div>

            <div className="flex flex-wrap gap-2 mt-4">
              {suggestions.map((item) => (
                <button
                  key={item}
                  onClick={() => setPrompt(item)}
                  className="px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-700 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                >
                  {item}
                </button>
              ))}
            </div>

            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || loading}
              className="btn-primary mt-4 disabled:opacity-50"
            >
              <Send className="w-4 h-4 mr-2 inline" />
              {loading ? 'Generating...' : 'Generate Image'}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {history.length === 0 ? (
              <div className="card p-12 text-center">
                <ImageIcon className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                <p className="text-gray-500 dark:text-gray-400">
                  Generate your first image to see results here.
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {history.map((item) => (
                  <div key={item.id} className="space-y-4">
                    <div className="flex justify-end">
                      <div className="max-w-2xl bg-primary-100 dark:bg-primary-900 text-gray-900 dark:text-gray-100 px-4 py-3 rounded-xl">
                        {item.prompt}
                      </div>
                    </div>
                    <div className="flex justify-start">
                      <div className="max-w-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 px-4 py-4 rounded-xl">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {item.images.map((src, idx) => (
                            <div key={idx} className="space-y-2">
                              <img
                                src={src}
                                alt="Generated"
                                className="rounded-lg border border-gray-200 dark:border-gray-700"
                              />
                              <a
                                href={src}
                                download={`nova-ai-${item.id}-${idx}.png`}
                                className="inline-flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                              >
                                <Download className="w-4 h-4" />
                                Download
                              </a>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default ImageGenerator;
