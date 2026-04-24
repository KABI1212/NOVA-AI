# 🔌 NOVA-AI REST API Documentation

## Complete API Specification with Conversation & Learning Management

---

## 📋 Table of Contents

1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Endpoints Reference](#endpoints-reference)
4. [Request/Response Formats](#requestresponse-formats)
5. [Error Handling](#error-handling)
6. [Integration with NOVA-AI](#integration-with-nova-ai)
7. [Code Examples](#code-examples)

---

## 🎯 API Overview

### Base URL
```
https://your-api.com/api
```

### Supported Operations
- ✅ **POST** - Create conversations/learning sessions
- ✅ **GET** - Retrieve data
- ✅ **PUT/PATCH** - Update conversations/progress
- ✅ **DELETE** - Remove conversations/learning records

### Response Format
- **Content-Type**: `application/json`
- **Status Codes**: Standard HTTP codes (200, 422, 404, 500, etc.)

---

## 🔐 Authentication

### API Key Authentication
```bash
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### Setup in NOVA-AI
```python
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://your-api.com/api")

class APIClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
```

---

## 📡 Endpoints Reference

### 1. Conversation Management

#### Create Conversation
```
POST /chat/conversations
Content-Type: application/json

{
  "title": "string",
  "topic": "string",
  "description": "string (optional)"
}

Response 200:
{
  "conversation_id": "string",
  "title": "string",
  "created_at": "ISO 8601 timestamp",
  "status": "active"
}

Response 422:
{
  "detail": [
    {
      "loc": ["string"],
      "msg": "string",
      "type": "string",
      "input": "string",
      "ctx": {}
    }
  ]
}
```

#### Get Conversation
```
GET /chat/conversations/{conversation_id}

Response 200:
{
  "conversation_id": "string",
  "title": "string",
  "topic": "string",
  "messages": [
    {
      "message_id": "string",
      "role": "user|assistant",
      "content": "string",
      "timestamp": "ISO 8601"
    }
  ],
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

#### Update Conversation
```
PUT /chat/conversations/{conversation_id}
Content-Type: application/json

{
  "title": "string (optional)",
  "topic": "string (optional)"
}

Response 200:
{
  "conversation_id": "string",
  "title": "string",
  "updated_at": "ISO 8601"
}
```

#### Delete Conversation
```
DELETE /chat/conversations/{conversation_id}

Path Parameters:
  conversation_id (string, required): Conversation ID

Response 200:
{
  "message": "Conversation deleted successfully"
}

Response 422:
{
  "detail": [
    {
      "loc": ["string"],
      "msg": "string",
      "type": "string",
      "input": "string",
      "ctx": {}
    }
  ]
}
```

#### List Conversations
```
GET /chat/conversations?skip=0&limit=10

Query Parameters:
  skip (integer): Number to skip (default: 0)
  limit (integer): Maximum results (default: 10)
  topic (string, optional): Filter by topic

Response 200:
{
  "conversations": [
    {
      "conversation_id": "string",
      "title": "string",
      "topic": "string",
      "message_count": "integer",
      "created_at": "ISO 8601"
    }
  ],
  "total": "integer",
  "skip": "integer",
  "limit": "integer"
}
```

### 2. Message Management

#### Add Message to Conversation
```
POST /chat/conversations/{conversation_id}/messages
Content-Type: application/json

{
  "role": "user|assistant",
  "content": "string",
  "metadata": {
    "model": "string (optional)",
    "confidence": "number (optional)",
    "sources": ["string (optional)"]
  }
}

Response 200:
{
  "message_id": "string",
  "conversation_id": "string",
  "role": "user|assistant",
  "content": "string",
  "created_at": "ISO 8601"
}
```

#### Get Message History
```
GET /chat/conversations/{conversation_id}/messages?limit=50

Query Parameters:
  limit (integer): Number of messages to fetch (default: 50)
  offset (integer): Offset for pagination (default: 0)

Response 200:
{
  "messages": [
    {
      "message_id": "string",
      "conversation_id": "string",
      "role": "user|assistant",
      "content": "string",
      "created_at": "ISO 8601",
      "metadata": {}
    }
  ],
  "total_count": "integer"
}
```

### 3. Learning Progress Management

#### Create Learning Session
```
POST /learning
Content-Type: application/json

{
  "user_id": "string",
  "topic": "string",
  "objective": "string"
}

Response 200:
{
  "learning_id": "integer",
  "user_id": "string",
  "topic": "string",
  "created_at": "ISO 8601",
  "progress": "0%"
}

Response 422:
{
  "detail": [
    {
      "loc": ["string"],
      "msg": "string",
      "type": "string",
      "input": "string",
      "ctx": {}
    }
  ]
}
```

#### Get Learning Progress
```
GET /learning/{learning_id}

Response 200:
{
  "learning_id": "integer",
  "user_id": "string",
  "topic": "string",
  "progress": "percentage",
  "completed_modules": ["string"],
  "quiz_scores": [
    {
      "quiz_id": "string",
      "score": "number",
      "completed_at": "ISO 8601"
    }
  ],
  "created_at": "ISO 8601",
  "last_accessed": "ISO 8601"
}
```

#### Update Learning Progress
```
PUT /learning/{learning_id}
Content-Type: application/json

{
  "progress": "percentage",
  "completed_modules": ["string"],
  "quiz_scores": [
    {
      "quiz_id": "string",
      "score": "number"
    }
  ]
}

Response 200:
{
  "learning_id": "integer",
  "progress": "percentage",
  "updated_at": "ISO 8601"
}
```

#### Delete Learning Progress
```
DELETE /learning/{learning_id}

Path Parameters:
  learning_id (integer, required): Learning Progress ID

Response 200:
{
  "message": "Learning progress deleted successfully"
}

Response 422:
{
  "detail": [
    {
      "loc": ["string"],
      "msg": "string",
      "type": "string",
      "input": "string",
      "ctx": {}
    }
  ]
}
```

#### List Learning Sessions
```
GET /learning?user_id=&skip=0&limit=10

Query Parameters:
  user_id (string): Filter by user
  skip (integer): Number to skip (default: 0)
  limit (integer): Maximum results (default: 10)

Response 200:
{
  "learning_sessions": [
    {
      "learning_id": "integer",
      "user_id": "string",
      "topic": "string",
      "progress": "percentage",
      "created_at": "ISO 8601"
    }
  ],
  "total": "integer"
}
```

---

## 📊 Request/Response Formats

### Standard Request Headers
```
Authorization: Bearer {api_key}
Content-Type: application/json
Accept: application/json
User-Agent: NOVA-AI/1.0
X-Request-ID: {uuid}  (optional for tracing)
```

### Standard Response Format
```json
{
  "status": "success|error",
  "code": 200,
  "data": {},
  "message": "string (if applicable)",
  "timestamp": "ISO 8601",
  "request_id": "uuid"
}
```

### Error Response Format
```json
{
  "status": "error",
  "code": 422,
  "detail": [
    {
      "loc": ["path", "or", "body"],
      "msg": "Human readable error message",
      "type": "value_error|validation_error",
      "input": "what was provided",
      "ctx": {
        "error": "Additional context"
      }
    }
  ],
  "timestamp": "ISO 8601",
  "request_id": "uuid"
}
```

---

## ⚠️ Error Handling

### HTTP Status Codes

```python
class APIStatusCode:
    OK = 200                   # Success
    CREATED = 201              # Resource created
    NO_CONTENT = 204           # Success, no content
    BAD_REQUEST = 400          # Invalid request
    UNAUTHORIZED = 401         # Auth failed
    FORBIDDEN = 403            # Access denied
    NOT_FOUND = 404            # Resource not found
    VALIDATION_ERROR = 422     # Invalid data
    SERVER_ERROR = 500         # Server error
    SERVICE_UNAVAILABLE = 503  # Service down
```

### Error Handling in Python

```python
import aiohttp
import json
from typing import Dict, Any, Optional

class APIError(Exception):
    """Base API error"""
    pass

class ValidationError(APIError):
    """422 Validation Error"""
    pass

class NotFoundError(APIError):
    """404 Not Found Error"""
    pass

class UnauthorizedError(APIError):
    """401 Unauthorized Error"""
    pass

class ServerError(APIError):
    """500+ Server Error"""
    pass

class APIHandler:
    """Handle API responses with proper error handling"""
    
    async def handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle API response with error checking"""
        
        data = await response.json()
        
        if response.status == 200 or response.status == 201:
            return data
        
        elif response.status == 422:
            raise ValidationError(
                f"Validation Error: {json.dumps(data.get('detail', []))}"
            )
        
        elif response.status == 404:
            raise NotFoundError(f"Resource not found: {data.get('message')}")
        
        elif response.status == 401:
            raise UnauthorizedError("Invalid API key or expired token")
        
        elif response.status >= 500:
            raise ServerError(f"Server error ({response.status}): {data.get('message')}")
        
        else:
            raise APIError(f"Unexpected error: {response.status}")
```

---

## 🔗 Integration with NOVA-AI

### Async API Client for NOVA-AI

```python
import aiohttp
import json
from typing import Dict, List, Optional
from datetime import datetime

class NOVAAIAPIClient:
    """API client for NOVA-AI conversation and learning management"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # CONVERSATION MANAGEMENT
    
    async def create_conversation(
        self,
        title: str,
        topic: str,
        description: Optional[str] = None
    ) -> Dict:
        """Create a new conversation"""
        
        url = f"{self.base_url}/api/chat/conversations"
        payload = {
            "title": title,
            "topic": topic,
            "description": description
        }
        
        async with self.session.post(
            url,
            json=payload,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def get_conversation(self, conversation_id: str) -> Dict:
        """Get conversation details"""
        
        url = f"{self.base_url}/api/chat/conversations/{conversation_id}"
        
        async with self.session.get(
            url,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def delete_conversation(self, conversation_id: str) -> Dict:
        """Delete a conversation"""
        
        url = f"{self.base_url}/api/chat/conversations/{conversation_id}"
        
        async with self.session.delete(
            url,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def list_conversations(
        self,
        skip: int = 0,
        limit: int = 10,
        topic: Optional[str] = None
    ) -> Dict:
        """List all conversations"""
        
        url = f"{self.base_url}/api/chat/conversations"
        params = {"skip": skip, "limit": limit}
        
        if topic:
            params["topic"] = topic
        
        async with self.session.get(
            url,
            params=params,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    # MESSAGE MANAGEMENT
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Add message to conversation"""
        
        url = f"{self.base_url}/api/chat/conversations/{conversation_id}/messages"
        payload = {
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }
        
        async with self.session.post(
            url,
            json=payload,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Dict:
        """Get message history"""
        
        url = f"{self.base_url}/api/chat/conversations/{conversation_id}/messages"
        params = {"limit": limit, "offset": offset}
        
        async with self.session.get(
            url,
            params=params,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    # LEARNING MANAGEMENT
    
    async def create_learning_session(
        self,
        user_id: str,
        topic: str,
        objective: str
    ) -> Dict:
        """Create learning session"""
        
        url = f"{self.base_url}/api/learning"
        payload = {
            "user_id": user_id,
            "topic": topic,
            "objective": objective
        }
        
        async with self.session.post(
            url,
            json=payload,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def get_learning_progress(self, learning_id: int) -> Dict:
        """Get learning progress"""
        
        url = f"{self.base_url}/api/learning/{learning_id}"
        
        async with self.session.get(
            url,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def update_learning_progress(
        self,
        learning_id: int,
        progress: Optional[str] = None,
        completed_modules: Optional[List[str]] = None,
        quiz_scores: Optional[List[Dict]] = None
    ) -> Dict:
        """Update learning progress"""
        
        url = f"{self.base_url}/api/learning/{learning_id}"
        payload = {}
        
        if progress:
            payload["progress"] = progress
        if completed_modules:
            payload["completed_modules"] = completed_modules
        if quiz_scores:
            payload["quiz_scores"] = quiz_scores
        
        async with self.session.put(
            url,
            json=payload,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def delete_learning_progress(self, learning_id: int) -> Dict:
        """Delete learning progress"""
        
        url = f"{self.base_url}/api/learning/{learning_id}"
        
        async with self.session.delete(
            url,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    async def list_learning_sessions(
        self,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 10
    ) -> Dict:
        """List learning sessions"""
        
        url = f"{self.base_url}/api/learning"
        params = {"skip": skip, "limit": limit}
        
        if user_id:
            params["user_id"] = user_id
        
        async with self.session.get(
            url,
            params=params,
            headers=self._get_headers()
        ) as response:
            return await self._handle_response(response)
    
    # HELPER METHODS
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict:
        """Handle response with error checking"""
        
        data = await response.json()
        
        if response.status in [200, 201]:
            return data
        elif response.status == 422:
            raise ValidationError(f"Validation Error: {json.dumps(data.get('detail', []))}")
        elif response.status == 404:
            raise NotFoundError(f"Not Found: {data.get('message')}")
        elif response.status == 401:
            raise UnauthorizedError("Unauthorized: Invalid API key")
        elif response.status >= 500:
            raise ServerError(f"Server Error ({response.status}): {data.get('message')}")
        else:
            raise APIError(f"Error {response.status}: {data.get('message')}")
```

---

## 💻 Code Examples

### Example 1: Create and Manage Conversation

```python
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

async def manage_conversation():
    """Create, add messages, and delete conversation"""
    
    api_key = os.getenv("API_KEY")
    api_client = NOVAAIAPIClient(api_key)
    
    async with api_client:
        # Create conversation
        conversation = await api_client.create_conversation(
            title="AI Learning Session",
            topic="Machine Learning",
            description="Learning about ML algorithms"
        )
        print(f"Created conversation: {conversation['conversation_id']}")
        conv_id = conversation['conversation_id']
        
        # Add user message
        user_msg = await api_client.add_message(
            conversation_id=conv_id,
            role="user",
            content="Explain neural networks",
            metadata={
                "model": "claude",
                "confidence": 0.95
            }
        )
        print(f"Added user message: {user_msg['message_id']}")
        
        # Add assistant response
        asst_msg = await api_client.add_message(
            conversation_id=conv_id,
            role="assistant",
            content="Neural networks are...",
            metadata={
                "model": "claude-3-5-sonnet",
                "confidence": 0.98,
                "sources": ["research_paper_1", "textbook_2"]
            }
        )
        print(f"Added assistant message: {asst_msg['message_id']}")
        
        # Get conversation details
        conv = await api_client.get_conversation(conv_id)
        print(f"Conversation has {len(conv['messages'])} messages")
        
        # Delete conversation
        result = await api_client.delete_conversation(conv_id)
        print(f"Deleted conversation: {result['message']}")

asyncio.run(manage_conversation())
```

### Example 2: Track Learning Progress

```python
async def track_learning():
    """Create and track learning progress"""
    
    api_key = os.getenv("API_KEY")
    api_client = NOVAAIAPIClient(api_key)
    
    async with api_client:
        # Create learning session
        learning = await api_client.create_learning_session(
            user_id="user_123",
            topic="Python Programming",
            objective="Master async programming"
        )
        learning_id = learning['learning_id']
        print(f"Created learning session: {learning_id}")
        
        # Get progress
        progress = await api_client.get_learning_progress(learning_id)
        print(f"Current progress: {progress['progress']}")
        
        # Update progress
        updated = await api_client.update_learning_progress(
            learning_id=learning_id,
            progress="50%",
            completed_modules=["basics", "decorators", "asyncio"],
            quiz_scores=[
                {"quiz_id": "q1", "score": 85},
                {"quiz_id": "q2", "score": 92}
            ]
        )
        print(f"Updated progress: {updated['progress']}")

asyncio.run(track_learning())
```

### Example 3: Integration with NOVA-AI Orchestrator

```python
from nova_ai_system import NOVAAIOrchestrator

class EnhancedNOVAAI(NOVAAIOrchestrator):
    """Extended NOVA-AI with API persistence"""
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_client = NOVAAIAPIClient(api_key)
        self.current_conversation_id = None
    
    async def process_with_persistence(
        self,
        query: str,
        conversation_id: Optional[str] = None
    ) -> Dict:
        """Process query and save to API"""
        
        async with self.api_client:
            # Create new conversation if needed
            if not conversation_id:
                conv = await self.api_client.create_conversation(
                    title=f"Query: {query[:50]}",
                    topic="General",
                )
                conversation_id = conv['conversation_id']
            
            # Process query with NOVA-AI
            result = await self.process_user_query(query)
            
            # Save user query
            await self.api_client.add_message(
                conversation_id=conversation_id,
                role="user",
                content=query
            )
            
            # Save assistant response
            await self.api_client.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=result['synthesized_response'],
                metadata={
                    "model": result['recommended_model'],
                    "confidence": result['confidence_score']
                }
            )
            
            self.current_conversation_id = conversation_id
            return result

# Usage
async def main():
    nova_ai = EnhancedNOVAAI(api_key="your_api_key")
    
    result = await nova_ai.process_with_persistence(
        "What is machine learning?"
    )
    
    print(f"Response: {result['synthesized_response']}")
    print(f"Conversation ID: {nova_ai.current_conversation_id}")

asyncio.run(main())
```

---

## 🔒 Security Considerations

### API Key Management
```python
# NEVER hardcode API keys
NEVER:
  api_key = "your_key_12345"

ALWAYS:
  from dotenv import load_dotenv
  load_dotenv()
  api_key = os.getenv("API_KEY")
```

### Rate Limiting
```python
# Implement rate limiting
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int = 100, window: int = 60):
        self.max_requests = max_requests
        self.window = window  # seconds
        self.requests = []
    
    async def check_limit(self) -> bool:
        """Check if within rate limit"""
        now = datetime.now()
        # Remove old requests outside window
        self.requests = [
            req for req in self.requests
            if (now - req).seconds < self.window
        ]
        
        if len(self.requests) >= self.max_requests:
            return False
        
        self.requests.append(now)
        return True
```

### Request Validation
```python
from pydantic import BaseModel, validator

class ConversationCreate(BaseModel):
    """Validate conversation creation"""
    title: str
    topic: str
    description: Optional[str] = None
    
    @validator('title')
    def title_not_empty(cls, v):
        if not v or len(v) < 1:
            raise ValueError('Title cannot be empty')
        return v
```

---

## 📝 Summary

This API provides complete conversation and learning management for NOVA-AI:

✅ **Conversation Management** - Create, read, update, delete conversations
✅ **Message Tracking** - Store all messages with metadata
✅ **Learning Progress** - Track user learning and quiz scores
✅ **Error Handling** - Comprehensive error responses
✅ **Async Support** - Built for high performance
✅ **Security** - API key authentication and validation

**All documented endpoints are ready for integration with your NOVA-AI system!**

