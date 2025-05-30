# app/services/vector_db_service.py
import time
import traceback
from pinecone import Pinecone, Index, IndexList, ServerlessSpec, PodSpec
from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.utils.text_processing import chunk_text # Assuming this is your chunking function
from typing import List, Dict, Optional, Tuple, Union
import asyncio
import logging
import uuid # For generating unique chunk IDs

logger = logging.getLogger(__name__)

# Define a default batch size for upserting to Pinecone
PINECONE_UPSERT_BATCH_SIZE = 100 # Pinecone recommends batch sizes up to 100 for optimal performance

class VectorDBService:
    def __init__(self):
        if not settings.PINECONE_API_KEY: # PINECONE_ENVIRONMENT is now the region for serverless
            logger.error("PINECONE_API_KEY is not set. Pinecone service will not be available.")
            self.pinecone: Optional[Pinecone] = None
            self.index: Optional[Index] = None
            self.dimension: int = 0
            return

        # For serverless indexes, PINECONE_ENVIRONMENT should be a valid cloud region (e.g., "us-east-1")
        # For pod-based, it's the Pinecone environment name (e.g., "gcp-starter")
        # We'll assume serverless is preferred given current trends unless a specific pod environment is set.
        if not settings.PINECONE_ENVIRONMENT:
            logger.warning("PINECONE_ENVIRONMENT (expected to be a cloud region for serverless, e.g., 'us-east-1', or a pod environment) is not set. Index initialization might fail or use defaults.")
        
        logger.info(f"Initializing Pinecone with API Key: {'SET' if settings.PINECONE_API_KEY else 'NOT_SET'}")
        self.pinecone = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME
        self.index: Optional[Index] = None
        self.dimension = embedding_service.get_embedding_dimension()
        
        if self.dimension == 0 and embedding_service.model:
             logger.warning(f"Embedding service dimension is 0, but model is loaded. This might indicate an issue with embedding model init. Attempting to re-fetch dimension.")
             # Attempt to get dimension again if model seems loaded but dimension is 0
             # This is a fallback, ideally embedding_service initializes dimension correctly.
             dim_from_model = embedding_service.model.get_sentence_embedding_dimension()
             if dim_from_model:
                 self.dimension = dim_from_model
                 logger.info(f"Re-fetched embedding dimension: {self.dimension}")


        if not self.dimension:
            logger.error("Embedding dimension is 0. Cannot initialize Pinecone index correctly. Ensure embedding model loads and provides dimension.")
            self.pinecone = None # Prevent further operations
            return

        self._init_index_sync() # Changed to synchronous for simplicity during app startup
         
    def _init_index_sync(self):
        """
        Initializes the Pinecone index synchronously.
        Suitable for application startup.
        """
        if not self.pinecone:
            logger.error("Pinecone client not initialized. Cannot init index.")
            return

        try:
            logger.info(f"Attempting to initialize index: '{self.index_name}' with dimension {self.dimension}")
            
            index_list_response = self.pinecone.list_indexes()
            existing_indexes = []
            if index_list_response and hasattr(index_list_response, 'indexes') and index_list_response.indexes is not None:
                existing_indexes = [idx['name'] for idx in index_list_response.indexes]
            else:
                logger.info("No existing indexes found or list_indexes returned an unexpected structure.")
            
            if self.index_name not in existing_indexes:
                logger.info(f"Index '{self.index_name}' not found in {existing_indexes}. Creating new serverless index...")
                if not settings.PINECONE_ENVIRONMENT:
                    logger.error("Cannot create serverless index: PINECONE_ENVIRONMENT (region) is not set.")
                    return

                self.pinecone.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric='cosine', # Common choice for semantic similarity
                    spec=ServerlessSpec(
                        cloud='aws', # Assuming AWS, common default
                        region=settings.PINECONE_ENVIRONMENT, # e.g., "us-east-1"
                    )
                    # If you were to use pod-based (older style or specific needs):
                    # spec=PodSpec(
                    #     environment=settings.PINECONE_ENVIRONMENT, # e.g., "gcp-starter", "us-west1-gcp"
                    #     pod_type="p1.x1", # example pod type
                    #     pods=1
                    # )
                )
                
                # Wait for the index to be ready
                ready_wait_time = 0
                max_wait_time = 300 # 5 minutes
                sleep_interval = 10 # seconds
                while True:
                    index_description = self.pinecone.describe_index(self.index_name)
                    if index_description.status and index_description.status['ready']:
                        logger.info(f"Index '{self.index_name}' created successfully and is ready.")
                        break
                    logger.info(f"Waiting for index '{self.index_name}' to be ready... (elapsed: {ready_wait_time}s)")
                    time.sleep(sleep_interval)
                    ready_wait_time += sleep_interval
                    if ready_wait_time > max_wait_time:
                        logger.error(f"Index '{self.index_name}' did not become ready in {max_wait_time} seconds.")
                        # self.pinecone = None # Potentially disable service if index creation fails critically
                        return # Exit if index not ready
            else:
                logger.info(f"Index '{self.index_name}' found.")
                index_description = self.pinecone.describe_index(self.index_name)
                if index_description.dimension != self.dimension:
                    logger.error(f"Dimension mismatch for index '{self.index_name}'. Expected {self.dimension}, found {index_description.dimension}. Please resolve this manually (e.g., delete and recreate index with correct dimension, or update embedding model).")
                    self.pinecone = None # Critical mismatch
                    return


            self.index = self.pinecone.Index(self.index_name)
            logger.info(f"Successfully connected to Pinecone index '{self.index_name}'. Status: {self.pinecone.describe_index(self.index_name).status}")

        except Exception as e:
            logger.error(f"Error during Pinecone index initialization for '{self.index_name}': {e}", exc_info=True)
            # traceback.print_exc() # For local debugging
            self.index = None # Ensure index is None if init fails
    
    async def _upsert_batch_to_pinecone(self, vectors_to_upsert: List[Union[Dict, Tuple]]):
        """Helper to upsert a single batch asynchronously."""
        if not self.index:
            logger.warning("Pinecone index not initialized. Skipping upsert.")
            return None
        try:
            loop = asyncio.get_event_loop()
            # The Pinecone client's upsert is blocking, so run in executor
            response = await loop.run_in_executor(None, self.index.upsert, vectors_to_upsert)
            logger.debug(f"Successfully upserted batch of {len(vectors_to_upsert)} vectors. Response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error upserting batch to Pinecone: {e}", exc_info=True)
            return None

    async def upsert_documents(self, documents: List[Tuple[str, List[float], Dict]], batch_size: int = PINECONE_UPSERT_BATCH_SIZE):
        """
        Upserts documents (ID, vector, metadata tuples) to Pinecone in batches.
        This is a lower-level function if you already have embeddings.
        """
        if not self.index:
            logger.warning("Pinecone index not initialized. Skipping upsert_documents.")
            return []
        
        all_responses = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            logger.info(f"Upserting batch {i // batch_size + 1}/{(len(documents) + batch_size - 1) // batch_size} with {len(batch)} documents.")
            response = await self._upsert_batch_to_pinecone(batch)
            if response:
                all_responses.append(response)
        return all_responses

    async def upsert_text_documents(
        self, 
        text_document_infos: List[Dict[str, any]],
        chunk_size: int = 500, # Characters per chunk
        chunk_overlap: int = 50   # Characters of overlap
    ):
        """
        Processes and upserts text documents into Pinecone.
        Each document is chunked, embedded, and then upserted.

        Args:
            text_document_infos: A list of dictionaries, where each dictionary
                                 represents a document and should contain:
                                 - "doc_id": A unique string identifier for the document.
                                 - "text": The full string content of the document.
                                 - "metadata": A dictionary of metadata to associate with
                                               all chunks of this document (e.g., {"source": "filename.txt"}).
            chunk_size: Max size of text chunks.
            chunk_overlap: Overlap between text chunks.
        """
        if not self.index or not self.pinecone:
            logger.warning("Pinecone index or client not initialized. Skipping upsert_text_documents.")
            return []
        if not embedding_service.model:
            logger.error("Embedding model not loaded. Cannot generate embeddings for upsert.")
            return []

        all_vectors_to_upsert: List[Tuple[str, List[float], Dict]] = []

        for doc_info in text_document_infos:
            doc_id = doc_info.get("doc_id")
            text_content = doc_info.get("text")
            base_metadata = doc_info.get("metadata", {})

            if not doc_id or not text_content:
                logger.warning(f"Skipping document due to missing 'doc_id' or 'text': {doc_info}")
                continue

            logger.info(f"Processing document: {doc_id} for chunking and embedding.")
            text_chunks = chunk_text(text_content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            
            if not text_chunks:
                logger.warning(f"No chunks generated for document {doc_id}. Text length: {len(text_content)}")
                continue

            # Generate embeddings for all chunks of the current document in one go (if model supports batching)
            chunk_embeddings_np = embedding_service.generate_embeddings(text_chunks)
            
            if chunk_embeddings_np is None or len(chunk_embeddings_np) != len(text_chunks):
                logger.error(f"Failed to generate embeddings for chunks of document {doc_id}.")
                continue
            
            chunk_embeddings_list = chunk_embeddings_np.tolist()


            for i, chunk_text_content in enumerate(text_chunks):
                chunk_id = f"{doc_id}::chunk_{str(i).zfill(4)}" # Ensure unique ID for each chunk
                
                # Combine base metadata with chunk-specific metadata
                # Most importantly, store the actual text of the chunk for RAG
                chunk_metadata = {
                    **base_metadata, 
                    "text": chunk_text_content, # Storing the original chunk text is crucial for RAG
                    "doc_id": doc_id,
                    "chunk_num": i
                }
                
                embedding_vector = chunk_embeddings_list[i]
                all_vectors_to_upsert.append((chunk_id, embedding_vector, chunk_metadata))
        
        if not all_vectors_to_upsert:
            logger.info("No vectors prepared for upserting.")
            return []

        logger.info(f"Total of {len(all_vectors_to_upsert)} text chunks prepared for upserting.")
        return await self.upsert_documents(all_vectors_to_upsert)

    async def query_documents(
        self, 
        query_vector: List[float], 
        top_k: int = 5, 
        namespace: Optional[str] = None, 
        filter_dict: Optional[Dict] = None
    ) -> List[Dict]: 
        if not self.index:
            logger.warning("Pinecone index not initialized for query.")
            return []
        try:
            loop = asyncio.get_event_loop()
            # The Pinecone client's query is blocking, so run in executor
            query_response = await loop.run_in_executor(
                None, 
                lambda: self.index.query(
                    vector=query_vector,
                    top_k = top_k,
                    include_metadata=True, # Essential for RAG
                    namespace=namespace,
                    filter=filter_dict
                )
            )
            matches = query_response.get('matches', [])
            logger.debug(f"Query returned {len(matches)} matches. Top score: {matches[0].score if matches else 'N/A'}")
            return matches
        except Exception as e:
            logger.error(f"Error querying documents from Pinecone: {e}", exc_info=True)
            return []
        
    async def get_pinecone_context(self, query_text: str, top_k: int = 3, **kwargs) -> str: 
        """
        Generates an embedding for the query text, queries Pinecone,
        and returns a formatted string of the retrieved contexts.
        """
        if not self.index or not embedding_service.model:
            logger.warning("Pinecone index or embedding model not ready for get_pinecone_context.")
            return "Knowledge base is currently unavailable."

        query_embedding_array = embedding_service.generate_embeddings(query_text) 
        if query_embedding_array is None:
            logger.error("Could not generate query embedding for Pinecone context retrieval.")
            return "Error generating query embedding for knowledge base search."
        
        # Handle if generate_embeddings returns a single embedding directly or a list with one
        if len(query_embedding_array.shape) > 1 and query_embedding_array.shape[0] == 1:
            query_embedding_list = query_embedding_array[0].tolist()
        else: # Assuming it's already a 1D array
            query_embedding_list = query_embedding_array.tolist()
        
        matches = await self.query_documents(query_vector = query_embedding_list, top_k=top_k, **kwargs)
            
        context_parts = []
        if not matches:
            logger.info(f"No relevant documents found in knowledge base for query: '{query_text[:50]}...'")
            return "No relevant documents found in the knowledge base for this query."

        for i, match in enumerate(matches):
            metadata = match.get('metadata', {})
            text_chunk = metadata.get('text') # This 'text' field is critical
            if not text_chunk:
                logger.warning(f"Retrieved match {match.id} has no 'text' in metadata. Skipping.")
                continue

            source = metadata.get('source', 'N/A')
            doc_id_meta = metadata.get('doc_id', 'N/A') # If you stored it
            score = match.get('score', 0.0)
            
            # You might only want to include very relevant documents
            # if score < 0.7: # Example threshold, depends on your embeddings and data
            #     logger.debug(f"Skipping match {match.id} due to low score: {score:.4f}")
            #     continue

            context_parts.append(
                f"Retrieved Document {i+1} (ID: {match.id}, Source: {source}, DocID: {doc_id_meta}, Score: {score:.4f}):\n{text_chunk}"
            )
        
        if not context_parts:
            return "No sufficiently relevant documents found in the knowledge base after filtering."
            
        return "\n\n".join(context_parts).strip()

    async def delete_all_vectors_in_index(self, namespace: Optional[str] = None):
        """Deletes all vectors in the current index or a specific namespace."""
        if not self.index:
            logger.warning("Pinecone index not initialized. Cannot delete vectors.")
            return None
        try:
            loop = asyncio.get_event_loop()
            logger.warning(f"Attempting to delete ALL vectors from index '{self.index_name}'" + (f" in namespace '{namespace}'" if namespace else ""))
            response = await loop.run_in_executor(None, lambda: self.index.delete(delete_all=True, namespace=namespace))
            logger.info(f"Deletion response for index '{self.index_name}': {response}")
            return response
        except Exception as e:
            logger.error(f"Error deleting all vectors from Pinecone index '{self.index_name}': {e}", exc_info=True)
            return None

# Global instance
vector_db_service: Optional[VectorDBService] = None
try:
    vector_db_service = VectorDBService()
except Exception as e:
    logger.critical(f"Failed to initialize VectorDBService: {e}", exc_info=True)
    vector_db_service = None # Ensure it's None if critical failure