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
- **Relational Integrity & Attribute Extraction**: Enforces multi-table SQL `JOIN` queries. Products extraction includes the `specs` column (storing JSON technical attributes such as color, key counts, and wood types) to fulfill detailed product inquiries.

### Policy Retrieval Layer / RAG (`src/tools.py`)

- **Continuous Document Ingestion & Cleaning**: Utilizes `pypdf` to extract raw text page-by-page from `data/politicas_da_loja.pdf`. Recurring header and footer noise (`Empório da Música Manual de Políticas...`, `Página X`) are automatically stripped using regular expressions, merging the entire manual into a clean, unified text stream.
- **Sliding-Window Chunking with Overlap**: Replaced rigid page-based chunking with a continuous sliding window (`chunk_size=900`, `overlap=250`). This design eliminates cross-page boundaries, ensuring multi-page tables (such as Section 5.2 shipping tables spanning pages 4 and 5) are preserved within shared chunks.
- **Stem-Based Relevance Retrieval**: Implements keyword tokenization with basic word stem matching (e.g., handling singular/plural query variations like `garantia` / `garantias`). Scores and retrieves top-matching relevant chunks for prompt synthesis.

### LLM Provider Integration & Resiliency (`src/llm.py`)

- **Provider Transition (Gemini to Groq)**: Migrated LLM orchestration from Google Gemini API to Groq API using the high-performance `qwen/qwen3.8-27b` model, delivering fast execution times and reliable inference.
- **Rate Limit & Server Fault Resiliency**:
  - **Output Token Budgeting (`max_tokens=700`)**: Explicitly capped output tokens to fit within Groq's Output Tokens Per Minute (OTPM 1,000) free-tier ceiling while preventing truncated response lists.
  - **Auto-Retry & Backoff (429 & 5xx)**: Integrated automatic exception handling for HTTP 429 (Rate Limit) and 5xx (Internal Server Error / Gateway Timeout) with exponential backoff (`time.sleep(3)`), ensuring uninterrupted session execution.

### Agent Persona & Orchestration Layer (`src/agent.py`)

- **Portuguese Policy-Grounded System Prompt**: Incorporates Section 7 store policy guidelines directly into the agent's core prompt in Brazilian Portuguese. Enforces a warm persona, a structured customer service flow, strict catalog boundaries (excluding accessories with mandatory partner redirection wording), compact single-line list formatting rules, and deterministic protocols for complaints (24 business hours SLA).
- **Multi-Turn Session Memory**: Maintains conversational history across user interaction turns, allowing context persistence when customers specify order information (e.g., providing customer name or email after asking for order status).
- **Flexible Order Lookup**: Supports regex extraction for numeric order IDs as well as fuzzy string matching against customer names (`c.name LIKE ?`), emails, and phone numbers in the database.
- **Dynamic Intent Routing**: Classifies query intents and routes user inquiries to the corresponding context provider (SQLite queries for stock/orders vs. PDF RAG chunks for store rules).

### Interactive Terminal Entry Point (`main.py`)

- **Real-Time CLI Shell**: Provides an interactive terminal interface (`main.py`) allowing real-time chat with `EmporioAgent`, handling user inputs, session termination (`exit` / `sair`), and graceful interrupt exceptions.