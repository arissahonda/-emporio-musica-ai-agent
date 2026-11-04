import sqlite3
from database import init_db
from tools import search_store_policies

# =====================================================================
# 1. DETAILED SYSTEM PROMPT (PERSONA & STORE POLICY SECTION 7)
# =====================================================================
SYSTEM_PROMPT = """
You are the customer service AI assistant for "Empório da Música", a specialized musical instrument store located in Campo Grande, MS, Brazil.

---------------------------------------------------------------------
1. VOICE & PERSONALITY DIRECTIVES (SECTION 7.1)
---------------------------------------------------------------------
- Tone: Informal yet professional, warm, and welcoming—like chatting with a knowledgeable friend who loves music.
- Style: Avoid overly formal, rigid, or robotic phrasing. Use natural, friendly language.
- Operating Hours & Delays: Outside operating hours (Mon-Fri 09:00-18:00, Sat 09:00-13:00), inform the customer of when human staff or normal service will return.

---------------------------------------------------------------------
2. STORE SCOPE & BOUNDARIES (SECTION 7.1)
---------------------------------------------------------------------
- Exclusive Catalog: Empório da Música sells EXCLUSIVELY musical instruments (guitars, basses, drums, keyboards, woodwinds, brass, orchestral strings, ukuleles).
- Out-of-Scope Items (Accessories): We DO NOT sell accessories (strings, cables, picks, pedals, amplifiers, instrument cases, gig bags). 
  * Action: If a customer requests accessories, politely explain that we focus strictly on instruments and suggest checking local partner music stores in the region.

---------------------------------------------------------------------
3. FACTUAL ACCURACY & DATA MANDATE (SECTION 7.1)
---------------------------------------------------------------------
- System Dependency: NEVER guess, fabricate, or promise prices, stock availability, discounts, or delivery dates without checking system data or store policies.
- Incorrect information damages customer trust and constitutes misleading advertising.

---------------------------------------------------------------------
4. STANDARD SERVICE FLOW (SECTION 7.2)
---------------------------------------------------------------------
Follow this 5-step conversational flow:
1. Greeting: Greet the customer warmly by name (if provided) and ask how you can assist them today.
2. Understanding: Identify the customer's intent (product search, query, order tracking, policy doubt, or complaint).
3. Retrieval: Consult system tools (SQL database for inventory/orders, PDF search for store policies).
4. Response: Present clear, objective options with accurate prices, stock counts, or policy details.
5. Closing: Confirm if the customer needs further assistance and close cordially.

---------------------------------------------------------------------
5. SPECIAL OPERATIONAL SCENARIOS (SECTION 7.3)
---------------------------------------------------------------------
- Out-of-Stock Products: Inform the customer that the item is temporarily unavailable. Immediately suggest available similar alternatives from active stock. NEVER confirm availability without verification.
- Discontinued Products: State that the item is no longer in our catalog and offer equivalent or successor models available in stock.
- Expired Promotions: Verify promotion status in system context. If a promotion has expired, communicate this transparently, state the current table price, and NEVER promise outdated discounts.
- Complaints & Support: Listen with high empathy, register the complaint, and inform the customer that it has been escalated to management with a response window of 24 business hours.
- Out-of-Scope Inquiries: Politely decline questions unrelated to Empório da Música or musical instruments.
"""


def execute_sql(conn: sqlite3.Connection, query: str) -> str:
    """Executes a SQL read-only query and returns formatted string records for LLM context."""
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        if not rows:
            return "No matching records found in the database."

        return str([dict(zip(columns, row)) for row in rows])
    except Exception as e:
        return f"Database execution error: {str(e)}"


class EmporioAgent:

    def __init__(self, data_dir: str = "data"):
        """Initializes database connection and agent resources."""
        self.db = init_db(data_dir)

    def get_context_for_query(self, user_message: str) -> tuple[str, str]:
        """Analyzes query intent and retrieves raw system context (SQL or PDF RAG)

        required by the LLM.
        """
        msg_lower = user_message.lower()

        # Policy & Store Information Queries (PDF RAG)
        policy_keywords = [
            "troca",
            "devolução",
            "frete",
            "entrega",
            "pagamento",
            "pix",
            "cartão",
            "horário",
            "endereço",
            "garantia",
            "desconto",
            "reclamação",
            "queixa",
            "return",
            "shipping",
            "payment",
            "hours",
        ]
        if any(kw in msg_lower for kw in policy_keywords):
            raw_pdf_context = search_store_policies(user_message, top_k=2)
            return (
                "RAG_PDF",
                f"STORE POLICY PDF CONTEXT:\n{raw_pdf_context}",
            )

        # Inventory & Product Queries (SQLite Database)
        if any(kw in msg_lower
               for kw in ["estoque", "disponível", "preço", "quanto custa", "valor", "guitarra", "violão", "teclado", "bateria"]):
            sql = (
                "SELECT name, price_brl, stock_quantity, status FROM products "
                "WHERE status = 'active' LIMIT 5;"
            )
            raw_db_context = execute_sql(self.db, sql)
            return (
                "SQL_DB",
                f"SQL DATABASE INVENTORY CONTEXT:\n{raw_db_context}",
            )

        # Order Status Queries (SQLite Database)
        if any(kw in msg_lower
               for kw in ["pedido", "rastreio", "status", "order", "tracking"]):
            sql = (
                "SELECT order_id, status, tracking_code, estimated_delivery "
                "FROM orders LIMIT 1;"
            )
            raw_db_context = execute_sql(self.db, sql)
            return (
                "SQL_DB",
                f"SQL DATABASE ORDER CONTEXT:\n{raw_db_context}",
            )

        return "GENERAL", "No external context retrieval required."

    def process_message(self, user_message: str) -> str:
        """Constructs the complete payload (System Prompt + Retrieved System Context + User Query)

        ready for LLM API invocation.
        """
        context_type, context_data = self.get_context_for_query(user_message)

        prompt_payload = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- RETRIEVED SYSTEM CONTEXT ---\n"
            f"{context_data}\n"
            f"--------------------------------\n\n"
            f"Customer Message: '{user_message}'\n\n"
            f"Assistant Response:"
        )

        return prompt_payload


if __name__ == "__main__":
    agent = EmporioAgent()

    test_messages = [
        "Vocês vendem encordoamento e palhetas?",
        "Qual a política de devolução por arrependimento?",
        "Quais violões estão disponíveis no estoque?",
        "Quero fazer uma reclamação sobre o meu atendimento",
        "Como fazer um bolo de cenoura?",
    ]

    print("=" * 70)
    print("      DETAILED SYSTEM PROMPT & PAYLOAD TEST")
    print("=" * 70)

    for msg in test_messages:
        print(f"\n[CUSTOMER]: '{msg}'")
        print("-" * 50)
        payload = agent.process_message(msg)
        print(payload[:500] + "\n... [payload truncated for preview]")
        print("-" * 50)