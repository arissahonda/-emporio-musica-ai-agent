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

## Architectural Decisions: 

### Data Layer

- **In-Memory SQLite Engine**: Operational CSV files (`categories`, `customers`, `orders`, `order_items`, `products`, `promotions`) are ingested into an in-memory SQLite database (`:memory:`) upon application startup. This provides zero-dependency, fast SQL querying for function-calling tools.
- **Categorical ID Handling**: Identifier fields (`customer_id`, `order_id`, `product_id`, `category_id`, `promotion_id`) are explicitly treated as string dimensions rather than numeric metrics. This prevents unintended mathematical aggregations and ensures consistency across LLM function calls.
- **Relational Integrity**: While SQLite ingests raw CSV DataFrames, relational joins (`JOIN` queries on primary and foreign keys) are enforced directly within the Python analytical tools used by the agent to ensure accurate data extraction.

### Policy Retrieval Layer (PDF RAG)

* **Lightweight Document Ingestion**: Utilizes `pypdf` to extract and clean text page-by-page from `data/politicas_da_loja.pdf`. This eliminates the need for heavy external vector database servers, keeping runtime dependencies minimal and fast execution.

* **Stem-Based Relevance Retrieval**: Implements keyword tokenization with basic word stem matching (e.g., handling singular/plural query variations like `garantia` / `garantias`). The engine scores and returns the top $k$ relevant policy pages (`top_k=2`) to provide complete contextual coverage for edge cases spanning page breaks.

* **Separation of Concerns (Prompt vs. Retrieval)**: Static agent behavior, tone of voice, greeting structure, and store boundaries (Section 7 of store policies) are defined directly inside the Agent System Prompt for deterministic adherence. Dynamic fact-based rules (e.g., return windows, store address, payment rules, and warranty terms) are queried on demand via `search_store_policies()`.