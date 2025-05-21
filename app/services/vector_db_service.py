import time
import traceback 
from pinecone import Pinecone, Index, IndexList , ServerlessSpec
from app.core.config import settings 
from app.services.embedding_service import embedding_service 
from typing import List, Dict, Optional, Tuple
import asyncio

class VectorDBService:
    def __init__(self):
        if not all([settings.PINECONE_API_KEY, settings.PINECONE_ENVIRONMENT]):
            raise ValueError("PINECONE_API_KEY or PINECONE_ENVIRONMENT not set.")
        
        print(f"Initializing Pinecone with API Key: {'SET' if settings.PINECONE_API_KEY else 'NOT_SET'}")
        self.pinecone = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME
        self.index: Optional[Index] = None
        self.dimension = embedding_service.get_embedding_dimension() 
                
        self._init_index()
         
    def _init_index(self): 
        try:
            print(f"Attempting to initialize index: '{self.index_name}'")
            
            indexes_list_response: Optional[IndexList] = self.pinecone.list_indexes()

            actual_index_names: List[str] = [] 

            if indexes_list_response: 
                if hasattr(indexes_list_response, 'names'):
                    retrieved_names = indexes_list_response.names
                    print(f"Value of indexes_list_response.names: {retrieved_names}")
                    if isinstance(retrieved_names, list):
                        actual_index_names = retrieved_names
                    elif callable(retrieved_names):
                        try:
                            actual_index_names = retrieved_names() 
                            if not isinstance(actual_index_names, list):
                                actual_index_names = [] 
                        except Exception as call_e:
                            print(f"Error calling .names(): {call_e}")
                            actual_index_names = [] 
                    else:
                        print(f"Warning: indexes_list_response.names is not a list or callable. Type: {type(retrieved_names)}")
                else:
                    print(f"Warning: IndexList response object does not have a 'names' attribute.")
            else:
                print("No indexes found or list_indexes() returned an empty/None response. Assuming no existing indexes.")


            if self.index_name not in actual_index_names:
                print(f"Index '{self.index_name}' not found in {actual_index_names}. Creating new index...")
                self.pinecone.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region=settings.PINECONE_ENVIRONMENT,
                    )
                )
                
                ready_wait_time = 0
                max_wait_time = 300
                sleep_interval = 5
                while True:
                    index_description = self.pinecone.describe_index(self.index_name)
                    if index_description.status['ready']:
                        break
                    print(f"Waiting for index '{self.index_name}' to be ready... (elapsed: {ready_wait_time}s)")
                    time.sleep(sleep_interval)
                    ready_wait_time += sleep_interval
                    if ready_wait_time > max_wait_time:
                        raise TimeoutError(f"Index '{self.index_name}' did not become ready in {max_wait_time} seconds.")
                print(f"Index '{self.index_name}' created successfully and is ready.")
            else:
                print(f"Index '{self.index_name}' found in {actual_index_names}.")
                
            self.index = self.pinecone.Index(self.index_name)
            print(f"Successfully connected to Pinecone index '{self.index_name}'.")

        except Exception as e:
            traceback.print_exc()
            self.index = None 
    
    async def upsert_documents(self, documents: List[Tuple[str, List[float], Dict]]):
        if not self.index:
            print("Pinecone index not initialized for upsert.")
            return None
        try:
            # Upsert is synchronous in the current pinecone-client
            # For async FastAPI, run in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.index.upsert(vectors=documents))
            return response
        except Exception as e:
            print(f"Error upserting documents to Pinecone: {e}")
            return None
        
    async def query_documents(self, query_vector: List[float], top_k: int = 5, namespace: Optional[str] = None, filter_dict: Optional[Dict] = None) -> List[Dict]: # Corrected filter_dict type
        if not self.index:
            print("Pinecone index not initialized for query.")
            return []
        try:
            # Query is synchronous
            loop = asyncio.get_event_loop()
            query_response = await loop.run_in_executor(
                None, 
                lambda: self.index.query(
                    vector=query_vector,
                    top_k = top_k,
                    include_metadata=True,
                    namespace=namespace,
                    filter=filter_dict
                )
            )
            return query_response.get('matches', [])
        except Exception as e:
            print(f"Error querying documents from Pinecone: {e}")
            return []
        
    async def get_pinecone_context(self, query_text: str, top_k: int = 3, **kwargs) -> str: # Changed top_k default
        query_embedding_array = embedding_service.generate_embeddings(query_text) # Returns numpy array
        if query_embedding_array is None:
            return "Could not generate query embedding for Pinecone."
        
        # If query_text was a single string, embedding_service returns a single embedding array
        # If it was a list, it returns a list of arrays. Assuming single query text here.
        query_embedding_list = query_embedding_array.tolist()
        
        matches = await self.query_documents(query_vector = query_embedding_list, top_k=top_k, **kwargs)
            
        context = ""
        if not matches:
            return "No relevant documents found in knowledge base."

        for i, match in enumerate(matches):
            metadata = match.get('metadata', {})
            text_chunk = metadata.get('text', 'No content available.')
            source = metadata.get('source', 'N/A')
            context += f"Retrieved Document {i+1} (Source: {source}, Score: {match.get('score', 0):.4f}):\n{text_chunk}\n\n"
        return context.strip()
    
vector_db_service = VectorDBService()