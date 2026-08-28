import os
import hashlib
from dotenv import load_dotenv
import psycopg2
import logging
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

# Sistema de logging para erros e informações importantes.
log_file = "debug_estoque.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'), # Salva em arquivo
        logging.StreamHandler() # Também mostra no terminal
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

class DatabaseManager:
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self):
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv("DB_HOST", "localhost"),
                dbname=os.getenv("DB_NAME", "Estoque_Mercado"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASS", "postgres"),
                port=int(os.getenv("DB_PORT", "5432"))
            )
            logger.info("Pool de conexões Singleton iniciado.")
        except Exception as e:
            logger.error(f"Falha crítica ao iniciar o Pool: {e}")
            raise e

    def get_connection(self):
        return self._pool.getconn()

    def put_connection(self, conn):
        self._pool.putconn(conn)

    def close_all(self):
        if self._pool:
            self._pool.closeall()
            logger.info("Todas as conexões do pool foram encerradas.")

# Instanciamos uma vez para todo o sistema usar
db_manager = DatabaseManager()

def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def listar_produtos_db():
    conn = db_manager.get_connection()
    if not conn: return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id_produto, codigo_barra, nome_produto, validade, qtd_estoque, preco, lote, prateleira, id_setor, id_adm
                    FROM produto ORDER BY validade NULLS LAST, nome_produto;
                """)
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar produtos: {e}")
        return []
    finally:
        if conn:
            db_manager.put_connection(conn)
def buscar_produto_por_codigo_db(codigo_barra):
    """
    Procura um produto pelo código de barras.

    O código de barras pode existir em vários registros,
    pois cada registro pode representar um lote diferente.

    Retorna:
        (True, produto) se encontrar
        (False, None) se não encontrar
    """
    conn = db_manager.get_connection()

    if not conn:
        return False, None

    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        codigo_barra,
                        nome_produto
                    FROM produto
                    WHERE codigo_barra = %s
                    ORDER BY id_produto
                    LIMIT 1;
                """, (codigo_barra,))

                produto = cur.fetchone()

                if produto:
                    return True, produto

                return False, None

    except Exception as e:
        logger.error(f"Erro ao buscar produto pelo código de barras: {e}")
        return False, None

    finally:
        if conn:
            db_manager.put_connection(conn)

def enviar_produto_area_venda_db(id_produto, quantidade):
    conn = db_manager.get_connection()

    if not conn:
        return False, "Sem conexão com o banco."

    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                # Busca o produto
                cur.execute("""
                    SELECT
                        id_produto,
                        codigo_barra,
                        nome_produto,
                        validade,
                        qtd_estoque,
                        lote
                    FROM produto
                    WHERE id_produto = %s
                    FOR UPDATE;
                """, (id_produto,))

                produto = cur.fetchone()

                if not produto:
                    return False, "Produto não encontrado."

                estoque_atual = produto["qtd_estoque"] or 0

                # Verifica estoque
                if quantidade <= 0:
                    return False, "A quantidade deve ser maior que zero."

                if quantidade > estoque_atual:
                    return False, (
                        f"Quantidade solicitada: {quantidade}\n"
                        f"Estoque disponível: {estoque_atual}"
                    )

                # Diminui o estoque
                novo_estoque = estoque_atual - quantidade

                cur.execute("""
                    UPDATE produto
                    SET qtd_estoque = %s
                    WHERE id_produto = %s;
                """, (novo_estoque, id_produto))

                # Verifica se já existe na área de venda
                cur.execute("""
                    SELECT id_area_venda, quantidade
                    FROM area_venda
                    WHERE id_produto = %s;
                """, (id_produto,))

                area = cur.fetchone()

                if area:

                    nova_quantidade = area["quantidade"] + quantidade

                    cur.execute("""
                        UPDATE area_venda
                        SET quantidade = %s,
                            data_entrada = CURRENT_TIMESTAMP
                        WHERE id_area_venda = %s;
                    """, (
                        nova_quantidade,
                        area["id_area_venda"]
                    ))

                else:

                    cur.execute("""
                        INSERT INTO area_venda (
                            id_produto,
                            codigo_barra,
                            nome_produto,
                            lote,
                            validade,
                            quantidade
                        )
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, (
                        produto["id_produto"],
                        produto["codigo_barra"],
                        produto["nome_produto"],
                        produto["lote"],
                        produto["validade"],
                        quantidade
                    ))

                return True, novo_estoque

    except Exception as e:
        logger.error(
            f"Erro ao enviar produto para área de venda: {e}"
        )
        return False, str(e)

    finally:
        if conn:
            db_manager.put_connection(conn)

def verificar_codigo_lote_existente_db(codigo_barra, lote):
    """
    Verifica se já existe um registro com a mesma combinação:

        código de barras + lote

    O mesmo código pode ter vários lotes.
    O mesmo lote pode existir para produtos diferentes.

    Retorna:
        True  -> combinação já existe
        False -> combinação ainda não existe
    """
    conn = db_manager.get_connection()

    if not conn:
        return False

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1
                    FROM produto
                    WHERE codigo_barra = %s
                      AND lote = %s
                    LIMIT 1;
                """, (codigo_barra, lote))

                return cur.fetchone() is not None

    except Exception as e:
        logger.error(f"Erro ao verificar código + lote: {e}")
        return False

    finally:
        if conn:
            db_manager.put_connection(conn)
