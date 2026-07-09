"""
Intelligent Query Router - Classifies user queries and routes to appropriate knowledge providers.

This module analyzes incoming questions and determines:
- Query type (general knowledge, programming, documentation, news, research, career guidance)
- Recommended knowledge providers
- Whether external data sources should be used
- Optimal AI provider selection strategy

This routing happens internally without changing the user experience.
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Classification of query types for routing."""
    
    GENERAL_KNOWLEDGE = "general_knowledge"
    PROGRAMMING = "programming"
    FRAMEWORK_DOCS = "framework_docs"
    OFFICIAL_DOCUMENTATION = "official_documentation"
    LATEST_NEWS = "latest_news"
    RESEARCH = "research"
    CAREER_GUIDANCE = "career_guidance"
    CODE_ASSISTANCE = "code_assistance"
    CREATIVE_WRITING = "creative_writing"
    IMAGE_GENERATION = "image_generation"
    MATH_SCIENCE = "math_science"
    CONVERSATIONAL = "conversational"
    UNKNOWN = "unknown"


class ProviderRecommendation(Enum):
    """Knowledge providers to use for a query."""
    
    WIKIPEDIA = "wikipedia"
    GEEKSFORGEEKS = "geeksforgeeks"
    OFFICIAL_DOCS = "official_docs"
    INTERNET_SEARCH = "internet_search"
    RESEARCH_API = "research_api"
    NOVA_CAREER_ENGINE = "nova_career_engine"
    LOCAL_KNOWLEDGE = "local_knowledge"  # Use only model knowledge


