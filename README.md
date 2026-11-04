# Empório da Música - AI Customer Service Agent Prototype
**Artefact AI Engineer Technical Case**

Prototype of an intelligent customer service agent developed in Python for "Empório da Música", a musical instruments store located in Campo Grande/MS. The agent addresses customer inquiries regarding active product inventory, order tracking statuses, store policies, and operating hours while observing business boundaries.

---

## 1. Quick Start & Setup Instructions

### Prerequisites
- **Python**: Version `3.10` or higher (Developed and tested on `Python 3.14.8`)
- **Environment Manager**: `venv`
- **Groq API Key**: A free API key from [Groq Console](https://console.groq.com/).

### Installation Steps

1. **Clone the Repository:**
   ```bash
   git clone <REPOSITORY_URL>
   cd emporio-musica-ai-agent
    ```
2. **Create & active Virtual Environment:**
    - Windows:
    ```bash
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```
    - Linux/ macOS:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3. Install Dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Environment Variables Configuration: 
Create a .env file in the root directory (or copy from .env.example if available) and add your Groq API key:
    ```bash
    GROQ_API_KEY=your_groq_api_key_here
    GROQ_MODEL=qwen/qwen3.8-27b
    ```
5. Run the Interactive CLI Application:
   ```bash
    python main.py
    ```
To exit the chat session, type exit or sair.

## 2. Technical Decisions & Architectural Justifications

### Database Entity-Relationship Model

To establish a clear understanding of the business context and support the agent's data retrieval capabilities, the operational data was modeled into a relational schema:

![Database ER Diagram](docs/er_diagram.png)

Mapping the relationships between entities is the foundational step in consolidating the core business logic. By defining primary keys and table relationships, we can effectively trace customer journeys, query order statuses, check real-time stock, and anticipate complex customer inquiry scenarios.

## Architectural Decisions

### Framework & Architecture Approach

- **Vanilla Python / Custom Native Orchestration:** Instead of adopting heavy orchestration frameworks (such as LangChain or LlamaIndex), the agent was built using native Python logic. This keeps dependencies minimal, eliminates hidden abstraction layers, speeds up execution time, and provides full control over context assembly and prompt engineering.

- **Hybrid Retrieval Architecture (SQL + PDF RAG):**

    - **Structured Data Layer (`src/database.py`):**
        - **In-Memory SQLite Engine**: Operational CSV files (`categories`, `customers`, `orders`, `order_items`, `products`, `promotions`) are ingested into an in-memory SQLite database (`:memory:`) upon application startup. This provides zero-dependency, fast SQL querying for function-calling tools.
        - **Categorical ID Handling**: Identifier fields (`customer_id`, `order_id`, `product_id`, `category_id`, `promotion_id`) are explicitly treated as string dimensions rather than numeric metrics. This prevents unintended mathematical aggregations and ensures consistency across LLM function calls.
        - **Relational Integrity & Attribute Extraction**: Enforces multi-table SQL `JOIN` queries. Products extraction includes the `specs` column (storing JSON technical attributes such as color, key counts, and wood types) to fulfill detailed product inquiries.

    - **Unstructured Policy Layer / RAG (`src/tools.py`):**
        - **Continuous Document Ingestion & Cleaning**: Utilizes `pypdf` to extract raw text page-by-page from `data/politicas_da_loja.pdf`. Recurring header and footer noise (`Empório da Música Manual de Políticas...`, `Página X`) are automatically stripped using regular expressions, merging the entire manual into a clean, unified text stream.
        - **Sliding-Window Chunking with Overlap**: Replaced rigid page-based chunking with a continuous sliding window (`chunk_size=900`, `overlap=250`). This design eliminates cross-page boundaries, ensuring multi-page tables (such as Section 5.2 shipping tables spanning pages 4 and 5) are preserved within shared chunks.
        - **Stem-Based Relevance Retrieval**: Implements keyword tokenization with basic word stem matching (e.g., handling singular/plural query variations like `garantia` / `garantias`). Scores and retrieves top-matching relevant chunks for prompt synthesis.

### Model & Provider Selection (`src/llm.py`)

- **Groq API (qwen/qwen3.8-27b):** Selected for its high-speed inference, strong reasoning capabilities, and robust multi-turn instruction following.
- **Rate Limit & Server Fault Resiliency**:
  - **Output Token Budgeting (`max_tokens=700`)**: Explicitly capped output tokens to fit within Groq's Output Tokens Per Minute (OTPM 1,000) free-tier ceiling while preventing truncated response lists.
  - **Auto-Retry & Backoff (429 & 5xx)**: Integrated automatic exception handling for HTTP 429 (Rate Limit) and 5xx (Internal Server Error / Gateway Timeout) with exponential backoff (`time.sleep(3)`), ensuring uninterrupted session execution.

### Prompt Strategy & System Persona (`src/agent.py`)

- **Native Brazilian Portuguese Prompt**: Designed directly in Brazilian Portuguese to eliminate translation subtle nuances or tone degradation.
- **Grounded Persona & Scope Enforcement**: Incorporates Section 7 store policy guidelines directly into the agent's system prompt. Enforces a friendly, music-focused persona ("expert friend"), strict catalog boundaries (excluding accessories like strings/picks and redirecting to local partners using mandatory phrasing), compact product listing formats (1 line per product), and deterministic 24-business-hour SLA complaint protocols.

### Conversation Persistence & Multi-Turn Context (`src/agent.py`)

- **In-Memory Session History**: Maintains recent conversation turns within `EmporioAgent`. This allows context retention across interaction turns (e.g., retrieving an order when a customer provides their name in a follow-up message after asking about an order).
- **Flexible Order Lookup**: Supports both regex-based numeric Order ID extraction and fuzzy database matching on customer names, emails, and phone numbers. Since it doesn't have an specific order number, we use the order_id to simulate the scenarios where a client would request to know the status of their order only with the order number.

### Interactive Terminal Entry Point (`main.py`)

- **Real-Time CLI Shell**: Provides an interactive terminal interface (`main.py`) allowing real-time chat with `EmporioAgent`, handling user inputs, session termination (`exit` / `sair`), and graceful interrupt exceptions.

## 3. Known Limitations & Future Improvements

With additional development time, the following enhancements would be implemented:

1. Semantic Vector Search (Embeddings): Replace keyword-stem scoring in src/tools.py with dense vector embeddings (e.g., ChromaDB or FAISS) for higher semantic accuracy on abstract policy queries.

2. LLM Structured Output / Function Calling: Migrate manual intent routing regex and SQL string generation to native JSON Function Calling / Tool Calling schemas.

3. Persistent Chat History: Persist conversation history to SQLite or Redis to support long-running multi-session interactions across multiple users.

4. Enhanced Prompt Structuring: Further refine prompt formatting and XML/JSON tags to standardize response structures across complex edge-case combinations.

## 4. Code Assistant Usage & AI Workflow

In this project, Generative AI (Google Gemini) was utilized as an accelerator for rapid code prototyping and technical concept exploration, while my oversight drove business domain understanding, architectural design, and quality assurance.

I chose Gemini as my development assistant because it aligns with my established workflow. Having previously built a public-facing data dashboard ([Observatório do Transporte Coletivo](https://observatorio-otc-web.vercel.app/)), I'm accustomed to an iterative human-in-the-loop dynamic. Regardless of the specific AI tool, I apply a consistent development flow and prompt engineering patterns that have proven effective in past projects.

### Workflow & Collaboration Pattern:

 - **Business Domain & Logic Ownership (Self-Led)**: Analyzed the operational CSVs and relational ER schema, established business edge cases (such as handling out-of-scope accessory inquiries, cancellation note lookups, and multi-page shipping tables), and defined the agent's behavioral constraints.

- **Code Generation & Scaffolding (AI-Assisted)**: Used AI to draft initial boilerplate code, helper functions, and technical implementations (such as pypdf extraction, regex patterns, and SQLite connection wrappers).

- **Validation, Debugging & Refinement (Self-Led)**: Continuously executed and tested the codebase in VS Code terminal. Investigated edge-case failures (e.g., handling plural vs. singular SQL searches for drums, extracting JSON technical attributes from product specs, and handling API 429/500 rate limits), guiding iterative code corrections.

- **Conceptual Learning**: Coming from an Architecture and Urban Planning background, I leverage AI assistants to quickly bridge technical vocabulary gaps while building end-to-end solutions. However, I do not rely solely on AI generation, I actively conduct independent research. For instance, when integrating the LLM API and handling resilience limits, I consulted the official documentation directly to implement robust rate-limiting logic when the AI assistant alone was insufficient.

## 5. Examples of Agent Interactions

Detailed conversation logs for various scenario evaluations are stored in the docs/ directory:

- docs/chat1.txt: Product inquiry, technical specification lookup (Music Man bass), active promotion filtering, and shipping policy rules.

- docs/chat2.txt: Multi-level budget filtering (instruments under R$ 1,000 and general catalog items under R$ 600).

- docs/chat3.txt: Multi-turn order tracking lookup by customer name, transparent cancellation explanation (notes field lookup), and formal customer complaint logging with 24-hour SLA.

- docs/chat4.txt: Out-of-scope intent handling (food request, accessory redirection to partners, and math calculation refusal).
