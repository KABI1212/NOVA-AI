# NOVA AI - Modern AI Chatbot Platform

![NOVA AI](https://img.shields.io/badge/NOVA-AI-blue)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![React](https://img.shields.io/badge/React-18.2-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-teal)

A production-ready, full-stack AI chatbot platform similar to ChatGPT, featuring real-time chat, code generation, document analysis, and personalized learning assistance.

## 🌟 Features

### 1. **NOVA AI Chat System**
- Real-time AI conversations with streaming responses
- Beautiful chat interface with markdown rendering
- Code block syntax highlighting with copy functionality
- Conversation history management
- AI typing animations

### 2. **Code Assistant**
- Generate code in multiple programming languages
- Step-by-step code explanations
- Debug and fix code issues
- Optimize code for better performance
- Support for Python, JavaScript, Java, C++, Go, and more

### 3. **Deep Explanation Engine**
- Step-by-step concept breakdowns
- Logical reasoning summaries
- Examples and learning support
- Audience and detail controls

### 4. **Image Generator**
- Generate images from text prompts
- Chat-style image history
- Download generated images
- Prompt suggestions

### 5. **Reasoning and Safe AI**
- Structured responses with safe guidance
- Clear reasoning summaries
- Ethical response filtering

### 6. **Knowledge Assistant**
- Answer knowledge questions
- Explain technical concepts
- Summarize text

### 7. **Document Analyzer**
- Upload and analyze PDF and TXT files
- Automatic text extraction and summarization
- Ask questions about your documents
- Semantic search using vector embeddings (FAISS)
- Document management system

### 8. **Learning Assistant**
- Generate personalized learning roadmaps
- Track learning progress
- Get course and resource recommendations
- Beginner, Intermediate, and Advanced levels

### 9. **User Authentication**
- Secure JWT-based authentication
- User registration and login
- Password hashing with bcrypt
- Protected API endpoints
- User profile management

## 🏗️ Architecture

### Backend Stack
- **Framework**: FastAPI (Python)
- **Database**: MongoDB
- **Cache**: Redis
- **AI**: OpenAI GPT-4
- **Vector DB**: FAISS
- **Authentication**: JWT
- **Password Hashing**: Bcrypt

### Frontend Stack
- **Framework**: React 18 with Vite
- **Styling**: Tailwind CSS
- **Animations**: Framer Motion
- **Icons**: Lucide React
- **State Management**: Zustand
- **Markdown**: react-markdown
- **Syntax Highlighting**: react-syntax-highlighter
- **HTTP Client**: Axios

## 📦 Project Structure

```
nova-ai/
├── backend/
│   ├── config/
│   │   ├── settings.py          # Configuration settings
│   │   └── database.py          # Database setup
│   ├── models/
│   │   ├── user.py              # User model
│   │   ├── conversation.py      # Chat models
│   │   ├── document.py          # Document model
│   │   └── learning.py          # Learning progress model
│   ├── routes/
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── chat.py              # Chat endpoints
│   │   ├── code.py              # Code assistant endpoints
│   │   ├── document.py          # Document endpoints
│   │   └── learning.py          # Learning endpoints
│   ├── services/
│   │   ├── ai_service.py        # OpenAI integration
│   │   ├── document_service.py  # Document processing
│   │   └── vector_service.py    # Vector database
│   ├── utils/
│   │   ├── auth.py              # Auth utilities
│   │   └── dependencies.py      # FastAPI dependencies
│   ├── main.py                  # FastAPI application
│   ├── requirements.txt         # Python dependencies
│   ├── Dockerfile              # Backend Docker config
│   └── .env.example            # Environment variables template
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/           # Chat components
│   │   │   ├── sidebar/        # Sidebar components
│   │   │   ├── auth/           # Auth components
│   │   │   └── common/         # Shared components
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Signup.jsx
│   │   │   ├── Chat.jsx
│   │   │   ├── CodeAssistant.jsx
│   │   │   ├── DocumentAnalyzer.jsx
│   │   │   └── LearningAssistant.jsx
│   │   ├── services/
│   │   │   └── api.js          # API client
│   │   ├── utils/
│   │   │   └── store.js        # Zustand stores
│   │   ├── styles/
│   │   │   └── index.css       # Global styles
│   │   ├── App.jsx             # Main app component
│   │   └── main.jsx            # Entry point
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── Dockerfile              # Frontend Docker config
│   └── nginx.conf              # Nginx configuration
│
├── docker-compose.yml          # Docker Compose config
└── README.md                   # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop or MongoDB 7+
- Redis 7+
- OpenAI API Key

### Option 1: Local Development Setup

#### Backend Setup

1. Navigate to backend directory:
```bash
cd nova-ai/backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
```

5. Configure environment variables in `.env`:
```env
DATABASE_URL=mongodb://localhost:27017/nova_ai
SECRET_KEY=your-super-secret-key-here
OPENAI_API_KEY=your-openai-api-key
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000
```

6. Start MongoDB:
```bash
docker compose up mongo -d
```

7. Run the backend:
```bash
python main.py
# or
uvicorn main:app --reload
```

Backend will be running at `http://localhost:8000`

#### Frontend Setup

1. Navigate to frontend directory:
```bash
cd nova-ai/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create `.env` file:
```bash
cp .env.example .env
```

4. Configure environment variables:
```env
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=NOVA AI
```

5. Run the frontend:
```bash
npm run dev
```

Frontend will be running at `http://localhost:3000`

### Option 2: Docker Deployment

1. Set environment variables:
```bash
export OPENAI_API_KEY=your-openai-api-key
export SECRET_KEY=your-secret-key
```

2. Build and run with Docker Compose:
```bash
docker compose up --build
```

Access the application:
- Frontend: `http://localhost`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## 🔑 API Endpoints

### Authentication
- `POST /api/auth/signup` - Register new user
- `POST /api/auth/login` - Login user

### Chat
- `POST /api/chat` - Send message (streaming)
- `POST /api/chat/regenerate` - Regenerate last assistant response
- `GET /api/chat/conversations` - Get all conversations
- `GET /api/chat/conversations/{id}` - Get conversation
- `DELETE /api/chat/conversations/{id}` - Delete conversation

### Code Assistant
- `POST /api/code/generate` - Generate code
- `POST /api/code/explain` - Explain code
- `POST /api/code/debug` - Debug code
- `POST /api/code/optimize` - Optimize code

### Deep Explanation and Reasoning
- `POST /api/explain` - Deep explanations, safe reasoning, and knowledge responses

### Image Generator
- `POST /api/image` - Generate images from prompts

### Document Analyzer
- `POST /api/document/upload` - Upload document
- `GET /api/document` - Get all documents
- `GET /api/document/{id}` - Get document
- `POST /api/document/ask` - Ask question about document
- `DELETE /api/document/{id}` - Delete document

### Learning Assistant
- `POST /api/learning/roadmap` - Generate learning roadmap
- `GET /api/learning` - Get learning progress
- `POST /api/learning/progress` - Update progress
- `DELETE /api/learning/{id}` - Delete learning progress

## 🌐 Deployment

### Deploy to Vercel (Frontend)

1. Install Vercel CLI:
```bash
npm i -g vercel
```

2. Deploy frontend:
```bash
cd frontend
vercel
```

3. Set environment variables in Vercel dashboard:
   - `VITE_API_URL` - Your backend URL

### Deploy to Render/Railway (Backend)

#### Render

1. Create new Web Service
2. Connect your repository
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `DATABASE_URL` (auto-added if using Render PostgreSQL)
   - `OPENAI_API_KEY`
   - `SECRET_KEY`
   - `REDIS_URL`

#### Railway

1. Create new project
2. Add PostgreSQL and Redis services
3. Deploy backend service
4. Add environment variables from Render list above

### Database Migration

The database tables are automatically created on startup. For production:

1. Install Alembic (already in requirements.txt)
2. Initialize migrations:
```bash
alembic init alembic
```

3. Create migration:
```bash
alembic revision --autogenerate -m "Initial migration"
```

4. Apply migration:
```bash
alembic upgrade head
```

## 🎨 UI Features

### Dark Mode
- Toggle between light and dark themes
- Persisted in localStorage
- Smooth transitions

### Responsive Design
- Mobile-friendly interface
- Adaptive sidebar
- Touch-optimized controls

### Animations
- Smooth page transitions (Framer Motion)
- Typing animations for AI responses
- Interactive button states
- Loading indicators

## 🔐 Security Features

- JWT-based authentication
- Password hashing with bcrypt
- Protected API routes
- CORS configuration
- SQL injection prevention (SQLAlchemy ORM)
- XSS protection (React auto-escaping)
- File upload validation
- Environment variable security

## 📊 Database Schema

### Users
- id, email, username, hashed_password
- full_name, is_active, is_verified
- created_at, updated_at

### Conversations
- id, user_id, title
- created_at, updated_at

### Messages
- id, conversation_id, role, content
- metadata, created_at

### Documents
- id, user_id, filename, file_path
- file_type, file_size, text_content
- summary, is_processed, created_at

### Learning Progress
- id, user_id, topic, roadmap
- completed_items, current_level
- notes, is_active, created_at

## 🛠️ Development

### Run Tests
```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Code Formatting
```bash
# Backend
black .
flake8 .

# Frontend
npm run lint
```

## 📝 Environment Variables

### Backend (.env)
```env
DATABASE_URL=mongodb://localhost:27017/nova_ai
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
OPENAI_API_KEY=sk-...
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000
MAX_FILE_SIZE_MB=10
UPLOAD_DIR=./uploads
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=NOVA AI
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- OpenAI for GPT API
- FastAPI framework
- React and Vite
- Tailwind CSS
- All open-source contributors

## 📧 Support

For issues and questions:
- Create an issue in the repository
- Email: support@nova-ai.com

## 🚀 Roadmap

- [ ] Voice chat integration
- [ ] Multi-language support
- [ ] Team collaboration features
- [ ] API rate limiting
- [ ] Advanced analytics dashboard
- [ ] Mobile apps (React Native)
- [ ] Plugin system for extensions

---

Built with ❤️ by the NOVA AI Team