def inserir_produto_db(prod):
    conn = db_manager.get_connection()

    if not conn:
        return False, "Sem conexão"

    try:
        with conn:
            with conn.cursor() as cur:

                codigo_barra = prod.get('codigo_barra')
                lote = prod.get('lote')

                # -------------------------------------------------
                # VERIFICAÇÃO DO CÓDIGO + LOTE
                # -------------------------------------------------
                if codigo_barra and lote:
                    cur.execute("""
                        SELECT 1
                        FROM produto
                        WHERE codigo_barra = %s
                          AND lote = %s
                        LIMIT 1;
                    """, (codigo_barra, lote))

                    existente = cur.fetchone()

                    if existente:
                        mensagem = (
                            f"O lote '{lote}' já está cadastrado "
                            f"para o código de barras '{codigo_barra}'."
                        )

                        logger.warning(mensagem)

                        return False, mensagem

                # -------------------------------------------------
                # VALIDADE
                # -------------------------------------------------
                validade = prod.get('validade')

                if not validade or str(validade).strip() == "":
                    validade = None

                # -------------------------------------------------
                # INSERÇÃO
                # -------------------------------------------------
                cur.execute("""
                    INSERT INTO produto
                    (
                        codigo_barra,
                        nome_produto,
                        validade,
                        qtd_estoque,
                        preco,
                        lote,
                        prateleira,
                        id_setor,
                        id_adm
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id_produto;
                """, (
                    codigo_barra,
                    prod.get('nome_produto'),
                    validade,
                    prod.get('qtd_estoque'),
                    prod.get('preco'),
                    lote,
                    prod.get('prateleira'),
                    prod.get('id_setor'),
                    prod.get('id_adm')
                ))

                res = cur.fetchone()[0]

                logger.info(
                    f"Produto inserido com sucesso: ID {res}, "
                    f"código {codigo_barra}, lote {lote}"
                )

                return True, res

    except Exception as e:
        logger.error(f"Erro ao inserir produto: {e}")
        return False, str(e)

    finally:
        if conn:
            db_manager.put_connection(conn)

def listar_area_venda_db():

    conn = db_manager.get_connection()

    if not conn:
        return []

    try:
        with conn:
            with conn.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                cur.execute("""
                    SELECT
                        id_area_venda,
                        id_produto,
                        codigo_barra,
                        nome_produto,
                        lote,
                        validade,
                        quantidade,
                        data_entrada
                    FROM area_venda
                    WHERE quantidade > 0
                    ORDER BY nome_produto;
                """)

                return cur.fetchall()

    except Exception as e:

        logger.error(
            f"Erro ao listar área de venda: {e}"
        )

        return []

    finally:

        if conn:
            db_manager.put_connection(conn)
