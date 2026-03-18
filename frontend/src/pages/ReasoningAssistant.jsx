// @ts-nocheck
import { useState } from 'react';
import { ShieldCheck, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import MessageBubble from '../components/chat/MessageBubble';
import { explainAPI } from '../services/api';

function ReasoningAssistant() {
  const [question, setQuestion] = useState('');
  const [detail, setDetail] = useState('balanced');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const suggestions = [
    'How should I evaluate a new tech stack for my team?',
    'What are the tradeoffs between SQL and NoSQL?',
    'How can I plan a safe rollout for a new feature?',
  ];

  const handleReason = async () => {
    if (!question.trim() || loading) return;
    setLoading(true);
    try {
      const response = await explainAPI.explain({
        prompt: question,
        mode: 'safe',
        audience: 'professional',
        detail,
      });
      setResult({ role: 'assistant', content: response.data.explanation });
    } catch (error) {
      toast.error('Failed to generate safe reasoning answer');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="h-full flex flex-col p-6">
        <div className="max-w-6xl mx-auto w-full flex-1 grid grid-cols-2 gap-6 overflow-hidden">
          <div className="card p-6 flex flex-col">
            <h3 className="text-lg font-semibold mb-4">Reasoning and Safe AI</h3>

            <select
              value={detail}
              onChange={(e) => setDetail(e.target.value)}
              className="input-field mb-4"
            >
              <option value="concise">Concise</option>
              <option value="balanced">Balanced</option>
              <option value="thorough">Thorough</option>
            </select>

            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question that needs structured reasoning..."
              className="input-field flex-1 resize-none text-sm"
            />

            <div className="flex flex-wrap gap-2 mt-4">
              {suggestions.map((item) => (
                <button
                  key={item}
                  onClick={() => setQuestion(item)}
                  className="px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-700 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                >
                  {item}
                </button>
              ))}
            </div>

            <button
              onClick={handleReason}
              disabled={!question.trim() || loading}
              className="btn-primary mt-4 disabled:opacity-50"
            >
              <Send className="w-4 h-4 mr-2 inline" />
              {loading ? 'Reasoning...' : 'Generate Answer'}
            </button>
          </div>

          <div className="card p-6 flex flex-col overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Structured Response</h3>
            {result ? (
              <MessageBubble message={result} />
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <ShieldCheck className="w-12 h-12" />
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default ReasoningAssistant;
