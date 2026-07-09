"""
Knowledge Enhancement Initialization Service

Orchestrates initialization of all knowledge providers and enhancement features.
This module ties together:
- Query routing
- Knowledge providers
- Provider registry
- Knowledge fusion
- Source visibility

All initialized on startup with proper error handling and graceful degradation.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from services.knowledge_providers import get_provider_registry, ProviderType
from services.wikipedia_provider import WikipediaProvider
from services.geeksforgeeks_provider import GeeksforGeeksProvider
from services.documentation_provider import DocumentationProvider
from services.intelligent_query_router import get_query_router
from services.knowledge_fusion import get_fusion_engine
from services.source_visibility import (
    get_auto_provider_selector,
    get_visibility_controller,
    get_source_tracker,
)

logger = logging.getLogger(__name__)


class KnowledgeEnhancementBootstrap:
    """Bootstrap and initialize all knowledge enhancement features."""
    
    def __init__(self):
        """Initialize the bootstrap."""
        self.initialized = False
        self.providers_status: Dict[str, bool] = {}
        self.initialization_errors: Dict[str, str] = {}
    
    async def initialize_all(self) -> Dict[str, Any]:
        """
        Initialize all knowledge enhancement features.
        
        Returns:
            Initialization status dictionary
        """
        logger.info("Starting NOVA AI Knowledge Enhancement initialization...")
        
        try:
            # Initialize knowledge providers
            await self._initialize_providers()
            
            # Initialize query router
            await self._initialize_query_router()
            
            # Initialize fusion engine
            await self._initialize_fusion_engine()
            
            # Initialize provider selection and visibility
            await self._initialize_provider_selection()
            await self._initialize_visibility_control()
            
            self.initialized = True
            logger.info("Knowledge Enhancement initialization completed successfully")
            
            return self._get_status()
        
        except Exception as e:
            logger.error(f"Critical error during initialization: {e}")
            self.initialization_errors["critical"] = str(e)
            # Continue with graceful degradation
            return self._get_status()
    
    async def _initialize_providers(self) -> None:
        """Initialize knowledge providers."""
        logger.info("Initializing knowledge providers...")
        
        registry = get_provider_registry()
        
        # Wikipedia provider
        try:
            wikipedia = WikipediaProvider()
            if await wikipedia.initialize():
                registry.register(wikipedia)
                self.providers_status["wikipedia"] = True
                logger.info("✓ Wikipedia provider initialized")
            else:
                self.providers_status["wikipedia"] = False
                self.initialization_errors["wikipedia"] = "Setup failed"
        except Exception as e:
            logger.error(f"Wikipedia provider initialization error: {e}")
            self.providers_status["wikipedia"] = False
            self.initialization_errors["wikipedia"] = str(e)
        
        # GeeksforGeeks provider
        try:
            gfg = GeeksforGeeksProvider()
            if await gfg.initialize():
                registry.register(gfg)
                self.providers_status["geeksforgeeks"] = True
                logger.info("✓ GeeksforGeeks provider initialized")
            else:
                self.providers_status["geeksforgeeks"] = False
                self.initialization_errors["geeksforgeeks"] = "Setup failed"
        except Exception as e:
            logger.error(f"GeeksforGeeks provider initialization error: {e}")
            self.providers_status["geeksforgeeks"] = False
            self.initialization_errors["geeksforgeeks"] = str(e)
        
        # Official Documentation provider
        try:
            docs = DocumentationProvider()
            if await docs.initialize():
                registry.register(docs)
                self.providers_status["documentation"] = True
                logger.info("✓ Documentation provider initialized")
            else:
                self.providers_status["documentation"] = False
                self.initialization_errors["documentation"] = "Setup failed"
        except Exception as e:
            logger.error(f"Documentation provider initialization error: {e}")
            self.providers_status["documentation"] = False
            self.initialization_errors["documentation"] = str(e)
        
        # Health check all providers
        logger.info("Running health checks on providers...")
        health_results = await registry.health_check_all()
        
        for provider_id, is_healthy in health_results.items():
            status = "✓" if is_healthy else "✗"
            logger.info(f"{status} {provider_id} - {'healthy' if is_healthy else 'unhealthy'}")
    
    async def _initialize_query_router(self) -> None:
        """Initialize query router."""
        logger.info("Initializing query router...")
        try:
            router = get_query_router()
            # Test with a simple query
            result = router.route_query("test query")
            logger.info(f"✓ Query router initialized - test result: {result['query_type']}")
        except Exception as e:
            logger.error(f"Query router initialization error: {e}")
            self.initialization_errors["query_router"] = str(e)
    
    async def _initialize_fusion_engine(self) -> None:
        """Initialize knowledge fusion engine."""
        logger.info("Initializing knowledge fusion engine...")
        try:
            engine = get_fusion_engine()
            logger.info("✓ Knowledge fusion engine initialized")
        except Exception as e:
            logger.error(f"Fusion engine initialization error: {e}")
            self.initialization_errors["fusion_engine"] = str(e)
    
    async def _initialize_provider_selection(self) -> None:
        """Initialize automatic provider selection."""
        logger.info("Initializing automatic provider selection...")
        try:
            selector = get_auto_provider_selector()
            logger.info("✓ Automatic provider selector initialized")
        except Exception as e:
            logger.error(f"Provider selector initialization error: {e}")
            self.initialization_errors["provider_selector"] = str(e)
    
    async def _initialize_visibility_control(self) -> None:
        """Initialize source visibility control."""
        logger.info("Initializing source visibility control...")
        try:
            visibility = get_visibility_controller()
            tracker = get_source_tracker()
            logger.info("✓ Source visibility control initialized")
        except Exception as e:
            logger.error(f"Visibility control initialization error: {e}")
            self.initialization_errors["visibility_control"] = str(e)
    
    def _get_status(self) -> Dict[str, Any]:
        """Get initialization status."""
        registry = get_provider_registry()
        healthy_providers = registry.get_healthy_providers()
        
        return {
            "initialized": self.initialized,
            "providers": {
                "total": len(registry.get_all_providers()),
                "healthy": len(healthy_providers),
                "status": self.providers_status,
            },
            "features": {
                "query_routing": "query_router" not in self.initialization_errors,
                "knowledge_fusion": "fusion_engine" not in self.initialization_errors,
                "provider_selection": "provider_selector" not in self.initialization_errors,
                "source_visibility": "visibility_control" not in self.initialization_errors,
            },
            "errors": self.initialization_errors if self.initialization_errors else None,
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all systems."""
        registry = get_provider_registry()
        health_results = await registry.health_check_all()
        
        healthy_count = sum(1 for v in health_results.values() if v)
        total_count = len(health_results)
        
        return {
            "status": "healthy" if healthy_count > 0 else "degraded",
            "providers_healthy": healthy_count,
            "providers_total": total_count,
            "provider_status": health_results,
        }


# Global bootstrap instance
_bootstrap: Optional[KnowledgeEnhancementBootstrap] = None


def get_bootstrap() -> KnowledgeEnhancementBootstrap:
    """Get or create the bootstrap instance."""
    global _bootstrap
    if _bootstrap is None:
        _bootstrap = KnowledgeEnhancementBootstrap()
    return _bootstrap


async def initialize_knowledge_enhancement() -> Dict[str, Any]:
    """
    Initialize all knowledge enhancement features.
    
    This should be called during application startup.
    
    Returns:
        Initialization status
    """
    bootstrap = get_bootstrap()
    return await bootstrap.initialize_all()


async def get_knowledge_system_health() -> Dict[str, Any]:
    """Get health status of knowledge systems."""
    bootstrap = get_bootstrap()
    return await bootstrap.health_check()
