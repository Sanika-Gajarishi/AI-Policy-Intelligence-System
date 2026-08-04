import os

from services.pdf_parser import extract_text_from_pdf
from services.chunker import chunk_text
from services.metadata import add_metadata
from services.vector_db import save_vector_store


def process_pdf(
    file_path,
    state,
    year,
    month,
    power_type,
    source_file=None
):
    try:
        text = extract_text_from_pdf(file_path)

        if not text or not text.strip():
            raise Exception("No text extracted from PDF")

        chunks = chunk_text(text)

        if not chunks:
            raise Exception("No chunks created")

        if source_file is None:
            source_file = os.path.basename(file_path)

        docs = add_metadata(
            chunks,
            state,
            year,
            month,
            power_type,
            source_file=source_file
        )

        db = save_vector_store(docs)

        if db is None:
            raise Exception("Indexing skipped")

        print(f"[RAG] Successfully indexed {source_file}")

        return db

    finally:
        # Delete only temporary downloaded PDFs.
        # Don't delete files that are stored in raw_pdfs.
        try:
            if (
                os.path.exists(file_path)
                and "raw_pdfs" not in file_path.replace("\\", "/")
            ):
                os.remove(file_path)
                print(f"[RAG] Deleted temporary file: {file_path}")
        except Exception as e:
            print(f"[RAG] Failed to remove temp file: {e}")