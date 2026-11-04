import re
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader


def load_and_clean_pdf(pdf_path: str = "data/politicas_da_loja.pdf") -> str:
    """Extracts text from PDF, removes headers/footers, and joins all pages into a continuous string."""
    file_path = Path(pdf_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Policy PDF not found at: {file_path.resolve()}")

    reader = PdfReader(str(file_path))
    full_text_pages = []

    for page in reader.pages:
        raw_text = page.extract_text() or ""
        # Clean repetitive headers and page footers
        cleaned = re.sub(r'Empório da Música\s+Manual de Políticas e Procedimentos', '', raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r'Página\s+\d+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        if cleaned:
            full_text_pages.append(cleaned)

    # Join full PDF text into a single continuous string without page boundaries
    return "\n\n".join(full_text_pages)


def create_chunks_with_overlap(text: str, chunk_size: int = 900, overlap: int = 250) -> List[Dict[str, Any]]:
    """Splits full document text into fixed-size chunks with sliding window overlap."""
    chunks = []
    start = 0
    text_length = len(text)
    chunk_id = 1

    while start < text_length:
        end = start + chunk_size
        chunk_text = text[start:end]

        chunks.append({
            "chunk_id": chunk_id,
            "content": chunk_text
        })

        # Advance window while maintaining overlap
        start += (chunk_size - overlap)
        chunk_id += 1

    return chunks


def search_store_policies(query: str, pdf_path: str = "data/politicas_da_loja.pdf", top_k: int = 2) -> str:
    """Searches store policy excerpts using keyword scoring over continuous text chunks."""
    full_text = load_and_clean_pdf(pdf_path)
    chunks = create_chunks_with_overlap(full_text, chunk_size=900, overlap=250)

    # Extract keyword stems from query
    raw_words = re.findall(r'\w+', query.lower())
    query_stems = [w[:-1] if w.endswith('s') and len(w) > 3 else w for w in raw_words if len(w) > 2]

    if not query_stems:
        return "No valid search terms provided."

    scored_chunks = []
    for chunk in chunks:
        content_lower = chunk["content"].lower()
        score = sum(content_lower.count(stem) for stem in query_stems)
        if score > 0:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    if not scored_chunks:
        return "\n\n".join([f"[Chunk {c['chunk_id']}]\n{c['content']}" for c in chunks[:top_k]])

    top_matches = [f"[Relevant Excerpt {c['chunk_id']}]\n{c['content']}" for _, c in scored_chunks[:top_k]]
    return "\n\n".join(top_matches)


if __name__ == "__main__":
    # Sanity check: test policy retrieval with sample customer queries
    test_queries = [
        "Qual a política de troca e devolução por arrependimento?",
        "Qual o endereço e horário de funcionamento da loja?",
        "Quais são as formas de pagamento aceitas?",
        "Qual o prazo de entrega para outras cidades?",
        "Quais garantias eu tenho?"
    ]

    print("=" * 70)
    print("           POLICY RETRIEVAL TEST (PDF RAG)")
    print("=" * 70)

    for query in test_queries:
        print(f"\nCUSTOMER QUERY: '{query}'")
        print("-" * 50)
        result = search_store_policies(query)
        print(result)
        print("-" * 50)