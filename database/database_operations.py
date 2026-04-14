import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
# Importamos as configurações e a conexão dos arquivos que você já criou
from database_connection import conectar, _hash_password

# --- Operações de Produtos ---

def listar_produtos_db():
    conn = conectar()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id_produto, codigo_barra, nome_produto, validade, qtd_estoque, preco, lote, id_setor, id_adm
                    FROM produto
                    ORDER BY validade NULLS LAST, nome_produto;
                """)
                return cur.fetchall()
    finally:
        conn.close()

def inserir_produto_db(prod):
    conn = conectar()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO produto
                    (codigo_barra, nome_produto, validade, qtd_estoque, preco, lote, id_setor, id_adm)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id_produto;
                """, (
                    prod.get('codigo_barra'), prod.get('nome_produto'), prod.get('validade'),
                    prod.get('qtd_estoque'), prod.get('preco'), prod.get('lote'),
                    prod.get('id_setor'), prod.get('id_adm')
                ))
                return True, cur.fetchone()[0]
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def remover_produto_db(id_produto):
    conn = conectar()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM produto WHERE id_produto = %s;", (id_produto,))
                return True, cur.rowcount
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# --- Notificações e Validade ---

def verificar_validade_db(alerta_dias=30):
    hoje = datetime.now().date()
    limite = hoje + timedelta(days=alerta_dias)
    conn = conectar()
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
                    mensagem = f"O produto '{p['nome_produto']}' vence em {dias} dias." if dias is not None else "Validade indefinida."
                    cur.execute("""
                        INSERT INTO notificacao (id_produto, tipo_notificacao, mensagem, data_envio)
                        VALUES (%s, %s, %s, %s);
                    """, (p["id_produto"], "AVISO DE VALIDADE", mensagem, datetime.now()))
                return produtos
    finally:
        conn.close()

def listar_notificacoes_db(limit=100):
    conn = conectar()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT n.id_notificacao, p.nome_produto, n.tipo_notificacao, n.mensagem, n.data_envio,
                           p.id_setor, p.id_adm
                    FROM notificacao n
                    LEFT JOIN produto p ON n.id_produto = p.id_produto
                    ORDER BY n.data_envio DESC LIMIT %s;
                """, (limit,))
                return cur.fetchall()
    finally:
        conn.close()

# --- Admin / Setor / Colaborador ---

def listar_administradores_db():
    conn = conectar()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_adm, nome, email FROM administrador_estoque ORDER BY nome;")
                return cur.fetchall()
    finally:
        conn.close()

def listar_setores_db():
    conn = conectar()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_setor, nome_setor FROM setor ORDER BY nome_setor;")
                return cur.fetchall()
    finally:
        conn.close()

def listar_colaboradores_db():
    conn = conectar()
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
    finally:
        conn.close()

def inserir_administrador_db(nome, email, senha=None):
    conn = conectar()
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

def verificar_credenciais(email, senha_plana):
    conn = conectar()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_adm, nome, email, senha FROM administrador_estoque WHERE email = %s;", (email,))
                row = cur.fetchone()
                if not row: return False, "Administrador não encontrado."
                
                stored = row.get("senha")
                if stored is None: return False, "Senha não definida."

                # Verifica se é Hash ou Texto Plano
                if isinstance(stored, str) and len(stored) == 64:
                    match = (_hash_password(senha_plana) == stored.lower())
                else:
                    match = (senha_plana == stored)
                
                return (True, row) if match else (False, "Senha incorreta.")
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()