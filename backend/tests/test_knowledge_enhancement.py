from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from main import app
from services.knowledge_providers import (
    KnowledgeProvider,
    KnowledgeSource,
    ProviderType,
    SearchResult,
    get_provider_registry,
)
from services.wikipedia_provider import WikipediaProvider
from services.geeksforgeeks_provider import GeeksforGeeksProvider
from services.documentation_provider import DocumentationProvider
from services.intelligent_query_router import (
    QueryRouter,
    QueryType,
    ProviderRecommendation,
    route_query,
)
from services.knowledge_fusion import KnowledgeFusionEngine, fuse_knowledge_sources
from services.source_visibility import (
    SourceVisibilityLevel,
    SourceVisibilityController,
    AutoProviderSelector,
)
from services.knowledge_enhancement_integration import (
    KnowledgeEnhancementIntegration,
    get_integration,
    enhance_chat_response,
    get_knowledge_only,
)
from services.knowledge_enhancement_bootstrap import KnowledgeEnhancementBootstrap


@pytest.fixture
def client():
    return TestClient(app)


def test_provider_base_properties():
    class DummyProvider(KnowledgeProvider):
        async def _setup(self) -> bool:
            return True
        async def _search(self, query: str, limit: int) -> SearchResult:
            return SearchResult(
                query=query,
                provider=self.provider_type,
                total_results=0,
                results=[],
                search_time_ms=1.0,
                is_successful=True,
            )
        async def _retrieve(self, source_id: str):
            return None
        async def _extract(self, content: str):
            return {}
        async def _normalize(self, raw_data):
            return KnowledgeSource(provider=self.provider_type, title="test", content="content")
        async def _generate(self, sources):
            return ""
        async def _health_check(self) -> bool:
            return True

    provider = DummyProvider("Dummy", ProviderType.CUSTOM)
    assert provider.id == "custom_dummy"
    assert "Dummy" in provider.description or "dummy" in provider.description.lower()
    assert "search" in provider.capabilities
    assert provider.get_status()["name"] == "Dummy"


@pytest.mark.anyio
async def test_wikipedia_provider_search_and_retrieve():
    provider = WikipediaProvider()
    assert provider.provider_type == ProviderType.WIKIPEDIA

    mock_client = AsyncMock()
    mock_setup_resp = MagicMock(status_code=200)
    mock_health_resp = MagicMock(status_code=200)
    mock_search_resp = MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "query": {
                "search": [
                    {"title": "Artificial intelligence", "snippet": "AI is intelligence demonstrated by machines", "size": 1234}
                ]
            }
        }),
    )
    mock_search_resp.raise_for_status = MagicMock()

    mock_extract_resp = MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "query": {
                "pages": {
                    "123": {
                        "title": "Artificial intelligence",
                        "extract": "Artificial intelligence is intelligence demonstrated by machines.",
                    }
                }
            }
        }),
    )
    mock_extract_resp.raise_for_status = MagicMock()

    mock_client.get.side_effect = [mock_setup_resp, mock_health_resp, mock_search_resp, mock_extract_resp]
    provider.http_client = mock_client

    assert await provider.initialize() is True
    search_res = await provider.search("AI", limit=2)
    assert search_res.is_successful is True
    assert len(search_res.results) == 1
    assert search_res.results[0]["title"] == "Artificial intelligence"

    # Retrieve
    source = await provider.retrieve("Artificial_intelligence")
    assert source is not None
    assert source.title == "Artificial intelligence"
    assert "intelligence" in source.content


@pytest.mark.anyio
async def test_query_router_classification():
    router = QueryRouter()
    
    res_code = router.route_query("How do I write a Python async function?")
    assert res_code["query_type"] in {QueryType.PROGRAMMING.value, QueryType.CODE_ASSISTANCE.value}
    assert "has_external_sources" in res_code

    res_news = router.route_query("Breaking latest news updates today")
    assert res_news["query_type"] == QueryType.LATEST_NEWS.value

    res_async = await route_query("Explain neural networks and backpropagation")
    assert "query_type" in res_async
    assert "providers" in res_async


@pytest.mark.anyio
async def test_knowledge_fusion_engine():
    engine = KnowledgeFusionEngine()
    s1 = KnowledgeSource(
        provider=ProviderType.WIKIPEDIA,
        title="Python",
        content="Python is a high-level programming language created by Guido van Rossum.",
        url="https://en.wikipedia.org/wiki/Python",
        confidence=0.9,
    )
    s2 = KnowledgeSource(
        provider=ProviderType.GEEKSFORGEEKS,
        title="Python Intro",
        content="Python is an interpreted object-oriented language. It supports dynamic typing.",
        url="https://www.geeksforgeeks.org/python-programming-language/",
        confidence=0.85,
    )

    fused = await engine.fuse_sources([s1, s2], "What is Python?")
    assert fused is not None
    assert len(fused.sources) == 2
    assert "Python" in fused.primary_content
    assert len(fused.facts) > 0


def test_source_visibility_controller():
    controller = SourceVisibilityController()
    level = controller.determine_visibility_level("Where did you get this source from?")
    assert level in {SourceVisibilityLevel.NORMAL, SourceVisibilityLevel.DETAILED, SourceVisibilityLevel.COMPREHENSIVE}

    wrapped = controller.get_hidden_response_wrapper("Raw answer text [Wikipedia]")
    assert "Wikipedia" not in wrapped or "Raw answer text" in wrapped


@pytest.mark.anyio
async def test_knowledge_enhancement_integration_flow():
    integration = KnowledgeEnhancementIntegration()
    assert integration.enabled is True

    # Test get_knowledge_only
    res = await integration.get_knowledge_only("Explain recursion")
    assert "query" in res
    assert "sources" in res

    # Test enhance_chat_response fallback and flow
    enh = await integration.enhance_chat_response(
        query="What is quantum computing?",
        ai_response="Quantum computing uses qubits.",
        include_sources=False,
    )
    assert "response" in enh
    assert "enhanced" in enh


def test_knowledge_enhancement_api_endpoints(client):
    # Test GET /api/knowledge/enabled
    resp = client.get("/api/knowledge/enabled")
    assert resp.status_code == 200
    assert "enabled" in resp.json()

    # Test GET /api/knowledge/settings
    resp = client.get("/api/knowledge/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "fusion_strategies" in data

    # Test GET /api/knowledge/providers
    resp = client.get("/api/knowledge/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data

    # Test GET /api/knowledge/providers/status
    resp = client.get("/api/knowledge/providers/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data

    # Test POST /api/knowledge/query-route
    resp = client.post("/api/knowledge/query-route", json={"query": "How to sort a list in Python?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "query_type" in data
    assert "providers" in data

    # Test GET /api/knowledge/health
    resp = client.get("/api/knowledge/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data

    # Test GET /api/knowledge/documentation
    resp = client.get("/api/knowledge/documentation")
    assert resp.status_code == 200
    data = resp.json()
    assert "features" in data
