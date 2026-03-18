import { useEffect, useRef, useState } from 'react'
import { sendMessage } from '../services/api'
import MessageBubble from './MessageBubble'

const createId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`

function VoiceAssistant() {
  const [messages, setMessages] = useState([
    {
      id: createId(),
      role: 'assistant',
      content: 'Voice mode ready. Tap the microphone and start speaking.',
    },
  ])
  const [isListening, setIsListening] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const recognitionRef = useRef(null)

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return
    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = false
    recognition.continuous = false

    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript || ''
      if (transcript) {
        handleUserMessage(transcript)
      }
    }

    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)

    recognitionRef.current = recognition
  }, [])

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

  const speak = (text) => {
    if (!window.speechSynthesis) return
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1
    utterance.pitch = 1
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  }

  const handleUserMessage = async (text) => {
    const userMessage = { id: createId(), role: 'user', content: text }
    const assistantId = createId()
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: 'assistant', content: '' },
    ])
    const answer = await sendMessage(text)
    await streamAnswer(assistantId, answer)
    speak(answer)
  }

  const toggleListening = () => {
    if (!recognitionRef.current) return
    if (isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
      return
    }
    setIsListening(true)
    recognitionRef.current.start()
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h1 className="text-2xl font-semibold text-white">Voice Assistant</h1>
        <p className="text-sm text-gray-400">
          Speak your prompt and hear NOVA AI respond.
        </p>
      </div>

      <div className="panel-body">
        <div className="voice-controls">
          <button className="mic-button" onClick={toggleListening}>
            {isListening ? 'Stop Listening' : 'Start Listening'}
          </button>
          <span className="text-xs text-gray-400">
            {isListening ? 'Listening...' : 'Idle'}
          </span>
        </div>

        <div className="chat-window">
          <div className="chat-messages">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isStreaming &&
              messages[messages.length - 1]?.role === 'assistant' &&
              !messages[messages.length - 1]?.content && <MessageBubble isTyping />}
          </div>
        </div>
      </div>
    </div>
  )
}

export default VoiceAssistant
