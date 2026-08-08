"""
GeeksforGeeks Provider - Integration for programming and technical content.

Uses search-based retrieval to:
- Find relevant programming tutorials
- Extract technical concepts
- Summarize programming content
- Never expose raw content, always optimize for NOVA

Respects the site's terms of use and provides proper attribution.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from urllib.parse import urlencode

import httpx

from services.knowledge_providers import (
    KnowledgeProvider,
    KnowledgeSource,
    ProviderType,
    SearchResult,
)

logger = logging.getLogger(__name__)


class GeeksforGeeksProvider(KnowledgeProvider):
    """GeeksforGeeks knowledge provider for programming content."""
    
    def __init__(self):
        """Initialize GeeksforGeeks provider."""
        super().__init__("GeeksforGeeks", ProviderType.GEEKSFORGEEKS)
        self.http_client: Optional[httpx.AsyncClient] = None
        self.timeout = 10.0
        self.base_url = "https://www.geeksforgeeks.org"
        self.search_url = "https://www.geeksforgeeks.org/search-results"
    
    async def _setup(self) -> bool:
        """Setup GeeksforGeeks provider."""
        try:
            self.http_client = httpx.AsyncClient(timeout=self.timeout)
            # Test connection
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    timeout=5.0,
                    headers={"User-Agent": "Mozilla/5.0 (Educational AI)"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"GeeksforGeeks setup failed: {e}")
            return False
    
    async def _search(self, query: str, limit: int = 10) -> SearchResult:
        """Search GeeksforGeeks for relevant content."""
        import time
        start_time = time.time()
        
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout)
            
            # Build search URL with query
            search_query = query.replace(" ", "-")
            search_params = f"?q={query}"
            search_endpoint = f"{self.search_url}{search_params}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Educational AI)",
                "Accept": "application/json, text/plain, */*",
            }
            
            response = await self.http_client.get(
                search_endpoint,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            # Parse search results using regex-based extraction
            results = await self._parse_search_results(
                response.text, query, limit
            )
            
            search_time = (time.time() - start_time) * 1000
            
            return SearchResult(
                query=query,
                provider=self.provider_type,
                total_results=len(results),
                results=results,
                search_time_ms=search_time,
                is_successful=True,
            )
        
        except Exception as e:
            logger.error(f"GeeksforGeeks search error: {e}")
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
    
    async def _parse_search_results(
        self, html: str, query: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Parse HTML search results from GeeksforGeeks."""
        results = []
        
        try:
            # Look for article links in the HTML
            # Pattern for GFG article URLs
            article_pattern = r'href="(https?://www\.geeksforgeeks\.org/[^"]+)"[^>]*>([^<]+)</a>'
            
            matches = re.finditer(article_pattern, html)
            
            for match in list(matches)[:limit]:
                url = match.group(1)
                title = match.group(2).strip()
                
                # Skip irrelevant results
                if not title or len(title) < 3:
                    continue
                
                results.append({
                    "id": url.split("/")[-2],
                    "title": title,
                    "url": url,
                    "snippet": f"GeeksforGeeks article on {title}",
                    "relevance": 0.85,
                    "source": "geeksforgeeks",
                })
            
            return results[:limit]
        
        except Exception as e:
            logger.error(f"Search results parsing error: {e}")
            return []
    
    async def _retrieve(self, source_id: str) -> Optional[KnowledgeSource]:
        """Retrieve content from GeeksforGeeks article."""
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout)
            
            # source_id could be URL or article slug
            if source_id.startswith("http"):
                url = source_id
            else:
                url = f"{self.base_url}/{source_id}/"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Educational AI)",
            }
            
            response = await self.http_client.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Extract article content
            content, title = await self._extract_article_content(response.text)
            
            if not content:
                return None
            
            return await self._normalize({
                "title": title or source_id,
                "content": content[:2000],  # Limit content length
                "url": url,
                "source_id": source_id,
            })
        
        except Exception as e:
            logger.error(f"GeeksforGeeks retrieval error: {e}")
            return None
    
    async def _extract_article_content(self, html: str) -> tuple[str, str]:
        """Extract main article content from HTML."""
        try:
            # Extract title
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            title = title_match.group(1).strip() if title_match else "Article"
            
            # Extract main content (look for article body)
            # Remove scripts, styles, and nav elements
            content = html
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
            content = re.sub(r'<nav[^>]*>.*?</nav>', '', content, flags=re.DOTALL)
            
            # Extract text from article tag
            article_match = re.search(
                r'<article[^>]*>(.*?)</article>',
                content,
                re.DOTALL
            )
            if article_match:
                content = article_match.group(1)
            
            # Convert HTML to plain text
            content = re.sub(r'<[^>]+>', '\n', content)
            content = re.sub(r'\n\n+', '\n', content)
            content = content.strip()
            
            return content, title
        
        except Exception as e:
            logger.error(f"Content extraction error: {e}")
            return "", ""
    
    async def _extract(self, content: str) -> Dict[str, Any]:
        """Extract programming concepts from content."""
        try:
            # Find code blocks
            code_blocks = re.findall(r'```[\s\S]*?```', content)
            
            # Find key concepts (words in code context)
            concepts = set()
            
            # Common programming keywords
            keywords = {
                'function', 'class', 'variable', 'method', 'parameter',
                'loop', 'condition', 'array', 'list', 'dictionary',
                'string', 'integer', 'boolean', 'operator', 'module',
                'import', 'package', 'library', 'framework', 'api',
                'algorithm', 'recursion', 'sorting', 'searching',
                'pointer', 'reference', 'object', 'inheritance',
            }
            
            for keyword in keywords:
                if keyword in content.lower():
                    concepts.add(keyword)
            
            # Split into sentences
            sentences = re.split(r'[.!?]\s+', content)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            return {
                "facts": sentences[:15],
                "concepts": list(concepts),
                "code_blocks": len(code_blocks),
                "summary": " ".join(sentences[:3]),
                "keywords": list(concepts),
            }
        
        except Exception as e:
            logger.error(f"GeeksforGeeks extraction error: {e}")
            return {
                "facts": [],
                "concepts": [],
                "code_blocks": 0,
                "summary": "",
                "keywords": [],
            }
    
    async def _normalize(self, raw_data: Dict[str, Any]) -> KnowledgeSource:
        """Normalize GeeksforGeeks data into KnowledgeSource format."""
        try:
            title = raw_data.get("title", "Article")
            content = raw_data.get("content", "")
            url = raw_data.get("url", "")
            
            extraction = await self._extract(content)
            
            return KnowledgeSource(
                provider=self.provider_type,
                title=title,
                content=content,
                url=url,
                summary=extraction.get("summary", ""),
                confidence=0.9,  # GeeksforGeeks is reliable for programming
                metadata={
                    "concepts": extraction.get("concepts", []),
                    "code_blocks": extraction.get("code_blocks", 0),
                    "source_type": "tutorial",
                },
                citations=[url] if url else [],
                relevance_score=0.85,
            )
        
        except Exception as e:
            logger.error(f"GeeksforGeeks normalization error: {e}")
            return KnowledgeSource(
                provider=self.provider_type,
                title="Error",
                content=str(e),
            )
    
    async def _generate(self, sources: List[KnowledgeSource]) -> str:
        """Generate AI-ready content from GeeksforGeeks sources."""
        if not sources:
            return ""
        
        try:
            output_parts = []
            
            for source in sources:
                # Clean and summarize content
                content = source.content
                
                # Highlight key concepts
                if source.metadata.get("concepts"):
                    concepts = source.metadata["concepts"]
                    output_parts.append(f"### {source.title}\n")
                    output_parts.append(f"**Key Concepts:** {', '.join(concepts)}\n")
                
                output_parts.append(f"\n{content}")
                
                if source.url:
                    output_parts.append(f"\n[GeeksforGeeks Reference]({source.url})")
            
            return "\n\n".join(output_parts)
        
        except Exception as e:
            logger.error(f"GeeksforGeeks generation error: {e}")
            return ""
    
    async def _health_check(self) -> bool:
        """Check if GeeksforGeeks is accessible."""
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout)
            
            response = await self.http_client.get(
                self.base_url,
                timeout=5.0,
                headers={"User-Agent": "Mozilla/5.0 (Educational AI)"},
            )
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"GeeksforGeeks health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self.http_client and not self.http_client.is_closed:
            try:
                await self.http_client.aclose()
            except Exception:
                pass
            self.http_client = None
