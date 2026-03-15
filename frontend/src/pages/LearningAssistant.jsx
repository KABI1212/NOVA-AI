// @ts-nocheck
import { useState, useEffect } from 'react';
import { BookOpen, Plus, Check } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import { learningAPI } from '../services/api';

function LearningAssistant() {
  const [roadmaps, setRoadmaps] = useState([]);
  const [topic, setTopic] = useState('');
  const [level, setLevel] = useState('beginner');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadRoadmaps();
  }, []);

  const loadRoadmaps = async () => {
    try {
      const response = await learningAPI.getProgress();
      setRoadmaps(response.data);
    } catch (error) {
      toast.error('Failed to load roadmaps');
    }
  };

  const handleGenerate = async () => {
    if (!topic.trim()) return;

    setLoading(true);
    try {
      const response = await learningAPI.generateRoadmap({ topic, level });
      setRoadmaps([response.data, ...roadmaps]);
      setTopic('');
      toast.success('Roadmap generated!');
    } catch (error) {
      toast.error('Failed to generate roadmap');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="h-full p-6">
        <div className="max-w-4xl mx-auto">
          {/* Generate Form */}
          <div className="card p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Generate Learning Roadmap</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="Enter a topic to learn (e.g., Python Programming)"
                  className="input-field"
                />
              </div>
              <select
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                className="input-field"
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
            <button
              onClick={handleGenerate}
              disabled={!topic.trim() || loading}
              className="btn-primary mt-4 disabled:opacity-50"
            >
              <Plus className="w-4 h-4 mr-2 inline" />
              {loading ? 'Generating...' : 'Generate Roadmap'}
            </button>
          </div>

          {/* Roadmaps List */}
          <div className="space-y-6">
            {roadmaps.map((roadmap) => (
              <div key={roadmap.id} className="card p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white">
                      {roadmap.topic}
                    </h3>
                    <span className="inline-block mt-2 px-3 py-1 bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 rounded-full text-sm font-medium">
                      {roadmap.current_level}
                    </span>
                  </div>
                  <BookOpen className="w-6 h-6 text-primary-600" />
                </div>

                <div className="prose dark:prose-invert max-w-none">
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                    {roadmap.roadmap.roadmap}
                  </p>
                </div>

                {roadmap.completed_items.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Completed Items:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {roadmap.completed_items.map((item, idx) => (
                        <span
                          key={idx}
                          className="flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded text-xs"
                        >
                          <Check className="w-3 h-3" />
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {roadmaps.length === 0 && (
              <div className="card p-12 text-center">
                <BookOpen className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                <p className="text-gray-500 dark:text-gray-400">
                  No learning roadmaps yet. Generate one to get started!
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default LearningAssistant;
