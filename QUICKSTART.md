# NOVA AI Quick Start

## 1. Start local services

```bash
docker compose up mongo redis -d
```

## 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

Minimum Gemini-ready `.env` values:

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

Backend: `http://localhost:8000`

## 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend: `http://localhost:3000`

## 4. First checks

- Sign up and open `/chat`
- Try a normal question
- Try `Create image` with a short prompt
- Upload a document and ask a question about it

## If something fails

- `No module named 'fastapi'`
  The backend packages are not installed in the same venv you are using to run the server.

- Image generation times out or fails too quickly
  Increase `AI_IMAGE_REQUEST_TIMEOUT_SECONDS` in `backend/.env` and restart the backend.

- Port `8000` is busy
  Stop the old backend process or run NOVA on another port.
