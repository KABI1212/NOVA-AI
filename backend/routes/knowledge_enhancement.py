"""
Knowledge Enhancement Routes - New API endpoints for knowledge features.

These routes expose the knowledge enhancement capabilities:
- /api/knowledge/enhance - Enhance an AI response with knowledge
- /api/knowledge/search - Search for knowledge only
- /api/knowledge/providers - Get provider status
- /api/knowledge/query-route - Analyze how a query will be routed

These are OPTIONAL endpoints that don't break existing functionality.
All existing routes continue to work unchanged.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from services.knowledge_enhancement_integration import (
    get_integration,
    enhance_chat_response,
    get_knowledge_only,
)
from services.knowledge_providers import get_provider_registry
from services.intelligent_query_router import route_query
from services.source_visibility import (
    SourceVisibilityLevel,
    get_visibility_controller,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Enhancement"])


# Request/Response models
class EnhanceRequest(BaseModel):
    """Request to enhance an AI response."""
    
    query: str
    ai_response: str
    include_sources: bool = False
    visibility_level: Optional[str] = None


class SearchRequest(BaseModel):
    """Request to search for knowledge."""
    
    query: str
    include_all_sources: bool = False


class QueryRouteRequest(BaseModel):
    """Request to analyze query routing."""
    
    query: str


# Endpoints

@router.post("/enhance")
async def enhance_response(request: EnhanceRequest):
    """
    Enhance an AI response with knowledge from providers.
    
    This endpoint takes a user query and AI response, then:
    1. Routes the query to appropriate knowledge providers
    2. Gathers knowledge from those providers
    3. Fuses the information intelligently
    4. Returns the enhanced response with optional source citations
    
    Args:
        request: EnhanceRequest with query and response
        
    Returns:
        Enhanced response with metadata
    """
    try:
        result = await enhance_chat_response(
            query=request.query,
            ai_response=request.ai_response,
            include_sources=request.include_sources,
        )
        return result
    
    except Exception as e:
        logger.error(f"Response enhancement error: {e}")
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {str(e)}")


@router.post("/search")
async def search_knowledge(request: SearchRequest):
    """
    Search for knowledge from providers without AI augmentation.
    
    This endpoint gathers information from knowledge providers
    based on the query, useful for:
    - Pure information retrieval
    - Research and fact-finding
    - Building context before AI generation
    
    Args:
        request: SearchRequest with query
        
    Returns:
        Knowledge dictionary with sources and facts
    """
    try:
        result = await get_knowledge_only(
            query=request.query,
            include_all_sources=request.include_all_sources,
        )
        return result
    
    except Exception as e:
        logger.error(f"Knowledge search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/providers/status")
async def get_providers_status():
    """
    Get status of all registered knowledge providers.
    
    Returns:
        Provider status information including:
        - Total provider count
        - Healthy provider count
        - Individual provider status
    """
    try:
        registry = get_provider_registry()
        all_providers = registry.get_all_providers()
        healthy_providers = registry.get_healthy_providers()
        
        return {
            "total": len(all_providers),
            "healthy": len(healthy_providers),
            "providers": registry.get_status(),
        }
    
    except Exception as e:
        logger.error(f"Provider status error: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/query-route")
async def analyze_query_route(request: QueryRouteRequest):
    """
    Analyze how a query will be routed to knowledge providers.
    
    This endpoint shows:
    - Query classification
    - Recommended providers
    - Confidence score
    - AI provider strategy
    - Keywords detected
    
    Useful for understanding the routing logic.
    
    Args:
        request: QueryRouteRequest with query
        
    Returns:
        Query routing analysis
    """
    try:
        result = await route_query(request.query)
        return result
    
    except Exception as e:
        logger.error(f"Query routing error: {e}")
        raise HTTPException(status_code=500, detail=f"Routing analysis failed: {str(e)}")


@router.get("/enabled")
async def is_knowledge_enhancement_enabled():
    """Check if knowledge enhancement is enabled."""
    integration = get_integration()
    return {
        "enabled": integration.is_enabled(),
    }


@router.post("/enable")
async def enable_knowledge_enhancement(enabled: bool = Body(...)):
    """Enable or disable knowledge enhancement."""
    integration = get_integration()
    integration.set_enabled(enabled)
    return {
        "enabled": integration.is_enabled(),
    }


@router.get("/settings")
async def get_knowledge_settings():
    """Get knowledge enhancement settings."""
    try:
        integration = get_integration()
        visibility_controller = get_visibility_controller()
        
        return {
            "enabled": integration.is_enabled(),
            "default_visibility_level": visibility_controller.default_level.value,
            "similarity_threshold": 0.85,  # From fusion engine
            "max_parallel_providers": 3,
        }
    
    except Exception as e:
        logger.error(f"Settings retrieval error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.get("/health")
async def knowledge_health_check():
    """
    Perform health check on knowledge systems.
    
    Returns:
        Health status of all knowledge components
    """
    try:
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
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/documentation")
async def get_knowledge_documentation():
    """Get documentation on knowledge enhancement features."""
    return {
        "title": "NOVA AI Knowledge Enhancement",
        "description": "Intelligent query routing and multi-provider knowledge fusion",
        "features": {
            "intelligent_routing": {
                "description": "Automatically routes queries to appropriate knowledge providers",
                "examples": [
                    "General knowledge → Wikipedia",
                    "Programming → GeeksforGeeks",
                    "Documentation → Official Docs",
                    "Latest news → Internet Search",
                ]
            },
            "knowledge_fusion": {
                "description": "Intelligently merges information from multiple sources",
                "operations": [
                    "Deduplication of facts",
                    "Conflict resolution",
                    "Priority-based ranking",
                ]
            },
            "source_visibility": {
                "description": "User control over source disclosure",
                "levels": [
                    "hidden - No sources shown",
                    "minimal - Only provider type",
                    "normal - Provider and title",
                    "detailed - With URLs",
                    "comprehensive - Full details",
                ]
            },
            "plugin_architecture": {
                "description": "Extensible provider system",
                "current_providers": [
                    "Wikipedia",
                    "GeeksforGeeks",
                    "Official Documentation",
                ]
            }
        },
        "endpoints": {
            "POST /api/knowledge/enhance": "Enhance AI response with knowledge",
            "POST /api/knowledge/search": "Search for knowledge",
            "GET /api/knowledge/providers/status": "Get provider status",
            "POST /api/knowledge/query-route": "Analyze query routing",
            "GET /api/knowledge/enabled": "Check if enhancement is enabled",
            "POST /api/knowledge/enable": "Enable/disable enhancement",
            "GET /api/knowledge/health": "Health check",
        }
    }
