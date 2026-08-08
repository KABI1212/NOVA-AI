"""
Knowledge Providers - Plugin architecture for knowledge sources.

This module defines the base interface for knowledge providers and utilities
for managing multiple sources of information (Wikipedia, GeeksforGeeks, Docs, etc).

Each provider implements:
- initialize(): Setup and health check
- search(): Find relevant content
- retrieve(): Get detailed content
- extract(): Extract useful facts
- normalize(): Format for consumption
- generate(): Prepare for AI integration
- healthCheck(): Verify provider is working

This allows future providers to be added without changing core application.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Types of knowledge providers."""
    
    WIKIPEDIA = "wikipedia"
    GEEKSFORGEEKS = "geeksforgeeks"
    OFFICIAL_DOCS = "official_docs"
    INTERNET_SEARCH = "internet_search"
    RESEARCH_API = "research_api"
    LOCAL_KNOWLEDGE = "local_knowledge"
    CUSTOM = "custom"


@dataclass
class KnowledgeSource:
    """Represents a piece of knowledge from a provider."""
    
    provider: ProviderType
    title: str
    content: str
    url: Optional[str] = None
    summary: Optional[str] = None
    confidence: float = 1.0
    retrieved_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    citations: List[str] = field(default_factory=list)
    relevance_score: float = 0.5
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "provider": self.provider.value,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "summary": self.summary,
            "confidence": self.confidence,
            "retrieved_at": self.retrieved_at.isoformat(),
            "metadata": self.metadata,
            "citations": self.citations,
            "relevance_score": self.relevance_score,
        }


@dataclass
class SearchResult:
    """Result of a provider search."""
    
    query: str
    provider: ProviderType
    total_results: int
    results: List[Dict[str, Any]]
    search_time_ms: float
    is_successful: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "provider": self.provider.value,
            "total_results": self.total_results,
            "results": self.results,
            "search_time_ms": self.search_time_ms,
            "is_successful": self.is_successful,
            "error": self.error,
        }


class KnowledgeProvider(ABC):
    """Base class for all knowledge providers."""
    
    def __init__(self, name: str, provider_type: ProviderType):
        """
        Initialize the provider.
        
        Args:
            name: Human-readable name for the provider
            provider_type: Type of provider
        """
        self.name = name
        self.provider_type = provider_type
        self.is_initialized = False
        self.last_health_check: Optional[datetime] = None
        self.is_healthy = False
        self.error_message: Optional[str] = None
        self.config: Dict[str, Any] = {}

    @property
    def id(self) -> str:
        """Provider unique identifier."""
        return f"{self.provider_type.value}_{self.name}".lower()

    @property
    def description(self) -> str:
        """Provider description from docstring or default."""
        return (self.__doc__ or f"{self.name} knowledge provider").strip()

    @property
    def capabilities(self) -> List[str]:
        """List of capabilities supported by this provider."""
        return ["search", "retrieve", "extract", "normalize", "generate"]
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize the provider with optional configuration.
        
        Args:
            config: Optional configuration dictionary
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if config:
                self.config = config
            
            success = await self._setup()
            self.is_initialized = success
            
            if success:
                health = await self.health_check()
                self.is_healthy = health
            
            return success
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}")
            self.error_message = str(e)
            self.is_initialized = False
            return False
    
    async def search(self, query: str, limit: int = 10) -> SearchResult:
        """
        Search for relevant content.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            SearchResult object with results
        """
        if not self.is_initialized:
            return SearchResult(
                query=query,
                provider=self.provider_type,
                total_results=0,
                results=[],
                search_time_ms=0,
                is_successful=False,
                error="Provider not initialized",
            )
        
        try:
            return await self._search(query, limit)
        except Exception as e:
            logger.error(f"Search error in {self.name}: {e}")
            return SearchResult(
                query=query,
                provider=self.provider_type,
                total_results=0,
                results=[],
                search_time_ms=0,
                is_successful=False,
                error=str(e),
            )
    
    async def retrieve(self, source_id: str) -> Optional[KnowledgeSource]:
        """
        Retrieve detailed content from a source.
        
        Args:
            source_id: ID of the source to retrieve
            
        Returns:
            KnowledgeSource object or None if not found
        """
        if not self.is_initialized:
            return None
        
        try:
            return await self._retrieve(source_id)
        except Exception as e:
            logger.error(f"Retrieval error in {self.name}: {e}")
            return None
    
    async def extract(self, content: str) -> Dict[str, Any]:
        """
        Extract useful facts from content.
        
        Args:
            content: Raw content to extract from
            
        Returns:
            Dictionary with extracted facts
        """
        try:
            return await self._extract(content)
        except Exception as e:
            logger.error(f"Extraction error in {self.name}: {e}")
            return {"facts": [], "summary": "", "entities": []}
    
    async def normalize(self, raw_data: Dict[str, Any]) -> KnowledgeSource:
        """
        Normalize raw data into KnowledgeSource format.
        
        Args:
            raw_data: Raw data from provider
            
        Returns:
            Normalized KnowledgeSource
        """
        try:
            return await self._normalize(raw_data)
        except Exception as e:
            logger.error(f"Normalization error in {self.name}: {e}")
            return KnowledgeSource(
                provider=self.provider_type,
                title="Normalization Error",
                content=f"Failed to normalize data: {e}",
            )
    
    async def generate(self, sources: List[KnowledgeSource]) -> str:
        """
        Generate AI-ready content from knowledge sources.
        
        Args:
            sources: List of KnowledgeSource objects
            
        Returns:
            Formatted content ready for AI processing
        """
        try:
            return await self._generate(sources)
        except Exception as e:
            logger.error(f"Generation error in {self.name}: {e}")
            return ""
    
    async def health_check(self) -> bool:
        """
        Check if the provider is operational.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            self.last_health_check = datetime.utcnow()
            result = await self._health_check()
            self.is_healthy = result
            return result
        except Exception as e:
            logger.error(f"Health check failed for {self.name}: {e}")
            self.is_healthy = False
            self.error_message = str(e)
            return False
    
    # Abstract methods - must be implemented by subclasses
    
    @abstractmethod
    async def _setup(self) -> bool:
        """Setup the provider. Return True if successful."""
        pass
    
    @abstractmethod
    async def _search(self, query: str, limit: int) -> SearchResult:
        """Implement search logic."""
        pass
    
    @abstractmethod
    async def _retrieve(self, source_id: str) -> Optional[KnowledgeSource]:
        """Implement retrieval logic."""
        pass
    
    @abstractmethod
    async def _extract(self, content: str) -> Dict[str, Any]:
        """Implement extraction logic."""
        pass
    
    @abstractmethod
    async def _normalize(self, raw_data: Dict[str, Any]) -> KnowledgeSource:
        """Implement normalization logic."""
        pass
    
    @abstractmethod
    async def _generate(self, sources: List[KnowledgeSource]) -> str:
        """Implement generation logic."""
        pass
    
    @abstractmethod
    async def _health_check(self) -> bool:
        """Implement health check logic."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the provider."""
        return {
            "name": self.name,
            "type": self.provider_type.value,
            "initialized": self.is_initialized,
            "healthy": self.is_healthy,
            "last_health_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
            "error": self.error_message,
        }


