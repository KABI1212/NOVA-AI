// @ts-nocheck
import { useEffect, useState } from 'react';
import { Bot, Globe2, Send, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';

import Layout from '../components/common/Layout';
import MessageBubble from '../components/chat/MessageBubble';
import { orchestratorAPI } from '../services/api';
import { formatApiError } from '../utils/apiErrors';
import { stopSpeechPlayback } from '../utils/speech';

const TABS = [
  {
    id: 'compose',
    label: 'Multi-AI Compose',
    icon: Sparkles,
    description: 'Blend multiple model outputs into one final answer.',
  },
  {
    id: 'agent',
    label: 'Live Research Agent',
    icon: Globe2,
    description: 'Use the web-backed agent flow with source collection.',
  },
];

function OrchestratorStudio() {
  const [activeTab, setActiveTab] = useState('compose');
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => () => {
    stopSpeechPlayback();
  }, []);

  const handleSubmit = async () => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    stopSpeechPlayback();
    setLoading(true);
    setResult(null);

    try {
      const response =
        activeTab === 'agent'
          ? await orchestratorAPI.agent({ question: trimmed })
          : await orchestratorAPI.compose({ question: trimmed });

      const data = response.data || {};
      const content = data.message || data.answer || 'No response returned.';
      setResult({
        role: 'assistant',
        content,
        meta: {
          badge: data.badge || null,
          modelsUsed: Array.isArray(data.models_used) ? data.models_used : [],
          responseTime: data.response_time ?? null,
          sources: Array.isArray(data.sources)
            ? data.sources.map((url, index) => ({
                title: `Source ${index + 1}`,
                url,
              }))
            : [],
          news: Array.isArray(data.news) ? data.news : [],
        },
      });
      toast.success(activeTab === 'agent' ? 'Agent answer ready.' : 'Orchestrated answer ready.');
    } catch (error) {
      const detail = formatApiError(error, 'Could not run this workflow right now.');
      setResult({ role: 'assistant', content: detail });
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  const resultMeta = result?.meta || {};

  return (
    <Layout>
      <div className="h-full flex flex-col p-6">
        <div className="max-w-6xl mx-auto w-full flex-1 grid grid-cols-2 gap-6 overflow-hidden">
          <div className="card p-6 flex flex-col">
            <div className="flex items-center gap-3 mb-4">
              <Bot className="w-6 h-6 text-primary-600" />
              <div>
                <h3 className="text-lg font-semibold">Orchestrator Studio</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Expose the advanced multi-model and live-agent flows already available in NOVA AI.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;

                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`rounded-xl border px-4 py-4 text-left transition-colors ${
                      isActive
                        ? 'border-primary-500 bg-primary-50 text-primary-700 dark:border-primary-400 dark:bg-primary-900/20 dark:text-primary-200'
                        : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-gray-700 dark:bg-gray-900/40 dark:text-gray-200 dark:hover:bg-gray-800'
                    }`}
                  >
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Icon className="w-4 h-4" />
                      {tab.label}
                    </div>
                    <div className="mt-1 text-xs opacity-80">{tab.description}</div>
                  </button>
                );
              })}
            </div>

            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={
                activeTab === 'agent'
                  ? 'Ask for a web-backed answer with source collection...'
                  : 'Ask for a combined answer across multiple AI systems...'
              }
              className="input-field flex-1 resize-none text-sm"
            />

            <button
              onClick={handleSubmit}
              disabled={!question.trim() || loading}
              className="btn-primary mt-4 disabled:opacity-50"
            >
              <Send className="w-4 h-4 mr-2 inline" />
              {loading ? 'Running...' : 'Run Workflow'}
            </button>
          </div>

          <div className="card p-6 flex flex-col overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Result</h3>
            {result ? (
              <div className="space-y-4">
                {(resultMeta.badge || resultMeta.responseTime != null || resultMeta.modelsUsed?.length) && (
                  <div className="flex flex-wrap gap-2">
                    {resultMeta.badge ? (
                      <span className="rounded-full bg-primary-100 px-3 py-1 text-xs font-medium text-primary-700 dark:bg-primary-900/20 dark:text-primary-200">
                        {resultMeta.badge}
                      </span>
                    ) : null}
                    {resultMeta.responseTime != null ? (
                      <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-200">
                        {resultMeta.responseTime}s
                      </span>
                    ) : null}
                    {resultMeta.modelsUsed?.length
                      ? resultMeta.modelsUsed.map((item) => (
                          <span
                            key={item}
                            className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-200"
                          >
                            {item}
                          </span>
                        ))
                      : null}
                  </div>
                )}

                <MessageBubble message={result} />

                {resultMeta.sources?.length ? (
                  <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
                    <h4 className="text-sm font-semibold mb-2">Sources</h4>
                    <div className="space-y-2">
                      {resultMeta.sources.map((source) => (
                        <a
                          key={source.url}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="block text-sm text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {source.title}: {source.url}
                        </a>
                      ))}
                    </div>
                  </div>
                ) : null}

                {resultMeta.news?.length ? (
                  <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
                    <h4 className="text-sm font-semibold mb-2">News Matches</h4>
                    <div className="space-y-3">
                      {resultMeta.news.map((item, index) => (
                        <div key={`${item.link}-${index}`} className="text-sm">
                          <div className="font-medium text-gray-900 dark:text-white">{item.title || 'Untitled'}</div>
                          {item.body ? (
                            <div className="mt-1 text-gray-600 dark:text-gray-300">{item.body}</div>
                          ) : null}
                          {item.link ? (
                            <a
                              href={item.link}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-1 inline-block text-blue-600 hover:underline dark:text-blue-400"
                            >
                              {item.link}
                            </a>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                <Bot className="w-12 h-12" />
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default OrchestratorStudio;
