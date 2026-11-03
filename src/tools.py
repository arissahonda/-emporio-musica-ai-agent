import re
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader


def load_policy_document(pdf_path: str = "data/politicas_da_loja.pdf") -> List[Dict[str, Any]]:
    """
    Extracts text from the store policy PDF page by page.
    Returns a list of dictionaries containing page numbers and text content.
    """
    file_path = Path(pdf_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Policy PDF not found at: {file_path.resolve()}")

    reader = PdfReader(str(file_path))
    chunks = []

    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        # Clean up excessive whitespace
        cleaned_text = re.sub(r'\s+', ' ', text).strip()
        if cleaned_text:
            chunks.append({
                "page": idx + 1,
                "content": cleaned_text
            })

    return chunks


def search_store_policies(query: str, pdf_path: str = "data/politicas_da_loja.pdf", top_k: int = 2) -> str:
    """
    Searches store policies using keyword relevance scoring across PDF pages.
    Handles basic word stems (e.g., singular/plural) and returns top_k matching pages.
    """
    chunks = load_policy_document(pdf_path)
    
    # Extract query words longer than 2 chars and derive basic stems (removing last 's' for simple plurals)
    raw_words = re.findall(r'\w+', query.lower())
    query_stems = [w[:-1] if w.endswith('s') and len(w) > 3 else w for w in raw_words if len(w) > 2]
    
    if not query_stems:
        return "No relevant query terms provided."

    scored_chunks = []
    for chunk in chunks:
        content_lower = chunk["content"].lower()
        score = 0
        for stem in query_stems:
            # Match count based on stem substring presence
            score += content_lower.count(stem)
            
        if score > 0:
            scored_chunks.append((score, chunk))

    # Sort pages by relevance score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    if not scored_chunks:
        # Fallback if no keywords matched
        return "\n\n".join([f"[Store Policy Page {c['page']}]\n{c['content']}" for c in chunks[:2]])

    top_matches = [f"[Store Policy Page {c['page']}]\n{c['content']}" for _, c in scored_chunks[:top_k]]
    return "\n\n".join(top_matches)


if __name__ == "__main__":
    # Sanity check: test policy retrieval with a sample query
    test_queries = [
        "Qual a política de troca e devolução por arrependimento?",
        "Qual o endereço e horário de funcionamento da loja?",
        "Quais são as formas de pagamento aceitas?",
        "Qual o prazo de entrega para outras cidades?",
        "Quais garantias eu tenho?"
    ]

    print("=" * 70)
    print("           TESTE DE RECUPERAÇÃO DE POLÍTICAS (PDF RAG)")
    print("=" * 70)

    for query in test_queries:
        print(f"\nPERGUNTA DO CLIENTE: '{query}'")
        print("-" * 50)
        resultado = search_store_policies(query)
        print(resultado)
        print("-" * 50)
