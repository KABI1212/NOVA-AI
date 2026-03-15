// @ts-nocheck
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

function MessageBubble({ message, isTyping = false }) {
  if (isTyping) {
    return (
      <div className="message-row justify-start">
        <div className="typing-bubble">
          <span />
          <span />
          <span />
        </div>
      </div>
    )
  }

  const isUser = message?.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`message-row ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`message-bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
        <ReactMarkdown
          className="markdown-content"
          components={{
            code({ inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '')
              const content = String(children).replace(/\n$/, '')
              if (!inline && match) {
                return (
                  <SyntaxHighlighter
                    style={vscDarkPlus}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{ background: '#0b1120' }}
                    {...props}
                  >
                    {content}
                  </SyntaxHighlighter>
                )
              }
              return (
                <code className="inline-code" {...props}>
                  {children}
                </code>
              )
            },
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </motion.div>
  )
}

export default MessageBubble
