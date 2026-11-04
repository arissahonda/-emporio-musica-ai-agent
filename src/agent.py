import re
import sqlite3
from database import init_db
from tools import search_store_policies
from llm import GroqClient  # Use GeminiClient or GroqClient based on your active provider

# =====================================================================
# SYSTEM PROMPT IN PORTUGUESE (STORE RULES, PERSONA & POLICIES)
# =====================================================================
SYSTEM_PROMPT = """
Você é o assistente virtual de atendimento ao cliente do "Empório da Música", uma loja especializada em instrumentos musicais localizada em Campo Grande, MS, Brasil.

---------------------------------------------------------------------
ESTRUTURA DO BANCO DE DADOS (RELACIONAMENTOS)
---------------------------------------------------------------------
- customers (customer_id, name, phone, email, city)
- products (product_id, name, category_id, price_brl, stock_quantity, status, specs)
- categories (category_id, name, description)
- orders (order_id, customer_id, order_date, status, total_brl, payment_method, tracking_code, estimated_delivery, notes)
- order_items (order_id, product_id, quantity) -> Relaciona pedidos aos produtos
- promotions (promotion_id, product_id, discount_percent, description, is_active) -> Relaciona promoções aos produtos (1=ativa, 0=expirada)

---------------------------------------------------------------------
1. TOM DE VOZ E PERSONALIDADE (SEÇÃO 7.1)
---------------------------------------------------------------------
- Tom: Informal mas profissional, acolhedor e simpático — como conversar com um amigo especialista que ama música.
- Estilo: Evite linguagem engessada, robótica ou excessivamente formal. Use um tom natural e solícito.

---------------------------------------------------------------------
2. ESCOPO E LIMITES DA LOJA (SEÇÃO 7.1)
---------------------------------------------------------------------
- Catálogo Exclusivo: O Empório da Música vende EXCLUSIVAMENTE instrumentos musicais (guitarras, baixos, violões, teclados, baterias, sopro, cordas orquestrais, ukuleles).
- Itens Fora de Escopo (Acessórios): NÃO vendemos acessórios (cordas, palhetas, cabos, pedais, amplificadores, capas, cases).
  * Ação: Explique educadamente que a loja vende apenas instrumentos. Ofereça a indicação de lojas parceiras locais em Campo Grande.
  * REGRA OBRIGATÓRIA DE FRASAGEM: Sempre diga "Temos lojas parceiras de confiança na região que vendem esses itens". NUNCA diga "Somos parceiros de confiança".

---------------------------------------------------------------------
3. FLUXO DE ATENDIMENTO PADRÃO (SEÇÃO 7.2)
---------------------------------------------------------------------
1. Saudação: Cumprimentar o cliente com simpatia e perguntar como pode ajudar.
2. Entendimento: Identificar a necessidade exata do cliente (busca de produto, dúvida de política, rastreamento, reclamação).
3. Consulta: Verificar as informações relevantes no contexto fornecido (SQL para estoque/pedidos ou RAG para políticas).
4. Resposta: Apresentar as opções de forma clara e objetiva. Ao listar produtos em estoque, mencione apenas se o produto está disponível (não precisa citar o número exato de unidades em estoque, a menos que haja poucas unidades).
5. Fechamento: Confirmar se o cliente precisa de mais alguma coisa e encerrar com cordialidade.

---------------------------------------------------------------------
4. SITUAÇÕES ESPECIAIS (SEÇÃO 7.3)
---------------------------------------------------------------------
- Produto fora de estoque: Informar que o produto está temporariamente indisponível e sugerir alternativas semelhantes que estejam disponíveis no estoque ativo. Nunca confirmar disponibilidade sem verificar o estoque atual.
- Produto descontinuado: Informar que o produto não faz mais parte do catálogo e oferecer modelos equivalentes ativos.
- Promoções: Apresentar os descontos vigentes e ressaltar que os descontos não são cumulativos com outras ofertas.
- Reclamações e Cancelamentos: Ouvir o cliente com empatia. Se houver informações de cancelamento no campo 'notes' do pedido, explique o motivo de forma transparente. Registre a insatisfação e informe que demandas formais de suporte possuem prazo de retorno de até 24 horas úteis.

---------------------------------------------------------------------
5. REGRAS GERAIS DE RESPOSTA
---------------------------------------------------------------------
- Responda SEMPRE em português do Brasil.
- Baseie todas as afirmações ESTRITAMENTE nos dados recuperados do contexto fornecido.
"""


def execute_sql(conn: sqlite3.Connection, query: str, params: tuple = ()) -> str:
    """Executes a SQL query and returns records formatted as a string for LLM context."""
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        if not rows:
            return "No matching records found in database."

        return str([dict(zip(columns, row)) for row in rows])
    except Exception as e:
        return f"Database execution error: {str(e)}"


