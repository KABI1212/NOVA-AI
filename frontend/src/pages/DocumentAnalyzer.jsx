// @ts-nocheck
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  BookOpen,
  Brain,
  CheckCircle2,
  FileText,
  Files,
  MessageSquare,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  Upload,
  User,
  Volume2,
  VolumeX,
} from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import MarkdownAnswer from '../components/common/MarkdownAnswer';
import { documentAPI } from '../services/api';
import {
  speakText,
  speechSupported as browserSpeechSupported,
  stopSpeechPlayback,
} from '../utils/speech';
import { useDocumentStore } from '../utils/store';

const QUESTION_PRESETS = [
  {
    label: 'Explain simply',
    prompt: 'Explain this document in the simplest possible words, as if teaching a beginner.',
  },
  {
    label: 'Exam answer',
    prompt: 'Write a long exam-style answer from this document with headings, key points, and a strong conclusion.',
  },
  {
    label: 'Compare ideas',
    prompt: 'Create a comparison table from the most important ideas in this document, then add a short explanation.',
  },
  {
    label: 'Revision notes',
    prompt: 'Turn this document into clean revision notes with the most important points, keywords, and memory hooks.',
  },
];

const DOCUMENT_ACCEPT =
  '.pdf,.txt,.docx,.md,.csv,.json,.py,.js,.jsx,.ts,.tsx,.html,.htm,.css,.xml,.yml,.yaml';

const SUPPORTED_DOCUMENT_EXTENSIONS = new Set(
  DOCUMENT_ACCEPT.split(',').map((value) => value.replace('.', '').toLowerCase())
);
const DOCUMENT_LOAD_TOAST_ID = 'documents-load-error';

