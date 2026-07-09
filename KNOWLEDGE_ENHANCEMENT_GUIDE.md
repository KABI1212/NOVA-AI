# NOVA AI - Knowledge Enhancement Features

## Overview

NOVA AI has been enhanced with intelligent knowledge routing and multi-provider knowledge fusion. These features automatically route queries to appropriate knowledge sources and intelligently merge information from multiple providers to deliver more comprehensive and current responses.

**Key Principle**: All existing functionality remains unchanged. These are purely additive features that don't break backward compatibility.

---

## Architecture

### 1. Intelligent Query Router

Automatically classifies user queries into categories:

- **General Knowledge** → Wikipedia
- **Programming** → GeeksforGeeks
- **Framework Documentation** → Official Docs
- **Latest News** → Internet Search
- **Research** → Research APIs
- **Career Guidance** → NOVA Career Engine
- **Creative Writing** → Local Knowledge Only
- **Code Assistance** → GeeksforGeeks + Official Docs

**No user action required** - routing happens automatically and internally.

### 2. Knowledge Providers

#### Wikipedia Provider
- Official Wikipedia API integration
- Retrieves authoritative general knowledge
- Extracts facts and entities
- Confidence: 0.85

#### GeeksforGeeks Provider
- Search-based retrieval
- Extracts programming tutorials
- Identifies technical concepts
- Respects terms of use
- Confidence: 0.9

#### Official Documentation Provider
- Supports 15+ languages and frameworks:
  - Python, Java, JavaScript, TypeScript, Rust, Go
  - React, Angular, Vue, Next.js, Node.js
  - FastAPI, Django, Spring, .NET, etc.
- Routes to appropriate official sources
- Highest confidence: 0.95

### 3. Knowledge Fusion

When multiple providers are used:
- **Deduplicates** facts across sources
- **Resolves conflicts** using provider priority
- **Ranks information** by confidence and relevance
- **Merges intelligently** to avoid redundancy
- **Generates unified NOVA response**

### 4. Source Visibility Control

By default:
- **Never** displays raw Wikipedia pages
- **Never** displays search results directly
- **Never** shows URLs or internal sources
- **Only** shows the final NOVA AI response

When user explicitly asks for sources:
- Shows citations with links
- Indicates provider attribution
- Provides reference URLs
- Transparency about sources used

### 5. Plugin Architecture

New providers can be added by implementing:
```python
class NewProvider(KnowledgeProvider):
    async def _setup(self) -> bool: ...
    async def _search(self, query: str, limit: int) -> SearchResult: ...
    async def _retrieve(self, source_id: str) -> Optional[KnowledgeSource]: ...
    async def _extract(self, content: str) -> Dict[str, Any]: ...
    async def _normalize(self, raw_data: Dict) -> KnowledgeSource: ...
    async def _generate(self, sources: List) -> str: ...
    async def _health_check(self) -> bool: ...
```

---

## Configuration

### Environment Variables

```env
# Optional: Enable/disable knowledge enhancement
KNOWLEDGE_ENHANCEMENT_ENABLED=true

# Optional: Set default source visibility level
DEFAULT_SOURCE_VISIBILITY=hidden  # hidden, minimal, normal, detailed, comprehensive

# Optional: Maximum parallel providers to use
MAX_PARALLEL_PROVIDERS=3

# Optional: Wikipedia specific
WIKIPEDIA_API_TIMEOUT=10

# Optional: GeeksforGeeks specific
GEEKSFORGEEKS_API_TIMEOUT=10

# Optional: Extended AI Providers (new feature)
MISTRAL_API_KEY=your-key-here
GROK_API_KEY=your-key-here
TOGETHER_API_KEY=your-key-here
OPENROUTER_API_KEY=your-key-here
OLLAMA_BASE_URL=http://localhost:11434

# Optional: Mistral specific
MISTRAL_MODEL=mistral-large-latest

# Optional: Grok specific
GROK_MODEL=grok-2-1212

# Optional: Together AI specific
TOGETHER_MODEL=meta-llama/Llama-3-70b-chat-hf

# Optional: OpenRouter specific
OPENROUTER_REFERER=http://localhost:3000
OPENROUTER_APP_NAME=NOVA AI
OPENROUTER_MODEL=gpt-4o-mini

# Optional: Ollama specific
OLLAMA_MODEL=neural-chat
OLLAMA_BASE_URL=http://localhost:11434
```

