"""
Knowledge Enhancement Integration Service

Seamlessly integrates knowledge providers into the chat flow.
This is the main orchestrator that:
- Analyzes incoming queries
- Selects appropriate knowledge providers
- Retrieves and fuses knowledge
- Manages source visibility
- Prepares enhanced responses

Designed to integrate with existing chat routes without breaking compatibility.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from services.intelligent_query_router import route_query, QueryType
from services.knowledge_providers import get_provider_registry, ProviderType, KnowledgeSource
from services.knowledge_fusion import fuse_knowledge_sources
from services.source_visibility import (
    get_auto_provider_selector,
    get_visibility_controller,
    get_source_tracker,
    SourceVisibilityLevel,
)

logger = logging.getLogger(__name__)


class KnowledgeEnhancementIntegration:
    """Integration point for knowledge enhancement in chat flow."""
    
    def __init__(self):
        """Initialize the integration."""
        self.registry = get_provider_registry()
        self.auto_selector = get_auto_provider_selector()
        self.visibility_controller = get_visibility_controller()
        self.source_tracker = get_source_tracker()
        self.enabled = True
    
    async def enhance_chat_response(
        self,
        query: str,
        ai_response: str,
        user_context: Optional[Dict[str, Any]] = None,
        include_sources: bool = False
    ) -> Dict[str, Any]:
        """
        Enhance a chat response with knowledge from providers.
        
        This is the main entry point for integrating knowledge enhancement
        into the existing chat flow.
        
        Args:
            query: User's original question
            ai_response: Response from AI model
            user_context: Optional user preferences
            include_sources: Force inclusion of sources (overrides default)
            
        Returns:
            Enhanced response dictionary with:
            - response: The enhanced response text
            - sources: List of sources used (if applicable)
            - metadata: Enhancement metadata
            - enhanced: Whether enhancement was applied
        """
        if not self.enabled:
            return {
                "response": ai_response,
                "sources": [],
                "metadata": {},
                "enhanced": False,
            }
        
        try:
            # Step 1: Route the query to appropriate providers
            routing_result = await route_query(query)
            
            # Step 2: Determine if enhancement should be attempted
            should_enhance = self._should_enhance(routing_result, query)
            
            if not should_enhance:
                return {
                    "response": ai_response,
                    "sources": [],
                    "metadata": {"reason": "enhancement_not_needed"},
                    "enhanced": False,
                }
            
            # Step 3: Select and query providers in parallel
            knowledge_sources = await self._gather_knowledge(
                query,
                routing_result
            )
            
            if not knowledge_sources:
                return {
                    "response": ai_response,
                    "sources": [],
                    "metadata": {"reason": "no_sources_found"},
                    "enhanced": False,
                }
            
            # Step 4: Fuse knowledge from multiple sources
            fused_knowledge = await fuse_knowledge_sources(
                knowledge_sources,
                query,
                include_supplementary=True
            )
            
            # Step 5: Determine source visibility level
            visibility_level = self.visibility_controller.determine_visibility_level(
                query,
                user_context
            )
            
            # Step 6: Prepare enhanced response
            enhanced_response = self._prepare_enhanced_response(
                ai_response,
                fused_knowledge,
                visibility_level,
                query
            )
            
            # Step 7: Track sources for analytics/logging
            self.source_tracker.track_sources(knowledge_sources)
            self.source_tracker.track_metadata({
                "query": query,
                "provider_count": len(knowledge_sources),
                "visibility_level": visibility_level.value,
            })
            
            return {
                "response": enhanced_response,
                "sources": [s.to_dict() for s in knowledge_sources],
                "metadata": {
                    "query_type": routing_result["query_type"],
                    "visibility_level": visibility_level.value,
                    "deduplication": fused_knowledge.deduplication_stats,
                    "conflicts": fused_knowledge.conflicts,
                    "enhanced": True,
                },
                "enhanced": True,
            }
        
        except Exception as e:
            logger.error(f"Knowledge enhancement error: {e}")
            # Gracefully fall back to original response
            return {
                "response": ai_response,
                "sources": [],
                "metadata": {"error": str(e)},
                "enhanced": False,
            }
    
    async def get_knowledge_only(
        self,
        query: str,
        include_all_sources: bool = False
    ) -> Dict[str, Any]:
        """
        Get knowledge from providers without AI generation.
        
        Useful for search-like queries where you want to gather
        information without AI augmentation.
        
        Args:
            query: Search query
            include_all_sources: Include all available sources
            
        Returns:
            Knowledge dictionary with sources and facts
        """
        try:
            routing_result = await route_query(query)
            
            knowledge_sources = await self._gather_knowledge(
                query,
                routing_result,
                max_providers=10 if include_all_sources else 3
            )
            
            if not knowledge_sources:
                return {
                    "query": query,
                    "sources": [],
                    "facts": [],
                    "found": False,
                }
            
            # Fuse knowledge
            fused_knowledge = await fuse_knowledge_sources(
                knowledge_sources,
                query,
                include_supplementary=include_all_sources
            )
            
            return {
                "query": query,
                "sources": [s.to_dict() for s in knowledge_sources],
                "facts": fused_knowledge.facts,
                "summary": fused_knowledge.summary,
                "found": True,
                "source_count": len(knowledge_sources),
            }
        
        except Exception as e:
            logger.error(f"Knowledge retrieval error: {e}")
            return {
                "query": query,
                "sources": [],
                "facts": [],
                "found": False,
                "error": str(e),
            }
    
    def _should_enhance(
        self,
        routing_result: Dict[str, Any],
        query: str
    ) -> bool:
        """Determine if enhancement should be attempted."""
        # Don't enhance local-only queries
        if routing_result.get("use_local_only"):
            return False
        
        # Don't enhance if no external sources recommended
        if not routing_result.get("has_external_sources"):
            return False
        
        # Check for explicit "no sources" request
        if any(phrase in query.lower() for phrase in [
            "don't use sources", "don't search", "just your knowledge",
            "from your training", "without searching"
        ]):
            return False
        
        return True
    
    async def _gather_knowledge(
        self,
        query: str,
        routing_result: Dict[str, Any],
        max_providers: int = 3
    ) -> List[KnowledgeSource]:
        """Gather knowledge from selected providers in parallel."""
        from services.knowledge_providers import ProviderRecommendation
        
        provider_names = routing_result.get("providers", [])
        if not provider_names:
            return []
        
        # Map provider names to provider objects
        tasks = []
        for provider_name in provider_names[:max_providers]:
            try:
                # Get providers by type
                ptype = ProviderType(provider_name)
                providers = self.registry.get_providers_by_type(ptype)
                
                for provider in providers:
                    if provider.is_healthy:
                        tasks.append(self._search_provider(provider, query))
            
            except ValueError:
                # Provider type not found
                continue
        
        if not tasks:
            return []
        
        # Gather results in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out errors and None values
            knowledge_sources = [
                r for r in results
                if isinstance(r, KnowledgeSource) and r
            ]
            
            return knowledge_sources
        
        except Exception as e:
            logger.error(f"Error gathering knowledge: {e}")
            return []
    
    async def _search_provider(
        self,
        provider: Any,
        query: str
    ) -> Optional[KnowledgeSource]:
        """Search a single provider for relevant knowledge."""
        try:
            # Search for relevant content
            search_result = await provider.search(query, limit=5)
            
            if not search_result.is_successful or not search_result.results:
                return None
            
            # Get the top result
            top_result = search_result.results[0]
            
            # Retrieve full content
            source_id = top_result.get("id") or top_result.get("url")
            knowledge_source = await provider.retrieve(source_id)
            
            return knowledge_source
        
        except Exception as e:
            logger.error(f"Provider search error: {e}")
            return None
    
    def _prepare_enhanced_response(
        self,
        ai_response: str,
        fused_knowledge,
        visibility_level: SourceVisibilityLevel,
        query: str
    ) -> str:
        """Prepare the final enhanced response."""
        # If visibility is hidden, just clean the response
        if visibility_level == SourceVisibilityLevel.HIDDEN:
            return self.visibility_controller.get_hidden_response_wrapper(ai_response)
        
        # For other visibility levels, add source information
        sources = [
            KnowledgeSource(
                provider=ProviderType[s["provider"].upper()],
                title=s["title"],
                content=s["content"],
                url=s["url"],
                confidence=s["confidence"],
            )
            for s in fused_knowledge.sources
        ]
        
        # Add source citations
        response_with_sources = self.visibility_controller.add_source_citations_inline(
            ai_response,
            sources
        )
        
        return response_with_sources
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable knowledge enhancement."""
        self.enabled = enabled
        logger.info(f"Knowledge enhancement {'enabled' if enabled else 'disabled'}")
    
    def is_enabled(self) -> bool:
        """Check if knowledge enhancement is enabled."""
        return self.enabled


# Global integration instance
_integration: Optional[KnowledgeEnhancementIntegration] = None


def get_integration() -> KnowledgeEnhancementIntegration:
    """Get or create the integration instance."""
    global _integration
    if _integration is None:
        _integration = KnowledgeEnhancementIntegration()
    return _integration


async def enhance_chat_response(
    query: str,
    ai_response: str,
    user_context: Optional[Dict[str, Any]] = None,
    include_sources: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to enhance a chat response.
    
    Args:
        query: User's question
        ai_response: AI-generated response
        user_context: Optional user context
        include_sources: Force include sources
        
    Returns:
        Enhanced response dictionary
    """
    integration = get_integration()
    return await integration.enhance_chat_response(
        query,
        ai_response,
        user_context,
        include_sources
    )


async def get_knowledge_only(
    query: str,
    include_all_sources: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to get knowledge without AI augmentation.
    
    Args:
        query: Search query
        include_all_sources: Include all available sources
        
    Returns:
        Knowledge dictionary
    """
    integration = get_integration()
    return await integration.get_knowledge_only(query, include_all_sources)
