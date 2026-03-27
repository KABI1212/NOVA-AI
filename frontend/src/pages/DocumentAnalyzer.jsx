// @ts-nocheck
import { useState, useEffect } from 'react';
import { Upload, FileText, Trash2, Send, Copy, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import MarkdownAnswer from '../components/common/MarkdownAnswer';
import { documentAPI } from '../services/api';
import { useDocumentStore } from '../utils/store';

async function copyToClipboard(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textArea = document.createElement('textarea');
  textArea.value = value;
  textArea.style.position = 'fixed';
  textArea.style.left = '-9999px';
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  document.execCommand('copy');
  document.body.removeChild(textArea);
}

function DocumentAnalyzer() {
  const { documents, currentDocument, setDocuments, setCurrentDocument, addDocument } = useDocumentStore();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [question, setQuestion] = useState('');
  const [askedQuestion, setAskedQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [answerImages, setAnswerImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [rewritingQuestion, setRewritingQuestion] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    setAskedQuestion('');
    setAnswer('');
    setAnswerImages([]);
  }, [currentDocument?.id]);

  const loadDocuments = async () => {
    try {
      const response = await documentAPI.getDocuments();
      setDocuments(response.data);
    } catch (error) {
      toast.error('Failed to load documents');
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setUploadProgress(0);
    try {
      const response = await documentAPI.upload(formData, {
        onUploadProgress: (event) => {
          const total = event.total || file.size || 0;
          if (!total) {
            return;
          }
          setUploadProgress(Math.min(100, Math.round((event.loaded / total) * 100)));
        },
      });
      addDocument(response.data);
      toast.success('Document uploaded successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = async (id) => {
    try {
      await documentAPI.deleteDocument(id);
      setDocuments(documents.filter((doc) => doc.id !== id));
      if (currentDocument?.id === id) {
        setCurrentDocument(null);
        setAskedQuestion('');
        setAnswer('');
        setAnswerImages([]);
      }
      toast.success('Document deleted');
    } catch (error) {
      toast.error('Failed to delete document');
    }
  };

  const handleAskQuestion = async () => {
    if (!question.trim() || !currentDocument) return;

    setLoading(true);
    setAskedQuestion(question.trim());
    setAnswer('');
    setAnswerImages([]);
    try {
      const response = await documentAPI.askQuestion({
        document_id: currentDocument.id,
        question,
      });
      setAskedQuestion(response.data.question || question.trim());
      setAnswer(response.data.answer);
      setAnswerImages(Array.isArray(response.data.answer_images) ? response.data.answer_images : []);
    } catch (error) {
      toast.error('Failed to get answer');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyQuestion = async () => {
    const sourceQuestion = (askedQuestion || question).trim();
    if (!sourceQuestion) {
      return;
    }

    try {
      await copyToClipboard(sourceQuestion);
      toast.success('Question copied');
    } catch {
      toast.error('Failed to copy question');
    }
  };

  const handleCopyAnswer = async () => {
    if (!answer.trim()) {
      return;
    }

    try {
      await copyToClipboard(answer);
      toast.success('Answer copied');
    } catch {
      toast.error('Failed to copy answer');
    }
  };

  const handleRewriteQuestion = async () => {
    const sourceQuestion = (question || askedQuestion).trim();
    if (!sourceQuestion) {
      return;
    }

    setRewritingQuestion(true);
    try {
      const response = await documentAPI.rewriteQuestion({ question: sourceQuestion });
      const rewrittenQuestion = response.data?.rewritten_question?.trim();
      if (!rewrittenQuestion) {
        throw new Error('No rewritten question returned');
      }
      setQuestion(rewrittenQuestion);
      toast.success('Question rewritten. Ask again when ready.');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to rewrite question');
    } finally {
      setRewritingQuestion(false);
    }
  };

  const handleQuestionKeyDown = (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      handleAskQuestion();
    }
  };

  return (
    <Layout>
      <div className="h-full p-4 sm:p-6">
        <div className="grid h-full gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="card flex min-h-0 flex-col p-5 sm:p-6">
            <div className="mb-4">
              <h3 className="text-lg font-semibold">Documents</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Upload notes, question papers, or study material and ask bigger exam-style questions.
              </p>
            </div>

            <label className="btn-primary mb-4 flex w-full cursor-pointer items-center justify-center gap-2">
              <Upload className="h-4 w-4" />
              {uploading ? 'Uploading...' : 'Upload Document'}
              <input
                type="file"
                accept=".pdf,.txt,.docx,.md,.csv,.json,.py,.js,.jsx,.ts,.tsx,.html,.htm,.css,.xml,.yml,.yaml"
                onChange={handleUpload}
                className="hidden"
                disabled={uploading}
              />
            </label>

            {uploading ? (
              <div className="mb-4">
                <div className="mb-1 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <span>Uploading and processing</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                  <div
                    className="h-full bg-primary-500 transition-all duration-200"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            ) : null}

            {currentDocument ? (
              <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/70">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl bg-primary-100 p-2 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                      Selected Document
                    </p>
                    <p className="mt-1 break-words text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {currentDocument.filename}
                    </p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {(currentDocument.file_size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <div className="mt-4 max-h-44 overflow-y-auto pr-1">
                  <MarkdownAnswer content={currentDocument.summary || 'Processing summary...'} />
                </div>
              </div>
            ) : null}

            <div className="min-h-0 flex-1 overflow-y-auto pr-1">
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className={`group cursor-pointer rounded-2xl border p-3 transition-colors ${
                      currentDocument?.id === doc.id
                        ? 'border-primary-300 bg-primary-50 dark:border-primary-700 dark:bg-primary-900/20'
                        : 'border-transparent hover:bg-gray-100 dark:hover:bg-gray-700/70'
                    }`}
                    onClick={() => setCurrentDocument(doc)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <FileText className="h-4 w-4 flex-shrink-0 text-primary-600" />
                          <span className="truncate text-sm font-medium">{doc.filename}</span>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {(doc.file_size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(doc.id);
                        }}
                        className="rounded-lg p-1 opacity-0 transition group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/20"
                      >
                        <Trash2 className="h-4 w-4 text-red-600" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card flex min-h-0 flex-col p-5 sm:p-6">
            <div className="mb-4">
              <h3 className="text-lg font-semibold">Document Q&A</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Ask for short answers, long assignment answers, comparison tables, or diagram-based explanations.
              </p>
            </div>

            {currentDocument ? (
              <>
                <div className="mb-4 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900/40">
                  <div className="flex flex-col gap-4 xl:flex-row">
                    <div className="min-w-0 flex-1">
                      <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-200">
                        Question
                      </label>
                      <textarea
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        onKeyDown={handleQuestionKeyDown}
                        placeholder="Ask a question about this document. You can also paste a full question paper here."
                        className="input-field min-h-[132px] w-full resize-y"
                        disabled={loading || rewritingQuestion}
                      />
                      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        Use Ctrl+Enter to ask. Multi-line question papers and mark-based prompts are supported.
                      </p>
                    </div>

                    <div className="flex shrink-0 flex-col gap-2 xl:w-44">
                      <button
                        type="button"
                        onClick={handleRewriteQuestion}
                        disabled={!(question || askedQuestion).trim() || loading || rewritingQuestion}
                        className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
                      >
                        <RefreshCw className={`h-4 w-4 ${rewritingQuestion ? 'animate-spin' : ''}`} />
                        {rewritingQuestion ? 'Rewriting...' : 'Rewrite'}
                      </button>
                      <button
                        type="button"
                        onClick={handleAskQuestion}
                        disabled={!question.trim() || loading || rewritingQuestion}
                        className="btn-primary inline-flex items-center justify-center gap-2 disabled:opacity-50"
                      >
                        <Send className="h-4 w-4" />
                        {loading ? 'Asking...' : 'Ask'}
                      </button>
                    </div>
                  </div>
                </div>

                {askedQuestion ? (
                  <div className="mb-4 rounded-2xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/70">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                          Latest Question
                        </p>
                        <p className="mt-2 whitespace-pre-wrap break-words text-sm text-gray-800 dark:text-gray-100">
                          {askedQuestion}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={handleCopyQuestion}
                          className="inline-flex items-center gap-2 rounded-xl border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-white dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-900"
                        >
                          <Copy className="h-4 w-4" />
                          Copy question
                        </button>
                        <button
                          type="button"
                          onClick={handleRewriteQuestion}
                          disabled={loading || rewritingQuestion}
                          className="inline-flex items-center gap-2 rounded-xl border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-900"
                        >
                          <RefreshCw className={`h-4 w-4 ${rewritingQuestion ? 'animate-spin' : ''}`} />
                          Rewrite question
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}

                <div className="min-h-0 flex-1 rounded-2xl bg-gray-50 p-4 sm:p-6 dark:bg-gray-800">
                  {loading ? (
                    <div className="flex h-full items-center justify-center text-center text-sm text-gray-500 dark:text-gray-400">
                      <p>NOVA AI is preparing the answer and checking for useful diagrams.</p>
                    </div>
                  ) : answer ? (
                    <div className="flex h-full min-h-0 flex-col">
                      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 dark:text-gray-400">
                            Answer
                          </p>
                          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            The answer area now uses the extra space so longer exam answers can breathe.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={handleCopyAnswer}
                          className="inline-flex items-center gap-2 self-start rounded-xl border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-white dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-900"
                        >
                          <Copy className="h-4 w-4" />
                          Copy answer
                        </button>
                      </div>

                      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                        <MarkdownAnswer content={answer} />
                        {answerImages.length > 0 ? (
                          <div className="mt-6 grid gap-4">
                            {answerImages.map((image, index) => (
                              <img
                                key={`${image}-${index}`}
                                src={image}
                                alt={`Answer diagram ${index + 1}`}
                                className="w-full rounded-2xl border border-gray-200 bg-white object-contain shadow-sm dark:border-gray-700"
                                loading="lazy"
                              />
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <div className="flex h-full items-center justify-center text-center text-sm text-gray-500 dark:text-gray-400">
                      <p>Ask a question and the answer will appear here with more space for long-form responses.</p>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex h-full items-center justify-center text-gray-400">
                <p>Select a document to start asking questions.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default DocumentAnalyzer;