class EmporioAgent:
    """Customer service AI agent orchestrator for Empório da Música."""

    def __init__(self, data_dir: str = "data"):
        self.db = init_db(data_dir)
        self.llm = GroqClient()

    def get_order_by_id(self, order_id: str) -> str:
        """Retrieves details for a specific order by order_id, including notes and customer info."""
        sql = """
            SELECT 
                o.order_id, 
                c.name AS customer_name,
                c.email AS customer_email,
                c.phone AS customer_phone,
                o.order_date, 
                o.status AS order_status, 
                o.total_brl,
                o.tracking_code,
                o.estimated_delivery,
                o.notes AS order_notes,
                p.name AS product_name,
                oi.quantity,
                p.price_brl
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN products p ON oi.product_id = p.product_id
            WHERE o.order_id = ?;
        """
        return execute_sql(self.db, sql, (order_id,))

    def get_order_details(self) -> str:
        """Retrieves a general list of recent orders."""
        sql = """
            SELECT o.order_id, o.order_date, o.status, o.total_brl, o.notes
            FROM orders o LIMIT 5;
        """
        return execute_sql(self.db, sql)

    def get_active_promotions(self) -> str:
        """Retrieves active promotions linked with product table."""
        sql = """
            SELECT 
                p.name AS product_name,
                p.price_brl AS original_price,
                pr.discount_percent,
                (p.price_brl * (1 - pr.discount_percent / 100.0)) AS promotional_price,
                pr.description AS promo_description
            FROM promotions pr
            JOIN products p ON pr.product_id = p.product_id
            WHERE pr.is_active = 1;
        """
        return execute_sql(self.db, sql)

    def get_context_for_query(self, user_message: str) -> str:
        """Classifies query intent and retrieves context from SQLite database or PDF RAG."""
        msg_lower = user_message.lower()

        # Extract order ID from user message (e.g., "pedido 20", "código 8", "pedido de número 2")
        order_match = re.search(r'\b(?:pedido|código|numero|número)\D*(\d+)\b', msg_lower)
        if order_match:
            order_id = order_match.group(1)
            raw_order_context = self.get_order_by_id(order_id)
            return f"REQUESTED ORDER {order_id} DETAILS:\n{raw_order_context}"

        # Store Policies & Store Information Queries (PDF RAG with top_k=3 to span page breaks)
        policy_keywords = [
            "troca", "devolução", "frete", "entrega", "pagamento", "pix",
            "cartão", "horário", "endereço", "garantia", "reclamação",
            "cidades", "outras cidades", "envio", "região", "sedex", "pac", "jadlog"
        ]
        if any(kw in msg_lower for kw in policy_keywords):
            raw_pdf = search_store_policies(user_message, top_k=3)
            return f"STORE POLICY PDF CONTEXT:\n{raw_pdf}"

        # Promotions (SQL JOIN + Policy Rules)
        if any(kw in msg_lower for kw in ["promoção", "promoções", "desconto", "oferta"]):
            raw_promo = self.get_active_promotions()
            promo_rules = search_store_policies("promoção desconto regras", top_k=1)
            return (
                f"ACTIVE PROMOTIONS CONTEXT:\n{raw_promo}\n\n"
                f"PROMOTION POLICY RULES:\n{promo_rules}"
            )

        # General Orders List
        if any(kw in msg_lower for kw in ["pedido", "rastreio", "status", "comprado"]):
            return f"RECENT ORDERS CONTEXT:\n{self.get_order_details()}"

        # Active Product Catalog / Inventory Queries
        if any(kw in msg_lower for kw in ["estoque", "disponível", "preço", "quanto custa", "valor", "guitarra", "violão", "teclado", "bateria", "ukulele"]):
            sql = (
                "SELECT p.name, p.price_brl, p.stock_quantity, c.name as category "
                "FROM products p JOIN categories c ON p.category_id = c.category_id "
                "WHERE p.status = 'active' LIMIT 40;"
            )
            return f"ACTIVE INVENTORY CONTEXT:\n{execute_sql(self.db, sql)}"

        return "No external context retrieval required."

    def answer_customer(self, user_message: str) -> str:
        """Retrieves system context, constructs prompt payload, and generates LLM response."""
        context_data = self.get_context_for_query(user_message)

        prompt_payload = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- RETRIEVED SYSTEM CONTEXT ---\n"
            f"{context_data}\n"
            f"--------------------------------\n\n"
            f"Customer Message: '{user_message}'\n\n"
            f"Assistant Response:"
        )

        return self.llm.generate_response(prompt_payload)


if __name__ == "__main__":
    import time

    agent = EmporioAgent()

    test_messages = [
        "Vocês vendem cordas e palhetas?",
        "Qual a política de devolução por arrependimento?",
        "Quais violões com corda de nylon estão disponíveis no estoque e quais os preços?",
        "Qual o horário de funcionamento da loja física?",
        "Quais itens estão na promoção?",
        "Gostaria de fazer uma reclamação, porque meu pedido de código 20 foi cancelado?",
        "Gostaria de saber sobre o meu pedido de número 2",
        "Vocês possuem o violão da Shelby com cordas de Nylon?",
        "Como funciona a entrega para outras cidades?",
    ]

    print("=" * 70)
    print("      EMPORIO DA MÚSICA - LIVE AGENT TEST")
    print("=" * 70)

    for msg in test_messages:
        print(f"\n[CUSTOMER]: {msg}")
        print("-" * 50)
        response = agent.answer_customer(msg)
        print(f"[ASSISTANT]:\n{response}")
        print("-" * 50)
        time.sleep(2)  # Short pause between batch requests to respect OTPM limits