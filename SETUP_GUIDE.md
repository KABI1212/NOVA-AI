# NOVA AI - Complete Setup Guide

This guide will walk you through setting up NOVA AI from scratch.

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Application](#running-the-application)
5. [Testing](#testing)
6. [Deployment](#deployment)
7. [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **OS**: Ubuntu 20.04+, macOS 11+, or Windows 10+
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 10GB free space
- **Python**: 3.11 or higher
- **Node.js**: 18.0 or higher
- **PostgreSQL**: 15 or higher
- **Redis**: 7 or higher

### Recommended for Production
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 50GB+ SSD

## Installation

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd nova-ai
```

### Step 2: Install PostgreSQL

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

#### Windows
Download and install from: https://www.postgresql.org/download/windows/

### Step 3: Install Redis

#### Ubuntu/Debian
```bash
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

#### macOS
```bash
brew install redis
brew services start redis
```

#### Windows
Download from: https://github.com/microsoftarchive/redis/releases

### Step 4: Create Database

```bash
# Login to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE nova_ai_db;
CREATE USER nova_user WITH ENCRYPTED PASSWORD 'nova_password';
GRANT ALL PRIVILEGES ON DATABASE nova_ai_db TO nova_user;
\q
```

### Step 5: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

Edit `.env` with your settings:
```env
DATABASE_URL=postgresql://nova_user:nova_password@localhost:5432/nova_ai_db
SECRET_KEY=generate-a-random-secret-key-here
OPENAI_API_KEY=your-openai-api-key-from-platform.openai.com
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 6: Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env
```

Edit `.env`:
```env
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=NOVA AI
```

## Configuration

### OpenAI API Key

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key to your backend `.env` file

### Database Schema

The database schema is automatically created when you first run the backend:

```bash
cd backend
python main.py
```

This will create all necessary tables:
- users
- conversations
- messages
- documents
- learning_progress

## Running the Application

### Development Mode

#### Terminal 1: Backend
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python main.py
```

Backend runs at: http://localhost:8000
API Documentation: http://localhost:8000/docs

#### Terminal 2: Frontend
```bash
cd frontend
npm run dev
```

Frontend runs at: http://localhost:3000

### Production Mode with Docker

```bash
# Set environment variables
export OPENAI_API_KEY=your-key
export SECRET_KEY=your-secret

# Build and run
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Testing

### Create Test User

1. Open http://localhost:3000
2. Click "Sign up"
3. Fill in the form:
   - Email: test@example.com
   - Username: testuser
   - Password: Test123!
   - Full Name: Test User
4. Click "Create Account"

### Test Features

#### 1. Chat System
1. Navigate to Chat page
2. Type a message: "Hello, who are you?"
3. Press Enter or click Send
4. Watch the AI response stream in

#### 2. Code Assistant
1. Navigate to Code Assistant
2. Select "Generate Code" tab
3. Enter prompt: "Create a Python function to calculate fibonacci numbers"
4. Click Submit
5. View generated code

#### 3. Document Analyzer
1. Navigate to Documents page
2. Click "Upload Document"
3. Select a PDF or TXT file
4. Wait for processing
5. Click on document to view summary
6. Ask a question about the document

#### 4. Learning Assistant
1. Navigate to Learning page
2. Enter topic: "Python Programming"
3. Select level: "Beginner"
4. Click "Generate Roadmap"
5. View personalized learning path

## Deployment

### Deploy Backend to Render

1. Create account at https://render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: nova-ai-backend
   - **Root Directory**: backend
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. Add Environment Variables:
   - `DATABASE_URL` - From Render PostgreSQL
   - `OPENAI_API_KEY`
   - `SECRET_KEY`
   - `REDIS_URL` - From Render Redis
   - `CORS_ORIGINS` - Your frontend URL

6. Create PostgreSQL Database:
   - Click "New +" → "PostgreSQL"
   - Note the Internal Database URL

7. Create Redis:
   - Click "New +" → "Redis"
   - Note the Internal Redis URL

### Deploy Frontend to Vercel

1. Install Vercel CLI:
```bash
npm i -g vercel
```

2. Deploy:
```bash
cd frontend
vercel --prod
```

3. Set environment variable in Vercel dashboard:
   - `VITE_API_URL` - Your Render backend URL

### Alternative: Deploy to Railway

1. Install Railway CLI:
```bash
npm i -g @railway/cli
```

2. Login:
```bash
railway login
```

3. Deploy backend:
```bash
cd backend
railway init
railway up
```

4. Add PostgreSQL and Redis:
```bash
railway add postgresql
railway add redis
```

5. Deploy frontend:
```bash
cd ../frontend
railway init
railway up
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Error

**Error**: `could not connect to server: Connection refused`

**Solution**:
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Check if database exists
psql -U nova_user -d nova_ai_db
```

#### 2. Redis Connection Error

**Error**: `Error connecting to Redis`

**Solution**:
```bash
# Check Redis status
redis-cli ping

# Should return: PONG

# If not running:
sudo systemctl start redis
```

#### 3. OpenAI API Error

**Error**: `Error: Invalid API key`

**Solution**:
- Verify your API key is correct in `.env`
- Check you have credits in your OpenAI account
- Ensure no extra spaces in the key

#### 4. Module Import Errors

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### 5. Frontend Build Errors

**Error**: `Module not found: Error: Can't resolve 'react'`

**Solution**:
```bash
# Remove node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

#### 6. CORS Errors

**Error**: `Access to XMLHttpRequest has been blocked by CORS policy`

**Solution**:
- Check `CORS_ORIGINS` in backend `.env` includes your frontend URL
- Restart backend server after changing `.env`

#### 7. Port Already in Use

**Error**: `Address already in use`

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
uvicorn main:app --port 8001
```

### Database Reset

If you need to reset the database:

```bash
# Drop and recreate database
sudo -u postgres psql
DROP DATABASE nova_ai_db;
CREATE DATABASE nova_ai_db;
GRANT ALL PRIVILEGES ON DATABASE nova_ai_db TO nova_user;
\q

# Restart backend to recreate tables
cd backend
python main.py
```

### Logs and Debugging

#### View Backend Logs
```bash
# In development
python main.py

# In Docker
docker-compose logs backend -f
```

#### View Frontend Logs
```bash
# In development - check browser console
# F12 → Console tab

# Build logs
npm run build
```

#### Enable Debug Mode

Backend `.env`:
```env
DEBUG=True
```

This will show detailed error messages.

## Performance Optimization

### Backend Optimization

1. **Use connection pooling**:
Already configured in `database.py`:
```python
pool_size=10
max_overflow=20
```

2. **Enable Redis caching**:
Cache frequently accessed data

3. **Use background tasks**:
For document processing and heavy operations

### Frontend Optimization

1. **Enable production build**:
```bash
npm run build
```

2. **Enable gzip compression** in nginx.conf:
```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript;
```

3. **Use lazy loading**:
React components are already optimized with code splitting

## Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Use strong database passwords
- [ ] Enable HTTPS in production
- [ ] Set secure CORS origins
- [ ] Validate file uploads
- [ ] Use environment variables for secrets
- [ ] Enable rate limiting
- [ ] Regular security updates
- [ ] Backup database regularly

## Backup and Restore

### Backup Database

```bash
pg_dump -U nova_user nova_ai_db > backup.sql
```

### Restore Database

```bash
psql -U nova_user nova_ai_db < backup.sql
```

### Backup Uploads

```bash
tar -czf uploads_backup.tar.gz backend/uploads/
```

## Monitoring

### Health Checks

- Backend: http://localhost:8000/health
- Database: `psql -U nova_user -d nova_ai_db -c "SELECT 1;"`
- Redis: `redis-cli ping`

### Performance Monitoring

Use tools like:
- New Relic
- Datadog
- Sentry for error tracking

## Getting Help

- Check API documentation: http://localhost:8000/docs
- Review logs for error messages
- Search existing issues in repository
- Create a new issue with details

## Next Steps

After successful setup:

1. Customize branding and colors in `tailwind.config.js`
2. Add custom AI prompts in `ai_service.py`
3. Configure additional file types for document analyzer
4. Set up automated backups
5. Configure monitoring and alerts
6. Add custom features based on your needs

---

**Congratulations! NOVA AI is now set up and running!** 🎉
