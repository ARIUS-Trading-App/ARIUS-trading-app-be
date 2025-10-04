from typing import List

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """Splits a long text into smaller, overlapping chunks.

    This is a simple sliding window chunking strategy useful for preparing
    text for embedding models that have a maximum token limit.

    Args:
        text (str): The input text to be chunked.
        chunk_size (int): The maximum size of each chunk in characters.
        chunk_overlap (int): The number of characters to overlap between
                             consecutive chunks.

    Returns:
        List[str]: A list of text chunks.
    """
    chunks = []
    start = 0
    if not text:
        return []
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += (chunk_size - chunk_overlap)
        if start >= len(text):
            break
    return chunks