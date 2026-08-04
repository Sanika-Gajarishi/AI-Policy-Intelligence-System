import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

DB_PATH = "data/vector_store"

_embedding_model = None


def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        print("[vector_db] Loading embedding model...")

        _embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        print("[vector_db] Embedding model loaded.")

    return _embedding_model


def load_vector_store():
    faiss_file = os.path.join(DB_PATH, "index.faiss")
    pkl_file = os.path.join(DB_PATH, "index.pkl")

    if not os.path.exists(faiss_file):
        return None

    if not os.path.exists(pkl_file):
        return None

    try:
        db = FAISS.load_local(
            DB_PATH,
            get_embedding_model(),
            allow_dangerous_deserialization=True,
        )

        return db

    except Exception as e:
        print(f"[vector_db] Failed to load vector store: {e}")
        return None


def save_vector_store(docs):

    if not docs:
        print("[vector_db] No documents to save.")
        return None

    texts = [d["text"] for d in docs]

    metadatas = [
        {
            "state": d["state"],
            "year": d["year"],
            "month": d["month"],
            "power_type": d["power_type"],
            "source_file": d.get("source_file", "")
        }
        for d in docs
    ]

    db = load_vector_store()

    if db is None:

        print("[vector_db] Creating new vector store...")

        db = FAISS.from_texts(
            texts,
            get_embedding_model(),
            metadatas=metadatas,
        )

        db.save_local(DB_PATH)

        return db

    ############################################################
    # Remove duplicate chunks for this PDF
    ############################################################

    source_file = metadatas[0].get("source_file")

    try:

        docs_dict = db.docstore._dict

        ids_to_delete = []

        for doc_id, document in docs_dict.items():

            meta = getattr(document, "metadata", {})

            if meta.get("source_file") == source_file:
                ids_to_delete.append(doc_id)

        if ids_to_delete:

            print(
                f"[vector_db] Removing {len(ids_to_delete)} old chunks "
                f"for {source_file}"
            )

            db.delete(ids_to_delete)

    except Exception as e:

        print(f"[vector_db] Duplicate cleanup skipped: {e}")

    ############################################################
    # Add fresh chunks
    ############################################################

    db.add_texts(
        texts,
        metadatas=metadatas,
    )

    db.save_local(DB_PATH)

    print(
        f"[vector_db] Indexed {len(texts)} chunks "
        f"for {source_file}"
    )

    return db


def get_docs_by_source_file(db, filenames: set[str]):
    """
    Return every chunk (as LangChain Document objects) whose metadata.source_file
    matches one of the given filenames (already lowercased, no path).
    Returns [] if none match or the docstore can't be inspected.
    """
    if db is None or not filenames:
        return []

    try:
        docs_dict = db.docstore._dict
    except Exception as e:
        print(f"[vector_db] Could not access docstore for filtered lookup: {e}")
        return []

    matched = []
    for _doc_id, document in docs_dict.items():
        meta = getattr(document, "metadata", {}) or {}
        source_file = str(meta.get("source_file", "")).strip().lower()
        # also compare against just the basename in case one side has a path
        basename = source_file.split("/")[-1].split("\\")[-1]
        if source_file in filenames or basename in filenames:
            matched.append(document)

    return matched