class ProviderRegistry:
    """Manages registered knowledge providers."""
    
    def __init__(self):
        """Initialize the registry."""
        self.providers: Dict[str, KnowledgeProvider] = {}
    
    def register(self, provider: KnowledgeProvider) -> None:
        """
        Register a knowledge provider.
        
        Args:
            provider: KnowledgeProvider instance to register
        """
        provider_id = f"{provider.provider_type.value}_{provider.name}".lower()
        self.providers[provider_id] = provider
        logger.info(f"Registered provider: {provider_id}")
    
    def unregister(self, provider_id: str) -> bool:
        """
        Unregister a provider.
        
        Args:
            provider_id: ID of provider to unregister
            
        Returns:
            True if unregistered, False if not found
        """
        if provider_id in self.providers:
            del self.providers[provider_id]
            logger.info(f"Unregistered provider: {provider_id}")
            return True
        return False
    
    def get_provider(self, provider_id: str) -> Optional[KnowledgeProvider]:
        """
        Get a provider by ID.
        
        Args:
            provider_id: ID of the provider
            
        Returns:
            KnowledgeProvider instance or None
        """
        return self.providers.get(provider_id)
    
    def get_providers_by_type(self, provider_type: ProviderType) -> List[KnowledgeProvider]:
        """
        Get all providers of a specific type.
        
        Args:
            provider_type: Type of providers to get
            
        Returns:
            List of matching providers
        """
        return [p for p in self.providers.values() if p.provider_type == provider_type]
    
    def get_all_providers(self) -> List[KnowledgeProvider]:
        """Get all registered providers."""
        return list(self.providers.values())
    
    def get_healthy_providers(self) -> List[KnowledgeProvider]:
        """Get all healthy providers."""
        return [p for p in self.providers.values() if p.is_healthy]
    
    async def initialize_all(self) -> Dict[str, bool]:
        """
        Initialize all registered providers.
        
        Returns:
            Dictionary with provider IDs and initialization status
        """
        results = {}
        tasks = []
        
        for provider_id, provider in self.providers.items():
            tasks.append((provider_id, provider.initialize()))
        
        for provider_id, task in tasks:
            try:
                results[provider_id] = await task
            except Exception as e:
                logger.error(f"Initialization error for {provider_id}: {e}")
                results[provider_id] = False
        
        return results
    
    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all providers.
        
        Returns:
            Dictionary with provider IDs and health status
        """
        results = {}
        tasks = [
            (provider_id, provider.health_check())
            for provider_id, provider in self.providers.items()
        ]
        
        for provider_id, task in tasks:
            try:
                results[provider_id] = await task
            except Exception as e:
                logger.error(f"Health check error for {provider_id}: {e}")
                results[provider_id] = False
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        return {
            provider_id: provider.get_status()
            for provider_id, provider in self.providers.items()
        }


# Global registry instance
_provider_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Get or create the global provider registry."""
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()
    return _provider_registry
