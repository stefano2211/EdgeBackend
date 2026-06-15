import os
import sys

def main():
    print("--- Pre-downloading embedding and reranker models ---")
    
    # Force cache directories to /app/models_cache for the build phase
    os.environ["HF_HOME"] = "/app/models_cache"
    os.environ["FASTEMBED_CACHE_PATH"] = "/app/models_cache"
    
    try:
        from sentence_transformers import SentenceTransformer
        print("Downloading sentence-transformers/all-MiniLM-L6-v2...")
        SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:
        print("Warning: failed to download SentenceTransformer:", e)
        
    try:
        from sentence_transformers import CrossEncoder
        print("Downloading BAAI/bge-reranker-v2-m3...")
        CrossEncoder("BAAI/bge-reranker-v2-m3")
    except Exception as e:
        print("Warning: failed to download CrossEncoder:", e)
        
    try:
        from fastembed import SparseTextEmbedding
        print("Downloading Qdrant/bm25...")
        SparseTextEmbedding("Qdrant/bm25")
    except Exception as e:
        print("Warning: failed to download SparseTextEmbedding:", e)
        
    print("--- Pre-downloading completed successfully ---")

if __name__ == '__main__':
    main()
