"""
Knowledge Enhancement Routes - Enhanced API endpoints.

This module provides a comprehensive set of endpoints for knowledge enhancement,
including query routing, multi‑provider fusion, source visibility, and health monitoring.

Endpoints:
- POST /enhance               – Enhance an AI response with knowledge
- POST /search                – Search for knowledge only
- GET  /providers             – List all available providers
- GET  /providers/status      – Get provider health status
- POST /query-route           – Analyze query routing
- GET  /enabled               – Check if enhancement is enabled
- POST /enable                – Enable/disable enhancement
- GET  /settings              – Get current settings
- GET  /health                – Detailed health check
- GET  /documentation         – Feature documentation
"""

import logging
import time
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Body, HTTPException, Query, Response
from pydantic import BaseModel, Field, validator

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

# ==============================
# Request/Response Models
# ==============================

class EnhanceRequest(BaseModel):
    """Request to enhance an AI response with knowledge."""
    query: str = Field(..., min_length=1, max_length=5000, description="User query")
    ai_response: str = Field(..., min_length=1, description="AI response to enhance")
    include_sources: bool = Field(False, description="Include source citations in response")
    visibility_level: Optional[str] = Field(None, description="Override default source visibility")
    providers: Optional[List[str]] = Field(None, description="Specific providers to use (all if None)")
    exclude_providers: Optional[List[str]] = Field(None, description="Providers to exclude")
    fusion_strategy: Optional[str] = Field(None, description="Fusion strategy: 'dedupe', 'priority', 'conflict_resolve'")

    @validator('visibility_level', pre=True, always=True)
    def validate_visibility(cls, v):
        if v is not None:
            allowed = [level.value for level in SourceVisibilityLevel]
            if v not in allowed:
                raise ValueError(f"visibility_level must be one of {allowed}")
        return v


class SearchRequest(BaseModel):
    """Request to search for knowledge only."""
    query: str = Field(..., min_length=1, max_length=5000, description="Search query")
    include_all_sources: bool = Field(False, description="Include every source, even low‑relevance")
    providers: Optional[List[str]] = Field(None, description="Specific providers to use")
    exclude_providers: Optional[List[str]] = Field(None, description="Providers to exclude")
    limit: int = Field(20, ge=1, le=100, description="Max results per provider")
    offset: int = Field(0, ge=0, description="Pagination offset")


class QueryRouteRequest(BaseModel):
    """Request to analyze query routing."""
    query: str = Field(..., min_length=1, max_length=5000)


class ProviderFilter(BaseModel):
    providers: Optional[List[str]] = None
    exclude_providers: Optional[List[str]] = None


# ==============================
# Helper Functions
# ==============================

def _apply_provider_filters(kwargs: Dict[str, Any], request: BaseModel) -> Dict[str, Any]:
    """Extract provider filters from request and add to kwargs."""
    if hasattr(request, 'providers'):
        if request.providers:
            kwargs['providers'] = request.providers
    if hasattr(request, 'exclude_providers'):
        if request.exclude_providers:
            kwargs['exclude_providers'] = request.exclude_providers
    return kwargs


def _add_cache_headers(response: Response, max_age: int = 60):
    """Add cache-control header to response."""
    response.headers["Cache-Control"] = f"public, max-age={max_age}"


# ==============================
# Endpoints
# ==============================

@router.post("/enhance")
async def enhance_response(request: EnhanceRequest, response: Response):
    """
    Enhance an AI response with knowledge from selected providers.

    This endpoint:
    - Routes the query to appropriate knowledge providers
    - Gathers knowledge from those providers (filtered by provider lists)
    - Fuses the information using the chosen strategy
    - Returns the enhanced response with optional source citations
    """
    start = time.perf_counter()
    logger.info(f"Enhance request: query={request.query[:50]}...")

    try:
        # Build kwargs
        kwargs = {
            "query": request.query,
            "ai_response": request.ai_response,
            "include_sources": request.include_sources,
        }
        if request.visibility_level is not None:
            kwargs["visibility_level"] = request.visibility_level
        if request.fusion_strategy:
            kwargs["fusion_strategy"] = request.fusion_strategy
        kwargs = _apply_provider_filters(kwargs, request)

        result = await enhance_chat_response(**kwargs)

        duration = time.perf_counter() - start
        logger.info(f"Enhance completed in {duration:.2f}s, sources={len(result.get('sources', []))}")
        _add_cache_headers(response, max_age=30)
        return result

    except ValueError as e:
        logger.warning(f"Enhance validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Enhance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {str(e)}")


@router.post("/search")
async def search_knowledge(request: SearchRequest, response: Response):
    """
    Search for knowledge from providers without AI augmentation.

    Useful for pure information retrieval, research, or building context.
    Supports pagination and provider filtering.
    """
    start = time.perf_counter()
    logger.info(f"Search request: query={request.query[:50]}...")

    try:
        kwargs = {
            "query": request.query,
            "include_all_sources": request.include_all_sources,
            "limit": request.limit,
            "offset": request.offset,
        }
        kwargs = _apply_provider_filters(kwargs, request)

        result = await get_knowledge_only(**kwargs)

        duration = time.perf_counter() - start
        logger.info(f"Search completed in {duration:.2f}s, results={len(result.get('facts', []))}")
        _add_cache_headers(response, max_age=60)
        return result

    except ValueError as e:
        logger.warning(f"Search validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/providers")
