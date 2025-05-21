#use another llm for better semantic splitting. Check where to do embedding and upsert 

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    chunks = []
    start = 0
    while start < len(text)
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
        if end >= len(text):
            break
    return chunks