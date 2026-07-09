# Quick Start - NOVA AI Knowledge Enhancement

## 5-Minute Setup

### Step 1: Copy Environment Template
```bash
cd "NOVA AI"
cp .env.knowledge-enhancement .env.local
```

### Step 2: Enable in Main App
Edit `backend/main.py` and add to imports:
```python
from services.knowledge_enhancement_bootstrap import initialize_knowledge_enhancement
```

Add to startup event:
```python
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    
    # Initialize knowledge enhancement
    init_result = await initialize_knowledge_enhancement()
    logger.info(f"Knowledge Enhancement: {init_result}")
```

Include routes:
```python
from routes.knowledge_enhancement import router as knowledge_router
app.include_router(knowledge_router)
```

### Step 3: Restart Backend
```bash
cd backend
python main.py
```

### Step 4: Test It Works
```bash
# Check provider status
curl http://localhost:8000/api/knowledge/health

# Try an enhancement
curl -X POST http://localhost:8000/api/knowledge/enhance \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "ai_response": "Machine learning is..."
  }'
```

---

## Key Files

| File | Purpose |
|------|---------|
| `intelligent_query_router.py` | Auto-classifies queries |
| `knowledge_providers.py` | Base provider system |
| `wikipedia_provider.py` | Wikipedia integration |
| `geeksforgeeks_provider.py` | Programming tutorials |
| `documentation_provider.py` | Official docs (15+ sources) |
| `extended_provider_clients.py` | New AI providers |
| `knowledge_fusion.py` | Merge multiple sources |
| `source_visibility.py` | Control source disclosure |
| `knowledge_enhancement_integration.py` | Chat flow integration |
| `knowledge_enhancement.py` (route) | REST API endpoints |

---

## Basic Usage

### In Your Chat Route
```python
from services.knowledge_enhancement_integration import enhance_chat_response

# After generating AI response
enhanced_result = await enhance_chat_response(
    query=user_query,
    ai_response=ai_response,
    include_sources=False  # Optional
)

# Use the enhanced response
response_to_send = enhanced_result["response"]
```

### Check If Sources Were Used
```python
if enhanced_result["enhanced"]:
    logger.info(f"Used {len(enhanced_result['sources'])} knowledge sources")
```

---

## Query Examples

### Example 1: General Knowledge
```python
await route_query("What is photosynthesis?")
# → wikipedia, internet_search

# Result: Wikipedia article + facts
```

### Example 2: Programming
```python
await route_query("How to use async/await in Python?")
# → geeksforgeeks, official_docs

# Result: Tutorial + Python docs
```

### Example 3: Documentation
```python
await route_query("React hooks documentation")
# → official_docs, geeksforgeeks

# Result: Official React docs + examples
```

### Example 4: With Source Request
```python
await route_query("Latest AI trends - show sources")
# → internet_search with visibility=detailed

# Result: News + citations with URLs
```

---

## Environment Variables (Essential)

```env
# Must be set to use features
KNOWLEDGE_ENHANCEMENT_ENABLED=true

# Optional: Set source visibility default
DEFAULT_SOURCE_VISIBILITY=hidden

# Optional: Add extended AI providers
MISTRAL_API_KEY=your-key
GROK_API_KEY=your-key
TOGETHER_API_KEY=your-key
OPENROUTER_API_KEY=your-key
OLLAMA_BASE_URL=http://localhost:11434
```

---

## API Endpoints

### Enhance Response
```bash
POST /api/knowledge/enhance
Content-Type: application/json

{
  "query": "What is Python?",
  "ai_response": "Python is a programming language...",
  "include_sources": false
}

Response:
{
  "response": "Enhanced response...",
  "sources": [...],
  "enhanced": true
}
```

### Search Knowledge
```bash
POST /api/knowledge/search
Content-Type: application/json

{
  "query": "Python async/await",
  "include_all_sources": false
}

Response:
{
  "query": "Python async/await",
  "sources": [...],
  "facts": [...],
  "found": true
}
```

