# NOVA AI - Project Summary

## Overview

NOVA AI is a full-stack AI workspace with chat, image generation, document
analysis, code help, search, sharing, learning tools, optional voice
features, and email-OTP-protected login.

## Current Stack

### Backend
- FastAPI for HTTP APIs and streaming responses
- MongoDB for persisted application data
- A small in-repo model/session layer built on top of `pymongo`
- Redis-backed rate limiting with in-memory fallback
- Provider routing for OpenAI, Gemini, Anthropic, DeepSeek, Groq, OpenRouter,
  and Ollama

### Frontend
- React 18 + Vite
- Zustand for client state
- `react-markdown` for rich answers
- Axios and `fetch` for API access

## Major Features

1. Chat with streaming responses, conversation history, regeneration, and
   provider selection.
2. Image generation, prompt optimization, and uploaded-image variation flows.
3. Document upload, summarization, question answering, rewrite helpers, and
   diagram/image enrichment.
4. Code generation, explanation, debugging, and optimization helpers.
5. Search mode with web results and source-aware streamed answers.
6. Shareable conversations and user-facing share management.
7. Learning roadmap generation and progress tracking.
8. Voice transcription and text-to-speech endpoints that use OpenAI when a key
   is configured.
9. Two-step login with email OTP verification and JWT session issuance.

## Storage Model

The active backend is MongoDB-based.

- Runtime bootstrap lives in
  `backend/config/database.py`.
- Collections and indexes are created in `init_db()` and `_ensure_indexes()`.
- There are no active SQLAlchemy models or relational migrations in the running
  app.
- `backend/alembic/` is retained only as a legacy placeholder so older tooling
  fails with a clear explanation.

The primary collections are:

- `users`
- `conversations`
- `messages`
- `documents`
- `learning_progress`
- `counters`

See `DATABASE_SCHEMA.sql` for the current Mongo-oriented storage reference.

## Retrieval and Search

- Document retrieval works in lexical mode by default.
- If OpenAI embeddings are configured, the app can also maintain embedding-based
  retrieval data in memory.
- FAISS support is optional; the app falls back cleanly when vector extras are
  unavailable.

## Important Paths

- `backend/main.py`: FastAPI entrypoint and frontend serving
- `backend/config/database.py`: Mongo connection, status checks, and index setup
- `backend/routes/`: API surface for auth, chat, image, document, voice, search,
  learning, and sharing
- `backend/services/`: AI provider logic, rate limiting, retrieval, search, and
  helper services
- `frontend/src/pages/`: main product surfaces
- `frontend/src/components/`: shared UI building blocks

## Local Development

### Services

Use Docker if you want the easiest local data stack:

```bash
docker compose up mongo redis -d
```

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

Recommended minimum `.env` values:

```env
DATABASE_URL=mongodb://localhost:27017/nova_ai
REDIS_URL=redis://localhost:6379
SECRET_KEY=change-me
AI_PROVIDER=auto
GOOGLE_API_KEY=your-google-key
GEMINI_API_KEY=your-google-key
```

Backend URL: `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend URL: `http://localhost:3000`

## Deployment Notes

- The backend expects MongoDB, not PostgreSQL.
- Redis is recommended for rate limiting, but the app can degrade to in-memory
  limits if Redis is unavailable.
- Voice endpoints still require `OPENAI_API_KEY`.
- Image generation availability depends on the configured provider keys and
  quotas.

## Documentation

- `README.md`: main project documentation
- `QUICKSTART.md`: shortest path to a local run
- `SETUP_GUIDE.md`: step-by-step setup guidance
- `CAPABILITY_MATRIX.md`: implemented, partial, and missing feature coverage
- `DATABASE_SCHEMA.sql`: current storage reference for Mongo collections/indexes
- `/docs`: FastAPI-generated API docs while the backend is running
