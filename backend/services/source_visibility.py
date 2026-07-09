"""
Source Visibility and Provider Selection Service

Controls:
- When and how sources are displayed
- Automatic provider selection based on query type
- Source citation formatting
- Hiding vs showing internal provider details

By default:
- Never displays Wikipedia, GeeksforGeeks, Official Docs raw content
- Never displays URLs unless explicitly requested
- Never displays search results directly
- Only shows the final NOVA AI response

When user explicitly asks for sources:
- Shows citations with URLs
- Indicates which providers were used
- Provides attribution
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from services.intelligent_query_router import QueryRouter, ProviderRecommendation
from services.knowledge_providers import KnowledgeSource, ProviderType

logger = logging.getLogger(__name__)


class SourceVisibilityLevel(Enum):
    """How much source information to display."""
    
    HIDDEN = "hidden"           # No sources shown
    MINIMAL = "minimal"         # Only provider type
    NORMAL = "normal"           # Citations with titles
    DETAILED = "detailed"       # Full citations with URLs
    COMPREHENSIVE = "comprehensive"  # All source details


class AutoProviderSelector:
    """Automatically selects appropriate providers for a query."""
    
    def __init__(self):
        """Initialize the selector."""
        self.query_router = QueryRouter()
    
    async def select_providers(
        self,
        query: str,
        max_parallel: int = 3,
        prefer_speed: bool = False
    ) -> List[ProviderRecommendation]:
        """
        Select providers based on query characteristics.
        
        Args:
            query: User query
            max_parallel: Max number of providers to query in parallel
            prefer_speed: Prefer fast providers over comprehensive
            
        Returns:
            List of recommended providers
        """
        routing_result = self.query_router.route_query(query)
        providers = [ProviderRecommendation(p) for p in routing_result["providers"]]
        
        # Limit number of parallel providers for performance
        if prefer_speed:
            providers = providers[:1]
        else:
            providers = providers[:max_parallel]
        
        return providers
    
    async def get_ai_provider_strategy(self, query: str) -> str:
        """
        Get AI provider selection strategy for the query.
        
        Args:
            query: User query
            
        Returns:
            Strategy string: "prefer_claude", "prefer_gemini", "prefer_gpt4", etc.
        """
        routing_result = self.query_router.route_query(query)
        return routing_result.get("ai_provider_strategy", "balanced")


class SourceVisibilityController:
    """Controls how and when sources are displayed."""
    
    def __init__(self):
        """Initialize the controller."""
        self.default_level = SourceVisibilityLevel.HIDDEN
    
    def determine_visibility_level(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> SourceVisibilityLevel:
        """
        Determine what source visibility level to use for a response.
        
        Args:
            query: User query
            user_context: Optional user preferences
            
        Returns:
            SourceVisibilityLevel to use
        """
        query_lower = query.lower()
        
        # Check if user explicitly asks for sources
        source_keywords = {
            "source", "citation", "reference", "where", "from where",
            "which source", "cite", "bibliography", "reference",
            "provider", "from which", "based on", "attributed to",
        }
        
        has_source_request = any(kw in query_lower for kw in source_keywords)
        
        if has_source_request:
            # User wants sources - show detailed information
            if any(kw in query_lower for kw in ["detailed", "comprehensive", "full"]):
                return SourceVisibilityLevel.COMPREHENSIVE
            else:
                return SourceVisibilityLevel.DETAILED
        
        # Check user preferences if available
        if user_context:
            preferred_level = user_context.get("source_visibility_level")
            if preferred_level:
                try:
                    return SourceVisibilityLevel(preferred_level)
                except ValueError:
                    pass
        
        # Default: hidden
        return self.default_level
    
    def format_sources_for_display(
        self,
        sources: List[KnowledgeSource],
        visibility_level: SourceVisibilityLevel
    ) -> str:
        """
        Format sources for display according to visibility level.
        
        Args:
            sources: List of KnowledgeSource objects
            visibility_level: How much to show
            
        Returns:
            Formatted source text
        """
        if not sources or visibility_level == SourceVisibilityLevel.HIDDEN:
            return ""
        
        formatted_lines = []
        
        if visibility_level == SourceVisibilityLevel.MINIMAL:
            # Just show provider types
            providers = set(s.provider.value for s in sources)
            if providers:
                provider_list = ", ".join(sorted(providers))
                formatted_lines.append(f"\n\n**Sources:** {provider_list}")
        
        elif visibility_level == SourceVisibilityLevel.NORMAL:
            # Show provider and title
            formatted_lines.append("\n\n**Sources:**")
            for source in sources:
                formatted_lines.append(
                    f"- {source.provider.value.title()}: {source.title}"
                )
        
        elif visibility_level == SourceVisibilityLevel.DETAILED:
            # Show provider, title, and URL
            formatted_lines.append("\n\n**Sources & References:**")
            for source in sources:
                citation = f"- **{source.provider.value.title()}**: {source.title}"
                if source.url:
                    citation += f" ([Link]({source.url}))"
                formatted_lines.append(citation)
        
        elif visibility_level == SourceVisibilityLevel.COMPREHENSIVE:
            # Show all details
            formatted_lines.append("\n\n**Comprehensive Source Information:**")
            for i, source in enumerate(sources, 1):
                formatted_lines.append(f"\n**Source {i}: {source.title}**")
                formatted_lines.append(f"- Provider: {source.provider.value.title()}")
                formatted_lines.append(f"- Confidence: {source.confidence:.1%}")
                formatted_lines.append(f"- Relevance: {source.relevance_score:.1%}")
                if source.url:
                    formatted_lines.append(f"- URL: {source.url}")
                if source.summary:
                    formatted_lines.append(f"- Summary: {source.summary[:200]}...")
        
        return "\n".join(formatted_lines)
    
    def get_hidden_response_wrapper(self, response: str) -> str:
        """
        Prepare response for hidden source mode (remove any source hints).
        
        Args:
            response: The response text
            
        Returns:
            Cleaned response text
        """
        # Remove common provider mentions that could leak
        removals = [
            "according to wikipedia",
            "per geeksforgeeks",
            "from the official docs",
            "the documentation states",
            "based on web search",
            "[wikipedia]",
            "[source]",
            "source:",
            "reference:",
        ]
        
        response_lower = response.lower()
        for removal in removals:
            if removal in response_lower:
                # Find and remove the mention
                import re
                response = re.sub(
                    removal,
                    "",
                    response,
                    flags=re.IGNORECASE
                )
        
        return response.strip()
    
    def add_source_citations_inline(
        self,
        response: str,
        sources: List[KnowledgeSource],
        max_citations: int = 3
    ) -> str:
        """
        Add inline citations to response.
        
        Args:
            response: The response text
            sources: List of sources
            max_citations: Max citations to add
            
        Returns:
            Response with citations
        """
        if not sources:
            return response
        
        # Add citations at the end
        citations = []
        for source in sources[:max_citations]:
            if source.url:
                citations.append(f"[{source.provider.value.title()}]({source.url})")
        
        if citations:
            response += f"\n\n**Sources**: {', '.join(citations)}"
        
        return response


class SourceTracker:
    """Tracks which sources were used for a response."""
    
    def __init__(self):
        """Initialize the tracker."""
        self.current_sources: List[KnowledgeSource] = []
        self.response_metadata: Dict[str, Any] = {}
    
    def track_sources(self, sources: List[KnowledgeSource]) -> None:
        """Track sources used for a response."""
        self.current_sources = sources
    
    def track_metadata(self, metadata: Dict[str, Any]) -> None:
        """Track response metadata."""
        self.response_metadata.update(metadata)
    
    def get_tracking_info(self) -> Dict[str, Any]:
        """Get full tracking information."""
        return {
            "sources_used": len(self.current_sources),
            "source_types": list(set(s.provider.value for s in self.current_sources)),
            "sources": [s.to_dict() for s in self.current_sources],
            "metadata": self.response_metadata,
        }
    
    def clear(self) -> None:
        """Clear tracking information."""
        self.current_sources = []
        self.response_metadata = {}


# Global instances
_auto_selector: Optional[AutoProviderSelector] = None
_visibility_controller: Optional[SourceVisibilityController] = None
_source_tracker: Optional[SourceTracker] = None


def get_auto_provider_selector() -> AutoProviderSelector:
    """Get or create the auto provider selector."""
    global _auto_selector
    if _auto_selector is None:
        _auto_selector = AutoProviderSelector()
    return _auto_selector


def get_visibility_controller() -> SourceVisibilityController:
    """Get or create the source visibility controller."""
    global _visibility_controller
    if _visibility_controller is None:
        _visibility_controller = SourceVisibilityController()
    return _visibility_controller


def get_source_tracker() -> SourceTracker:
    """Get or create the source tracker."""
    global _source_tracker
    if _source_tracker is None:
        _source_tracker = SourceTracker()
    return _source_tracker
