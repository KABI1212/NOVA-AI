import { useState } from 'react';
import { BookOpen, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import MessageBubble from '../components/chat/MessageBubble';
import { explainAPI } from '../services/api';

function KnowledgeAssistant() {
  const [activeTab, setActiveTab] = useState('ask');
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const tabs = [
    { id: 'ask', label: 'Ask a Question' },
    { id: 'summarize', label: 'Summarize Text' },
  ];

  const suggestions = [
    'Explain how TLS keeps connections secure',
    'What is the difference between REST and GraphQL?',
    'Summarize: The product team shipped a new feature last week...',
  ];

  const handleSubmit = async () => {
    if (!prompt.trim() || loading) return;
    setLoading(true);
    try {
      const response = await explainAPI.explain({
        prompt,
        mode: activeTab === 'summarize' ? 'summary' : 'knowledge',
        audience: 'general',
        detail: 'balanced',
      });
      setResult({ role: 'assistant', content: response.data.explanation });
    } catch (error) {
      toast.error('Failed to generate response');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="h-full flex flex-col p-6">
        <div className="max-w-6xl mx-auto w-full flex-1 grid grid-cols-2 gap-6 overflow-hidden">
          <div className="card p-6 flex flex-col">
            <h3 className="text-lg font-semibold mb-4">Knowledge Assistant</h3>

            <div className="flex gap-2 mb-4">
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

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                activeTab === 'summarize'
                  ? 'Paste text you want summarized...'
                  : 'Ask a knowledge question...'
              }
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
              onClick={handleSubmit}
              disabled={!prompt.trim() || loading}
              className="btn-primary mt-4 disabled:opacity-50"
            >
              <Send className="w-4 h-4 mr-2 inline" />
              {loading ? 'Working...' : 'Submit'}
            </button>
          </div>

          <div className="card p-6 flex flex-col overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Response</h3>
            {result ? (
              <MessageBubble message={result} />
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <BookOpen className="w-12 h-12" />
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default KnowledgeAssistant;
