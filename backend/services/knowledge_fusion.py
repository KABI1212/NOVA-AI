"""
Knowledge Fusion Service - Combines information from multiple knowledge providers.

When multiple providers are used:
- Merge information intelligently
- Remove duplicate facts
- Resolve conflicts between sources
- Generate a unified NOVA AI response
- Track sources for optional disclosure

Implements deduplication, conflict resolution, and intelligent merging.
"""

import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from services.knowledge_providers import KnowledgeSource, ProviderType

logger = logging.getLogger(__name__)


@dataclass
class FusedKnowledge:
    """Result of fusing multiple knowledge sources."""
    
    primary_content: str
    supplementary_content: Dict[str, str]  # provider -> content
    facts: List[str]
    summary: str
    sources: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    deduplication_stats: Dict[str, int]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "primary_content": self.primary_content,
            "supplementary_content": self.supplementary_content,
            "facts": self.facts,
            "summary": self.summary,
            "sources": self.sources,
            "conflicts": self.conflicts,
            "deduplication_stats": self.deduplication_stats,
            "metadata": self.metadata,
        }


class KnowledgeFusionEngine:
    """Engine for fusing information from multiple knowledge sources."""
    
    def __init__(self):
        """Initialize the fusion engine."""
        self.provider_priorities = {
            ProviderType.OFFICIAL_DOCS: 1.0,      # Highest priority
            ProviderType.WIKIPEDIA: 0.9,
            ProviderType.GEEKSFORGEEKS: 0.85,
            ProviderType.INTERNET_SEARCH: 0.7,
            ProviderType.RESEARCH_API: 0.8,
            ProviderType.LOCAL_KNOWLEDGE: 0.5,    # Lowest priority
        }
        self.similarity_threshold = 0.85
    
    async def fuse_sources(
        self,
        sources: List[KnowledgeSource],
        query: str,
        include_supplementary: bool = True
    ) -> FusedKnowledge:
        """
        Fuse multiple knowledge sources into a cohesive response.
        
        Args:
            sources: List of KnowledgeSource objects
            query: Original user query
            include_supplementary: Whether to include supplementary content
            
        Returns:
            FusedKnowledge object
        """
        if not sources:
            return self._create_empty_fused_knowledge()
        
        # Sort sources by priority
        ranked_sources = self._rank_sources(sources)
        
        # Deduplicate content
        deduped_sources, dedup_stats = await self._deduplicate_sources(ranked_sources)
        
        # Extract and merge facts
        all_facts = await self._extract_all_facts(deduped_sources)
        deduplicated_facts, fact_dedup_stats = self._deduplicate_facts(all_facts)
        
        # Detect conflicts
        conflicts = await self._detect_conflicts(deduped_sources)
        
        # Generate primary and supplementary content
        primary_content = self._generate_primary_content(deduped_sources, deduplicated_facts)
        supplementary_content = {}
        
        if include_supplementary:
            supplementary_content = self._generate_supplementary_content(deduped_sources)
        
        # Create summary
        summary = self._create_summary(deduplicated_facts, deduped_sources)
        
        # Build source information
        source_info = self._build_source_info(deduped_sources)
        
        # Combine stats
        dedup_stats.update(fact_dedup_stats)
        
        return FusedKnowledge(
            primary_content=primary_content,
            supplementary_content=supplementary_content,
            facts=deduplicated_facts[:20],  # Top 20 facts
            summary=summary,
            sources=source_info,
            conflicts=conflicts,
            deduplication_stats=dedup_stats,
            metadata={
                "query": query,
                "source_count": len(sources),
                "deduped_count": len(deduped_sources),
                "total_facts": len(all_facts),
                "merged_facts": len(deduplicated_facts),
                "conflict_count": len(conflicts),
            },
        )
    
    def _rank_sources(self, sources: List[KnowledgeSource]) -> List[KnowledgeSource]:
        """Rank sources by provider priority and relevance."""
        def sort_key(source: KnowledgeSource) -> tuple:
            priority = self.provider_priorities.get(source.provider, 0.5)
            relevance = source.relevance_score
            confidence = source.confidence
            # Combined score: priority > relevance > confidence
            return (priority, relevance, confidence)
        
        return sorted(sources, key=sort_key, reverse=True)
    
    async def _deduplicate_sources(
        self,
        sources: List[KnowledgeSource]
    ) -> tuple[List[KnowledgeSource], Dict[str, int]]:
        """Remove duplicate or near-duplicate sources."""
        if not sources:
            return [], {}
        
        unique_sources = [sources[0]]
        removed_count = 0
        
        for source in sources[1:]:
            if not self._is_similar_to_any(source, unique_sources):
                unique_sources.append(source)
            else:
                removed_count += 1
        
        stats = {
            "original_sources": len(sources),
            "deduplicated_sources": len(unique_sources),
            "removed_duplicate_sources": removed_count,
        }
        
        return unique_sources, stats
    
    def _is_similar_to_any(
        self,
        source: KnowledgeSource,
        sources: List[KnowledgeSource]
    ) -> bool:
        """Check if source is similar to any in the list."""
        for existing in sources:
            source_text = source.title + " " + (source.summary or source.content[:100] if source.content else "")
            existing_text = existing.title + " " + (existing.summary or existing.content[:100] if existing.content else "")
            similarity = self._calculate_text_similarity(source_text, existing_text)
            if similarity >= self.similarity_threshold:
                return True
        return False
    
    @staticmethod
    def _calculate_text_similarity(text1: str, text2: str) -> float:
        """Calculate simple text similarity using word overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    async def _extract_all_facts(self, sources: List[KnowledgeSource]) -> List[Dict[str, Any]]:
        """Extract facts from all sources with source attribution."""
        all_facts = []
        
        for source in sources:
            # Extract from content
            sentences = [
                s.strip() for s in
                source.content.split('.')
                if s.strip() and len(s.strip()) > 15
            ]
            
            for sentence in sentences[:5]:  # Take first 5 meaningful sentences
                all_facts.append({
                    "text": sentence,
                    "source": source.provider.value,
                    "provider": source.provider.value,
                    "url": source.url,
                    "confidence": source.confidence,
                    "relevance": source.relevance_score,
                })
        
        return all_facts
    
    def _deduplicate_facts(self, facts: List[Dict[str, Any]]) -> tuple[List[str], Dict[str, int]]:
        """Remove duplicate facts."""
        if not facts:
            return [], {}
        
        seen_facts: Set[str] = set()
        unique_facts = []
        removed_count = 0
        
        for fact in facts:
            fact_text = fact["text"].lower()
            
            # Check for similarity with existing facts
            is_duplicate = False
            for seen in seen_facts:
                similarity = self._calculate_text_similarity(fact_text, seen)
                if similarity >= self.similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_facts.append(fact["text"])
                seen_facts.add(fact_text)
            else:
                removed_count += 1
        
        stats = {
            "original_facts": len(facts),
            "unique_facts": len(unique_facts),
            "removed_duplicate_facts": removed_count,
        }
        
        return unique_facts, stats
    
    async def _detect_conflicts(self, sources: List[KnowledgeSource]) -> List[Dict[str, Any]]:
        """Detect conflicting information between sources."""
        conflicts = []
        
        # This is a simplified conflict detection
        # In a production system, you might use NER and knowledge graphs
        
        for i, source1 in enumerate(sources):
            for source2 in sources[i+1:]:
                # Look for direct contradictions
                if self._has_contradiction(source1.content, source2.content):
                    conflicts.append({
                        "source1": source1.provider.value,
                        "source2": source2.provider.value,
                        "type": "potential_contradiction",
                        "resolution": "Use higher-priority source",
                    })
        
        return conflicts
    
    @staticmethod
    def _has_contradiction(text1: str, text2: str) -> bool:
        """Simple contradiction detection (can be enhanced with NLP)."""
        # Look for explicit negations or conflicts
        contradiction_pairs = [
            ("true", "false"),
            ("yes", "no"),
            ("always", "never"),
            ("supported", "not supported"),
        ]
        
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        for pos, neg in contradiction_pairs:
            if (pos in text1_lower and neg in text2_lower) or \
               (neg in text1_lower and pos in text2_lower):
                return True
        
        return False
    
    def _generate_primary_content(
        self,
        sources: List[KnowledgeSource],
        facts: List[str]
    ) -> str:
        """Generate primary content from top sources."""
        if not sources:
            return ""
        
        content_parts = []
        
        # Use content from highest priority source as main content
        primary_source = sources[0]
        content_parts.append(primary_source.content)
        
        # Add supplementary facts from other sources if they add value
        for source in sources[1:2]:  # Add from second source if available
            if source.content not in content_parts[0]:
                content_parts.append(f"\n\n**Additional perspective:** {source.content[:500]}")
        
        return "\n".join(content_parts)
    
    def _generate_supplementary_content(
        self, sources: List[KnowledgeSource]
    ) -> Dict[str, str]:
        """Generate supplementary content from other sources."""
        supplementary = {}
        
        for i, source in enumerate(sources[1:], 1):  # Skip primary source
            key = f"{source.provider.value}_{i}"
            supplementary[key] = {
                "provider": source.provider.value,
                "title": source.title,
                "content": source.content[:500],
                "url": source.url,
            }
        
        return supplementary
    
    def _create_summary(
        self,
        facts: List[str],
        sources: List[KnowledgeSource]
    ) -> str:
        """Create a concise summary."""
        if not sources:
            return ""
        
        # Use primary source's summary if available
        if sources[0].summary:
            return sources[0].summary
        
        # Otherwise, create from facts
        if facts:
            return " ".join(facts[:3])
        
        return ""
    
    def _build_source_info(self, sources: List[KnowledgeSource]) -> List[Dict[str, Any]]:
        """Build information about sources for optional disclosure."""
        source_info = []
        
        for source in sources:
            source_info.append({
                "provider": source.provider.value,
                "title": source.title,
                "url": source.url,
                "confidence": source.confidence,
                "relevance": source.relevance_score,
                "type": source.metadata.get("source_type", "unknown"),
            })
        
        return source_info
    
    def _create_empty_fused_knowledge(self) -> FusedKnowledge:
        """Create an empty FusedKnowledge object."""
        return FusedKnowledge(
            primary_content="",
            supplementary_content={},
            facts=[],
            summary="",
            sources=[],
            conflicts=[],
            deduplication_stats={},
            metadata={},
        )


# Singleton instance
_fusion_engine: Optional[KnowledgeFusionEngine] = None


def get_fusion_engine() -> KnowledgeFusionEngine:
    """Get or create the singleton fusion engine instance."""
    global _fusion_engine
    if _fusion_engine is None:
        _fusion_engine = KnowledgeFusionEngine()
    return _fusion_engine


async def fuse_knowledge_sources(
    sources: List[KnowledgeSource],
    query: str,
    include_supplementary: bool = True
) -> FusedKnowledge:
    """
    Convenience function to fuse knowledge sources.
    
    Args:
        sources: List of KnowledgeSource objects
        query: Original user query
        include_supplementary: Whether to include supplementary content
        
    Returns:
        FusedKnowledge object
    """
    engine = get_fusion_engine()
    return await engine.fuse_sources(sources, query, include_supplementary)
