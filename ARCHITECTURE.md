# NOVA AI Architecture

NOVA AI is a ChatGPT-style AI workspace with streaming chat, multi-provider model routing, file intelligence, image generation, search, sharing, learning tools, and email-OTP authentication.

## System Overview

```text
+-------------------------------------------------+
|                      USER                       |
+-------------------------------------------------+
                         |
                         v
+-------------------------------------------------+
|                   FRONTEND UI                   |
|                                                 |
|  +--------------+   +------------------------+  |
|  |   Sidebar    |   |   Conversation Area    |  |
|  | Chat History |   |   AI Responses         |  |
|  +--------------+   +------------------------+  |
|                                                 |
|       Input Box + File Upload + Voice Input     |
+-------------------------------------------------+
                         |
                         v
+-------------------------------------------------+
|                  FASTAPI BACKEND                |
|                                                 |
|  +--------------+   +------------------------+  |
|  | Auth System  |   | Session Management     |  |
|  +--------------+   +------------------------+  |
|                                                 |
|  +-------------------------------------------+  |
|  |        AI Routing + Response Engine       |  |
|  +-------------------------------------------+  |
|                                                 |
|  +--------------+   +------------------------+  |
|  | File Parser  |   | Markdown Formatter     |  |
|  +--------------+   +------------------------+  |
+-------------------------------------------------+
                         |
             +-----------+-----------+
             v                       v
+--------------------------+  +-------------------+
|       AI PROVIDERS       |  |      DATABASE     |
|                          |  |                   |
| OpenAI / Gemini /        |  | MongoDB + Redis   |
| Anthropic / DeepSeek /   |  |                   |
| Groq / OpenRouter /      |  | Users, chats,     |
| Ollama                   |  | files, history    |
+--------------------------+  +-------------------+
```

## Chat Flow

```text
User Message
      |
      v
Frontend Input Box
      |
      v
Backend Chat Route
      |
      v
Prompt Building + Context Retrieval
      |
      v
AI Provider Stream
      |
      v
Server-Sent Events
      |
      v
Frontend Streaming Renderer
      |
      v
Markdown Formatter
      |
      v
Conversation Window
      |
      v
MongoDB Persistence
      |
      v
Visible in Sidebar History
```

## Frontend Architecture

```text
frontend/src
|
+-- pages
|   +-- Chat.jsx
|   +-- SearchChat.jsx
|   +-- ImageGenerator.jsx
|   +-- DocumentAnalyzer.jsx
|   +-- CodeAssistant.jsx
|   +-- LearningAssistant.jsx
|
+-- components
|   +-- Sidebar.jsx
|   +-- ChatWindow.jsx
|   +-- ChatInput.jsx
|   +-- TypingIndicator.jsx
|   +-- uploads
|   +-- common
|       +-- MarkdownAnswer.jsx
|
+-- services
|   +-- api.js
|
+-- styles
    +-- index.css
```

## Frontend Responsibilities

```text
Frontend
|
+-- Sidebar
|   +-- New Chat
|   +-- Chat History
|   +-- Search Chats
|   +-- Settings
|
+-- Main Chat
|   +-- Messages
|   +-- Streaming Answers
|   +-- Markdown
|   +-- Code Blocks
|   +-- Images
|   +-- Tables
|
+-- Input Section
    +-- Textarea
    +-- Upload Button
    +-- Voice Input
    +-- Model Selector
    +-- Send Button
```

## Backend Architecture

```text
backend
|
+-- routes
|   +-- auth.py
|   +-- chat.py
|   +-- files.py
|   +-- image.py
|   +-- search.py
|   +-- share.py
|   +-- voice.py
|
+-- services
|   +-- ai_service.py
|   +-- ai_provider.py
|   +-- ai_router.py
|   +-- conversation_store.py
|   +-- file_parser.py
|   +-- retriever.py
|   +-- redis_store.py
|   +-- email_service.py
|
+-- models
|   +-- user.py
|   +-- conversation.py
|   +-- chat.py
|   +-- file_record.py
|   +-- file_chunk.py
|   +-- document.py
|
+-- config
    +-- settings.py
    +-- database.py
```

## Backend Responsibilities

```text
Backend
|
+-- Authentication and JWT handling
+-- Email OTP verification
+-- Chat session management
+-- AI provider routing and fallback
+-- Streaming response orchestration
+-- File upload and parsing
+-- Retrieval over uploaded files
+-- Image generation and proxying
+-- Shareable conversation views
+-- Rate limiting
+-- MongoDB persistence
```

## Data Storage

NOVA AI uses MongoDB as the primary application database. Collections and indexes are created at runtime by `backend/config/database.py`.

```text
MongoDB
|
+-- users
+-- conversations
+-- messages
+-- documents
+-- files
+-- file_chunks
+-- chat_sessions
+-- learning_progress
+-- counters
```

Redis is used where available for short-lived operational state such as file-processing queues, cache entries, and rate-limit counters. The app can degrade when some Redis-backed helpers are unavailable, depending on the feature path.

## Streaming Architecture

```text
AI Provider
   |
   v
Token / Chunk Stream
   |
   v
Backend Stream Normalizer
   |
   v
FastAPI StreamingResponse
   |
   v
Server-Sent Events
   |
   v
Frontend Stream Reader
   |
   v
Live Markdown Rendering
```

## Chat Message Shape

```json
{
  "role": "assistant",
  "content": "AI response here",
  "timestamp": "2026-05-10",
  "meta": {
    "provider": "openai",
    "model": "selected-model",
    "sources": []
  }
}
```

## ChatGPT-Style UI Structure

```text
+-------------+-----------------------------+
| Sidebar     |     Conversation Area       |
|             |                             |
| Chat List   |     AI Responses            |
|             |                             |
| New Chat    |                             |
+-------------+-----------------------------+
| Settings    |        Input Bar            |
+-------------+-----------------------------+
```

## Responsive Layout

```text
Desktop:
Sidebar + Chat Area

Mobile:
Hamburger Menu -> Sidebar
Full Width Chat Area
Sticky Input Bottom
```

## Core Features

- Infinite conversation scrolling
- Streaming answers
- Markdown rendering
- Code block formatting and copy actions
- File upload and document intelligence
- AI typing animation
- Chat history
- Responsive mobile UI
- Dark interface
- Search chats
- Session saving
- Auto-scroll to latest response
- Multi-provider AI routing
- Shareable conversations

## Tech Stack

| Part | Technology |
| --- | --- |
| Frontend | React 18, Vite, Tailwind CSS, Zustand |
| Backend | FastAPI, Python, Uvicorn/Gunicorn |
| Database | MongoDB |
| Cache / Queues | Redis |
| Authentication | JWT, bcrypt, email OTP |
| AI | OpenAI, Gemini, Anthropic, DeepSeek, Groq, OpenRouter, Ollama |
| Markdown | react-markdown, remark-gfm, remark-breaks |
| File Parsing | PyMuPDF, pdfplumber, python-docx, pandas, openpyxl |
| Hosting | Render / Vercel / Docker |

## Deployment Shape

```text
User
 |
 v
CDN / Hosting Edge
 |
 v
Frontend (React + Vite)
 |
 v
Backend API (FastAPI)
 |
 +-- AI Engine
 +-- Auth
 +-- File Intelligence
 +-- Search
 +-- Persistence Layer
 |   +-- MongoDB
 |   +-- Redis
 |
 v
AI Provider APIs
```