def buscar_produto_por_codigo_lote_db(codigo_barra, lote):
    conn = db_manager.get_connection()

    if not conn:
        return False, "Sem conexão com o banco."

    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                cur.execute("""
                    SELECT
                        id_produto,
                        codigo_barra,
                        nome_produto,
                        validade,
                        qtd_estoque,
                        preco,
                        lote,
                        prateleira,
                        id_setor,
                        id_adm
                    FROM produto
                    WHERE codigo_barra = %s
                      AND lote = %s
                    LIMIT 1;
                """, (codigo_barra, lote))

                produto = cur.fetchone()

                if produto:
                    return True, produto

                return False, "Produto não encontrado para este código e lote."

    except Exception as e:
        logger.error(f"Erro ao buscar produto por código e lote: {e}")
        return False, str(e)

    finally:
        if conn:
            db_manager.put_connection(conn)
def remover_produto_db(id_produto):
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM produto WHERE id_produto = %s;", (id_produto,))
                logger.info(f"Produto removido com sucesso: ID {id_produto}")
                return True, cur.rowcount
    except Exception as e:
        logger.error(f"Erro ao remover produto: {e}")
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)

def verificar_validade_db(alerta_dias=30):
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=alerta_dias)
    conn = db_manager.get_connection()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id_produto, nome_produto, validade, qtd_estoque, id_setor, id_adm
                    FROM produto
                    WHERE validade <= %s
                    ORDER BY validade;
                """, (limite,))
                produtos = cur.fetchall()
                for p in produtos:
                    dias = (p['validade'] - hoje).days if p['validade'] else None
                    mensagem = f"O produto '{p['nome_produto']}' vence em {dias} dias." if dias is not None else f"O produto '{p['nome_produto']}' possui validade indefinida."
                    tipo = "AVISO DE VALIDADE"
                    cur.execute("""
                        INSERT INTO notificacao (id_produto, tipo_notificacao, mensagem, data_envio)
                        VALUES (%s, %s, %s, %s);
                    """, (p["id_produto"], tipo, mensagem, datetime.now()))
                logger.info(f"Verificação de validade concluída. {len(produtos)}")
                return produtos
    except Exception as e:
        logger.error(f"Erro no processamento de validade: {e}", exc_info=True)
        return []
    finally:
        if conn:
            db_manager.put_connection(conn)

def listar_notificacoes_db(limit=6):
    conn = db_manager.get_connection()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT n.id_notificacao, p.nome_produto, n.tipo_notificacao, n.mensagem, n.data_envio,
                           p.id_setor, p.id_adm
                    FROM notificacao n
                    LEFT JOIN produto p ON n.id_produto = p.id_produto
                    ORDER BY n.data_envio DESC
                    LIMIT %s;
                """, (limit,))
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar notificações: {e}")
        return []
    finally:
        if conn:
            db_manager.put_connection(conn)

# --- Admin / Setor / Colaborador ----------
def listar_administradores_db():
    conn = db_manager.get_connection()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_adm, nome, email FROM administrador_estoque ORDER BY nome;")
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar administradores: {e}")
        return []
    finally:
        if conn:
            db_manager.put_connection(conn)

def listar_setores_db():
    conn = db_manager.get_connection()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_setor, nome_setor FROM setor ORDER BY nome_setor;")
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar setores: {e}")
        return []
    finally:
        if conn:
            db_manager.put_connection(conn)

