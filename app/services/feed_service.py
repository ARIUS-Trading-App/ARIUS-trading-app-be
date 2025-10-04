import asyncio
from typing import List, Optional
from datetime import datetime, timedelta

from app.services.web_search_service import web_search_service
from app.services.llm_provider_service import llm_service
from app.crud.feed import create_feed_item, update_feed_summary
from app.schemas.feed import FeedItem, FeedItemCreate
from app.models.feed import FeedItem
from sqlalchemy.orm import Session

class FeedFetcher:
    def __init__(self, db: Session, user_id: int):
        """Initializes the FeedFetcher with database session and user context.

        Args:
            db (Session): The SQLAlchemy database session.
            user_id (int): The ID of the user for whom the feed is being fetched.
        """
        self.db = db
        self.user_id = user_id

    async def fetch_news(self, query: str, limit: int = 10):
        """Fetches news, stores new items, and triggers summarization.

        Uses the web search service to find relevant news articles, then processes
        each result to store it in the database and generate a summary using an LLM.

        Args:
            query (str): The search query for fetching news.
            limit (int): The maximum number of news items to fetch.
        """
        print(f"Fetching news for query: '{query}', limit: {limit}")
        results = await web_search_service.search(
            query=query, search_depth="basic", max_results=limit,
            include_domains=["reuters.com", "bloomberg.com"]
        )
        
        stored_items_count = 0
        for res_idx, res_data in enumerate(results):
            print(f"Processing news result {res_idx + 1}/{len(results)}")
            if not isinstance(res_data, dict):
                print(f"  WARNING: Expected a dictionary from web_search_service for item {res_idx + 1}, got {type(res_data)}. Skipping.")
                continue

            item = await self._store_item("news", res_data)
            
            if item and item.id is not None:
                stored_items_count += 1
                content_for_summary = item.content 
                if not content_for_summary:
                    print(f"  WARNING: Content for item ID {item.id} (Original ID: {item.original_id}) is empty. Skipping summarization.")
                else:
                    print(f"  Summarizing item ID {item.id} (Original ID: {item.original_id})")
                    await self._summarize(item.id, content_for_summary)
            else:
                print(f"  INFO: News item from result {res_idx + 1} was skipped during storage (e.g., missing suitable ID). Raw data: {res_data.get('content', '')[:50]}...")
        print(f"Finished fetching news. Stored {stored_items_count} items.")

    async def fetch_tweets(self, query: str, limit: int = 10):
        """(Placeholder) Fetches tweets, stores them, and triggers summarization.

        This is a mock implementation to demonstrate the intended functionality
        for fetching and processing tweets.

        Args:
            query (str): The search query for fetching tweets.
            limit (int): The maximum number of tweets to fetch.
        """
        print(f"Fetching tweets for query: '{query}', limit: {limit} (Placeholder)")
        mock_tweets_data = [
            {"id": "tweet123", "text": "This is a sample tweet about " + query, "user": "twitter_user1"},
            {"id": "tweet456", "text": "Another interesting tweet regarding " + query, "user": "twitter_user2"}
        ]
        tweets = mock_tweets_data[:limit]

        stored_items_count = 0
        for t_idx, t_data in enumerate(tweets):
            print(f"Processing tweet {t_idx + 1}/{len(tweets)}")
            item_payload = {
                "original_id": str(t_data["id"]),
                "content": t_data["text"],
                "source": "twitter.com",
                "metadata": {"author": t_data["user"], "tweet_id_num": t_data["id"]}
            }
            item = await self._store_item("tweet", item_payload)
            
            if item and item.id is not None:
                stored_items_count += 1
                content_for_summary = item.content
                if not content_for_summary:
                     print(f"  WARNING: Content for tweet ID {item.id} (Original ID: {item.original_id}) is empty. Skipping summarization.")
                else:
                    print(f"  Summarizing tweet ID {item.id} (Original ID: {item.original_id})")
                    await self._summarize(item.id, content_for_summary)
            else:
                print(f"  INFO: Tweet from data {t_idx+1} was skipped during storage. Raw data: {t_data.get('text', '')[:50]}...")
        print(f"Finished fetching tweets. Stored {stored_items_count} items.")
    
    async def _store_item(self, typ: str, raw: dict) -> Optional[FeedItem]:
        """Validates and stores a single raw item in the database.

        Args:
            typ (str): The type of the item (e.g., "news", "tweet").
            raw (dict): The dictionary containing the raw data of the item.

        Returns:
            Optional[FeedItem]: The created FeedItem object from the database,
                                or None if storing failed.
        """
        original_id_value = raw.get("original_id")

        if original_id_value is None:
            if typ == "news":
                original_id_value = raw.get("url") 
                if original_id_value is None:
                    original_id_value = raw.get("id")
                
                if original_id_value is None:
                    print(f"  ERROR (_store_item): Could not determine a unique ID (tried original_id, url, id) for news item. Raw content snippet: '{raw.get('content', '')[:70]}...'. Skipping.")
                    return None
            else:
                print(f"  ERROR (_store_item): 'original_id' is missing for item of type '{typ}'. Raw content snippet: '{raw.get('content', '')[:70]}...'. Skipping.")
                return None
        
        content_value = raw.get("content", "")
        if not content_value:
            print(f"  WARNING (_store_item): Item of type '{typ}' with ID '{original_id_value}' has empty content.")
        try:
            dto = FeedItemCreate(
                type=typ,
                source=raw.get("source", "unknown"),
                original_id=str(original_id_value),
                content=content_value,
                metadata=raw.get("metadata", {})
            )
        except ValueError as e:
            print(f"  ERROR (_store_item): Failed to create DTO for item type '{typ}', original_id '{original_id_value}'. Error: {e}. Skipping.")
            return None

        try:
            db_item = create_feed_item(self.db, self.user_id, dto)
            print(f"  SUCCESS (_store_item): Stored item type '{typ}', original_id '{dto.original_id}', new DB ID: {db_item.id}")
            return db_item
        except Exception as e:
            print(f"  ERROR (_store_item): Failed to save item type '{typ}', original_id '{dto.original_id}' to DB. Error: {e}. Skipping.")
            return None


    async def _summarize(self, feed_id: int, text: str):
        """Generates a summary for text and updates the corresponding feed item.

        Args:
            feed_id (int): The database ID of the feed item to update.
            text (str): The content to be summarized.
        """
        if not text.strip():
            print(f"  WARNING (_summarize): Text for feed_id {feed_id} is empty. Skipping summarization.")
            return

        prompt = (
            "Summarize the following financial news/tweet in 2 sentences:\n\n"
            + text
        )
        print(f"  LLM (_summarize): Requesting summary for feed_id {feed_id}.")
        summary = await llm_service.generate_response(prompt)
        
        try:
            update_feed_summary(self.db, feed_id, summary)
            print(f"  SUCCESS (_summarize): Summary updated for feed_id {feed_id}.")
        except Exception as e:
            print(f"  ERROR (_summarize): Failed to update summary for feed_id {feed_id}. Error: {e}")