function formatFileSize(bytes = 0) {
  const size = Number(bytes) || 0;

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDocumentType(document) {
  const rawType = String(document?.file_type || '').trim();

  if (rawType) {
    return rawType.replace(/^application\//i, '').replace(/^text\//i, '').toUpperCase();
  }

  const filename = String(document?.filename || '');
  const extension = filename.includes('.') ? filename.split('.').pop() : 'file';
  return String(extension || 'file').toUpperCase();
}

function isSupportedDocumentFile(file) {
  const filename = String(file?.name || '');
  const extension = filename.includes('.') ? filename.split('.').pop()?.toLowerCase() : '';
  return Boolean(extension && SUPPORTED_DOCUMENT_EXTENSIONS.has(extension));
}

function getUploadErrorMessage(error) {
  if (error?.response?.data?.detail) {
    return error.response.data.detail;
  }

  if (error?.message) {
    return error.message;
  }

  return 'Upload failed';
}

function createDocumentMessage(role, content, extra = {}) {
  return {
    id:
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : String(Date.now() + Math.random()),
    role,
    content,
    images: Array.isArray(extra.images) ? extra.images : [],
    createdAt: extra.createdAt || new Date().toISOString(),
    ...extra,
  };
}

function formatMessageTime(value) {
  if (!value) {
    return '';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }

  return parsed.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function buildInitialDocumentSession(documentId, introMessage) {
  return {
    askedQuestion: '',
    answer: '',
    answerImages: [],
    answerMode: 'idle',
    messages: [
      createDocumentMessage('assistant', introMessage, {
        documentId,
        mode: 'intro',
      }),
    ],
  };
}

function buildDocumentIntroMessage(document, summary, isReady) {
  const filename = String(document?.filename || 'this document').trim() || 'this document';

  if (!isReady) {
    return `I uploaded **${filename}**, but I still need readable text before I can answer from it.\n\n${summary || 'Try a text-based PDF, DOCX, TXT, Markdown, or code file.'}`;
  }

  if (summary) {
    return `I have read **${filename}**. Here is a quick overview:\n\n${summary}\n\nAsk me anything about this document and I will answer like a study chatbot.`;
  }

  return `I have loaded **${filename}** and it is ready.\n\nAsk me anything about this document and I will answer like a study chatbot.`;
}

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
  const fileInputRef = useRef(null);
  const chatBottomRef = useRef(null);
  const documentSessionsRef = useRef({});
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [question, setQuestion] = useState('');
  const [askedQuestion, setAskedQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [answerImages, setAnswerImages] = useState([]);
  const [documentMessages, setDocumentMessages] = useState([]);
  const [answerMode, setAnswerMode] = useState('idle');
  const [loading, setLoading] = useState(false);
  const [rewritingQuestion, setRewritingQuestion] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);
  const documentCount = documents.length;
  const processedCount = documents.filter((doc) => doc.is_processed).length;
  const attentionCount = Math.max(documentCount - processedCount, 0);
  const selectedDocumentReady = Boolean(currentDocument?.is_processed);
  const currentSummary = currentDocument?.summary?.trim() || '';
  const activeQuestionText = (question || askedQuestion).trim();
  const introMessage =
    currentDocument ? buildDocumentIntroMessage(currentDocument, currentSummary, selectedDocumentReady) : '';
  const questionCount = documentMessages.reduce((count, message) => count + (message.role === 'user' ? 1 : 0), 0);
  const hasConversationBeyondIntro = questionCount > 0;

  const loadDocuments = useCallback(async ({ silent = false, retry = false } = {}) => {
    try {
      const response = await documentAPI.getDocuments();
      toast.dismiss(DOCUMENT_LOAD_TOAST_ID);
      setDocuments(response.data);
      return response.data;
    } catch (error) {
      if (retry) {
        window.setTimeout(() => {
          loadDocuments({ silent: true });
        }, 900);
      }

      if (!silent) {
        toast.error(error.response?.data?.detail || error.message || 'Failed to load documents', {
          id: DOCUMENT_LOAD_TOAST_ID,
        });
      }
      return [];
    }
  }, [setDocuments]);

  useEffect(() => {
    loadDocuments({ retry: true });
  }, [loadDocuments]);

  useEffect(() => {
    if (!currentDocument) {
      setAskedQuestion('');
      setAnswer('');
      setAnswerImages([]);
      setAnswerMode('idle');
      setDocumentMessages([]);
      return;
    }

    const existingSession = documentSessionsRef.current[currentDocument.id];
    const nextSession = existingSession
      ? {
          ...buildInitialDocumentSession(currentDocument.id, introMessage),
          ...existingSession,
          answerImages: Array.isArray(existingSession.answerImages) ? existingSession.answerImages : [],
          messages:
            Array.isArray(existingSession.messages) && existingSession.messages.length
              ? existingSession.messages.length === 1 && existingSession.messages[0]?.role === 'assistant'
                ? [
                    {
                      ...existingSession.messages[0],
                      content: introMessage,
                      documentId: currentDocument.id,
                    },
                  ]
                : existingSession.messages
              : buildInitialDocumentSession(currentDocument.id, introMessage).messages,
        }
      : buildInitialDocumentSession(currentDocument.id, introMessage);

    documentSessionsRef.current[currentDocument.id] = nextSession;
    setAskedQuestion(nextSession.askedQuestion || '');
    setAnswer(nextSession.answer || '');
    setAnswerImages(nextSession.answerImages || []);
    setAnswerMode(nextSession.answerMode || 'idle');
    setDocumentMessages(nextSession.messages);
  }, [currentDocument, introMessage]);

  useEffect(() => {
    if (!currentDocument?.id) {
      return;
    }

    documentSessionsRef.current[currentDocument.id] = {
      askedQuestion,
      answer,
      answerImages,
      answerMode,
      messages: documentMessages,
    };
  }, [currentDocument?.id, askedQuestion, answer, answerImages, answerMode, documentMessages]);

  useEffect(() => {
    const validDocumentIds = new Set(documents.map((doc) => doc.id));
    Object.keys(documentSessionsRef.current).forEach((documentId) => {
      if (!validDocumentIds.has(Number(documentId))) {
        delete documentSessionsRef.current[documentId];
      }
    });
  }, [documents]);

  useEffect(() => {
    if (!documents.length) {
      if (currentDocument) {
        setCurrentDocument(null);
      }
      return;
    }

    if (!currentDocument) {
      setCurrentDocument(documents[0]);
      return;
    }

    const matchingDocument = documents.find((doc) => doc.id === currentDocument.id);
    if (!matchingDocument) {
      setCurrentDocument(documents[0]);
      return;
    }

    if (matchingDocument !== currentDocument) {
      setCurrentDocument(matchingDocument);
    }
  }, [currentDocument, documents, setCurrentDocument]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [documentMessages, loading]);

  const stopSpeaking = useCallback(() => {
    stopSpeechPlayback();
    setSpeakingMessageId(null);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    setSpeechSupported(browserSpeechSupported());

    return () => {
      stopSpeaking();
    };
  }, [stopSpeaking]);

  const handleSpeakMessage = useCallback(
    (message) => {
      if (!speechSupported || !message?.content || message.role === 'user') {
        return;
      }

      if (speakingMessageId === message.id) {
        stopSpeaking();
        return;
      }

      const started = speakText(message.content, {
        onStart: () => {
          setSpeakingMessageId(message.id);
        },
        onEnd: () => {
          setSpeakingMessageId((current) => (current === message.id ? null : current));
        },
        onError: () => {
          setSpeakingMessageId((current) => (current === message.id ? null : current));
        },
      });

      if (!started) {
        setSpeakingMessageId(null);
      }
    },
    [speechSupported, speakingMessageId, stopSpeaking]
  );

  const triggerFilePicker = () => {
    if (!uploading) {
      fileInputRef.current?.click();
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!isSupportedDocumentFile(file)) {
      toast.error('Unsupported file type. Use PDF, DOCX, TXT, Markdown, CSV, JSON, HTML, XML, YAML, or code files.');
      e.target.value = '';
      return;
    }

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
      await loadDocuments({ silent: true });
      setCurrentDocument(response.data);
      setQuestion('');
      setAskedQuestion('');
      setAnswer('');
      setAnswerImages([]);
      toast.success('Document uploaded successfully!');
    } catch (error) {
      toast.error(getUploadErrorMessage(error));
    } finally {
      setUploading(false);
      setUploadProgress(0);
      e.target.value = '';
    }
  };

  const handleDelete = async (id) => {
    try {
      await documentAPI.deleteDocument(id);
      delete documentSessionsRef.current[id];
      const nextDocuments = documents.filter((doc) => doc.id !== id);
      setDocuments(nextDocuments);
      await loadDocuments({ silent: true });
      if (currentDocument?.id === id) {
        stopSpeaking();
        setCurrentDocument(nextDocuments[0] || null);
        setAskedQuestion('');
        setAnswer('');
        setAnswerImages([]);
        setAnswerMode('idle');
      }
      toast.success('Document deleted');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete document');
    }
  };

  const handleClearChat = useCallback(() => {
    if (!currentDocument) {
      return;
    }

    stopSpeaking();
    const resetSession = buildInitialDocumentSession(currentDocument.id, introMessage);
    documentSessionsRef.current[currentDocument.id] = resetSession;
    setQuestion('');
    setAskedQuestion('');
    setAnswer('');
    setAnswerImages([]);
    setAnswerMode('idle');
    setDocumentMessages(resetSession.messages);
    toast.success('Document chat cleared');
  }, [currentDocument, introMessage, stopSpeaking]);

  const handleAskQuestion = async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || !currentDocument) return;

    stopSpeaking();
    const userMessage = createDocumentMessage('user', trimmedQuestion, {
      documentId: currentDocument.id,
    });
    setDocumentMessages((previous) => [...previous, userMessage]);
    setLoading(true);
    setAskedQuestion(trimmedQuestion);
    setAnswer('');
    setAnswerImages([]);
    setAnswerMode('idle');
    setQuestion('');
    try {
      const response = await documentAPI.askQuestion({
        document_id: currentDocument.id,
        question: trimmedQuestion,
      });
      const nextQuestion = response.data.question || trimmedQuestion;
      const nextAnswer = response.data.answer || 'I could not find a good answer in this document.';
      const nextAnswerImages = Array.isArray(response.data.answer_images) ? response.data.answer_images : [];
      const nextAnswerMode = response.data.answer_mode || 'ai';

      setAskedQuestion(nextQuestion);
      setAnswer(nextAnswer);
      setAnswerImages(nextAnswerImages);
      setAnswerMode(nextAnswerMode);
      setDocumentMessages((previous) => [
        ...previous,
        createDocumentMessage('assistant', nextAnswer, {
          images: nextAnswerImages,
          documentId: currentDocument.id,
          mode: nextAnswerMode,
        }),
      ]);
      if (nextAnswerMode === 'fallback') {
        toast.success('Using document fallback mode for this answer.');
      }
    } catch (error) {
      const detail = error.response?.data?.detail || 'Failed to get answer';
      toast.error(detail);
      setAnswerMode('error');
      setDocumentMessages((previous) => [
        ...previous,
        createDocumentMessage('assistant', `I could not answer from this document right now.\n\n${detail}`, {
          documentId: currentDocument.id,
          mode: 'error',
        }),
      ]);
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
      const rewriteMode = response.data?.rewrite_mode || 'ai';
      if (!rewrittenQuestion) {
        throw new Error('No rewritten question returned');
      }
      setQuestion(rewrittenQuestion);
      toast.success(
        rewriteMode === 'fallback'
          ? 'Question cleaned locally. Ask again when ready.'
          : 'Question rewritten. Ask again when ready.'
      );
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

  const shellClass =
    'rounded-[28px] border border-white/10 bg-[#10192a]/92 shadow-[0_24px_60px_rgba(2,8,23,0.35)]';
  const subtleClass = 'rounded-[22px] border border-white/10 bg-white/[0.04]';
  const labelClass = 'text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400';

  const renderLibrary = () => (
    <aside className={`${shellClass} flex min-h-0 flex-col overflow-hidden`}>
      <div className="border-b border-white/10 p-5">
        <div className="inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-100">
          <Files className="h-3.5 w-3.5" />
          Library
        </div>
        <h2 className="mt-4 text-2xl font-semibold text-white">Documents</h2>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          Upload a file, switch the active source, and keep your study material within reach.
        </p>

        <div className="mt-5 grid grid-cols-3 gap-3">
          <div className={`${subtleClass} px-3 py-3`}>
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Files</p>
            <p className="mt-2 text-2xl font-semibold text-white">{documentCount}</p>
          </div>
          <div className="rounded-[22px] border border-emerald-400/15 bg-emerald-500/10 px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-emerald-100/70">Ready</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-100">{processedCount}</p>
          </div>
          <div className="rounded-[22px] border border-amber-400/15 bg-amber-500/10 px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.18em] text-amber-100/70">Review</p>
            <p className="mt-2 text-2xl font-semibold text-amber-100">{attentionCount}</p>
          </div>
        </div>
      </div>

      <div className="p-5">
        <button
          type="button"
          onClick={triggerFilePicker}
          disabled={uploading}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-cyan-500 to-teal-500 px-4 py-4 text-sm font-semibold text-white shadow-[0_18px_36px_rgba(14,165,233,0.25)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Upload className="h-4 w-4" />
          {uploading ? 'Uploading document...' : 'Add New Document'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept={DOCUMENT_ACCEPT}
          onChange={handleUpload}
          className="hidden"
          disabled={uploading}
        />

        {uploading ? (
          <div className={`${subtleClass} mt-4 p-4`}>
            <div className="mb-2 flex items-center justify-between text-xs text-slate-300">
              <span>Processing your file</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-400 to-teal-400 transition-all duration-200"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        ) : null}

        <div className={`${subtleClass} mt-4 p-4`}>
          <p className={labelClass}>Current Focus</p>
          {currentDocument ? (
            <>
              <p className="mt-2 break-words text-base font-semibold text-white">{currentDocument.filename}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold text-slate-200">
                  {formatFileSize(currentDocument.file_size)}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold text-slate-200">
                  {formatDocumentType(currentDocument)}
                </span>
                <span
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
                    selectedDocumentReady
                      ? 'border border-emerald-400/20 bg-emerald-500/12 text-emerald-100'
                      : 'border border-amber-400/20 bg-amber-500/12 text-amber-100'
                  }`}
                >
                  {selectedDocumentReady ? 'Answer-ready' : 'Needs review'}
                </span>
              </div>
            </>
          ) : (
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Select a document from the list or upload a new one to begin a document chat.
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between px-5 pb-3">
        <div>
          <h4 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">Files</h4>
          <p className="mt-1 text-xs text-slate-500">Choose which document powers the workspace.</p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200">
          {documentCount}
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
        {documents.length ? (
          <div className="space-y-3">
            {documents.map((doc) => {
              const isActive = currentDocument?.id === doc.id;

              return (
                <div
                  key={doc.id}
                  className={`group cursor-pointer rounded-[24px] border p-4 transition ${
                    isActive
                      ? 'border-sky-300/30 bg-[linear-gradient(180deg,rgba(14,165,233,0.18),rgba(17,24,39,0.12))]'
                      : 'border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]'
                  }`}
                  onClick={() => setCurrentDocument(doc)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start gap-3">
                        <div className={`rounded-2xl p-2 ${isActive ? 'bg-sky-400/15 text-sky-100' : 'bg-white/5 text-slate-300'}`}>
                          <FileText className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold text-white">{doc.filename}</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">
                              {formatFileSize(doc.file_size)}
                            </span>
                            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">
                              {formatDocumentType(doc)}
                            </span>
                            <span
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                                doc.is_processed
                                  ? 'border border-emerald-400/20 bg-emerald-500/12 text-emerald-100'
                                  : 'border border-amber-400/20 bg-amber-500/12 text-amber-100'
                              }`}
                            >
                              {doc.is_processed ? 'Ready' : 'Needs review'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(doc.id);
                      }}
                      className="rounded-2xl border border-transparent p-2 text-slate-500 opacity-0 transition group-hover:opacity-100 hover:border-red-400/20 hover:bg-red-500/10 hover:text-red-200"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-[24px] border border-dashed border-white/15 bg-white/[0.03] px-5 py-8 text-center">
            <p className="text-base font-semibold text-white">Your library is empty.</p>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Upload notes, question papers, study material, or code files to start building answers.
            </p>
          </div>
        )}
      </div>
    </aside>
  );

  const renderContextPanel = () => (
    <div className="flex min-h-0 flex-col gap-5">
      <div className={`${shellClass} flex min-h-[300px] flex-col p-5`}>
        <div className="flex items-start gap-3">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-sky-100">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <p className={labelClass}>Document Brief</p>
            <h3 className="mt-2 text-xl font-semibold text-white">Summary</h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Use this as a refresher before sending the next question.
            </p>
          </div>
        </div>

        <div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-1">
          {currentSummary ? (
            <MarkdownAnswer content={currentSummary} className="text-[15px] text-slate-100" />
          ) : (
            <div className="flex h-full items-center justify-center rounded-[22px] border border-dashed border-white/15 bg-white/[0.03] px-4 text-center">
              <p className="text-sm leading-6 text-slate-400">A summary is not available yet for this file.</p>
            </div>
          )}
        </div>
      </div>

      <div className={`${shellClass} p-5`}>
        <p className={labelClass}>Quick Prompts</p>
        <h3 className="mt-2 text-xl font-semibold text-white">Start faster</h3>
        <div className="mt-4 grid gap-3">
          {QUESTION_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => setQuestion(preset.prompt)}
              disabled={!selectedDocumentReady}
              className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-4 text-left transition hover:border-sky-300/25 hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <p className="text-sm font-semibold text-white">{preset.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">Load into the chat composer.</p>
            </button>
          ))}
        </div>
      </div>

      <div className={`${shellClass} p-5`}>
        <p className={labelClass}>{selectedDocumentReady ? 'Latest Question' : 'Document Status'}</p>
        {selectedDocumentReady ? (
          <>
            <div className="mt-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-base font-semibold text-white">{askedQuestion || 'No question asked yet'}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {hasConversationBeyondIntro
                    ? `${questionCount} question${questionCount === 1 ? '' : 's'} in this document chat`
                    : 'Start the first question to build this study thread'}
                </p>
              </div>
              {hasConversationBeyondIntro ? (
                <button
                  type="button"
                  onClick={handleClearChat}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/[0.08]"
                >
                  Clear chat
                </button>
              ) : null}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleCopyQuestion}
                disabled={!activeQuestionText}
                className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Copy question
              </button>
              <button
                type="button"
                onClick={handleRewriteQuestion}
                disabled={!activeQuestionText || loading || rewritingQuestion}
                className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {rewritingQuestion ? 'Rewriting...' : 'Rewrite question'}
              </button>
              <button
                type="button"
                onClick={handleCopyAnswer}
                disabled={!answer.trim()}
                className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Copy answer
              </button>
            </div>
          </>
        ) : (
          <div className="mt-3 rounded-[22px] border border-amber-400/15 bg-amber-500/10 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-100" />
              <p className="text-sm leading-6 text-amber-50">
                This document needs readable text before the chat can answer from it. Try a text-based PDF, DOCX, TXT,
                Markdown, or code file.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const renderChatWorkspace = () => (
    <div className={`${shellClass} flex min-h-[720px] flex-col overflow-hidden`}>
      <div className="border-b border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.92),rgba(12,20,34,0.84))] px-5 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl border border-cyan-300/15 bg-cyan-400/10 p-3 text-cyan-100">
              <MessageSquare className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className={labelClass}>Document Chat</p>
              <h2 className="mt-2 break-words text-2xl font-semibold text-white">Chat with your file</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                Your questions and the document-backed answers now stay together like a chatbot thread.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-semibold text-slate-200">
                  {formatFileSize(currentDocument.file_size)}
                </span>
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-semibold text-slate-200">
                  {formatDocumentType(currentDocument)}
                </span>
                <span
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
                    selectedDocumentReady
                      ? 'border border-emerald-400/20 bg-emerald-500/12 text-emerald-100'
                      : 'border border-amber-400/20 bg-amber-500/12 text-amber-100'
                  }`}
                >
                  {selectedDocumentReady ? 'Ready to chat' : 'Needs readable text'}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {hasConversationBeyondIntro ? (
              <button
                type="button"
                onClick={handleClearChat}
                className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/[0.08]"
              >
                Clear chat
              </button>
            ) : null}

            <span
              className={`inline-flex items-center gap-2 self-start rounded-full px-3 py-2 text-xs font-semibold ${
                loading
                  ? 'border border-sky-300/20 bg-sky-500/12 text-sky-100'
                  : answerMode === 'fallback'
                    ? 'border border-amber-300/20 bg-amber-500/12 text-amber-100'
                    : answer
                      ? 'border border-emerald-400/20 bg-emerald-500/12 text-emerald-100'
                      : 'border border-white/10 bg-white/[0.04] text-slate-200'
              }`}
            >
              {loading ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : answerMode === 'fallback' ? (
                <AlertTriangle className="h-3.5 w-3.5" />
              ) : answer ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              {loading
                ? 'Answering'
                : answerMode === 'fallback'
                  ? 'Document fallback mode'
                  : answer
                    ? 'Last answer ready'
                    : 'Waiting for question'}
            </span>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div className="space-y-5">
          {selectedDocumentReady && !hasConversationBeyondIntro ? (
            <div className={`${subtleClass} grid gap-3 p-4 md:grid-cols-2`}>
              {QUESTION_PRESETS.map((preset) => (
                <button
                  key={`chat-${preset.label}`}
                  type="button"
                  onClick={() => setQuestion(preset.prompt)}
                  className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-4 text-left transition hover:border-cyan-300/25 hover:bg-white/[0.06]"
                >
                  <p className="text-sm font-semibold text-white">{preset.label}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-400">Start this chat angle instantly.</p>
                </button>
              ))}
            </div>
          ) : null}

          {documentMessages.map((message) => {
            const isUser = message.role === 'user';

            return (
              <div key={message.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div className={`flex w-full max-w-4xl items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border ${
                      isUser
                        ? 'border-cyan-300/20 bg-cyan-400/12 text-cyan-100'
                        : 'border-sky-300/20 bg-sky-400/10 text-sky-100'
                    }`}
                  >
                    {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>

                  <div
                    className={`max-w-[85%] rounded-[24px] border px-4 py-4 ${
                      isUser
                        ? 'border-cyan-300/20 bg-[linear-gradient(180deg,rgba(34,211,238,0.16),rgba(8,47,73,0.28))] text-white'
                        : 'border-white/10 bg-[#0c1422] text-slate-100'
                    }`}
                  >
                    <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                      <span>{isUser ? 'You' : 'NOVA'}</span>
                      {formatMessageTime(message.createdAt) ? <span>{formatMessageTime(message.createdAt)}</span> : null}
                      {!isUser && message.mode === 'fallback' ? (
                        <span className="rounded-full border border-amber-300/20 bg-amber-500/12 px-2 py-0.5 text-[10px] text-amber-100">
                          Fallback
                        </span>
                      ) : null}
                    </div>

                    {isUser ? (
                      <p className="whitespace-pre-wrap text-sm leading-7 text-white">{message.content}</p>
                    ) : (
                      <MarkdownAnswer content={message.content} className="text-[15px] text-slate-100" />
                    )}

                    {Array.isArray(message.images) && message.images.length > 0 ? (
                      <div className="mt-4 grid gap-4 xl:grid-cols-2">
                        {message.images.map((image, index) => (
                          <img
                            key={`${message.id}-${index}`}
                            src={image}
                            alt={`Answer diagram ${index + 1}`}
                            className="w-full rounded-[20px] border border-white/10 bg-[#09111d] object-contain"
                            loading="lazy"
                          />
                        ))}
                      </div>
                    ) : null}

                    {!isUser && message.content?.trim() ? (
                      <div className="mt-4 flex items-center justify-end border-t border-white/10 pt-3">
                        <button
                          type="button"
                          onClick={() => handleSpeakMessage(message)}
                          disabled={!speechSupported}
                          className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold transition ${
                            speakingMessageId === message.id
                              ? 'border-sky-300/30 bg-sky-400/10 text-sky-100'
                              : 'border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]'
                          } disabled:cursor-not-allowed disabled:opacity-50`}
                        >
                          {speakingMessageId === message.id ? (
                            <VolumeX className="h-3.5 w-3.5" />
                          ) : (
                            <Volume2 className="h-3.5 w-3.5" />
                          )}
                          {speakingMessageId === message.id ? 'Stop' : 'Speak'}
                        </button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}

          {loading ? (
            <div className="flex justify-start">
              <div className="flex w-full max-w-4xl items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-sky-300/20 bg-sky-400/10 text-sky-100">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="rounded-[24px] border border-white/10 bg-[#0c1422] px-4 py-4 text-slate-100">
                  <div className="flex items-center gap-2 text-sm text-slate-300">
                    <RefreshCw className="h-4 w-4 animate-spin text-sky-200" />
                    NOVA is reading the document and preparing the reply...
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          <div ref={chatBottomRef} />
        </div>
      </div>

      <div className="border-t border-white/10 bg-[#0b1422]/55 p-5">
        <div className="rounded-[24px] border border-white/10 bg-[#0a1220] p-4">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleQuestionKeyDown}
            placeholder="Ask a question about this document, paste a question paper, or request structured notes."
            className="min-h-[140px] w-full resize-y bg-transparent text-[15px] leading-7 text-slate-100 outline-none placeholder:text-slate-500"
            disabled={!selectedDocumentReady || loading || rewritingQuestion}
          />

          <div className="mt-4 flex flex-col gap-4 border-t border-white/10 pt-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-200">
                {selectedDocumentReady
                  ? 'Use Ctrl+Enter to ask instantly.'
                  : 'Upload a text-readable document to unlock the chat composer.'}
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Multi-line prompts, long exam-style instructions, and revision-note requests are supported.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleRewriteQuestion}
                disabled={!selectedDocumentReady || !activeQuestionText || loading || rewritingQuestion}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${rewritingQuestion ? 'animate-spin' : ''}`} />
                {rewritingQuestion ? 'Rewriting...' : 'Rewrite question'}
              </button>
              <button
                type="button"
                onClick={handleAskQuestion}
                disabled={!selectedDocumentReady || !question.trim() || loading || rewritingQuestion}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 to-cyan-500 px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_36px_rgba(14,165,233,0.22)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                {loading ? 'Asking NOVA...' : 'Ask NOVA'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderWorkspace = () => {
    if (!currentDocument) {
      return (
        <div className={`${shellClass} flex h-full min-h-[620px] items-center justify-center p-8 sm:p-10`}>
          <div className="max-w-3xl text-center">
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[28px] border border-sky-300/20 bg-sky-500/10 text-sky-100">
              <Files className="h-9 w-9" />
            </div>
            <p className="mt-6 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">Document Workspace</p>
            <h2 className="mt-3 text-3xl font-semibold text-white sm:text-4xl">
              Turn one document into a focused study chat.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-400 sm:text-[15px]">
              Upload a file from the library rail, select it as the current focus, then ask for explanations, exam
              answers, comparison tables, or revision notes in the chat workspace.
            </p>

            <div className="mt-8 grid gap-4 text-left sm:grid-cols-3">
              <div className={`${subtleClass} p-4`}>
                <p className={labelClass}>1. Upload</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Add a PDF, DOCX, TXT, Markdown file, or source file from the library rail.
                </p>
              </div>
              <div className={`${subtleClass} p-4`}>
                <p className={labelClass}>2. Review</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Use the summary and quick prompts to decide how you want NOVA to answer.
                </p>
              </div>
              <div className={`${subtleClass} p-4`}>
                <p className={labelClass}>3. Chat</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Ask questions naturally and keep the full back-and-forth in one conversation thread.
                </p>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="grid min-h-full gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-h-0 flex-col gap-6">
          <div className="relative overflow-hidden rounded-[30px] border border-sky-300/15 bg-[linear-gradient(135deg,rgba(17,24,39,0.96),rgba(17,69,89,0.92))] p-6 shadow-[0_28px_70px_rgba(2,8,23,0.34)] sm:p-7">
            <div className="absolute inset-y-0 right-0 w-1/2 bg-[radial-gradient(circle_at_top_right,rgba(45,212,191,0.16),transparent_55%)]" />
            <div className="relative flex flex-col gap-6">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-3xl">
                  <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-100">
                    <Brain className="h-3.5 w-3.5" />
                    Answer Studio
                  </div>
                  <h1 className="mt-4 break-words text-3xl font-semibold tracking-tight text-white sm:text-[2.5rem]">
                    {currentDocument.filename}
                  </h1>
                  <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-200 sm:text-[15px]">
                    Keep one document in focus, ask natural questions, and turn the source into explanations,
                    structured notes, or exam-ready answers without leaving the workspace.
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[320px]">
                  <div className="rounded-[22px] border border-white/10 bg-white/[0.06] p-4 backdrop-blur">
                    <p className={labelClass}>File Size</p>
                    <p className="mt-2 text-xl font-semibold text-white">{formatFileSize(currentDocument.file_size)}</p>
                  </div>
                  <div className="rounded-[22px] border border-white/10 bg-white/[0.06] p-4 backdrop-blur">
                    <p className={labelClass}>Type</p>
                    <p className="mt-2 text-xl font-semibold text-white">{formatDocumentType(currentDocument)}</p>
                  </div>
                  <div className="rounded-[22px] border border-white/10 bg-white/[0.06] p-4 backdrop-blur">
                    <p className={labelClass}>Question Flow</p>
                    <p className="mt-2 text-xl font-semibold text-white">{questionCount}</p>
                  </div>
                  <div className="rounded-[22px] border border-white/10 bg-white/[0.06] p-4 backdrop-blur">
                    <p className={labelClass}>Status</p>
                    <p className={`mt-2 text-xl font-semibold ${selectedDocumentReady ? 'text-emerald-100' : 'text-amber-100'}`}>
                      {selectedDocumentReady ? 'Ready to chat' : 'Needs review'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {QUESTION_PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => setQuestion(preset.prompt)}
                    disabled={!selectedDocumentReady}
                    className="rounded-[22px] border border-white/10 bg-[#081120]/35 px-4 py-4 text-left transition hover:border-cyan-300/25 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <p className="text-sm font-semibold text-white">{preset.label}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-300">Load this prompt straight into the composer.</p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {renderChatWorkspace()}
        </div>

        <div className="min-h-0">{renderContextPanel()}</div>
      </div>
    );
  };

  return (
    <Layout>
      <div className="h-full overflow-y-auto bg-[#0b1422] text-slate-100 xl:overflow-hidden">
        <div className="min-h-full bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.16),transparent_30%),radial-gradient(circle_at_top_right,rgba(34,197,94,0.1),transparent_24%),linear-gradient(180deg,#101b2d_0%,#0c1626_48%,#0b1422_100%)] p-4 sm:p-6 xl:h-full">
          <div className="grid min-h-full gap-6 xl:h-full xl:grid-cols-[320px_minmax(0,1fr)]">
            {renderLibrary()}
            <section className="min-h-0">{renderWorkspace()}</section>
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default DocumentAnalyzer;
