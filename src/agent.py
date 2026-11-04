import sqlite3
from database import init_db
from tools import search_store_policies

# =====================================================================
# 1. SYSTEM PROMPT WITH DATABASE SCHEMA KNOWLEDGE
# =====================================================================
SYSTEM_PROMPT = """
You are the customer service AI assistant for "Empório da Música", a specialized musical instrument store located in Campo Grande, MS, Brazil.

---------------------------------------------------------------------
DATABASE SCHEMA & RELATIONAL MAP
---------------------------------------------------------------------
- customers (customer_id, name, phone, email, city)
- products (product_id, name, category_id, price_brl, stock_quantity, status, specs)
- categories (category_id, name, description)
- orders (order_id, customer_id, order_date, status, total_brl, payment_method, tracking_code, estimated_delivery)
- order_items (order_id, product_id, quantity) -> Links orders to products (one order can contain multiple products)
- promotions (promotion_id, product_id, discount_percent, description, is_active) -> Links promotions to products (is_active: 1=active, 0=expired)

---------------------------------------------------------------------
1. VOICE & PERSONALITY DIRECTIVES (SECTION 7.1)
---------------------------------------------------------------------
- Tone: Informal yet professional, warm, and welcoming—like chatting with a knowledgeable friend who loves music.
- Style: Avoid overly formal, rigid, or robotic phrasing. Use natural, friendly language.

---------------------------------------------------------------------
2. STORE SCOPE & BOUNDARIES (SECTION 7.1)
---------------------------------------------------------------------
- Exclusive Catalog: Empório da Música sells EXCLUSIVELY musical instruments (guitars, basses, drums, keyboards, woodwinds, brass, orchestral strings, ukuleles).
- Out-of-Scope Items (Accessories): We DO NOT sell accessories (strings, cables, picks, pedals, amplifiers, instrument cases, gig bags). 
  * Action: Politely explain this restriction and suggest checking local partner music stores.

---------------------------------------------------------------------
3. SPECIAL OPERATIONAL SCENARIOS (SECTION 7.3)
---------------------------------------------------------------------
- Out-of-Stock Products: Inform the customer and immediately suggest available similar alternatives from active stock.
- Expired Promotions: Check promotion status. If expired (is_active = 0), communicate transparently and state current table price.
- Complaints: Listen with empathy, register the complaint, and state a return window of 24 business hours.
"""


def execute_sql(conn: sqlite3.Connection, query: str) -> str:
    """Executes a SQL query and returns records formatted for LLM context."""
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
        self.db = init_db(data_dir)

    def get_order_details(self, order_id: str = None) -> str:
        """Executes a SQL JOIN linking orders, order_items, and products."""
        sql = """
            SELECT 
                o.order_id, 
                o.order_date, 
                o.status AS order_status, 
                o.total_brl,
                o.tracking_code,
                o.estimated_delivery,
                p.name AS product_name,
                oi.quantity,
                p.price_brl
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN products p ON oi.product_id = p.product_id
            LIMIT 5;
        """
        return execute_sql(self.db, sql)

    def get_active_promotions(self) -> str:
        """Executes a SQL JOIN linking promotions and products."""
        sql = """
            SELECT 
                p.name AS product_name,
                p.price_brl AS original_price,
                pr.discount_percent,
                (p.price_brl * (1 - pr.discount_percent / 100.0)) AS promotional_price,
                pr.description AS promo_description,
                pr.is_active
            FROM promotions pr
            JOIN products p ON pr.product_id = p.product_id
            WHERE pr.is_active = 1;
        """
        return execute_sql(self.db, sql)

    def get_context_for_query(self, user_message: str) -> tuple[str, str]:
        """Routes query intent and fetches raw system context (SQL or PDF RAG)."""
        msg_lower = user_message.lower()

        # Policy & Store Info Queries (PDF RAG)
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
            "reclamação",
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

        # Promotion Queries (SQL JOIN promotions + products)
        if any(kw in msg_lower for kw in ["promoção", "desconto", "oferta"]):
            raw_promo_context = self.get_active_promotions()
            return (
                "SQL_PROMOTIONS",
                f"ACTIVE PROMOTIONS CONTEXT:\n{raw_promo_context}",
            )

        # Order Status Queries (SQL JOIN orders + order_items + products)
        if any(kw in msg_lower
               for kw in ["pedido", "rastreio", "status", "comprado", "order"]):
            raw_order_context = self.get_order_details()
            return (
                "SQL_ORDERS",
                f"ORDER DETAILS CONTEXT:\n{raw_order_context}",
            )

        # Inventory / Product Catalog Queries
        if any(kw in msg_lower
               for kw in ["estoque", "disponível", "preço", "quanto custa", "valor", "guitarra", "violão", "teclado", "bateria"]):
            sql = (
                "SELECT p.name, p.price_brl, p.stock_quantity, c.name as category "
                "FROM products p JOIN categories c ON p.category_id = c.category_id "
                "WHERE p.status = 'active' LIMIT 5;"
            )
            raw_db_context = execute_sql(self.db, sql)
            return (
                "SQL_INVENTORY",
                f"INVENTORY CONTEXT:\n{raw_db_context}",
            )

        return "GENERAL", "No external context retrieval required."

    def process_message(self, user_message: str) -> str:
        """Constructs complete payload ready for LLM API invocation."""
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
        "Quais promoções estão ativas na loja?",
        "Qual o status e os itens do meu pedido?",
    ]

    print("=" * 70)
    print("      RELATIONAL SCHEMA & ORCHESTRATOR TEST")
    print("=" * 70)

    for msg in test_messages:
        print(f"\n[CUSTOMER]: '{msg}'")
        print("-" * 50)
        payload = agent.process_message(msg)
        print(payload[:550] + "\n... [payload truncated for preview]")
        print("-" * 50)