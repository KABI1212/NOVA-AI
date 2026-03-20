// @ts-nocheck
import { useState } from 'react'
import { generateImage } from '../services/api'

function ImageGenerator() {
  const [prompt, setPrompt] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleGenerate = async () => {
    const trimmed = prompt.trim()
    if (!trimmed) return
    setLoading(true)
    setError('')
    const url = await generateImage(trimmed)
    if (!url) {
      setError('Looks like I got stuck for a second. Want me to try again?')
      setLoading(false)
      return
    }
    setImageUrl(url)
    setLoading(false)
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h1 className="text-2xl font-semibold text-white">Image Generator</h1>
        <p className="text-sm text-gray-400">Describe what you want to create.</p>
      </div>

      <div className="panel-body">
        <div className="flex flex-col gap-3">
          <textarea
            className="chat-textarea"
            placeholder="e.g. Neon city skyline in the rain"
            rows={3}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <button className="chat-send" onClick={handleGenerate} disabled={loading}>
            {loading ? 'Generating...' : 'Generate Image'}
          </button>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>

        {imageUrl && (
          <div className="image-preview">
            <img src={imageUrl} alt="Generated" />
          </div>
        )}
      </div>
    </div>
  )
}

export default ImageGenerator
