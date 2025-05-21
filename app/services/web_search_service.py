from tavily import TavilyClient
from app.core.config import settings
from typing import List, Dict, Optional 

class WebSearchService:
    def __init__(self):
        if not settings.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY not set in environment variables.")
        self.client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    async def search(self, query: str, search_depth: str = "basic", max_results: int = 5, include_domains: Optional[List[str]] = None, exclude_domains: Optional[List[str]] = None) -> List[Dict]:
        try:
            response = self.client.search(
                query=query,
                search_depth=search_depth, 
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains
            )
            return response.get("results", [])
        except Exception as e:
            print(f"Error during Tavily search: {e}")
            return []

    async def get_search_context(self, query: str, max_chars_per_result: int = 500, **kwargs) -> str:
        results = await self.search(query, **kwargs)
        context = ""
        for i, result in enumerate(results):
            content_snippet = result.get('content', '')[:max_chars_per_result]
            context += f"Source {i+1} (URL: {result.get('url', 'N/A')}):\n{content_snippet}\n\n"
        return context.strip() if context else "No relevant information found from web search."

web_search_service = WebSearchService()
