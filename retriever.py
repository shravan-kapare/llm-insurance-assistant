from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
import pickle

model = SentenceTransformer('all-MiniLM-L6-v2')

def build_vector_index(chunks, save_path='index/faiss.index'):
    import os
    os.makedirs('index', exist_ok=True)  # ✅ Auto-create the folder if missing

    embeddings = model.encode(chunks)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(np.array(embeddings))

    with open('index/chunks.pkl', 'wb') as f:
        pickle.dump(chunks, f)

    faiss.write_index(index, save_path)


def search(query, top_k=5):
    query_vec = model.encode([query])
    index = faiss.read_index('index/faiss.index')
    D, I = index.search(np.array(query_vec), top_k)
    with open('index/chunks.pkl', 'rb') as f:
        chunks = pickle.load(f)
    return [(i, chunks[i]) for i in I[0]]
