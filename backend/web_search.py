"""
DuckDuckGo Web Search Integration for Real-Time Data
Completely FREE - No API key required
"""

import requests
from typing import List, Dict, Optional
import json
from datetime import datetime


class DuckDuckGoSearch:
    """Free web search using DuckDuckGo API"""
    
    BASE_URL = "https://api.duckduckgo.com"
    
    @staticmethod
    def search(query: str, max_results: int = 5) -> List[Dict]:
        """
        Search using DuckDuckGo API
        
        Args:
            query: Search query (e.g., "India T20 cricket captain 2026")
            max_results: Number of results to return
            
        Returns:
            List of search results with title, description, and URL
        """
        try:
            params = {
                "q": query,
                "format": "json",
                "pretty": 1,
                "no_redirect": 1,
            }
            
            headers = {
                "User-Agent": "NOVA-AI/1.0"
            }
            
            response = requests.get(
                DuckDuckGoSearch.BASE_URL,
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Extract results from DuckDuckGo response
            if "Results" in data:
                for result in data["Results"][:max_results]:
                    results.append({
                        "title": result.get("Title", ""),
                        "url": result.get("FirstURL", ""),
                        "snippet": result.get("Text", ""),
                        "source": "DuckDuckGo"
                    })
            
            # Also add instant answer if available
            if data.get("AbstractText"):
                results.insert(0, {
                    "title": data.get("AbstractTitle", "Quick Answer"),
                    "snippet": data.get("AbstractText", ""),
                    "url": data.get("AbstractURL", ""),
                    "source": "DuckDuckGo Instant Answer"
                })
            
            return results
            
        except Exception as e:
            print(f"DuckDuckGo search error: {str(e)}")
            return []


class RealTimeDataProvider:
    """Combine web search with AI for real-time answers"""
    
    @staticmethod
    def format_search_results(results: List[Dict]) -> str:
        """Format search results for AI context"""
        if not results:
            return "No search results found."
        
        formatted = "Real-time search results:\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result['title']}\n"
            formatted += f"   Source: {result['source']}\n"
            formatted += f"   {result['snippet']}\n"
            if result.get('url'):
                formatted += f"   URL: {result['url']}\n"
            formatted += "\n"
        
        return formatted
    
    @staticmethod
    def get_real_time_context(user_query: str) -> str:
        """
        Get real-time context for a user query
        
        Args:
            user_query: User's question
            
        Returns:
            Formatted search results to send to AI
        """
        # Search for relevant information
        search_results = DuckDuckGoSearch.search(user_query, max_results=5)
        
        # Format for AI
        context = RealTimeDataProvider.format_search_results(search_results)
        
        return context


# Example usage in FastAPI
def enhance_with_real_time_data(user_message: str) -> str:
    """
    Enhance user message with real-time data
    
    Usage in your FastAPI endpoint:
        enhanced_prompt = enhance_with_real_time_data(user_message)
        # Then send enhanced_prompt to your AI model
    """
    real_time_context = RealTimeDataProvider.get_real_time_context(user_message)
    
    enhanced_prompt = f"""
Based on the following real-time information, answer the user's question:

{real_time_context}

User Question: {user_message}

Please provide an answer based on the latest information above.
"""
    
    return enhanced_prompt
