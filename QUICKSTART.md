# NOVA AI - Quick Start Guide

Get NOVA AI up and running in 5 minutes!

## Prerequisites

✅ Python 3.11+
✅ Node.js 18+
✅ Docker Desktop (recommended) or MongoDB 7+
✅ Redis 7+
✅ OpenAI API Key

## 5-Minute Setup

### Step 1: Start MongoDB (1 minute)

```bash
# Recommended: Docker
docker compose up mongo -d

# Alternative: use your local MongoDB service
# mongod --dbpath C:\data\db
```

For Windows local backend development after Docker Desktop is installed:
```powershell
.\scripts\start-local-dev-services.ps1
```

For Windows local backend development without Docker:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-portable-mongo.ps1
```

### Step 2: Backend Setup (2 minutes)

```bash
cd backend

# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
# DATABASE_URL defaults to mongodb://localhost:27017/nova_ai

# Run backend
python main.py
```

✅ Backend running at: http://localhost:8000

Windows shortcut for local Mongo + backend:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-nova-local.ps1
```

### Step 3: Frontend Setup (2 minutes)

```bash
# Open new terminal
cd frontend

# Install and run
npm install
npm run dev
```

✅ Frontend running at: http://localhost:3000

## First Login

1. Open http://localhost:3000
2. Click "Sign Up"
3. Create account:
   - Email: your@email.com
   - Username: yourusername
   - Password: YourPassword123

4. Start chatting! 🎉

## Quick Docker Setup (Alternative)

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=your-key-here

# Run frontend, backend, MongoDB, and Redis
docker compose up --build
```

Access at: http://localhost

## Test Features

### 1. Chat
Navigate to Chat → Type "Hello NOVA!" → Press Enter

### 2. Code Generation
Code Assistant → Enter "Create a Python calculator" → Submit

### 3. Document Analysis
Documents → Upload a PDF → Ask questions about it

### 4. Learning Roadmap
Learning → Enter "JavaScript" → Generate Roadmap

## Need Help?

- 📖 Full docs: README.md
- 🛠️ Setup guide: SETUP_GUIDE.md
- 🐛 Issues: Check troubleshooting section
- 📧 Email: support@nova-ai.com

## Important URLs

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Next Steps

✨ Customize the UI in `frontend/src/styles`
🔧 Modify AI prompts in `backend/services/ai_service.py`
🚀 Deploy to production (see README.md)

---

Happy building with NOVA AI! 🚀
