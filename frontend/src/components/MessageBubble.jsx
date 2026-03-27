// @ts-nocheck
import { motion } from 'framer-motion'
import MarkdownAnswer from './common/MarkdownAnswer'

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
        <MarkdownAnswer content={message.content} />
      </div>
    </motion.div>
  )
}

export default MessageBubble
