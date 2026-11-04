import re
import sqlite3
from src.database import init_db
from src.tools import search_store_policies
from src.llm import GroqClient

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
  * A coluna 'specs' contém um JSON com características técnicas (ex: cor/color, quantidade de teclas/keys, polifonia, tipo de madeira, cordas). Utilize essas informações para descrever detalhes e cores dos produtos aos clientes.
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
- Catálogo Exclusivo: O Empório da Música vende EXCLUSIVAMENTE instrumentos musicais.
  * ATENÇÃO: Ao informar quais categorias/tipos de instrumentos a loja vende, consulte ESTRITAMENTE o contexto retornado do banco de dados.
- Itens Fora de Escopo (Acessórios): NÃO vendemos acessórios (cordas, palhetas, cabos, pedais, amplificadores, capas, cases).
  * Ação: Explique educadamente que a loja vende apenas instrumentos. Ofereça a indicação de lojas parceiras locais em Campo Grande.
  * REGRA OBRIGATÓRIA DE FRASAGEM: Sempre diga "Temos lojas parceiras de confiança na região que vendem esses itens". NUNCA diga "Somos parceiros de confiança".

---------------------------------------------------------------------
3. FLUXO DE ATENDIMENTO PADRÃO (SEÇÃO 7.2)
---------------------------------------------------------------------
1. Saudação: Cumprimentar o cliente com simpatia e perguntar como pode ajudar.
2. Entendimento: Identificar a necessidade exata do cliente.
3. Consulta: Verificar as informações relevantes no contexto fornecido.
4. Resposta: Apresentar as opções de forma clara e objetiva.
   * REGRA DE FORMATAÇÃO DE LISTAS: Ao listar múltiplos produtos, utilize 1 linha por item:
     - **Nome do Produto** – R$ XXX,XX (Cor: X)
   * REGRA DE DETALHAMENTO DE PRODUTOS:
     - Dúvidas gerais ("pode detalhar?", "me fale sobre ele"): Faça uma descrição fluida e natural em 2 parágrafos explicativos sobre a proposta do instrumento.
     - Dúvidas técnicas ("quais as especificações?", "ficha técnica"): Apresente os dados da coluna 'specs' formatados em tópicos (madeiras, escala, captação, cor).
5. Fechamento: Confirmar se o cliente precisa de mais alguma coisa e encerrar com cordialidade.