class QueryRouter:
    """Routes queries to appropriate knowledge sources and AI providers."""
    
    # Query classification patterns
    PROGRAMMING_KEYWORDS = {
        "code", "python", "javascript", "java", "c++", "rust", "golang", "ruby",
        "bug", "error", "debug", "exception", "algorithm", "data structure",
        "function", "class", "method", "variable", "syntax", "library", "api",
        "framework", "package", "module", "import", "require", "git", "github",
        "database", "sql", "orm", "rest", "graphql", "regex", "loop", "array",
        "object", "async", "await", "promise", "callback", "test", "unittest",
        "docker", "kubernetes", "devops", "ci/cd", "deployment", "server",
    }
    
    FRAMEWORK_KEYWORDS = {
        "react", "vue", "angular", "django", "fastapi", "flask", "springboot",
        "express", "nodejs", "next.js", "nextjs", "nuxt", "svelte", "ember",
        "rails", "asp.net", "laravel", "symfony", "wordpress", "tensorflow",
        "pytorch", "keras", "scikit-learn", "pandas", "numpy", "matplotlib",
    }
    
    DOCUMENTATION_KEYWORDS = {
        "docs", "documentation", "tutorial", "guide", "how to", "howto",
        "reference", "api reference", "examples", "sample", "cookbook",
        "specification", "spec", "standard", "rfc",
    }
    
    OFFICIAL_DOC_SOURCES = {
        "python": ["python.org", "docs.python.org"],
        "javascript": ["developer.mozilla.org", "mdn", "mdn web docs"],
        "java": ["oracle.com", "docs.oracle.com"],
        "react": ["react.dev", "reactjs.org"],
        "angular": ["angular.io"],
        "vue": ["vuejs.org"],
        "django": ["djangoproject.com"],
        "fastapi": ["fastapi.tiangolo.com"],
        "flask": ["flask.palletsprojects.com"],
        "springboot": ["spring.io"],
        "express": ["expressjs.com"],
        "nodejs": ["nodejs.org"],
        "nextjs": ["nextjs.org"],
        "kotlin": ["kotlinlang.org"],
        "rust": ["rust-lang.org"],
        "go": ["golang.org"],
        "csharp": ["docs.microsoft.com", "microsoft.com"],
        "dotnet": ["learn.microsoft.com"],
        "azure": ["learn.microsoft.com"],
        "aws": ["aws.amazon.com"],
        "gcp": ["cloud.google.com"],
    }
    
    NEWS_KEYWORDS = {
        "news", "latest", "recent", "today", "breaking", "announced", "released",
        "new version", "update", "security vulnerability", "exploit", "breach",
        "trending", "headline", "current events",
    }
    
    RESEARCH_KEYWORDS = {
        "research", "study", "paper", "academic", "journal", "experiment",
        "hypothesis", "analysis", "statistics", "data", "methodology", "peer-reviewed",
    }
    
    CAREER_KEYWORDS = {
        "career", "job", "interview", "resume", "skill", "salary", "promotion",
        "roadmap", "learning path", "certification", "course", "bootcamp",
        "growth", "development", "opportunity",
    }
    
    NEWS_TEMPORAL_PATTERNS = [
        r"\b(?:today|yesterday|tonight|right now|just now|breaking)\b",
        r"\b(?:current|latest|recent|new)\s+(?:news|updates?|events?|developments?)\b",
        r"\bwhat'?s\s+(?:happening|going on)\b",
        r"\b(?:did you hear about|have you seen)\b",
    ]
    
    RESEARCH_PATTERNS = [
        r"\b(?:research|study|paper|academic|journal|peer-reviewed)\b",
        r"\b(?:statistics|statistical|data\s+analysis|methodology)\b",
    ]
    
    CODE_PATTERNS = [
        r"```[\s\S]*?```",  # Code block
        r"def\s+\w+\s*\(|function\s+\w+\s*\(|class\s+\w+\s*[({]",  # Function/class definition
        r"^\s*[a-zA-Z_]\w*\s*[:=]",  # Variable assignment
    ]
    
    def __init__(self):
        """Initialize the query router."""
        self.query_type: Optional[QueryType] = None
        self.providers: List[ProviderRecommendation] = []
        self.confidence: float = 0.5
        self.keywords_found: List[str] = []
        self.metadata: Dict = {}
    
    def route_query(self, query: str) -> Dict:
        """
        Analyze a query and return routing recommendations.
        
        Args:
            query: The user's question or request
            
        Returns:
            Dictionary with routing information including:
            - query_type: Classification of the query
            - providers: List of recommended knowledge providers
            - use_local_only: Whether to use only model knowledge
            - ai_provider_strategy: How to select AI providers
            - confidence: Confidence score (0-1)
            - keywords: Keywords that influenced the classification
            - metadata: Additional routing metadata
        """
        query_lower = query.lower()
        
        # Detect query type
        self.query_type = self._classify_query(query_lower)
        
        # Get provider recommendations
        self.providers = self._get_provider_recommendations(query_lower, self.query_type)
        
        # Calculate confidence
        self.confidence = self._calculate_confidence(query_lower, self.query_type)
        
        # Determine AI provider strategy
        ai_strategy = self._get_ai_provider_strategy(self.query_type, query_lower)
        
        return {
            "query_type": self.query_type.value,
            "providers": [p.value for p in self.providers],
            "use_local_only": self.query_type in {
                QueryType.CREATIVE_WRITING,
                QueryType.CONVERSATIONAL,
                QueryType.IMAGE_GENERATION,
            },
            "ai_provider_strategy": ai_strategy,
            "confidence": self.confidence,
            "keywords": self.keywords_found,
            "metadata": self.metadata,
            "has_external_sources": len(self.providers) > 0 and
                                   ProviderRecommendation.LOCAL_KNOWLEDGE not in self.providers,
        }
    
    def _classify_query(self, query_lower: str) -> QueryType:
        """Classify the query into a specific type."""
        query_words = set(query_lower.split())
        
        # Check for specific types
        if self._match_pattern(query_lower, self.NEWS_TEMPORAL_PATTERNS):
            self.keywords_found.append("temporal_news")
            return QueryType.LATEST_NEWS
        
        if self._match_pattern(query_lower, self.RESEARCH_PATTERNS):
            self.keywords_found.append("research")
            return QueryType.RESEARCH
        
        # Check keywords
        prog_count = len(query_words & self.PROGRAMMING_KEYWORDS)
        framework_count = len(query_words & self.FRAMEWORK_KEYWORDS)
        doc_count = len(query_words & self.DOCUMENTATION_KEYWORDS)
        news_count = len(query_words & self.NEWS_KEYWORDS)
        career_count = len(query_words & self.CAREER_KEYWORDS)
        
        # Check for code patterns
        if re.search(r"(?:" + "|".join(self.CODE_PATTERNS) + ")", query_lower):
            if prog_count > 0 or framework_count > 0:
                self.keywords_found.extend(["code", "programming"])
                return QueryType.CODE_ASSISTANCE
        
        # Framework documentation
        if framework_count > prog_count and doc_count > 0:
            self.keywords_found.append("framework_docs")
            return QueryType.FRAMEWORK_DOCS
        
        # Official documentation
        if any(source in query_lower for source in self.OFFICIAL_DOC_SOURCES.get("python", [])):
            self.keywords_found.append("official_docs")
            return QueryType.OFFICIAL_DOCUMENTATION
        
        # Programming/coding
        if prog_count >= 2 or (prog_count > 0 and doc_count > 0):
            self.keywords_found.append("programming")
            return QueryType.PROGRAMMING
        
        # Career guidance
        if career_count > 0:
            self.keywords_found.append("career")
            return QueryType.CAREER_GUIDANCE
        
        # News
        if news_count > 0:
            self.keywords_found.append("news")
            return QueryType.LATEST_NEWS
        
        # Creative writing
        if any(word in query_lower for word in ["write", "story", "poem", "essay", "fiction", "creative"]):
            self.keywords_found.append("creative")
            return QueryType.CREATIVE_WRITING
        
        # Image generation
        if any(word in query_lower for word in ["generate", "create", "draw", "image", "picture", "photo", "visualize"]):
            if any(word in query_lower for word in ["image", "picture", "photo", "illustration", "visual", "diagram"]):
                self.keywords_found.append("image")
                return QueryType.IMAGE_GENERATION
        
        # Math and science
        if any(word in query_lower for word in ["math", "physics", "chemistry", "biology", "equation", "formula", "calculate"]):
            self.keywords_found.append("math_science")
            return QueryType.MATH_SCIENCE
        
        # Default to general knowledge or conversational
        if len(query_lower.split()) <= 5 or self._is_conversational(query_lower):
            self.keywords_found.append("conversational")
            return QueryType.CONVERSATIONAL
        
        self.keywords_found.append("general_knowledge")
        return QueryType.GENERAL_KNOWLEDGE
    
    def _get_provider_recommendations(
        self, query_lower: str, query_type: QueryType
    ) -> List[ProviderRecommendation]:
        """Get recommended knowledge providers for the query."""
        providers = []
        
        if query_type == QueryType.GENERAL_KNOWLEDGE:
            providers = [
                ProviderRecommendation.WIKIPEDIA,
                ProviderRecommendation.INTERNET_SEARCH,
            ]
        
        elif query_type == QueryType.PROGRAMMING:
            providers = [
                ProviderRecommendation.GEEKSFORGEEKS,
                ProviderRecommendation.INTERNET_SEARCH,
            ]
        
        elif query_type == QueryType.FRAMEWORK_DOCS:
            providers = [
                ProviderRecommendation.OFFICIAL_DOCS,
                ProviderRecommendation.GEEKSFORGEEKS,
            ]
        
        elif query_type == QueryType.OFFICIAL_DOCUMENTATION:
            providers = [ProviderRecommendation.OFFICIAL_DOCS]
        
        elif query_type == QueryType.CODE_ASSISTANCE:
            providers = [
                ProviderRecommendation.GEEKSFORGEEKS,
                ProviderRecommendation.OFFICIAL_DOCS,
            ]
        
        elif query_type == QueryType.LATEST_NEWS:
            providers = [ProviderRecommendation.INTERNET_SEARCH]
        
        elif query_type == QueryType.RESEARCH:
            providers = [
                ProviderRecommendation.RESEARCH_API,
                ProviderRecommendation.INTERNET_SEARCH,
            ]
        
        elif query_type == QueryType.CAREER_GUIDANCE:
            providers = [ProviderRecommendation.NOVA_CAREER_ENGINE]
        
        elif query_type == QueryType.MATH_SCIENCE:
            providers = [
                ProviderRecommendation.WIKIPEDIA,
                ProviderRecommendation.INTERNET_SEARCH,
            ]
        
        else:
            # For creative writing, conversational, image generation - use local knowledge
            providers = [ProviderRecommendation.LOCAL_KNOWLEDGE]
        
        return providers
    
    def _calculate_confidence(self, query_lower: str, query_type: QueryType) -> float:
        """Calculate confidence score for the classification."""
        confidence = 0.5
        
        if query_type == QueryType.CONVERSATIONAL:
            confidence = 0.9
        elif query_type == QueryType.IMAGE_GENERATION:
            confidence = 0.85 if any(w in query_lower for w in ["image", "picture", "photo"]) else 0.7
        elif query_type == QueryType.PROGRAMMING:
            confidence = 0.8 + (0.1 if len(self.keywords_found) > 1 else 0)
        elif query_type == QueryType.FRAMEWORK_DOCS:
            confidence = 0.85
        elif len(self.keywords_found) > 2:
            confidence = 0.8
        elif len(self.keywords_found) > 0:
            confidence = 0.65
        
        return min(0.99, max(0.3, confidence))
    
    def _get_ai_provider_strategy(self, query_type: QueryType, query_lower: str) -> str:
        """Determine AI provider selection strategy."""
        if query_type in {QueryType.CREATIVE_WRITING, QueryType.CODE_ASSISTANCE}:
            return "prefer_claude"  # Claude excels at creative and code
        elif query_type == QueryType.PROGRAMMING:
            return "prefer_gemini"  # Gemini good for technical Q&A
        elif query_type == QueryType.MATH_SCIENCE:
            return "prefer_gpt4"  # GPT-4 strong in STEM
        elif query_type == QueryType.LATEST_NEWS:
            return "prefer_fastest"  # Speed matters for time-sensitive queries
        else:
            return "balanced"  # Default: use best available
    
    @staticmethod
    def _match_pattern(text: str, patterns: List[str]) -> bool:
        """Check if any pattern matches the text."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def _is_conversational(text: str) -> bool:
        """Check if the query is conversational."""
        conversational_starts = {
            "hi ", "hello ", "hey ", "how are you", "what's up",
            "tell me about", "explain", "describe", "what is",
        }
        return any(text.startswith(start) for start in conversational_starts)


# Singleton instance
_router: Optional[QueryRouter] = None


def get_query_router() -> QueryRouter:
    """Get or create the singleton query router instance."""
    global _router
    if _router is None:
        _router = QueryRouter()
    return _router


async def route_query(query: str) -> Dict:
    """
    Async wrapper to route a query.
    
    Args:
        query: The user's question
        
    Returns:
        Routing recommendations dictionary
    """
    router = get_query_router()
    return router.route_query(query)
