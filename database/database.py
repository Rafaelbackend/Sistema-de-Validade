import os
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

def conectar():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            dbname=os.getenv("DB_NAME", "Estoque_Mercado"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASS", "postgres"),
            port=int(os.getenv("DB_PORT", "5432"))
        )
        return conn
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def listar_produtos_db():
    conn = conectar()
    if not conn: return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id_produto, codigo_barra, nome_produto, validade, qtd_estoque, preco, lote, id_setor, id_adm
                    FROM produto ORDER BY validade NULLS LAST, nome_produto;
                """)
                return cur.fetchall()
    finally:
        conn.close()

def inserir_produto_db(prod):
    conn = conectar()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO produto
                    (codigo_barra, nome_produto, validade, qtd_estoque, preco, lote, id_setor, id_adm)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id_produto;
                """, (
                    prod.get('codigo_barra'),
                    prod.get('nome_produto'),
                    prod.get('validade'),
                    prod.get('qtd_estoque'),
                    prod.get('preco'),
                    prod.get('lote'),
                    prod.get('id_setor'),
                    prod.get('id_adm')
                ))
                return True, cur.fetchone()[0]
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def remover_produto_db(id_produto):
    conn = conectar()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM produto WHERE id_produto = %s;", (id_produto,))
                return True, cur.rowcount
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def verificar_validade_db(alerta_dias=30):
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=alerta_dias)
    conn = conectar()
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
                return produtos
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao verificar validade:\n{e}")
        return []
    finally:
        conn.close()

def listar_notificacoes_db(limit=100):
    conn = conectar()
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
        messagebox.showerror("Erro", f"Erro ao listar notificações:\n{e}")
        return []
    finally:
        conn.close()

# --- Admin / Setor / Colaborador ----------
def listar_administradores_db():
    conn = conectar()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_adm, nome, email FROM administrador_estoque ORDER BY nome;")
                return cur.fetchall()
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao listar administradores:\n{e}")
        return []
    finally:
        conn.close()

def listar_setores_db():
    conn = conectar()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_setor, nome_setor FROM setor ORDER BY nome_setor;")
                return cur.fetchall()
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao listar setores:\n{e}")
        return []
    finally:
        conn.close()

def listar_colaboradores_db():
    conn = conectar()
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
        messagebox.showerror("Erro", f"Erro ao listar colaboradores:\n{e}")
        return []
    finally:
        conn.close()

def inserir_administrador_db(nome, email, senha=None):
    """
    Insere administrador; senha opcional (texto claro).
    Se senha for fornecida, armazena o HASH (SHA-256).
    Retorna (True, id_adm) ou (False, mensagem).
    """
    conn = conectar()
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
        return False, str(e)
    finally:
        conn.close()

def inserir_setor_db(nome):
    conn = conectar()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO setor ("nome_setor") VALUES (%s) RETURNING id_setor;""", (nome,))
                return True, cur.fetchone()[0]
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def inserir_colaborador_db(nome, email_celular, cargo, id_adm=None, id_setor=None):
    conn = conectar()
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
    except psycopg2.Error as e:
        msg = str(e)
        suggestion = ""
        if 'column "id_setor"' in msg.lower():
            suggestion = ("\nSugestão: adicione a coluna id_setor na tabela colaborador com este comando SQL (execute no pgAdmin):\n\n"
                          "ALTER TABLE colaborador ADD COLUMN id_setor INTEGER;\n\n")
        return False, msg + suggestion
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def remover_administrador_db(id_adm):
    conn = conectar()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM administrador_estoque WHERE id_adm = %s;", (id_adm,))
                return True, cur.rowcount
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def remover_colaborador_db(id_colaborador):
    conn = conectar()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM colaborador WHERE id_colaborador = %s;", (id_colaborador,))
                return True, cur.rowcount
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def verificar_credenciais(email: str, senha: str):
    """
    Verifica email + senha (texto claro informado pelo usuário).
    Suporta:
      - senha no banco como hash SHA-256 (64 hex chars): compara hash(senha_informada)
      - senha no banco em texto plano (ex.: '1234'): compara diretamente
    Retorna (True, admin_row) ou (False, mensagem).
    """
    conn = conectar()
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
                if isinstance(stored, str) and len(stored) == 64 and all(c in "0123456789abcdefABCDEF" for c in stored):
                    if _hash_password(senha) == stored.lower():
                        return True, row
                    else:
                        return False, "Senha incorreta."
                else:
                    # comparação texto-plano (compatibilidade)
                    if senha == stored:
                        return True, row
                    else:
                        return False, "Senha incorreta."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def obter_dados_tv_db(dias):
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=dias)
    conn = conectar()
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
        conn.close()