# NOVA AI

NOVA AI is a full-stack AI workspace with chat, image generation, document analysis, code help, search, sharing, and learning tools.

## Features

- Multi-provider chat with OpenAI, Gemini, Anthropic, DeepSeek, Groq, OpenRouter, and Ollama support
- Gemini-backed prompt-to-image generation and uploaded-photo remixing
- Document upload, summarization, and question answering
- Code generation, explanation, debugging, and optimization helpers
- Search mode, shareable chats, and learning-roadmap flows
- Markdown answers with tables, code blocks, callouts, and friendly heading formatting

## Stack

- Backend: FastAPI, MongoDB, Redis, httpx, provider SDKs
- Frontend: React 18, Vite, Zustand, react-markdown
- Auth: JWT + bcrypt
- Retrieval: lexical fallback by default, optional embedding-assisted retrieval when OpenAI embeddings are configured

## Local Setup

### Requirements

- Python 3.11+
- Node.js 18+
- MongoDB 7+ or Docker Desktop
- Redis 7+ recommended
- At least one AI provider key

### 1. Start MongoDB and Redis

```bash
docker compose up mongo redis -d
```

If you already run MongoDB and Redis locally, you can keep using those instead.

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Suggested `backend/.env` for Gemini-first usage:

```env
DATABASE_URL=mongodb://localhost:27017/nova_ai
REDIS_URL=redis://localhost:6379
SECRET_KEY=change-me
AI_PROVIDER=auto
GOOGLE_API_KEY=your-google-key
GEMINI_API_KEY=your-google-key
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=180
```

Run the backend:

```bash
python main.py
```

Backend URL: `http://localhost:8000`

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend URL: `http://localhost:3000`

## Docker

```bash
docker compose up --build
```

Useful environment variables for Docker:

```env
AI_PROVIDER=auto
GOOGLE_API_KEY=your-google-key
GEMINI_API_KEY=your-google-key
OPENAI_API_KEY=
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=180
SECRET_KEY=change-me
```

## Provider Notes

- Chat provider auto-detection works when `AI_PROVIDER=auto` or when `AI_PROVIDER` is left blank.
- Image generation uses Gemini when Google keys are present and Gemini is selected or OpenAI is unavailable.
- Backend voice endpoints still require `OPENAI_API_KEY`.
- Document retrieval works without FAISS; the app falls back to lexical search when embedding/vector extras are unavailable.

## Troubleshooting

- `ModuleNotFoundError: fastapi`
  Install backend packages in the same virtual environment you use to run `main.py`.

- `Image generation failed for that prompt`
  Check `GOOGLE_API_KEY` / `GEMINI_API_KEY`, confirm the backend is restarted, and try a shorter prompt.

- `Only one usage of each socket address`
  Port `8000` is already being used by another backend process. Stop the old process or run on a different port.

- Chat says providers failed
  Make sure the backend is running and at least one provider key is configured in `backend/.env`.
