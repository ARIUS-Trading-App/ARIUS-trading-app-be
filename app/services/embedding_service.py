from sentence_transformers import SentenceTransformer
from app.core.config import settings 
from typing import List, Union
import numpy as np

class EmbeddingService:
    def __init__(self):
        """Initializes the EmbeddingService.

        Loads the SentenceTransformer model specified in the settings and sets
        the embedding dimension. Handles potential errors during model loading.
        """
        self.model_name = settings.EMBEDDING_MODEL_NAME
        try:
            self.model = SentenceTransformer(self.model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            print(f"Embedding model '{self.model_name} loaded. Dimension: {self.dimension}")
        except Exception as e:
            print(f"Error loading SentenceTransformer model '{self.model_name}': {e}")
            self.model = None
            self.dimension = 0 
            
    def get_embedding_dimension(self) -> int:
        """Returns the dimension of the embeddings produced by the model.

        Returns:
            int: The embedding vector dimension.
        """
        return self.dimension
    
    def generate_embeddings(self, texts: Union[str, List[str]]) -> Union[np.ndarray, List[np.ndarray], None]:
        """Generates embeddings for a given text or list of texts.

        Args:
            texts (Union[str, List[str]]): A single string or a list of strings
                                           to be encoded.

        Returns:
            Union[np.ndarray, List[np.ndarray], None]: A numpy array or a list
                of numpy arrays representing the embeddings, or None if the
                model failed to load or an error occurred.
        """
        if not self.model:
            print("Embedding model not loaded.")
            return None
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            return None
        
embedding_service = EmbeddingService()