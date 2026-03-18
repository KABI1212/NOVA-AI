# NOVA AI - Quick Start Guide

Get NOVA AI up and running in 5 minutes!

## Prerequisites

✅ Python 3.11+
✅ Node.js 18+
✅ PostgreSQL 15+
✅ Redis 7+
✅ OpenAI API Key

## 5-Minute Setup

### Step 1: Database Setup (1 minute)

```bash
# Create PostgreSQL database
sudo -u postgres psql
CREATE DATABASE nova_ai_db;
CREATE USER nova_user WITH PASSWORD 'nova_password';
GRANT ALL PRIVILEGES ON DATABASE nova_ai_db TO nova_user;
\q
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

# Run backend
python main.py
```

✅ Backend running at: http://localhost:8000

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

# Run everything with one command
docker-compose up --build
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
