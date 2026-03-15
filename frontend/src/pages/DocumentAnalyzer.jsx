// @ts-nocheck
import { useState, useEffect } from 'react';
import { Upload, FileText, Trash2, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import Layout from '../components/common/Layout';
import { documentAPI } from '../services/api';
import { useDocumentStore } from '../utils/store';

function DocumentAnalyzer() {
  const { documents, currentDocument, setDocuments, setCurrentDocument, addDocument } = useDocumentStore();
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

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
    try {
      const response = await documentAPI.upload(formData);
      addDocument(response.data);
      toast.success('Document uploaded successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await documentAPI.deleteDocument(id);
      setDocuments(documents.filter((doc) => doc.id !== id));
      if (currentDocument?.id === id) {
        setCurrentDocument(null);
        setAnswer('');
      }
      toast.success('Document deleted');
    } catch (error) {
      toast.error('Failed to delete document');
    }
  };

  const handleAskQuestion = async () => {
    if (!question.trim() || !currentDocument) return;

    setLoading(true);
    try {
      const response = await documentAPI.askQuestion({
        document_id: currentDocument.id,
        question,
      });
      setAnswer(response.data.answer);
    } catch (error) {
      toast.error('Failed to get answer');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="h-full grid grid-cols-3 gap-6 p-6">
        {/* Documents List */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">Documents</h3>

          <label className="btn-primary w-full cursor-pointer flex items-center justify-center gap-2 mb-4">
            <Upload className="w-4 h-4" />
            {uploading ? 'Uploading...' : 'Upload Document'}
            <input
              type="file"
              accept=".pdf,.txt"
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>

          <div className="space-y-2 overflow-y-auto max-h-[calc(100vh-16rem)]">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className={`group p-3 rounded-lg cursor-pointer transition-colors ${
                  currentDocument?.id === doc.id
                    ? 'bg-primary-100 dark:bg-primary-900'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                onClick={() => setCurrentDocument(doc)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <FileText className="w-4 h-4 text-primary-600 flex-shrink-0" />
                      <span className="text-sm font-medium truncate">
                        {doc.filename}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {(doc.file_size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(doc.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 dark:hover:bg-red-900/20 rounded"
                  >
                    <Trash2 className="w-4 h-4 text-red-600" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Document Summary */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">Summary</h3>
          {currentDocument ? (
            <div className="prose dark:prose-invert max-w-none">
              <p className="text-sm text-gray-700 dark:text-gray-300">
                {currentDocument.summary || 'Processing...'}
              </p>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              <p>Select a document to view summary</p>
            </div>
          )}
        </div>

        {/* Q&A */}
        <div className="card p-6 flex flex-col">
          <h3 className="text-lg font-semibold mb-4">Ask Questions</h3>

          {currentDocument ? (
            <>
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleAskQuestion()}
                  placeholder="Ask a question about this document..."
                  className="input-field flex-1"
                  disabled={loading}
                />
                <button
                  onClick={handleAskQuestion}
                  disabled={!question.trim() || loading}
                  className="btn-primary disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>

              {answer && (
                <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                    {answer}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              <p>Select a document to ask questions</p>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

export default DocumentAnalyzer;
