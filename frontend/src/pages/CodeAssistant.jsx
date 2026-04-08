// @ts-nocheck
import { useEffect, useState } from 'react';
import { Code, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import { codeAPI } from '../services/api';
import MessageBubble from '../components/chat/MessageBubble';
import { formatApiError } from '../utils/apiErrors';
import { stopSpeechPlayback } from '../utils/speech';

function CodeAssistant() {
  const [activeTab, setActiveTab] = useState('generate');
  const [prompt, setPrompt] = useState('');
  const [language, setLanguage] = useState('python');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => () => {
    stopSpeechPlayback();
  }, []);

  const handleSubmit = async () => {
    if (!prompt.trim()) return;

    stopSpeechPlayback();
    setLoading(true);
    setResult(null);
    try {
      let response;
      if (activeTab === 'generate') {
        response = await codeAPI.generate({ prompt, language });
        setResult({ content: response.data.code, role: 'assistant' });
      } else if (activeTab === 'explain') {
        response = await codeAPI.explain({ code: prompt, language });
        setResult({ content: response.data.explanation, role: 'assistant' });
      } else if (activeTab === 'debug') {
        response = await codeAPI.debug({ code: prompt });
        setResult({ content: response.data.debug_result, role: 'assistant' });
      } else if (activeTab === 'optimize') {
        response = await codeAPI.optimize({ code: prompt, language });
        setResult({ content: response.data.optimization, role: 'assistant' });
      }
      toast.success('Code processed successfully!');
    } catch (error) {
      const detail = formatApiError(error, 'Failed to process code');
      setResult({ content: detail, role: 'assistant' });
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'generate', label: 'Generate Code' },
    { id: 'explain', label: 'Explain Code' },
    { id: 'debug', label: 'Debug Code' },
    { id: 'optimize', label: 'Optimize Code' },
  ];

  return (
    <Layout>
      <div className="h-full flex flex-col p-6">
        <div className="flex gap-2 mb-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex-1 grid grid-cols-2 gap-6 overflow-hidden">
          <div className="card p-6 flex flex-col">
            <h3 className="text-lg font-semibold mb-4">Input</h3>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="input-field mb-4"
            >
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
              <option value="java">Java</option>
              <option value="cpp">C++</option>
              <option value="go">Go</option>
            </select>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                activeTab === 'generate'
                  ? 'Describe what code you want to generate...'
                  : 'Paste your code here...'
              }
              className="input-field flex-1 resize-none text-sm"
            />
            <button
              onClick={handleSubmit}
              disabled={!prompt.trim() || loading}
              className="btn-primary mt-4 disabled:opacity-50"
            >
              <Send className="w-4 h-4 mr-2 inline" />
              {loading ? 'Processing...' : 'Submit'}
            </button>
          </div>

          <div className="card p-6 flex flex-col overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Result</h3>
            {result ? (
              <MessageBubble message={result} />
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <Code className="w-12 h-12" />
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default CodeAssistant;