async def list_providers(response: Response):
    """
    Get detailed information about all registered knowledge providers.
    """
    try:
        registry = get_provider_registry()
        providers = registry.get_all_providers()
        provider_details = []
        for provider in providers:
            provider_details.append({
                "id": provider.id,
                "name": provider.name,
                "description": provider.description,
                "capabilities": provider.capabilities,
                "health": await provider.health_check(),
                "is_healthy": await provider.is_healthy(),
                "priority": getattr(provider, "priority", 0),
            })
        _add_cache_headers(response, max_age=120)
        return {
            "total": len(provider_details),
            "providers": provider_details,
        }
    except Exception as e:
        logger.error(f"Provider list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/status")
async def get_providers_status(response: Response):
    """
    Get health status of all registered providers.
    """
    try:
        registry = get_provider_registry()
        status = registry.get_status()
        _add_cache_headers(response, max_age=30)
        return {
            "total": len(status),
            "healthy": sum(1 for s in status.values() if s.get("healthy", False)),
            "providers": status,
        }
    except Exception as e:
        logger.error(f"Provider status error: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/query-route")
async def analyze_query_route(request: QueryRouteRequest, response: Response):
    """
    Analyze how a query will be routed to knowledge providers.

    Returns:
    - Query classification
    - Recommended providers
    - Confidence score
    - AI provider strategy
    - Keywords detected
    """
    try:
        result = await route_query(request.query)
        _add_cache_headers(response, max_age=300)  # cache longer as routing is deterministic
        return result
    except Exception as e:
        logger.error(f"Query routing error: {e}")
        raise HTTPException(status_code=500, detail=f"Routing analysis failed: {str(e)}")


@router.get("/enabled")
async def is_knowledge_enhancement_enabled(response: Response):
    """Check if knowledge enhancement is enabled globally."""
    integration = get_integration()
    _add_cache_headers(response, max_age=10)
    return {"enabled": integration.is_enabled()}


@router.post("/enable")
async def enable_knowledge_enhancement(enabled: bool = Body(..., description="Enable or disable")):
    """Enable or disable knowledge enhancement globally."""
    integration = get_integration()
    integration.set_enabled(enabled)
    logger.info(f"Knowledge enhancement {'enabled' if enabled else 'disabled'} by API request")
    return {"enabled": integration.is_enabled()}


@router.get("/settings")
async def get_knowledge_settings(response: Response):
    """Get current knowledge enhancement settings."""
    try:
        integration = get_integration()
        visibility_controller = get_visibility_controller()
        _add_cache_headers(response, max_age=60)
        return {
            "enabled": integration.is_enabled(),
            "default_visibility_level": visibility_controller.default_level.value,
            "similarity_threshold": 0.85,
            "max_parallel_providers": 3,
            "fusion_strategies": ["dedupe", "priority", "conflict_resolve"],
            "default_fusion_strategy": "dedupe",
        }
    except Exception as e:
        logger.error(f"Settings retrieval error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.get("/health")
async def knowledge_health_check(response: Response):
    """
    Detailed health check of all knowledge systems.

    Returns:
    - Overall status
    - Per‑provider health with latency and success rate
    - Component statuses
    """
    try:
        registry = get_provider_registry()
        health_results = await registry.health_check_all()
        healthy_count = sum(1 for v in health_results.values() if v.get("healthy", False))
        total_count = len(health_results)

        # Calculate average latency and success rate if available
        latencies = [v.get("latency_ms", 0) for v in health_results.values() if "latency_ms" in v]
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        status = "healthy" if healthy_count > 0 else "degraded"
        _add_cache_headers(response, max_age=10)
        return {
            "status": status,
            "providers_healthy": healthy_count,
            "providers_total": total_count,
            "average_latency_ms": avg_latency,
            "provider_status": health_results,
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/documentation")
async def get_knowledge_documentation(response: Response):
    """Get documentation on knowledge enhancement features."""
    _add_cache_headers(response, max_age=3600)
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
                "description": "Extensible provider system with filtering and pagination",
                "current_providers": [
                    "Wikipedia",
                    "GeeksforGeeks",
                    "Official Documentation",
                ]
            }
        },
        "endpoints": {
            "POST /api/knowledge/enhance": "Enhance AI response with knowledge",
            "POST /api/knowledge/search": "Search for knowledge (with pagination)",
            "GET  /api/knowledge/providers": "List all providers with details",
            "GET  /api/knowledge/providers/status": "Get provider health status",
            "POST /api/knowledge/query-route": "Analyze query routing",
            "GET  /api/knowledge/enabled": "Check if enhancement is enabled",
            "POST /api/knowledge/enable": "Enable/disable enhancement",
            "GET  /api/knowledge/health": "Detailed health check",
        }
    }