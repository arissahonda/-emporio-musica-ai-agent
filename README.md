# emporio-musica-ai-agent
Customer service AI agent prototype for Empório da Música (Artefact AI Engineer Case)

## Database Entity-Relationship Model

To establish a clear understanding of the business context and support the agent's data retrieval capabilities, the operational data was modeled into a relational schema:

![Database ER Diagram](docs/er_diagram.png)

Mapping the relationships between entities is the foundational step in consolidating the core business logic. By defining primary keys and table relationships, we can effectively trace customer journeys, query order statuses, check real-time stock, and anticipate complex customer inquiry scenarios.

## Architectural Decisions: Data Layer

- **In-Memory SQLite Engine**: Operational CSV files (`categories`, `customers`, `orders`, `order_items`, `products`, `promotions`) are ingested into an in-memory SQLite database (`:memory:`) upon application startup. This provides zero-dependency, fast SQL querying for function-calling tools.
- **Categorical ID Handling**: Identifier fields (`customer_id`, `order_id`, `product_id`,'`category_id`,`promotion_id`) are explicitly treated as string dimensions rather than numeric metrics. This prevents unintended mathematical aggregations and ensures consistency across LLM function calls.
- **Relational Integrity**: While SQLite ingests raw CSV DataFrames, relational joins (`JOIN` queries on primary and foreign keys) are enforced directly within the Python analytical tools used by the agent to ensure accurate data extraction.