#use another llm for better semantic splitting. Check where to do embedding and upsert 

from typing import List # Added import

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    chunks = []
    start = 0
    if not text: # Handle empty text
        return []
    while start < len(text): # Added colon
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text): # Check if we've reached or passed the end
            break
        start += (chunk_size - chunk_overlap)
        if start >= len(text): # Ensure start doesn't go beyond text length due to overlap
            break
    return chunks