---

## API Endpoints

All new endpoints are optional and don't affect existing chat endpoints.

### Enhance Response
```
POST /api/knowledge/enhance

Request:
{
    "query": "What is Python?",
    "ai_response": "Python is a programming language...",
    "include_sources": false,
    "visibility_level": null
}

Response:
{
    "response": "Enhanced response with knowledge...",
    "sources": [...],
    "metadata": {...},
    "enhanced": true
}
```

### Search Knowledge
```
POST /api/knowledge/search

Request:
{
    "query": "How to use React hooks?",
    "include_all_sources": false
}

Response:
{
    "query": "How to use React hooks?",
    "sources": [...],
    "facts": [...],
    "summary": "...",
    "found": true,
    "source_count": 3
}
```

### Get Provider Status
```
GET /api/knowledge/providers/status

Response:
{
    "total": 3,
    "healthy": 3,
    "providers": {
        "wikipedia_Wikipedia": {...},
        "geeksforgeeks_GeeksforGeeks": {...},
        "official_docs_Official Documentation": {...}
    }
}
```

### Analyze Query Route
```
POST /api/knowledge/query-route

Request:
{
    "query": "How to debug Python code?"
}

Response:
{
    "query_type": "programming",
    "providers": ["geeksforgeeks", "official_docs"],
    "use_local_only": false,
    "ai_provider_strategy": "prefer_gemini",
    "confidence": 0.95,
    "keywords": ["programming", "python", "debug"]
}
```

### Check Enhancement Status
```
GET /api/knowledge/enabled

Response:
{
    "enabled": true
}
```

### Health Check
```
GET /api/knowledge/health

Response:
{
    "status": "healthy",
    "providers_healthy": 3,
    "providers_total": 3,
    "provider_status": {
        "wikipedia_Wikipedia": true,
        "geeksforgeeks_GeeksforGeeks": true,
        "official_docs_Official Documentation": true
    }
}
```

---

## Integration Points

The knowledge enhancement integrates at:

1. **Chat Response Enhancement** - Optional call after AI generation
2. **Search Queries** - Enhanced search results
3. **Code Queries** - Technical documentation routing
4. **General Knowledge** - Wikipedia augmentation

**Integration is optional** - existing chat flows continue unchanged.

---

## Usage Examples

### Example 1: General Knowledge Query
```
User: "What is photosynthesis?"

Router Decision:
- Type: general_knowledge
- Providers: [wikipedia, internet_search]
- Strategy: balanced

Result:
- Wikipedia article retrieved
- Facts extracted and verified
- Response enhanced with authoritative information
- Sources: hidden (default)
```

### Example 2: Programming Question
```
User: "How do I use async/await in Python?"

Router Decision:
- Type: code_assistance
- Providers: [geeksforgeeks, official_docs]
- Strategy: prefer_gemini

Result:
- GeeksforGeeks tutorial retrieved
- Python official docs searched
- Knowledge fused and deduplicated
- Code examples provided
- Sources: hidden by default
```

### Example 3: Explicit Source Request
```
User: "What are the latest AI trends? Show me your sources."

Router Decision:
- Type: latest_news
- Providers: [internet_search]
- Visibility: detailed (detected from "show me your sources")

Result:
- Recent news articles searched
- Comprehensive information gathered
- Response includes citations with URLs
- Sources displayed inline
```

### Example 4: Framework Documentation
```
User: "React hooks documentation"

Router Decision:
- Type: framework_docs
- Providers: [official_docs, geeksforgeeks]
- Strategy: balanced

Result:
- Official React docs retrieved (priority 1.0)
- GeeksforGeeks examples retrieved (priority 0.85)
- Knowledge merged
- Links to official docs included
```

---

## New AI Providers

Extended support for additional AI providers:

### Mistral AI
```python
await ask_mistral(prompt, system_prompt, model="mistral-large-latest")
```
- Requires: MISTRAL_API_KEY

### Grok (xAI)
```python
await ask_grok(prompt, system_prompt, model="grok-2-1212")
```
- Requires: GROK_API_KEY

