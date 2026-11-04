# emporio-musica-ai-agent
Customer service AI agent prototype for Empório da Música (Artefact AI Engineer Case)

## Prerequisites & System Requirements

### Prerequisites
- **Python**: Version `3.10` or higher (Tested and developed using `Python 3.14.8`)
- **Environment Management**: `venv` (built-in Python virtual environment)
- **Package Manager**: `pip`

## Database Entity-Relationship Model

To establish a clear understanding of the business context and support the agent's data retrieval capabilities, the operational data was modeled into a relational schema:

![Database ER Diagram](docs/er_diagram.png)

Mapping the relationships between entities is the foundational step in consolidating the core business logic. By defining primary keys and table relationships, we can effectively trace customer journeys, query order statuses, check real-time stock, and anticipate complex customer inquiry scenarios.

## Architectural Decisions

### Data Layer (`src/database.py`)

- **In-Memory SQLite Engine**: Operational CSV files (`categories`, `customers`, `orders`, `order_items`, `products`, `promotions`) are ingested into an in-memory SQLite database (`:memory:`) upon application startup. This provides zero-dependency, fast SQL querying for function-calling tools.
- **Categorical ID Handling**: Identifier fields (`customer_id`, `order_id`, `product_id`, `category_id`, `promotion_id`) are explicitly treated as string dimensions rather than numeric metrics. This prevents unintended mathematical aggregations and ensures consistency across LLM function calls.
- **Relational Integrity**: While SQLite ingests raw CSV DataFrames, relational joins (`JOIN` queries on primary and foreign keys) are enforced directly within the Python analytical tools used by the agent to ensure accurate data extraction.

### Policy Retrieval Layer / RAG (`src/tools.py`)

- **Continuous Document Ingestion & Cleaning**: Utilizes `pypdf` to extract raw text page-by-page from `data/politicas_da_loja.pdf`. Recurring header and footer noise (`Empório da Música Manual de Políticas...`, `Página X`) are automatically stripped using regular expressions, merging the entire manual into a clean, unified text stream.
- **Sliding-Window Chunking with Overlap**: Replaced rigid page-based chunking with a continuous sliding window (`chunk_size=900`, `overlap=250`). This design eliminates cross-page boundaries, ensuring multi-page tables and contiguous sections are preserved within shared chunks.
- **Stem-Based Relevance Retrieval**: Implements keyword tokenization with basic word stem matching (e.g., handling singular/plural query variations like `garantia` / `garantias`). Scores and retrieves the top $k$ relevant chunks for prompt synthesis.

### LLM Provider Integration & Rate Limit Handling (`src/llm.py`)

- **Provider Transition (Gemini to Groq)**: Migrated LLM orchestration from Google Gemini API (`gemini-2.0-flash`) to Groq API using the high-performance `qwen/qwen3.8-27b` model, providing fast execution times and reliable inference.
- **Rate Limit & Resiliency Handling**:
  - **Output Token Budgeting (`max_tokens=600`)**: Capped response output tokens below Groq's free tier Output Tokens Per Minute (OTPM 1,000) ceiling, preventing quota rejection.
  - **Auto-Retry & Backoff**: Retained and adapted exception handling logic across provider migrations — handling 503 server unavailability during Gemini testing and 429 rate limits on Groq via automated retry loops (`time.sleep(3)`).
  - **Test Suite Pacing**: Added inter-request delay intervals (`time.sleep(2)`) in test runners to maintain execution within Per-Minute limits (RPM/TPM).

### Agent Persona & Orchestration Layer (`src/agent.py`)

- **Portuguese Policy-Grounded System Prompt**: Incorporates Section 7 store policy guidelines directly into the agent's core prompt in Brazilian Portuguese. Enforces a warm, music-focused persona, a structured 5-step customer service flow, strict catalog boundaries (excluding accessories with mandatory partner redirection wording), and deterministic protocols for out-of-stock items, expired promotions, and complaint handling (24 business hours SLA).
- **Regex Order ID Extraction & Schema Awareness**: Uses regex patterns to capture explicit order IDs (e.g., `pedido`, `número`) and queries the `orders` database table including `notes` fields to transparently report cancellation root causes.
- **Dynamic Intent Routing**: Implements query intent classification in `EmporioAgent` to route user inquiries to the appropriate context provider (SQLite queries for stock/orders vs. PDF RAG chunks for store rules).