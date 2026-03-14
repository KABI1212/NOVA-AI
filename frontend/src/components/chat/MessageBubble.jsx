import { motion } from 'framer-motion';
import { Bot, User, Copy, Check, Sparkles, Bookmark, Volume2, VolumeX } from 'lucide-react';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import toast from 'react-hot-toast';

function MessageBubble({
  message,
  isTyping,
  onExplain,
  onSave,
  onSpeak,
  onStopSpeak,
  isSpeaking,
}) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success('Copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  if (isTyping) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start gap-4 p-4"
      >
        <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
          <Bot className="w-5 h-5 text-white" />
        </div>
        <div className="flex gap-1 mt-2">
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </motion.div>
    );
  }

  const isUser = message?.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex items-start p-4 ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`flex items-start gap-4 max-w-4xl w-full ${isUser ? 'flex-row-reverse' : ''}`}>
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isUser ? 'bg-gray-300 dark:bg-gray-600' : 'bg-primary-600'
          }`}
        >
          {isUser ? (
            <User className="w-5 h-5 text-gray-700 dark:text-gray-300" />
          ) : (
            <Bot className="w-5 h-5 text-white" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div
            className={`rounded-2xl px-4 py-3 ${
              isUser
                ? 'bg-primary-600 text-white'
                : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
            }`}
          >
            <div
              className={`markdown-content prose max-w-none ${
                isUser ? 'text-white prose-invert' : 'dark:prose-invert'
              }`}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const codeString = String(children).replace(/\n$/, '');

                    if (!inline && match) {
                      return (
                        <div className="relative group">
                          <button
                            onClick={() => copyToClipboard(codeString)}
                            className="absolute right-2 top-2 p-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            {copied ? (
                              <Check className="w-4 h-4" />
                            ) : (
                              <Copy className="w-4 h-4" />
                            )}
                          </button>
                          <SyntaxHighlighter
                            style={vscDarkPlus}
                            language={match[1]}
                            PreTag="div"
                            customStyle={{
                              fontFamily: 'Times New Roman, Times, serif',
                              fontStyle: 'italic',
                              fontSize: '0.9rem',
                            }}
                            {...props}
                          >
                            {codeString}
                          </SyntaxHighlighter>
                        </div>
                      );
                    }

                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>

            {message.images?.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                {message.images.map((img, idx) => {
                  const src = img.startsWith('data:') || img.startsWith('http')
                    ? img
                    : `data:image/png;base64,${img}`;
                  return (
                    <img
                      key={`${idx}-${img.slice(0, 12)}`}
                      src={src}
                      alt="Generated"
                      className="w-full rounded-lg border border-gray-200 dark:border-gray-700"
                    />
                  );
                })}
              </div>
            )}
          </div>

          {!isUser && (
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
              <button
                onClick={() => copyToClipboard(message.content)}
                className="hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
              >
                {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
              <button
                onClick={() => onExplain?.(message.content)}
                className="hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
              >
                <Sparkles className="w-3 h-3" />
                Explain
              </button>
              <button
                onClick={() => onSave?.(message.content)}
                className="hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
              >
                <Bookmark className="w-3 h-3" />
                Save
              </button>
              {isSpeaking ? (
                <button
                  onClick={() => onStopSpeak?.()}
                  className="hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
                >
                  <VolumeX className="w-3 h-3" />
                  Stop
                </button>
              ) : (
                <button
                  onClick={() => onSpeak?.(message.content)}
                  className="hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
                >
                  <Volume2 className="w-3 h-3" />
                  Speak
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default MessageBubble;