### Get Provider Status
```bash
GET /api/knowledge/providers/status

Response:
{
  "total": 3,
  "healthy": 3,
  "providers": {...}
}
```

### Analyze Query Route
```bash
POST /api/knowledge/query-route
Content-Type: application/json

{
  "query": "How to debug code?"
}

Response:
{
  "query_type": "code_assistance",
  "providers": ["geeksforgeeks", "official_docs"],
  "confidence": 0.95
}
```

### Health Check
```bash
GET /api/knowledge/health

Response:
{
  "status": "healthy",
  "providers_healthy": 3,
  "providers_total": 3
}
```

---

## Testing

### Test Providers
```python
import asyncio
from services.knowledge_enhancement_bootstrap import initialize_knowledge_enhancement

async def test():
    status = await initialize_knowledge_enhancement()
    print(status)
    # Output: Shows all providers initialized

asyncio.run(test())
```

### Test Query Router
```python
from services.intelligent_query_router import route_query

result = route_query("How to use React hooks?")
print(result["query_type"])        # "framework_docs"
print(result["providers"])         # ["official_docs", "geeksforgeeks"]
print(result["confidence"])        # 0.95
```

### Test Knowledge Fusion
```python
from services.knowledge_fusion import fuse_knowledge_sources
from services.knowledge_providers import KnowledgeSource

# Create test sources
sources = [
    KnowledgeSource(provider=..., title="...", content="..."),
    KnowledgeSource(provider=..., title="...", content="..."),
]

# Fuse them
result = await fuse_knowledge_sources(sources, "query")
print(result.facts)        # Deduplicated facts
print(result.conflicts)    # Any conflicts detected
```

---

## Disable If Needed

To disable knowledge enhancement without code changes:

```env
# In .env
KNOWLEDGE_ENHANCEMENT_ENABLED=false
```

Or programmatically:
```python
from services.knowledge_enhancement_integration import get_integration

integration = get_integration()
integration.set_enabled(False)
```

---

## Logging

Enable debug logging:
```env
KNOWLEDGE_DEBUG_LOGGING=true
KNOWLEDGE_LOG_LEVEL=DEBUG
```

Check logs:
```bash
tail -f backend/logs/app.log | grep knowledge
```

---

## Troubleshooting

### Providers Not Initializing
```bash
# Check health
curl http://localhost:8000/api/knowledge/health

# Review logs
grep -i "initialization\|error" backend/logs/app.log
```

### Enhancement Not Working
```bash
# Check if enabled
curl http://localhost:8000/api/knowledge/enabled

# Check provider status
curl http://localhost:8000/api/knowledge/providers/status
```

### Slow Responses
```env
# Reduce parallel providers
MAX_PARALLEL_PROVIDERS=1

# Disable less important providers
ENABLE_WIKIPEDIA_PROVIDER=false
ENABLE_GEEKSFORGEEKS_PROVIDER=false
```

---

## Next Steps

1. **Review** [KNOWLEDGE_ENHANCEMENT_GUIDE.md](KNOWLEDGE_ENHANCEMENT_GUIDE.md)
2. **Test** each endpoint in Postman or curl
3. **Integrate** into your chat flow
4. **Configure** settings in .env
5. **Monitor** health and performance
6. **Extend** with custom providers if needed

---

## Support

For questions:
1. Check `/api/knowledge/documentation` endpoint
2. Review logs with `DEBUG=true`
3. Test each component independently
4. Verify provider connectivity

---

## Feature Summary

| Feature | Status | File |
|---------|--------|------|
| Query Router | ✅ | `intelligent_query_router.py` |
| Wikipedia | ✅ | `wikipedia_provider.py` |
| GeeksforGeeks | ✅ | `geeksforgeeks_provider.py` |
| Docs | ✅ | `documentation_provider.py` |
| Fusion | ✅ | `knowledge_fusion.py` |
| Visibility | ✅ | `source_visibility.py` |
| Extended AI | ✅ | `extended_provider_clients.py` |
| REST API | ✅ | `knowledge_enhancement.py` |

All features work independently and together!

---
