from services.vector_db import load_vector_store

def check_metadata():
    print("Checking metadata in vector database...")
    
    db = load_vector_store()
    if db is None:
        print("No vector database found")
        return
    
    # Get a few sample documents to check metadata
    # Since we can't directly access all docs, let's check if we can search and examine
    try:
        docs = db.similarity_search("test", k=5)
        print(f"Found {len(docs)} documents")
        
        for i, doc in enumerate(docs):
            print(f"\nDocument {i+1}:")
            print(f"Content preview: {doc.page_content[:100]}...")
            print(f"Metadata: {doc.metadata}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_metadata()
