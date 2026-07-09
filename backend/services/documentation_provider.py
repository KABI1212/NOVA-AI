"""
Official Documentation Provider - Integration for language and framework docs.

Supports:
- Python Docs
- Java Docs
- React Docs
- FastAPI Docs
- Django Docs
- MDN (Mozilla Developer Network)
- Microsoft Learn
- Oracle Docs
- Spring Docs

Routes documentation queries to the appropriate official source.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from services.knowledge_providers import (
    KnowledgeProvider,
    KnowledgeSource,
    ProviderType,
    SearchResult,
)

logger = logging.getLogger(__name__)


class DocumentationProvider(KnowledgeProvider):
    """Official documentation provider for languages and frameworks."""
    
    # Documentation sources mapping
    DOCUMENTATION_SOURCES = {
        "python": {
            "base_url": "https://docs.python.org/3",
            "search_url": "https://docs.python.org/3/search.html",
            "name": "Python Official Documentation",
        },
        "java": {
            "base_url": "https://docs.oracle.com/en/java/javase/",
            "search_url": "https://docs.oracle.com/en/java/javase/21/docs/api/",
            "name": "Java API Documentation",
        },
        "react": {
            "base_url": "https://react.dev",
            "search_url": "https://react.dev",
            "name": "React Documentation",
        },
        "fastapi": {
            "base_url": "https://fastapi.tiangolo.com",
            "search_url": "https://fastapi.tiangolo.com/search/",
            "name": "FastAPI Documentation",
        },
        "django": {
            "base_url": "https://docs.djangoproject.com",
            "search_url": "https://docs.djangoproject.com/search/",
            "name": "Django Documentation",
        },
        "mdn": {
            "base_url": "https://developer.mozilla.org/en-US",
            "search_url": "https://developer.mozilla.org/en-US/search",
            "name": "MDN Web Docs",
        },
        "javascript": {
            "base_url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
            "search_url": "https://developer.mozilla.org/en-US/search",
            "name": "MDN JavaScript",
        },
        "typescript": {
            "base_url": "https://www.typescriptlang.org/docs",
            "search_url": "https://www.typescriptlang.org/docs",
            "name": "TypeScript Documentation",
        },
        "angular": {
            "base_url": "https://angular.io/docs",
            "search_url": "https://angular.io/docs",
            "name": "Angular Documentation",
        },
        "vue": {
            "base_url": "https://vuejs.org",
            "search_url": "https://vuejs.org/guide/",
            "name": "Vue.js Documentation",
        },
        "nextjs": {
            "base_url": "https://nextjs.org/docs",
            "search_url": "https://nextjs.org/docs",
            "name": "Next.js Documentation",
        },
        "nodejs": {
            "base_url": "https://nodejs.org/docs",
            "search_url": "https://nodejs.org/docs",
            "name": "Node.js Documentation",
        },
        "rust": {
            "base_url": "https://doc.rust-lang.org",
            "search_url": "https://doc.rust-lang.org",
            "name": "Rust Documentation",
        },
        "go": {
            "base_url": "https://golang.org/doc",
            "search_url": "https://golang.org/doc",
            "name": "Go Documentation",
        },
        "csharp": {
            "base_url": "https://learn.microsoft.com/en-us/dotnet/csharp",
            "search_url": "https://learn.microsoft.com/en-us/dotnet",
            "name": "C# Documentation",
        },
        "dotnet": {
            "base_url": "https://learn.microsoft.com/en-us/dotnet",
            "search_url": "https://learn.microsoft.com/en-us/dotnet",
            "name": ".NET Documentation",
        },
        "spring": {
            "base_url": "https://spring.io/projects/spring-boot",
            "search_url": "https://spring.io/projects/spring-boot",
            "name": "Spring Boot Documentation",
        },
    }
    
    def __init__(self):
        """Initialize documentation provider."""
        super().__init__("Official Documentation", ProviderType.OFFICIAL_DOCS)
        self.http_client: Optional[httpx.AsyncClient] = None
        self.timeout = 10.0
    
    async def _setup(self) -> bool:
        """Setup documentation provider."""
        try:
            self.http_client = httpx.AsyncClient(timeout=self.timeout)
            return True
        except Exception as e:
            logger.error(f"Documentation provider setup failed: {e}")
            return False
    
    def _detect_documentation_type(self, query: str) -> Optional[str]:
        """Detect which documentation to use for the query."""
        query_lower = query.lower()
        
        for doc_type in self.DOCUMENTATION_SOURCES.keys():
            if doc_type in query_lower:
                return doc_type
        
        # Check for framework-specific keywords
        framework_keywords = {
            "python": ["python", "pip", "conda", "virtualenv"],
            "java": ["java", "jvm", "maven", "gradle"],
            "react": ["react", "jsx", "hooks", "useState"],
            "fastapi": ["fastapi", "starlette", "pydantic"],
            "django": ["django", "wsgi", "orm"],
            "javascript": ["javascript", "js", "node", "npm"],
            "typescript": ["typescript", "ts", "tsc"],
            "nextjs": ["next.js", "nextjs", "ssr"],
            "vue": ["vue", "vue.js"],
            "angular": ["angular", "ngmodule"],
            "rust": ["rust", "cargo", "crate"],
            "go": ["golang", "go", "goroutine"],
            "csharp": ["c#", "csharp", "dotnet"],
            "spring": ["spring", "springboot", "annotation"],
        }
        
        for doc_type, keywords in framework_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return doc_type
        
        return None
    
    async def _search(self, query: str, limit: int = 10) -> SearchResult:
        """Search documentation for relevant content."""
        import time
        start_time = time.time()
        
        try:
            # Detect which docs to search
            doc_type = self._detect_documentation_type(query)
            
            if not doc_type or doc_type not in self.DOCUMENTATION_SOURCES:
                doc_type = "mdn"  # Default to MDN
            
            source = self.DOCUMENTATION_SOURCES[doc_type]
            
            # Build results list with documentation links
            results = self._generate_documentation_results(query, doc_type, source)
            
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
            logger.error(f"Documentation search error: {e}")
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
    
    def _generate_documentation_results(
        self, query: str, doc_type: str, source: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Generate documentation search results."""
        results = []
        
        # Build search-specific URLs based on doc type
        if doc_type == "python":
            # Build Python docs search URL
            search_terms = query.split()
            results.append({
                "id": "python_main",
                "title": "Python Official Documentation",
                "url": f"{source['base_url']}/",
                "snippet": "Official Python documentation and API reference",
                "relevance": 0.95,
                "source": "python",
            })
            
            if any(term in query.lower() for term in ["library", "module", "function"]):
                results.append({
                    "id": "python_library",
                    "title": "Python Standard Library",
                    "url": f"{source['base_url']}/library/",
                    "snippet": "Python standard library reference",
                    "relevance": 0.9,
                    "source": "python",
                })
        
        elif doc_type in ["mdn", "javascript"]:
            results.append({
                "id": "mdn_main",
                "title": f"MDN - {query}",
                "url": f"{source['base_url']}/",
                "snippet": f"MDN Web Docs for {query}",
                "relevance": 0.95,
                "source": "mdn",
            })
        
        elif doc_type == "react":
            results.append({
                "id": "react_docs",
                "title": "React Documentation",
                "url": f"{source['base_url']}/",
                "snippet": "Official React documentation",
                "relevance": 0.95,
                "source": "react",
            })
            
            if any(term in query.lower() for term in ["hook", "component", "api"]):
                results.append({
                    "id": "react_api",
                    "title": "React API Reference",
                    "url": f"{source['base_url']}/reference/",
                    "snippet": "React API and hooks reference",
                    "relevance": 0.9,
                    "source": "react",
                })
        
        else:
            # Generic documentation result
            results.append({
                "id": f"{doc_type}_main",
                "title": source["name"],
                "url": source["base_url"],
                "snippet": f"Official {source['name']} documentation",
                "relevance": 0.95,
                "source": doc_type,
            })
        
        return results[:limit]
    
    async def _retrieve(self, source_id: str) -> Optional[KnowledgeSource]:
        """Retrieve content from official documentation."""
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout)
            
            # Parse the source ID to get URL and type
            parts = source_id.split(":", 1)
            if len(parts) == 2:
                doc_type, identifier = parts
            else:
                return None
            
            if doc_type not in self.DOCUMENTATION_SOURCES:
                return None
            
            source = self.DOCUMENTATION_SOURCES[doc_type]
            url = f"{source['base_url']}/{identifier}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Educational AI)",
            }
            
            response = await self.http_client.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Extract content
            content = await self._extract_doc_content(response.text, doc_type)
            
            return await self._normalize({
                "title": identifier.replace("-", " ").title(),
                "content": content,
                "url": url,
                "source_id": source_id,
                "doc_type": doc_type,
            })
        
        except Exception as e:
            logger.error(f"Documentation retrieval error: {e}")
            return None
    
    async def _extract_doc_content(self, html: str, doc_type: str) -> str:
        """Extract documentation content from HTML."""
        try:
            # Remove scripts and styles
            content = html
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
            
            # Extract main article/content section
            patterns = [
                r'<main[^>]*>(.*?)</main>',
                r'<article[^>]*>(.*?)</article>',
                r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    content = match.group(1)
                    break
            
            # Convert HTML to plain text
            content = re.sub(r'<[^>]+>', '\n', content)
            content = re.sub(r'\n\n+', '\n', content)
            
            # Clean up
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            cleaned = '\n'.join(lines[:50])  # Limit to 50 lines
            
            return cleaned
        
        except Exception as e:
            logger.error(f"Documentation content extraction error: {e}")
            return ""
    
    async def _extract(self, content: str) -> Dict[str, Any]:
        """Extract information from documentation content."""
        try:
            lines = content.split('\n')
            
            # Extract code blocks
            code_patterns = re.findall(r'```[\s\S]*?```|<code>.*?</code>', content)
            
            return {
                "facts": [line for line in lines if line and len(line) > 10][:10],
                "code_blocks": len(code_patterns),
                "summary": '\n'.join(lines[:3]),
                "line_count": len(lines),
            }
        
        except Exception as e:
            logger.error(f"Documentation extraction error: {e}")
            return {
                "facts": [],
                "code_blocks": 0,
                "summary": "",
                "line_count": 0,
            }
    
    async def _normalize(self, raw_data: Dict[str, Any]) -> KnowledgeSource:
        """Normalize documentation data into KnowledgeSource format."""
        try:
            title = raw_data.get("title", "Documentation")
            content = raw_data.get("content", "")
            url = raw_data.get("url", "")
            doc_type = raw_data.get("doc_type", "unknown")
            
            extraction = await self._extract(content)
            
            return KnowledgeSource(
                provider=self.provider_type,
                title=title,
                content=content,
                url=url,
                summary=extraction.get("summary", ""),
                confidence=0.95,  # Official docs are highly authoritative
                metadata={
                    "doc_type": doc_type,
                    "code_blocks": extraction.get("code_blocks", 0),
                    "source_type": "official_documentation",
                },
                citations=[url] if url else [],
                relevance_score=0.95,
            )
        
        except Exception as e:
            logger.error(f"Documentation normalization error: {e}")
            return KnowledgeSource(
                provider=self.provider_type,
                title="Error",
                content=str(e),
            )
    
    async def _generate(self, sources: List[KnowledgeSource]) -> str:
        """Generate AI-ready content from documentation sources."""
        if not sources:
            return ""
        
        try:
            output_parts = []
            
            for source in sources:
                output_parts.append(f"### {source.title}\n")
                output_parts.append(f"\n{source.content}\n")
                
                if source.url:
                    doc_type = source.metadata.get("doc_type", "documentation")
                    output_parts.append(f"\n[Official {doc_type.title()} Reference]({source.url})")
            
            return "\n\n".join(output_parts)
        
        except Exception as e:
            logger.error(f"Documentation generation error: {e}")
            return ""
    
    async def _health_check(self) -> bool:
        """Check if documentation sources are accessible."""
        try:
            if not self.http_client:
                self.http_client = httpx.AsyncClient(timeout=self.timeout)
            
            # Check a few major documentation sources
            test_urls = [
                self.DOCUMENTATION_SOURCES["python"]["base_url"],
                self.DOCUMENTATION_SOURCES["mdn"]["base_url"],
            ]
            
            for url in test_urls:
                try:
                    response = await self.http_client.get(
                        url,
                        timeout=5.0,
                        headers={"User-Agent": "Mozilla/5.0 (Educational AI)"},
                    )
                    if response.status_code == 200:
                        return True
                except:
                    continue
            
            return False
        
        except Exception as e:
            logger.error(f"Documentation health check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
