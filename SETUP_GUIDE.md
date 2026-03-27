# NOVA AI Setup Guide

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer
- MongoDB 7+ and Redis 7+, or Docker Desktop
- One or more AI provider keys

## Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Recommended `backend/.env`:

```env
DATABASE_URL=mongodb://localhost:27017/nova_ai
MONGODB_DB_NAME=
REDIS_URL=redis://localhost:6379
SECRET_KEY=change-me

AI_PROVIDER=auto
AI_MODEL=

GOOGLE_API_KEY=your-google-key
GEMINI_API_KEY=your-google-key
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=

AI_REQUEST_TIMEOUT_SECONDS=60
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=180
DEBUG=true
APP_HOST=127.0.0.1
APP_PORT=8000
```

Start the backend:

```bash
python main.py
```

## Frontend Setup

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

`frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=NOVA AI
```

## Local Services

With Docker:

```bash
docker compose up mongo redis -d
```

Without Docker:

- Run MongoDB on `mongodb://localhost:27017`
- Run Redis on `redis://localhost:6379`

## Docker Deployment

Set environment variables and build:

```bash
docker compose up --build
```

Recommended Docker env:

```env
AI_PROVIDER=auto
GOOGLE_API_KEY=your-google-key
GEMINI_API_KEY=your-google-key
OPENAI_API_KEY=
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
AI_IMAGE_REQUEST_TIMEOUT_SECONDS=180
SECRET_KEY=change-me
```

## Notes

- Chat provider auto-detection is enabled when `AI_PROVIDER=auto`.
- Gemini image generation is used when Google keys are configured.
- Voice transcription / TTS backend endpoints still depend on OpenAI.
- Retrieval works without FAISS; lexical fallback is available by default.

## Common Problems

### `No module named 'fastapi'`

You are running `main.py` from a virtual environment that does not have the backend packages installed.

### `Image generation failed for that prompt`

Check:

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_IMAGE_MODEL`
- backend restart after changing `.env`

### `Only one usage of each socket address`

Port `8000` is already in use. Stop the other backend process or change `APP_PORT`.
