"""
Real-Time Web Search for NOVA AI
Uses Google Gemini AI (FREE with Google API key)
No credit card required
"""

import requests
import os
from typing import Optional

class GoogleGeminiSearch:
    """Real-time search using Google Gemini AI with web access"""
    
    @staticmethod
    def search_with_gemini(query: str) -> str:
        """
        Search using Google Gemini AI with web grounding
        
        Args:
            query: Search query
            
        Returns:
            Real-time answer from Gemini
        """
        try:
            api_key = os.getenv("GOOGLE_API_KEY", "")
            
            if not api_key:
                print("⚠️ GOOGLE_API_KEY not set, using fallback...")
                return GoogleGeminiSearch.fallback_search(query)
            
            # Using Gemini API with web search capability
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
            
            headers = {
                "Content-Type": "application/json",
            }
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"""You are a real-time information assistant. Answer this question with the most current information you have:

{query}

Provide:
1. Direct answer to the question
2. Source of information if known
3. Any recent updates (2026)
"""
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 500
                }
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                params={"key": api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return answer if answer else GoogleGeminiSearch.fallback_search(query)
            else:
                print(f"Gemini API error: {response.status_code} - {response.text}")
                return GoogleGeminiSearch.fallback_search(query)
                
        except Exception as e:
            print(f"Gemini search error: {str(e)}")
            return GoogleGeminiSearch.fallback_search(query)
    
    @staticmethod
    def fallback_search(query: str) -> str:
        """Fallback to Wikipedia + DuckDuckGo"""
        try:
            # Try Wikipedia
            wiki_url = "https://en.wikipedia.org/w/api.php"
            wiki_params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1
            }
            
            headers = {"User-Agent": "NOVA-AI/1.0"}
            wiki_response = requests.get(wiki_url, params=wiki_params, headers=headers, timeout=5)
            wiki_data = wiki_response.json()
            
            if wiki_data.get("query", {}).get("search"):
                result = wiki_data["query"]["search"][0]
                snippet = result.get("snippet", "").replace("<span class='searchmatch'>", "").replace("</span>", "")
                return f"**{result['title']}**\n\n{snippet}\n\n📌 Source: Wikipedia"
            
            # Try DuckDuckGo
            ddg_url = "https://api.duckduckgo.com/"
            ddg_params = {
                "q": query,
                "format": "json",
                "no_html": 1
            }
            
            ddg_response = requests.get(ddg_url, params=ddg_params, headers=headers, timeout=5)
            ddg_data = ddg_response.json()
            
            if ddg_data.get("AbstractText"):
                return f"**{ddg_data.get('Heading', 'Answer')}**\n\n{ddg_data['AbstractText']}\n\n📌 Source: DuckDuckGo"
            
            return f"⚠️ Could not find information about '{query}'. Please try a different search or provide more context."
            
        except Exception as e:
            print(f"Fallback search error: {str(e)}")
            return f"Search error: {str(e)}"


class RealTimeSearcher:
    """Alternative methods for real-time search - completely FREE"""
    
    @staticmethod
    def search_openweather(query: str) -> Optional[str]:
        """For weather queries - FREE API"""
        if "weather" in query.lower() and ("today" in query.lower() or "now" in query.lower()):
            try:
                # This is just an example - you'd need to implement weather search
                return None
            except:
                return None
        return None
    
    @staticmethod
    def search_newsapi(query: str) -> Optional[str]:
        """For news queries - FREE tier available"""
        if any(keyword in query.lower() for keyword in ["news", "breaking", "latest", "today"]):
            try:
                # NewsAPI has free tier
                api_key = os.getenv("NEWSAPI_KEY", "")
                if not api_key:
                    return None
                
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "apiKey": api_key,
                    "pageSize": 1
                }
                
                response = requests.get(url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("articles"):
                        article = data["articles"][0]
                        return f"""**{article['title']}**

{article.get('description', '')}

📌 Source: {article.get('source', {}).get('name', 'News')}
🔗 URL: {article.get('url', '')}"""
            except:
                pass
        return None


def enhance_with_real_time_data(user_message: str) -> str:
    """
    Enhance user message with real-time data
    
    Tries multiple free sources:
    1. Google Gemini (if API key available)
    2. NewsAPI (if API key available)
    3. Wikipedia + DuckDuckGo (always free)
    """
    print(f"🔍 Searching for real-time data: {user_message}")
    
    # Try news search first
    news_result = RealTimeSearcher.search_newsapi(user_message)
    if news_result:
        search_result = news_result
        print("✅ Found via NewsAPI")
    else:
        # Try Gemini
        search_result = GoogleGeminiSearch.search_with_gemini(user_message)
        print("✅ Search complete")
    
    # Create enhanced prompt
    enhanced_prompt = f"""You are NOVA AI with real-time information access.

Real-time search result:

{search_result}

---

Based on the above information, answer this question accurately:

User Question: {user_message}

Instructions:
- Use the search results above
- Be factual and concise
- Cite sources when available
- If information is incomplete, acknowledge it
"""
    
    return enhanced_prompt