### Together AI
```python
await ask_together(prompt, system_prompt, model="meta-llama/Llama-3-70b-chat-hf")
```
- Requires: TOGETHER_API_KEY

### OpenRouter
```python
await ask_openrouter(prompt, system_prompt, model="gpt-4o-mini")
```
- Requires: OPENROUTER_API_KEY
- Supports: 200+ models via single API

### Ollama (Extended)
```python
await ask_ollama_extended(
    prompt,
    system_prompt,
    model="neural-chat",
    base_url="http://localhost:11434"
)
```
- Local deployment
- No API keys needed
- Supports: Llama, Mistral, Neural Chat, Orca, etc.

---

## Source Visibility Levels

### Hidden (Default)
```
User sees: "Based on my knowledge..."
User doesn't see: Any provider information
```

### Minimal
```
User sees: "Based on Wikipedia"
User doesn't see: URLs or specific pages
```

### Normal
```
User sees:
- Wikipedia: Photosynthesis article
- GeeksforGeeks: Python async tutorial
```

### Detailed
```
User sees:
- [Wikipedia](https://en.wikipedia.org/wiki/Photosynthesis)
- [GeeksforGeeks](https://www.geeksforgeeks.org/async-await-python/)
```

### Comprehensive
```
User sees: Full source details, confidence scores, relevance scores, summaries
```

---

## System Architecture Diagram

```
User Query
     ↓
Intelligent Router
     ↓
[Classify Query Type]
     ↓
Provider Selection
     ├── Wikipedia
     ├── GeeksforGeeks
     └── Official Docs
     ↓
[Search in Parallel]
     ↓
[Retrieve & Extract]
     ↓
Knowledge Fusion
├── Deduplicate
├── Resolve Conflicts
└── Rank by Priority
     ↓
Source Visibility Control
├── Hidden (default)
├── Minimal
├── Normal
├── Detailed
└── Comprehensive
     ↓
Enhanced Response
```

---

## Performance Considerations

- **Caching**: Provider results cached by default
- **Timeouts**: Parallel queries timeout independently
- **Degradation**: Healthy providers used when some fail
- **Defaults**: Falls back to AI-only if no sources available
- **Optimization**: Similarity-based deduplication reduces redundancy

---

## Troubleshooting

### Providers showing as unhealthy
1. Check internet connectivity
2. Verify API endpoints are accessible
3. Review logs for specific errors
4. Restart backend service

### Knowledge enhancement not working
1. Verify `KNOWLEDGE_ENHANCEMENT_ENABLED=true` in .env
2. Check `/api/knowledge/health` endpoint
3. Review server logs for initialization errors
4. Ensure providers are registered

### Sources appearing when hidden
1. Check source visibility level setting
2. Verify visibility controller is initialized
3. Review response formatting logic
4. Check for provider mention keywords

---

## Future Extensibility

The plugin architecture allows easy addition of:

- **ArXiv Integration** - Research papers
- **GitHub Integration** - Code repositories
- **Stack Overflow Integration** - Q&A
- **Custom APIs** - Domain-specific sources
- **Machine Learning APIs** - Advanced reasoning
- **Vector Databases** - Semantic search

Simply implement the `KnowledgeProvider` interface and register with the provider registry.

---

## Backward Compatibility

✅ All existing routes unchanged
✅ All existing chat functionality works as before
✅ No database schema changes
✅ No authentication changes
✅ Optional feature - can be disabled
✅ Graceful degradation if providers unavailable
✅ No breaking API changes

---

## Support & Questions

For issues or questions about knowledge enhancement:

1. Check the Knowledge Enhancement API documentation: `/api/knowledge/documentation`
2. Review provider status: `/api/knowledge/providers/status`
3. Analyze query routing: `/api/knowledge/query-route`
4. Run health check: `/api/knowledge/health`
5. Review logs in `backend/logs/`

---

## Changelog

### V1.0 (Initial Release)
- ✅ Intelligent Query Router
- ✅ Wikipedia Provider
- ✅ GeeksforGeeks Provider
- ✅ Official Documentation Provider
- ✅ Knowledge Fusion Engine
- ✅ Source Visibility Control
- ✅ Plugin Architecture
- ✅ Extended AI Providers
- ✅ Optional REST API

---
