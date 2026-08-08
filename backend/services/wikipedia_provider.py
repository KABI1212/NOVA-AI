"""
Wikipedia Provider - Integration with Wikipedia API for general knowledge retrieval.

Uses the official Wikipedia API to:
- Search for relevant articles
- Retrieve article content
- Extract key facts and summaries
- Normalize data for AI integration

Never displays raw Wikipedia pages or unnecessary branding unless explicitly requested.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

from services.knowledge_providers import (
    KnowledgeProvider,
    KnowledgeSource,
    ProviderType,
    SearchResult,
)

logger = logging.getLogger(__name__)

# Wikipedia API endpoints
WIKIPEDIA_API_BASE = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_SEARCH_URL = f"{WIKIPEDIA_API_BASE}"
WIKIPEDIA_EXTRACT_URL = f"{WIKIPEDIA_API_BASE}"


class WikipediaProvider(KnowledgeProvider):
    """Wikipedia knowledge provider using official API."""
    
    def __init__(self):
        """Initialize Wikipedia provider."""
        super().__init__("Wikipedia", ProviderType.WIKIPEDIA)
        self.http_client: Optional[httpx.AsyncClient] = None
        self.timeout = 10.0
        self.headers = {
            "User-Agent": "NovaAI/1.0 (https://nova-ai.org; contact@nova-ai.org)",
            "Accept": "application/json",
        }
    
    async def _setup(self) -> bool:
        """Setup Wikipedia provider."""
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
            # Test the API connection
            response = await self.http_client.get(
                WIKIPEDIA_API_BASE,
                params={"action": "query", "format": "json", "meta": "siteinfo"},
                timeout=self.timeout,
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Wikipedia setup failed: {e}")
            return False
    
    async def _search(self, query: str, limit: int = 10) -> SearchResult:
        """Search Wikipedia for articles matching the query."""
        import time
        start_time = time.time()
        
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
            
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": min(limit, 50),
                "srprop": "snippet|size",
            }
            
            response = await self.http_client.get(WIKIPEDIA_SEARCH_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            
            results = []
            for item in search_results[:limit]:
                raw_title = item.get("title", "")
                wiki_slug = raw_title.replace(" ", "_")
                results.append({
                    "id": wiki_slug,
                    "title": raw_title,
                    "snippet": item.get("snippet", ""),
                    "size": item.get("size", 0),
                    "url": f"https://en.wikipedia.org/wiki/{wiki_slug}",
                    "relevance": 0.8,  # Wikipedia is fairly authoritative
                })
            
            search_time = (time.time() - start_time) * 1000
            
            return SearchResult(
                query=query,
                provider=self.provider_type,
                total_results=len(search_results),
                results=results,
                search_time_ms=search_time,
                is_successful=True,
            )
        
        except Exception as e:
            logger.error(f"Wikipedia search error: {e}")
            search_time = (time.time() - start_time) * 1000
            return SearchResult(
                query=query,
                provider=self.provider_type,
                total_results=0,
                results=[],
                search_time_ms=search_time,
                is_successful=False,
                error=str(e),
            )
    
    async def _retrieve(self, source_id: str) -> Optional[KnowledgeSource]:
        """Retrieve full article content from Wikipedia."""
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
            
            # source_id is the article title or slug
            clean_title = source_id.replace("_", " ")
            wiki_slug = clean_title.replace(" ", "_")
            params = {
                "action": "query",
                "format": "json",
                "titles": clean_title,
                "prop": "extracts|pageprops",
                "explaintext": True,
                "exsectionformat": "plain",
                "redirects": True,
            }
            
            response = await self.http_client.get(WIKIPEDIA_EXTRACT_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            
            for page_id, page_data in pages.items():
                if page_id == "-1":  # Article not found
                    return None
                
                title = page_data.get("title", clean_title)
                content = page_data.get("extract", "")[:3000]  # Limit to 3000 chars
                
                if not content:
                    return None
                
                return await self._normalize({
                    "title": title,
                    "content": content,
                    "source_id": source_id,
                    "url": f"https://en.wikipedia.org/wiki/{wiki_slug}",
                })
            
            return None
        
        except Exception as e:
            logger.error(f"Wikipedia retrieval error: {e}")
            return None
    
    async def _extract(self, content: str) -> Dict[str, Any]:
        """Extract facts from Wikipedia content."""
        try:
            # Simple fact extraction - split by sentences and paragraphs
            paragraphs = content.split("\n\n")
            sentences = []
            
            for para in paragraphs:
                # Split into sentences, limit length
                para_sentences = re.split(r'(?<=[.!?])\s+', para.strip())
                sentences.extend([s.strip() for s in para_sentences if s.strip() and len(s) > 10])
            
            # Extract entities (simplified - look for capitalized words)
            entities = set()
            for sentence in sentences[:10]:  # First 10 sentences
                words = sentence.split()
                for word in words:
                    if word[0].isupper() and len(word) > 3:
                        entities.add(word.rstrip('.,;:!?'))
            
            # Create summary from first few sentences
            summary = " ".join(sentences[:3]) if sentences else content[:200]
            
            return {
                "facts": sentences[:20],  # First 20 relevant facts
                "entities": list(entities)[:10],
                "summary": summary,
                "sentence_count": len(sentences),
                "paragraph_count": len(paragraphs),
            }
        
        except Exception as e:
            logger.error(f"Wikipedia extraction error: {e}")
            return {"facts": [], "entities": [], "summary": "", "error": str(e)}
    
    async def _normalize(self, raw_data: Dict[str, Any]) -> KnowledgeSource:
        """Normalize Wikipedia data into KnowledgeSource format."""
        try:
            title = raw_data.get("title", "Unknown")
            content = raw_data.get("content", "")
            url = raw_data.get("url", "")
            
            # Extract facts
            extraction = await self._extract(content)
            
            return KnowledgeSource(
                provider=self.provider_type,
                title=title,
                content=content,
                url=url,
                summary=extraction.get("summary", ""),
                confidence=0.85,  # Wikipedia has good general reliability
                metadata={
                    "entities": extraction.get("entities", []),
                    "fact_count": len(extraction.get("facts", [])),
                    "source_type": "encyclopedia",
                },
                citations=[url] if url else [],
                relevance_score=0.8,
            )
        
        except Exception as e:
            logger.error(f"Wikipedia normalization error: {e}")
            return KnowledgeSource(
                provider=self.provider_type,
                title="Error",
                content=str(e),
            )
    
    async def _generate(self, sources: List[KnowledgeSource]) -> str:
        """Generate AI-ready content from Wikipedia sources."""
        if not sources:
            return ""
        
        try:
            output_parts = []
            
            for source in sources:
                # Remove Wikipedia-specific markup
                content = source.content
                content = re.sub(r'\[\d+\]', '', content)  # Remove citation markers
                content = re.sub(r'\{.*?\}', '', content)  # Remove template markup
                
                # Create a clean content block
                output_parts.append(f"### {source.title}\n\n{content}")
                
                if source.url:
                    output_parts.append(f"\n*Source: {source.url}*")
            
            return "\n\n".join(output_parts)
        
        except Exception as e:
            logger.error(f"Wikipedia generation error: {e}")
            return ""
    
    async def _health_check(self) -> bool:
        """Check if Wikipedia API is accessible."""
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout)
            
            response = await self.http_client.get(
                WIKIPEDIA_API_BASE,
                params={"action": "query", "format": "json", "meta": "siteinfo"},
                timeout=5.0,
            )
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Wikipedia health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self.http_client and not self.http_client.is_closed:
            try:
                await self.http_client.aclose()
            except Exception:
                pass
            self.http_client = None