---------------------------------------------------------------------
4. SITUAÇÕES ESPECIAIS (SEÇÃO 7.3)
---------------------------------------------------------------------
- Produto fora de estoque ou não existente: Informar que o produto não está disponível no momento e sugerir alternativas semelhantes que estejam disponíveis no estoque ativo. Nunca confirmar disponibilidade sem verificar o estoque atual.
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
    """Customer service AI agent orchestrator for Empório da Música with conversation memory."""

    def __init__(self, data_dir: str = "data"):
        self.db = init_db(data_dir)
        self.llm = GroqClient()
        self.conversation_history = []

    def search_orders(self, query_text: str) -> str:
        """Searches customer orders by order_id, customer name, email, or phone number."""
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
            WHERE o.order_id = ? 
               OR LOWER(c.name) LIKE ? 
               OR LOWER(c.email) LIKE ? 
               OR c.phone LIKE ?;
        """
        search_pattern = f"%{query_text.lower().strip()}%"
        return execute_sql(self.db, sql, (query_text, search_pattern, search_pattern, search_pattern))

    def get_active_categories_and_products(self, search_term: str = None) -> str:
        """Retrieves active store categories and products from stock, including specs (JSON attributes)."""
        cat_sql = """
            SELECT DISTINCT c.name AS category_name
            FROM categories c
            JOIN products p ON c.category_id = p.category_id
            WHERE p.status = 'active';
        """
        categories_result = execute_sql(self.db, cat_sql)

        if search_term:
            # Basic plural normalization (e.g., baterias -> bateria, violões -> viol)
            clean_term = search_term.lower().strip()
            if clean_term.endswith('s') and len(clean_term) > 3:
                clean_term = clean_term[:-1]
            if "violõ" in clean_term or "violoe" in clean_term:
                clean_term = "viol"

            prod_sql = """
                SELECT p.name, p.price_brl, p.stock_quantity, c.name as category, p.specs
                FROM products p
                JOIN categories c ON p.category_id = c.category_id
                WHERE p.status = 'active'
                  AND (LOWER(p.name) LIKE ? OR LOWER(c.name) LIKE ? OR LOWER(p.specs) LIKE ?)
                LIMIT 30;
            """
            term_pattern = f"%{clean_term}%"
            products_result = execute_sql(self.db, prod_sql, (term_pattern, term_pattern, term_pattern))
        else:
            prod_sql = """
                SELECT p.name, p.price_brl, p.stock_quantity, c.name as category, p.specs
                FROM products p
                JOIN categories c ON p.category_id = c.category_id
                WHERE p.status = 'active'
                LIMIT 50;
            """
            products_result = execute_sql(self.db, prod_sql)

        return (
            f"CATEGORIES WITH ACTIVE PRODUCTS IN STOCK:\n{categories_result}\n\n"
            f"PRODUCTS IN STOCK (INCLUDING SPECS & COLORS):\n{products_result}"
        )

    def get_active_promotions(self) -> str:
        """Retrieves active promotions from database."""
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
        """Classifies intent using recent conversation history and fetches context from SQL or PDF RAG."""
        msg_lower = user_message.lower()
        combined_text = user_message
        
        if self.conversation_history:
            recent_user_msgs = [m["content"] for m in self.conversation_history if m["role"] == "user"]
            if recent_user_msgs:
                combined_text = f"{' '.join(recent_user_msgs[-2:])} {user_message}".lower()

        # 1. Order / Customer Inquiry
        order_keywords = ["pedido", "rastreio", "status", "comprado", "cancelado", "entrega", "onde esta", "informações"]
        has_order_intent = any(kw in combined_text for kw in order_keywords)
        
        if has_order_intent or (len(user_message.split()) >= 2 and not any(k in msg_lower for k in ["bateria", "guitarra", "violao", "teclado", "ukulele", "preco", "preço"])):
            order_match = re.search(r'\b(?:pedido|código|numero|número)\D*(\d+)\b', combined_text)
            search_key = order_match.group(1) if order_match else user_message.strip()
            
            raw_order_context = self.search_orders(search_key)
            if "No matching records found" not in raw_order_context:
                return f"ORDER / CUSTOMER DETAILS FOUND FOR '{search_key}':\n{raw_order_context}"

        # 2. Store Policy Queries (PDF RAG)
        policy_keywords = [
            "troca", "devolução", "frete", "entrega", "pagamento", "pix",
            "cartão", "horário", "endereço", "garantia", "reclamação",
            "cidades", "outras cidades", "envio", "região", "sedex", "pac", "jadlog"
        ]
        if any(kw in msg_lower for kw in policy_keywords) and not any(k in msg_lower for k in ["modelo", "cor", "korg", "roland", "yamaha"]):
            raw_pdf = search_store_policies(user_message, top_k=2)
            return f"STORE POLICY PDF CONTEXT:\n{raw_pdf}"

        # 3. Active Promotions
        if any(kw in msg_lower for kw in ["promoção", "promoções", "desconto", "oferta"]):
            raw_promo = self.get_active_promotions()
            promo_rules = search_store_policies("promoção desconto regras", top_k=1)
            return f"ACTIVE PROMOTIONS IN DATABASE:\n{raw_promo}\n\nPROMOTION POLICY RULES:\n{promo_rules}"

        # 4. Instrument-Specific Catalog Filters
        specific_instruments = [
            "bateria", "baterias", "guitarra", "guitarras", "violão", "violao", "violões", "violoes",
            "teclado", "teclados", "piano", "pianos", "ukulele", "ukuleles", "baixo", "baixos",
            "sopro", "sintetizador", "korg", "roland", "nord", "yamaha", "fender", "gibson", "shelby"
        ]
        found_instrument = next((inst for inst in specific_instruments if inst in msg_lower), None)
        if found_instrument:
            return self.get_active_categories_and_products(found_instrument)

        # 5. Generic Inventory Query
        if any(kw in msg_lower for kw in ["estoque", "disponível", "preço", "quanto custa", "valor", "instrumentos", "vendem", "opções"]):
            return self.get_active_categories_and_products(None)

        return "No external context retrieval required."

    def answer_customer(self, user_message: str) -> str:
        """Assembles prompt payload with history and generates response via LLM API."""
        context_data = self.get_context_for_query(user_message)

        history_str = ""
        if self.conversation_history:
            history_str = "\n--- RECENT CONVERSATION HISTORY ---\n"
            for turn in self.conversation_history[-4:]:
                history_str += f"{turn['role'].upper()}: {turn['content']}\n"

        prompt_payload = (
            f"{SYSTEM_PROMPT}\n\n"
            f"--- RETRIEVED SYSTEM CONTEXT ---\n"
            f"{context_data}\n"
            f"{history_str}"
            f"--------------------------------\n\n"
            f"CLIENTE: {user_message}\n\n"
            f"ASSISTENTE:"
        )

        response = self.llm.generate_response(prompt_payload)

        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": response})

        return response