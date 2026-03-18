// @ts-nocheck
import { useEffect, useRef, useState } from 'react'
import { sendMessage } from '../services/api'
import MessageBubble from './MessageBubble'

const createId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`

function ChatUI() {
  const [messages, setMessages] = useState([
    {
      id: createId(),
      role: 'assistant',
      content: 'Hello, I am NOVA AI. Ask me anything.',
    },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  const streamAnswer = (id, text) =>
    new Promise((resolve) => {
      let index = 0
      if (!text) {
        setIsStreaming(false)
        resolve()
        return
      }

      setIsStreaming(true)
      const timer = setInterval(() => {
        index += 1
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === id ? { ...msg, content: text.slice(0, index) } : msg
          )
        )
        if (index >= text.length) {
          clearInterval(timer)
          setIsStreaming(false)
          resolve()
        }
      }, 12)
    })

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return

    const userMessage = {
      id: createId(),
      role: 'user',
      content: trimmed,
    }
    const assistantId = createId()
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: 'assistant', content: '' },
    ])
    setInput('')

    const answer = await sendMessage(trimmed)
    await streamAnswer(assistantId, answer)
  }

  return (
    <div className="chat-shell">
      <div className="chat-header">
        <div>
          <p className="text-sm text-gray-400">NOVA AI</p>
          <h1 className="text-2xl font-semibold text-white">Chat</h1>
        </div>
        <div className="text-xs text-gray-400">Streaming responses enabled</div>
      </div>

      <div className="chat-window">
        <div className="chat-messages">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {isStreaming &&
            messages[messages.length - 1]?.role === 'assistant' &&
            !messages[messages.length - 1]?.content && <MessageBubble isTyping />}
          <div ref={endRef} />
        </div>
      </div>

      <div className="chat-input">
        <textarea
          className="chat-textarea"
          placeholder="Type your message..."
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              handleSend()
            }
          }}
          rows={2}
          disabled={isStreaming}
        />
        <button className="chat-send" onClick={handleSend} disabled={isStreaming}>
          Send
        </button>
      </div>
    </div>
  )
}

export default ChatUI