def listar_colaboradores_db():
    conn = db_manager.get_connection()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT c.id_colaborador, c.nome, c.email_celular, c.cargo, c.id_adm, c.id_setor,
                           a.nome as nome_adm, s.nome_setor
                    FROM colaborador c
                    LEFT JOIN administrador_estoque a ON c.id_adm = a.id_adm
                    LEFT JOIN setor s ON c.id_setor = s.id_setor
                    ORDER BY c.nome;
                """)
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar colaboradores: {e}")
        return []
    finally:
        if conn:
            db_manager.put_connection(conn)

def inserir_administrador_db(nome, email, senha=None):
    """
    Insere administrador; senha opcional (texto claro).
    Se senha for fornecida, armazena o HASH (SHA-256).
    Retorna (True, id_adm) ou (False, mensagem).
    """
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                hashed = _hash_password(senha) if senha is not None else None
                cur.execute("""
                    INSERT INTO administrador_estoque (nome, email, senha) VALUES (%s, %s, %s) RETURNING id_adm;
                """, (nome, email, hashed))
                return True, cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Erro ao inserir administrador: {e}")
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)

def inserir_setor_db(nome):
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO setor ("nome_setor") VALUES (%s) RETURNING id_setor;""", (nome,))
                return True, cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Erro ao inserir setor: {e}")
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)

def inserir_colaborador_db(nome, email_celular, cargo, id_adm=None, id_setor=None):
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO colaborador (nome, email_celular, cargo, id_adm, id_setor)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_colaborador;
                """, (nome, email_celular, cargo, id_adm, id_setor))
                return True, cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Erro ao inserir colaborador: {e}")
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)

def remover_administrador_db(id_adm):
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM administrador_estoque WHERE id_adm = %s;", (id_adm,))
                return True, cur.rowcount
    except Exception as e:
        logger.error(f"Erro ao remover administrador: {e}")
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)

def remover_colaborador_db(id_colaborador):
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM colaborador WHERE id_colaborador = %s;", (id_colaborador,))
                return True, cur.rowcount
    except Exception as e:
        logger.error(f"Erro ao remover colaborador: {e}")
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)

def verificar_credenciais(email: str, senha: str):
    """
    Verifica email + senha (texto claro informado pelo usuário).
    Suporta:
      - senha no banco como hash SHA-256 (64 hex chars): compara hash(senha_informada)
      - senha no banco em texto plano (ex.: '1234'): compara diretamente
    Retorna (True, admin_row) ou (False, mensagem).
    """
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_adm, nome, email, senha FROM administrador_estoque WHERE email = %s;", (email,))
                row = cur.fetchone()
                if not row:
                    return False, "Administrador não encontrado."
                
                stored = row.get("senha")
                if stored is None:
                    return False, "Administrador sem senha definida. Atualize a senha no banco."
                
                # Se tiver 64 caracteres e for hexadecimal, assumimos SHA-256
                if isinstance(stored, str) and len(stored) == 64:
                    is_valid = (_hash_password(senha) == stored.lower())
                else:
                    is_valid = (senha == stored)

                if is_valid:
                    logger.info(f"Login bem-sucedido: {email}")
                    return True, row
                else:
                    logger.warning(f"Tentativa de login inválida para: {email}")
                    return False, "Senha incorreta."
    except Exception as e:
        logger.error(f"Erro ao verificar credenciais: {e}")
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)

def obter_dados_tv_db(dias):
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=dias)
    conn = db_manager.get_connection()
    if not conn:
        return False, "Sem conexão com o banco."
    
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        p.id_produto, 
                        p.nome_produto, 
                        p.validade, 
                        p.qtd_estoque, 
                        p.lote, 
                        p.id_setor, 
                        s.nome_setor, 
                        a.nome as nome_adm,
                        (SELECT STRING_AGG(c.nome, ', ') 
                         FROM colaborador c 
                         WHERE c.id_setor = p.id_setor) as responsaveis
                    FROM produto p
                    LEFT JOIN setor s ON p.id_setor = s.id_setor
                    LEFT JOIN administrador_estoque a ON p.id_adm = a.id_adm
                    WHERE p.validade <= %s
                    ORDER BY p.validade ASC;
                """
                cur.execute(query, (limite,))
                rows = cur.fetchall()
                return True, rows
    except Exception as e:
        return False, str(e)
    finally:
        if conn:
            db_manager.put_connection(conn)