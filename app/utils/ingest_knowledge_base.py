import asyncio
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.vector_db_service import vector_db_service
from app.core.config import settings
from app.db.session import SessionLocal 
from app.utils.text_processing import chunk_text 


async def main():
    if not vector_db_service or not vector_db_service.index:
        print("VectorDBService not available or index not initialized. Exiting.")
        return

    knowledge_docs_path = "/Users/mihaibogdandeaconu/Documents/LLMTradingProject/vector_db_texts" 

    documents_to_ingest = []
    for filename in os.listdir(knowledge_docs_path):
        if filename.endswith((".txt", ".md")):
            filepath = os.path.join(knowledge_docs_path, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            doc_info = {
                "doc_id": os.path.splitext(filename)[0], 
                "text": content,
                "metadata": {
                    "source": filename,
                    "category": "finance_basics" 
                }
            }
            documents_to_ingest.append(doc_info)

    if documents_to_ingest:
        print(f"Found {len(documents_to_ingest)} documents to ingest.")

        await vector_db_service.upsert_text_documents(
            documents_to_ingest,
            chunk_size=700, 
            chunk_overlap=100
        )
        print("Ingestion process completed.")
    else:
        print("No documents found to ingest.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
   

    asyncio.run(main())