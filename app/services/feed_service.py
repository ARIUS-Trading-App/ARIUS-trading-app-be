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
    def __init__(self, db: Session, user_id: int): # Changed Session to MockDBSession for example
        self.db = db
        self.user_id = user_id

    async def fetch_news(self, query: str, limit: int = 10):
        """
        Fetches news using web_search_service, stores them, and triggers summarization.
        """
        print(f"Fetching news for query: '{query}', limit: {limit}")
        # Use web_search_service to pull news headlines/text
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
            
            if item and item.id is not None: # Check if item was successfully created and has an ID
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
        """
        Placeholder for fetching tweets, storing them, and triggering summarization.
        """
        print(f"Fetching tweets for query: '{query}', limit: {limit} (Placeholder)")
        # Placeholder: integrate with Twitter API client
        # Example tweet data structure
        mock_tweets_data = [
            {"id": "tweet123", "text": "This is a sample tweet about " + query, "user": "twitter_user1"},
            {"id": "tweet456", "text": "Another interesting tweet regarding " + query, "user": "twitter_user2"}
        ]
        tweets = mock_tweets_data[:limit] # Simulate API call returning tweets

        stored_items_count = 0
        for t_idx, t_data in enumerate(tweets):
            print(f"Processing tweet {t_idx + 1}/{len(tweets)}")
            item_payload = {
                "original_id": str(t_data["id"]), # Ensure original_id is a string
                "content": t_data["text"],
                "source": "twitter.com", # Explicitly set source for tweets
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
    
    async def _store_item(self, typ: str, raw: dict) -> Optional[FeedItem]: # Return type is Optional[YourFeedItemModel]
        """
        Stores an item (news or tweet) in the database.
        Tries to find a suitable original_id, especially for news items.
        """
        # from app.schemas.feed import FeedItemCreate # Assuming this is correctly imported in your actual code
        
        original_id_value = raw.get("original_id")

        if original_id_value is None:
            if typ == "news":
                # For news items from web_search_service, 'url' is a strong candidate for a unique ID.
                # Fallback to 'id' if 'url' isn't present.
                # You should verify the actual key names provided by web_search_service.
                original_id_value = raw.get("url") 
                if original_id_value is None:
                    original_id_value = raw.get("id") # Try 'id' as another common key
                
                if original_id_value is None:
                    # If no suitable ID can be found for a news item, log and skip.
                    print(f"  ERROR (_store_item): Could not determine a unique ID (tried original_id, url, id) for news item. Raw content snippet: '{raw.get('content', '')[:70]}...'. Skipping.")
                    return None # Indicate failure to store
            else:
                # For other types (e.g., tweets), if 'original_id' is explicitly missing from `raw`
                # (though fetch_tweets constructs it), it's an issue.
                print(f"  ERROR (_store_item): 'original_id' is missing for item of type '{typ}'. Raw content snippet: '{raw.get('content', '')[:70]}...'. Skipping.")
                return None # Indicate failure to store
        
        # Ensure content is present, default to empty string if not.
        content_value = raw.get("content", "")
        if not content_value:
            # It might be valid for some items to have no content, but for summarization it's an issue.
            print(f"  WARNING (_store_item): Item of type '{typ}' with ID '{original_id_value}' has empty content.")
            # Depending on requirements, you might still store it or skip it.
            # For now, we'll proceed with empty content.

        try:
            dto = FeedItemCreate(
                type=typ,
                source=raw.get("source", "unknown"), # Default source if not provided
                original_id=str(original_id_value),  # Ensure original_id is a string
                content=content_value,
                metadata=raw.get("metadata", {})      # Default to empty dict for metadata
            )
        except ValueError as e: # Catch potential validation errors from FeedItemCreate
            print(f"  ERROR (_store_item): Failed to create DTO for item type '{typ}', original_id '{original_id_value}'. Error: {e}. Skipping.")
            return None

        # Assuming create_feed_item is a synchronous function as it's not awaited in the original.
        # If create_feed_item were async, it should be 'await create_feed_item(...)'
        try:
            # In a real scenario, ensure create_feed_item handles potential DB errors.
            db_item = create_feed_item(self.db, self.user_id, dto)
            print(f"  SUCCESS (_store_item): Stored item type '{typ}', original_id '{dto.original_id}', new DB ID: {db_item.id}")
            return db_item
        except Exception as e: # Catch any exception during DB operation
            print(f"  ERROR (_store_item): Failed to save item type '{typ}', original_id '{dto.original_id}' to DB. Error: {e}. Skipping.")
            return None


    async def _summarize(self, feed_id: int, text: str):
        """
        Generates a summary for the given text and updates the feed item.
        """
        if not text.strip(): # Check if text is empty or just whitespace
            print(f"  WARNING (_summarize): Text for feed_id {feed_id} is empty. Skipping summarization.")
            return

        prompt = (
            "Summarize the following financial news/tweet in 2 sentences:\n\n"
            + text
        )
        print(f"  LLM (_summarize): Requesting summary for feed_id {feed_id}.")
        summary = await llm_service.generate_response(prompt)
        
        # Assuming update_feed_summary is a synchronous function.
        # If it were async, it should be 'await update_feed_summary(...)'
        try:
            update_feed_summary(self.db, feed_id, summary)
            print(f"  SUCCESS (_summarize): Summary updated for feed_id {feed_id}.")
        except Exception as e:
            print(f"  ERROR (_summarize): Failed to update summary for feed_id {feed_id}. Error: {e}")
