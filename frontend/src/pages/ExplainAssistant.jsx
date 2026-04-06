import { useEffect, useState } from 'react';
import { Lightbulb, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import MessageBubble from '../components/chat/MessageBubble';
import { explainAPI } from '../services/api';
import { stopSpeechPlayback } from '../utils/speech';

function ExplainAssistant() {
  const [prompt, setPrompt] = useState('');
  const [audience, setAudience] = useState('student');
  const [detail, setDetail] = useState('detailed');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => () => {
    stopSpeechPlayback();
  }, []);

  const suggestions = [
    'Explain how transformers work step-by-step',
    'Why does a model overfit? Provide a simple example',
    'Explain recursion with a real-world analogy',
    'Break down the OSI model for beginners',
  ];

  const handleExplain = async () => {
    if (!prompt.trim() || loading) return;
    stopSpeechPlayback();
    setLoading(true);
    try {
      const response = await explainAPI.explain({
        prompt,
        mode: 'deep',
        audience,
        detail,
      });
      setResult({ role: 'assistant', content: response.data.explanation });
    } catch (error) {
      toast.error('Failed to generate explanation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="h-full flex flex-col p-6">
        <div className="max-w-6xl mx-auto w-full flex-1 grid grid-cols-2 gap-6 overflow-hidden">
          <div className="card p-6 flex flex-col">
            <h3 className="text-lg font-semibold mb-4">Deep Explanation Engine</h3>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <select
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                className="input-field"
              >
                <option value="student">Student</option>
                <option value="developer">Developer</option>
                <option value="executive">Executive</option>
              </select>
              <select
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                className="input-field"
              >
                <option value="brief">Brief</option>
                <option value="detailed">Detailed</option>
                <option value="deep">Deep Dive</option>
              </select>
            </div>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask for a deep, step-by-step explanation..."
              className="input-field flex-1 resize-none text-sm"
            />

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
              onClick={handleExplain}
              disabled={!prompt.trim() || loading}
              className="btn-primary mt-4 disabled:opacity-50"
            >
              <Send className="w-4 h-4 mr-2 inline" />
              {loading ? 'Explaining...' : 'Explain'}
            </button>
          </div>

          <div className="card p-6 flex flex-col overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Explanation</h3>
            {result ? (
              <MessageBubble message={result} />
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <Lightbulb className="w-12 h-12" />
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default ExplainAssistant;
