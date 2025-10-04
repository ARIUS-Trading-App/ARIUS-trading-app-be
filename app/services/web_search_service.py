from tavily import TavilyClient
from app.core.config import settings
from typing import List, Dict, Optional 

class WebSearchService:
    def __init__(self):
        """Initializes the WebSearchService.

        Raises:
            ValueError: If the TAVILY_API_KEY is not set.
        """
        if not settings.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY not set in environment variables.")
        self.client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    async def search(self, query: str, search_depth: str = "advanced", max_results: int = 5, include_domains: Optional[List[str]] = None, exclude_domains: Optional[List[str]] = None) -> List[Dict]:
        """Performs a web search using the Tavily API.

        Args:
            query (str): The search query.
            search_depth (str): The depth of the search ("basic" or "advanced").
            max_results (int): The maximum number of results to return.
            include_domains (Optional[List[str]]): A list of domains to focus the search on.
            exclude_domains (Optional[List[str]]): A list of domains to exclude.

        Returns:
            List[Dict]: A list of search result dictionaries, or an empty list on error.
        """
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
        """Performs a search and formats the results into a single context string.

        This is useful for providing context to a language model.

        Args:
            query (str): The search query.
            **kwargs: Additional arguments to be passed to the `search` method.

        Returns:
            str: A formatted string containing the content of all search results,
                 or a message if no results were found.
        """
        results = await self.search(query, **kwargs)
        context = ""
        for i, result in enumerate(results):
            content_snippet = result.get('content', '')
            context += f"Source {i+1} (URL: {result.get('url', 'N/A')}):\n{content_snippet}\n\n"
        return context.strip() if context else "No relevant information found from web search."

web_search_service = WebSearchService()