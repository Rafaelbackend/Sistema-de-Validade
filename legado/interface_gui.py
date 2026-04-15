# interface_gui.py
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
import sys
import hashlib

import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------
# Configuração de conexão DB
# ---------------------------
def _env_or_default(key: str, default: str):
    v = os.getenv(key)
    return v if v is not None else default

DB_PARAMS = {
    "host": _env_or_default("DB_HOST", "localhost"),
    "dbname": _env_or_default("DB_NAME", "Estoque_Mercado"),
    "user": _env_or_default("DB_USER", "postgres"),
    "password": _env_or_default("DB_PASS", "postgres"),
    "port": int(_env_or_default("DB_PORT", "5432")),
}

# ---------------------------
# Utilitários de senha
# ---------------------------
def _hash_password(pw: str) -> str:
    """Hash simples usando SHA-256 (hex)."""
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def conectar():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        try:
            messagebox.showerror("Erro de conexão", f"Não foi possível conectar ao banco:\n{e}")
        except Exception:
            print("Erro de conexão:", e)
        return None


def _ensure_password_column_and_seed():
    """
    Garante que a tabela administrador_estoque tenha coluna 'senha'.
    Garante também que exista o admin rafaelvbarbosa@gmail.com com senha '1234'
    (armazenada como hash) — se já existir sem senha, atualiza; se não existir, cria.
    """
    conn = conectar()
    if not conn:
        return
    try:
        with conn:
            with conn.cursor() as cur:
                # Verifica se coluna existe
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'administrador_estoque' AND column_name = 'senha';
                """)
                col = cur.fetchone()
                if not col:
                    cur.execute("ALTER TABLE administrador_estoque ADD COLUMN senha VARCHAR(128);")

                target_email = "rafaelvbarbosa@gmail.com"
                cur.execute("SELECT id_adm, senha FROM administrador_estoque WHERE email = %s;", (target_email,))
                row = cur.fetchone()
                hashed = _hash_password("1234")
                if row:
                    id_adm, senha = row
                    # se senha vazia ou NULL ou comprimento diferente de 64 (possivelmente em texto claro),
                    # escrevemos o hash para garantir login com '1234'
                    if not senha or (isinstance(senha, str) and len(senha) != 64):
                        cur.execute("UPDATE administrador_estoque SET senha = %s WHERE id_adm = %s;", (hashed, id_adm))
                else:
                    # cria administrador padrão com nome 'Administrador' para permitir login inicial
                    cur.execute("""
                        INSERT INTO administrador_estoque (nome, email, senha) VALUES (%s, %s, %s);
                    """, ("Administrador", target_email, hashed))
    except Exception as e:
        try:
            print("Aviso (seed senha):", e)
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

# chama no início para garantir coluna e senha do admin inicial
_try_ensure = _ensure_password_column_and_seed()

# ---------- Consultas / operações ----------
def listar_produtos_db():
    conn = conectar()
    if not conn:
        return []
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id_produto, codigo_barra, nome_produto, validade, qtd_estoque, preco, lote, id_setor, id_adm
                    FROM produto
                    ORDER BY validade NULLS LAST, nome_produto;
                """)
                return cur.fetchall()
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao listar produtos:\n{e}")
        return []
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

# ---------- Interface Tkinter ----------
class LoginWindow:
    def __init__(self, master):
        self.master = master
        self.result = False
        self.admin = None
        self.top = tk.Toplevel(master)
        self.top.title("Login - Controle de Validade")
        self.top.geometry("420x220")
        self.top.resizable(False, False)
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self._on_close)

        frm = ttk.Frame(self.top, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="E-mail do administrador:").grid(row=0, column=0, sticky="w", pady=6)
        self.email_ent = ttk.Entry(frm, width=45)
        self.email_ent.grid(row=1, column=0, pady=4)

        ttk.Label(frm, text="Senha:").grid(row=2, column=0, sticky="w", pady=6)
        self.senha_ent = ttk.Entry(frm, width=45, show="*")
        self.senha_ent.grid(row=3, column=0, pady=4)

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=4, column=0, pady=10, sticky="e")
        ttk.Button(btn_frame, text="Entrar", command=self._fazer_login).pack(side="right", padx=6)
        ttk.Button(btn_frame, text="Cancelar", command=self._on_close).pack(side="right")

        # Dica rápida
        ttk.Label(frm, text="(Informe suas credenciais cadastradas no banco)", font=("Arial", 9)).grid(row=5, column=0, sticky="w", pady=6)

        # foco no e-mail
        self.email_ent.focus_set()

    def _on_close(self):
        self.result = False
        try:
            self.top.destroy()
        except Exception:
            pass

    def _fazer_login(self):
        email = self.email_ent.get().strip()
        senha = self.senha_ent.get().strip()
        if not email or not senha:
            messagebox.showwarning("Atenção", "Informe e-mail e senha.")
            return
        ok, resp = verificar_credenciais(email, senha)
        if ok:
            self.result = True
            self.admin = resp
            messagebox.showinfo("Bem-vindo", f"Olá, {resp.get('nome')}! Acesso permitido.")
            try:
                self.top.destroy()
            except Exception:
                pass
        else:
            messagebox.showerror("Erro de autenticação", resp)

class TVDisplay:
    def __init__(self, master, refresh_seconds=60, alerta_dias=30, speed='medium'):
        # refresh_seconds controls how often the content is reloaded from DB
        # scrolling operates independently and loops gracefully
        self.win = tk.Toplevel(master)
        self.win.title("Painel TV - Notificações")
        self.win.attributes("-fullscreen", True)
        self.win.config(bg="black")
        self.refresh_seconds = refresh_seconds
        self.alerta_dias = alerta_dias

        # speed presets: low (lento), medium, fast
        if speed == 'low':
            self.scroll_step = 0.0010
            self.scroll_delay_ms = 130
            self.end_pause_ms = 5000
        elif speed == 'fast':
            self.scroll_step = 0.006
            self.scroll_delay_ms = 60
            self.end_pause_ms = 1200
        else:  # medium (default)
            self.scroll_step = 0.0035
            self.scroll_delay_ms = 90
            self.end_pause_ms = 2500

        self.frame = tk.Frame(self.win, bg="black")
        self.frame.pack(fill="both", expand=True)

        self.header = tk.Label(self.frame, text="NOTIFICAÇÕES DE VALIDADE", font=("Arial", 44, "bold"), bg="black", fg="white")
        self.header.pack(pady=20)

        # Text widget usado para rolagem automática
        self.txt = tk.Text(self.frame, bg="black", fg="white", font=("Arial", 28), bd=0, highlightthickness=0, wrap="word")
        self.txt.pack(fill="both", expand=True, padx=40, pady=10)

        self.footer = tk.Label(self.frame, text="Pressione ESC para sair do modo TV", font=("Arial", 18), bg="black", fg="white")
        self.footer.pack(pady=10)

        self.win.bind("<Escape>", lambda e: self.close())

        # Scrolling control
        self.scroll_pos = 0.0
        self._scroll_job = None
        self._refresh_job = None
        self.running = True

        # Inicializa conteúdo e inicia timers
        self.update_once()
        self._refresh_job = self.win.after(self.refresh_seconds * 1000, self._periodic_refresh)
        # start scrolling after a short delay to let content render
        self.win.after(600, self._start_scrolling)

    def _periodic_refresh(self):
        if not self.running:
            return
        self.update_once()
        self._refresh_job = self.win.after(self.refresh_seconds * 1000, self._periodic_refresh)

    def update_once(self):
        hoje = datetime.now().date()
        limite = hoje + timedelta(days=self.alerta_dias)
        conn = conectar()
        lines = []
        if conn:
            try:
                with conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT p.id_produto, p.nome_produto, p.validade, p.qtd_estoque,
                                   p.lote, p.id_setor, s.nome_setor, p.id_adm, a.nome as nome_adm
                            FROM produto p
                            LEFT JOIN setor s ON p.id_setor = s.id_setor
                            LEFT JOIN administrador_estoque a ON p.id_adm = a.id_adm
                            WHERE p.validade <= %s
                            ORDER BY p.validade;
                        """, (limite,))
                        rows = cur.fetchall()
                        if not rows:
                            lines.append("Nenhum produto próximo do vencimento.")
                        else:
                            for r in rows:
                                validade = r.get('validade')
                                validade_str = validade.strftime("%d/%m/%Y") if validade else "—"
                                dias = (validade - hoje).days if validade else "?"
                                setor = r.get('nome_setor') or "—"
                                colaboradores = []
                                if r.get('id_setor'):
                                    cur.execute("""
                                        SELECT nome FROM colaborador WHERE id_setor = %s ORDER BY nome;
                                    """, (r['id_setor'],))
                                    cols = cur.fetchall()
                                    colaboradores = [c['nome'] for c in cols] if cols else []
                                if colaboradores:
                                    responsaveis_text = ", ".join(colaboradores)
                                else:
                                    responsaveis_text = r.get('nome_adm') or "—"

                                lines.append(f"Produto: {r['nome_produto']}  |  Validade: {validade_str}  ({dias} dias)")
                                lines.append(f"Qtd: {r['qtd_estoque']}  |  Lote: {r.get('lote') or '—'}  |  Setor: {setor}  |  Responsável(s): {responsaveis_text}")
                                lines.append("-" * 120)
            except Exception as e:
                lines = [f"Erro ao carregar notificações: {e}"]
            finally:
                conn.close()
        else:
            lines = ["Sem conexão com o banco."]

        # Atualiza conteúdo do Text widget e reinicia posição de rolagem
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        # junta linhas com espaçamento para leitura confortável
        content = "\n\n".join(lines)
        # adiciona um espaçamento extra para dar pausa visual antes de recomeçar a rolagem
        content += "\n\n\n\n"
        self.txt.insert("end", content)
        self.txt.config(state="disabled")

        # reset scroll
        self.scroll_pos = 0.0
        try:
            self.txt.yview_moveto(0.0)
        except Exception:
            pass

    def _start_scrolling(self):
        # cancela job anterior e inicia novo
        if self._scroll_job:
            try:
                self.win.after_cancel(self._scroll_job)
            except Exception:
                pass
        self._scroll_step_internal()

    def _scroll_step_internal(self):
        if not self.running:
            return
        try:
            first, last = self.txt.yview()
        except Exception:
            first, last = 0.0, 1.0

        # se já estiver no fim (last >= 0.999), faz uma pausa e reinicia do topo
        if last >= 0.999:
            # pequena pausa antes de recomeçar
            self.scroll_pos = 0.0
            try:
                self.txt.yview_moveto(0.0)
            except Exception:
                pass
            # aguarda um tempo maior antes de recomeçar para dar chance de leitura final
            self._scroll_job = self.win.after(self.end_pause_ms, self._scroll_step_internal)
            return

        # avança um pouco usando moveto por fração
        self.scroll_pos = min(1.0, self.scroll_pos + self.scroll_step)
        try:
            self.txt.yview_moveto(self.scroll_pos)
        except Exception:
            pass

        self._scroll_job = self.win.after(self.scroll_delay_ms, self._scroll_step_internal)

    def close(self):
        self.running = False
        try:
            if self._scroll_job:
                self.win.after_cancel(self._scroll_job)
        except Exception:
            pass
        try:
            if self._refresh_job:
                self.win.after_cancel(self._refresh_job)
        except Exception:
            pass
        self.win.destroy()

class App:
    def __init__(self, root, current_admin=None):
        self.root = root
        root.title("Controle de Validade - Interface Local")
        root.geometry("1200x700")
        self.current_admin = current_admin

        # topo: botões de ação
        top = ttk.Frame(root, padding=8)
        top.pack(side="top", fill="x")

        ttk.Button(top, text="Listar produtos", command=self.mostrar_lista).pack(side="left", padx=4)
        ttk.Button(top, text="Adicionar produto", command=self.abrir_form_adicionar).pack(side="left", padx=4)
        ttk.Button(top, text="Verificar validade (30d)", command=self.acao_verificar_validade).pack(side="left", padx=4)
        ttk.Button(top, text="Listar notificações", command=self.mostrar_notificacoes).pack(side="left", padx=4)

        # botões para cadastros
        ttk.Button(top, text="Cadastrar Admin", command=self.abrir_form_admin).pack(side="left", padx=8)
        ttk.Button(top, text="Cadastrar Setor", command=self.abrir_form_setor).pack(side="left", padx=4)
        ttk.Button(top, text="Cadastrar Colaborador", command=self.abrir_form_colab).pack(side="left", padx=4)

        # botões para visualizar admin/colabs e TV
        ttk.Button(top, text="Ver Administradores", command=self.mostrar_administradores).pack(side="left", padx=8)
        ttk.Button(top, text="Ver Colaboradores", command=self.mostrar_colaboradores).pack(side="left", padx=4)
        ttk.Button(top, text="Abrir modo TV (fullscreen)", command=self.abrir_tv_display).pack(side="right", padx=4)

        ttk.Button(top, text="Atualizar", command=self.atualizar_tudo).pack(side="right", padx=4)

        # frame central com treeview
        middle = ttk.Frame(root, padding=8)
        middle.pack(fill="both", expand=True)

        cols = ("id", "codigo", "nome", "validade", "qtd", "preco", "lote", "setor", "responsavel")
        self.tree = ttk.Treeview(middle, columns=cols, show="headings")
        headers = ["ID", "Código", "Nome", "Validade", "Qtd", "Preço", "Lote", "Setor", "Responsável"]
        for c, title in zip(cols, headers):
            self.tree.heading(c, text=title)
            if c == "nome":
                self.tree.column(c, width=350)
            elif c == "responsavel":
                self.tree.column(c, width=180)
            elif c == "validade":
                self.tree.column(c, width=110, anchor="center")
            else:
                self.tree.column(c, width=90, anchor="center")

        # tags: 'perigo' (próx. a vencer) e 'vencido'
        self.tree.tag_configure('perigo', background='#ffcccc')   # vermelho claro
        self.tree.tag_configure('vencido', background='#ff9999')  # vermelho mais forte

        vsb = ttk.Scrollbar(middle, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, side="left")

        # bottom
        bottom = ttk.Frame(root, padding=8)
        bottom.pack(side="bottom", fill="x")
        ttk.Button(bottom, text="Remover selecionado", command=self.remover_selecionado).pack(side="right", padx=4)
        self.status = ttk.Label(bottom, text="Pronto")
        self.status.pack(side="left")

        # mostra admin logado no status (se houver)
        if self.current_admin:
            nome = self.current_admin.get("nome") if isinstance(self.current_admin, dict) else "-"
            self.atualizar_status(f"Logado como: {nome}")

        # carrega lista inicial
        self.mostrar_lista()
        self.tv_display = None

    def atualizar_tudo(self):
        self.mostrar_lista()

    def atualizar_status(self, texto):
        self.status.config(text=texto)

    # ---------- produtos ----------
    def mostrar_lista(self):
        self.atualizar_status("Carregando lista...")
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = listar_produtos_db()
        for r in rows:
            validade = r['validade']
            validade_str = validade.strftime("%d/%m/%Y") if validade else "-"
            preco = f"R$ {float(r['preco']):.2f}" if r.get('preco') is not None else "-"
            setor = "-"
            responsavel = "-"
            try:
                conn = conectar()
                if conn:
                    with conn:
                        with conn.cursor(cursor_factory=RealDictCursor) as cur:
                            if r.get('id_setor'):
                                cur.execute("SELECT nome_setor FROM setor WHERE id_setor = %s", (r['id_setor'],))
                                s = cur.fetchone()
                                setor = s['nome_setor'] if s else "-"
                            if r.get('id_setor'):
                                cur.execute("SELECT nome FROM colaborador WHERE id_setor = %s ORDER BY nome", (r['id_setor'],))
                                cols = cur.fetchall()
                                if cols:
                                    responsavel = ", ".join([c['nome'] for c in cols])
                                else:
                                    if r.get('id_adm'):
                                        cur.execute("SELECT nome FROM administrador_estoque WHERE id_adm = %s", (r['id_adm'],))
                                        a = cur.fetchone()
                                        responsavel = a['nome'] if a else "-"
                            else:
                                if r.get('id_adm'):
                                    cur.execute("SELECT nome FROM administrador_estoque WHERE id_adm = %s", (r['id_adm'],))
                                    a = cur.fetchone()
                                    responsavel = a['nome'] if a else "-"
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            tag = ''
            if validade:
                dias = (validade - datetime.now().date()).days
                if dias < 0:
                    tag = 'vencido'
                elif dias <= 7:
                    tag = 'perigo'

            self.tree.insert("", "end",
                             values=(r['id_produto'], r.get('codigo_barra'), r.get('nome_produto'),
                                     validade_str, r.get('qtd_estoque'), preco, r.get('lote'), setor, responsavel),
                             tags=(tag,) if tag else ())
        self.atualizar_status(f"{len(rows)} produtos carregados")

    # ---------- adicionar ----------
    def abrir_form_adicionar(self):
        win = tk.Toplevel(self.root)
        win.title("Adicionar produto")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        labels = ["Código de barras", "Nome do produto", "Validade (DD-MM-AAAA)", "Quantidade", "Preço", "Lote", "ID do Setor (opcional)", "ID do Admin (opcional)"]
        entries = {}
        for i, lbl in enumerate(labels):
            ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w", pady=4)
            ent = ttk.Entry(frm, width=40)
            ent.grid(row=i, column=1, pady=4, padx=6)
            entries[i] = ent

        def _parse_date_input(text):
            """Aceita DD-MM-AAAA ou DD/MM/AAAA. Retorna date ou lança ValueError."""
            text = text.strip()
            if not text:
                return None
            for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
                try:
                    return datetime.strptime(text, fmt).date()
                except Exception:
                    continue
            raise ValueError("Formato de data inválido. Use DD-MM-AAAA ou DD/MM/AAAA.")

        def salvar():
            codigo = entries[0].get().strip()
            nome = entries[1].get().strip()
            validade_text = entries[2].get().strip()
            qtd_text = entries[3].get().strip()
            preco_text = entries[4].get().strip()
            lote = entries[5].get().strip() or None
            id_setor = entries[6].get().strip() or None
            id_adm = entries[7].get().strip() or None

            if not codigo or not nome:
                messagebox.showwarning("Atenção", "Código e Nome são obrigatórios.")
                return
            validade = None
            if validade_text:
                try:
                    validade = _parse_date_input(validade_text)
                except ValueError as ve:
                    messagebox.showwarning("Atenção", str(ve))
                    return
            try:
                qtd = int(qtd_text) if qtd_text else 0
            except ValueError:
                messagebox.showwarning("Atenção", "Quantidade deve ser número inteiro.")
                return
            try:
                preco = float(preco_text.replace(",", ".")) if preco_text else None
            except ValueError:
                messagebox.showwarning("Atenção", "Preço inválido.")
                return

            id_setor_val = int(id_setor) if id_setor and id_setor.isdigit() else None
            id_adm_val = int(id_adm) if id_adm and id_adm.isdigit() else None

            prod = {
                'codigo_barra': codigo,
                'nome_produto': nome,
                'validade': validade,
                'qtd_estoque': qtd,
                'preco': preco,
                'lote': lote,
                'id_setor': id_setor_val,
                'id_adm': id_adm_val
            }
            ok, resp = inserir_produto_db(prod)
            if ok:
                messagebox.showinfo("Sucesso", f"Produto criado. ID: {resp}")
                win.destroy()
                self.mostrar_lista()
            else:
                messagebox.showerror("Erro", f"Não foi possível inserir: {resp}")

        ttk.Button(frm, text="Salvar", command=salvar).grid(row=len(labels), column=1, sticky="e", pady=8)

    def acao_verificar_validade(self):
        produtos = verificar_validade_db(30)
        if not produtos:
            messagebox.showinfo("Validade", "Nenhum produto próximo do vencimento (30 dias).")
            return
        win = tk.Toplevel(self.root)
        win.title("Produtos próximos do vencimento")
        txt = tk.Text(win, width=100, height=20)
        txt.pack(fill="both", expand=True)
        hoje = datetime.now().date()
        for p in produtos:
            validade = p.get('validade')
            validade_str = validade.strftime("%d/%m/%Y") if validade else "?"
            dias = (validade - hoje).days if validade else "?"
            txt.insert("end", f"ID {p['id_produto']} - {p['nome_produto']} - Vence em {dias} dias ({validade_str})\n")
        ttk.Button(win, text="Fechar", command=win.destroy).pack(pady=6)
        self.mostrar_lista()

    def mostrar_notificacoes(self):
        rows = listar_notificacoes_db()
        if not rows:
            messagebox.showinfo("Notificações", "Nenhuma notificação registrada.")
            return
        win = tk.Toplevel(self.root)
        win.title("Notificações")
        txt = tk.Text(win, width=120, height=25)
        txt.pack(fill="both", expand=True)
        for n in rows:
            data_envio = n.get('data_envio')
            data_str = data_envio.strftime("%d/%m/%Y %H:%M:%S") if data_envio else "-"
            txt.insert("end", f"[{data_str}] ID {n['id_notificacao']} - {n['nome_produto']} - {n['tipo_notificacao']}\n{n['mensagem']}\n\n")
        ttk.Button(win, text="Fechar", command=win.destroy).pack(pady=6)

    # ---------- Admin / Setor / Colaborador ----------
    def abrir_form_admin(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Administrador")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Nome:").grid(row=0, column=0, sticky="w")
        nome = ttk.Entry(frm, width=40); nome.grid(row=0, column=1, pady=4)
        ttk.Label(frm, text="E-mail:").grid(row=1, column=0, sticky="w")
        email = ttk.Entry(frm, width=40); email.grid(row=1, column=1, pady=4)
        ttk.Label(frm, text="Senha (opcional - será armazenada como hash):").grid(row=2, column=0, sticky="w")
        senha = ttk.Entry(frm, width=40, show="*"); senha.grid(row=2, column=1, pady=4)

        def salvar_admin():
            n = nome.get().strip(); e = email.get().strip(); s = senha.get().strip()
            if not n or not e:
                messagebox.showwarning("Atenção", "Nome e E-mail são obrigatórios"); return
            ok, resp = inserir_administrador_db(n, e, senha=s if s else None)
            if ok:
                messagebox.showinfo("Sucesso", f"Administrador criado. ID {resp}"); win.destroy()
            else:
                messagebox.showerror("Erro", resp)
        ttk.Button(frm, text="Salvar", command=salvar_admin).grid(row=3, column=1, sticky="e", pady=8)

    def abrir_form_setor(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Setor")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Nome do setor:").grid(row=0, column=0, sticky="w")
        nome = ttk.Entry(frm, width=40); nome.grid(row=0, column=1, pady=4)
        def salvar_setor():
            n = nome.get().strip()
            if not n:
                messagebox.showwarning("Atenção", "Nome obrigatório"); return
            ok, resp = inserir_setor_db(n)
            if ok:
                messagebox.showinfo("Sucesso", f"Setor criado. ID {resp}"); win.destroy()
            else:
                messagebox.showerror("Erro", resp)
        ttk.Button(frm, text="Salvar", command=salvar_setor).grid(row=2, column=1, sticky="e", pady=8)

    def abrir_form_colab(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Colaborador")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Nome:").grid(row=0, column=0, sticky="w")
        nome = ttk.Entry(frm, width=40); nome.grid(row=0, column=1, pady=4)

        ttk.Label(frm, text="E-mail / Celular:").grid(row=1, column=0, sticky="w")
        email = ttk.Entry(frm, width=40); email.grid(row=1, column=1, pady=4)

        ttk.Label(frm, text="Cargo:").grid(row=2, column=0, sticky="w")
        cargo = ttk.Entry(frm, width=40); cargo.grid(row=2, column=1, pady=4)

        admins = listar_administradores_db()
        setores = listar_setores_db()

        ttk.Label(frm, text="Administrador responsável (opcional):").grid(row=3, column=0, sticky="w")
        admin_options = ["(Nenhum)"] + [f"{a['id_adm']} - {a['nome']}" for a in admins]
        admin_var = tk.StringVar(value=admin_options[0])
        admin_combo = ttk.Combobox(frm, values=admin_options, textvariable=admin_var, state="readonly", width=37)
        admin_combo.grid(row=3, column=1, pady=4)

        ttk.Label(frm, text="Setor responsável (opcional):").grid(row=4, column=0, sticky="w")
        setor_options = ["(Nenhum)"] + [f"{s['id_setor']} - {s['nome_setor']}" for s in setores]
        setor_var = tk.StringVar(value=setor_options[0])
        setor_combo = ttk.Combobox(frm, values=setor_options, textvariable=setor_var, state="readonly", width=37)
        setor_combo.grid(row=4, column=1, pady=4)

        def salvar_colab():
            n = nome.get().strip()
            ec = email.get().strip()
            c = cargo.get().strip()
            adm_sel = admin_var.get()
            setor_sel = setor_var.get()

            if not n:
                messagebox.showwarning("Atenção", "Nome obrigatório"); return

            id_adm = None
            if adm_sel and adm_sel != "(Nenhum)":
                id_adm = adm_sel.split(" - ")[0]

            id_setor = None
            if setor_sel and setor_sel != "(Nenhum)":
                id_setor = setor_sel.split(" - ")[0]

            id_adm_val = int(id_adm) if id_adm and str(id_adm).isdigit() else None
            id_setor_val = int(id_setor) if id_setor and str(id_setor).isdigit() else None

            ok, resp = inserir_colaborador_db(n, ec, c, id_adm=id_adm_val, id_setor=id_setor_val)
            if ok:
                messagebox.showinfo("Sucesso", f"Colaborador criado. ID {resp}"); win.destroy()
            else:
                messagebox.showerror("Erro ao cadastrar colaborador", resp)

        ttk.Button(frm, text="Salvar", command=salvar_colab).grid(row=5, column=1, sticky="e", pady=8)

    def mostrar_administradores(self):
        rows = listar_administradores_db()
        win = tk.Toplevel(self.root)
        win.title("Administradores de Estoque")
        win.geometry("600x400")

        cols = ("id_adm", "nome", "email")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, h in zip(cols, ["ID", "Nome", "E-mail"]):
            tree.heading(c, text=h)
            tree.column(c, width=180 if c != "email" else 220, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        for r in rows:
            tree.insert("", "end", values=(r['id_adm'], r['nome'], r.get('email') or '-'))

        def remover_selecionado_admin():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Atenção", "Selecione um administrador para remover.")
                return
            vals = tree.item(sel[0])['values']
            id_adm = vals[0]
            nome = vals[1]
            if not messagebox.askyesno("Confirmar remoção", f"Remover administrador {nome} (ID {id_adm})?"):
                return
            ok, resp = remover_administrador_db(id_adm)
            if ok:
                messagebox.showinfo("Removido", f"Administrador ID {id_adm} removido.")
                tree.delete(sel[0])
            else:
                messagebox.showerror("Erro ao remover administrador", f"{resp}\n\nObservação: verifique se existem registros (produtos/colaboradores) que referenciam este administrador. Remova/ou atualize-os antes de apagar o administrador.")

        btn_frame = ttk.Frame(win, padding=6)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Remover selecionado", command=remover_selecionado_admin).pack(side="right", padx=6)
        ttk.Button(btn_frame, text="Fechar", command=win.destroy).pack(side="right")

    def mostrar_colaboradores(self):
        rows = listar_colaboradores_db()
        win = tk.Toplevel(self.root)
        win.title("Colaboradores")
        win.geometry("900x450")

        cols = ("id_col", "nome", "email", "cargo", "adm", "setor")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        headers = ["ID", "Nome", "E-mail / Celular", "Cargo", "Administrador", "Setor"]
        for c, h in zip(cols, headers):
            tree.heading(c, text=h)
            tree.column(c, width=140 if c in ("nome","adm","setor") else 110, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        for r in rows:
            tree.insert("", "end", values=(r['id_colaborador'], r['nome'], r.get('email_celular') or '-', r.get('cargo') or '-', r.get('nome_adm') or '-', r.get('nome_setor') or '-'))

        def remover_selecionado_colab():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Atenção", "Selecione um colaborador para remover.")
                return
            vals = tree.item(sel[0])['values']
            id_col = vals[0]
            nome = vals[1]
            if not messagebox.askyesno("Confirmar remoção", f"Remover colaborador {nome} (ID {id_col})?"):
                return
            ok, resp = remover_colaborador_db(id_col)
            if ok:
                messagebox.showinfo("Removido", f"Colaborador ID {id_col} removido.")
                tree.delete(sel[0])
            else:
                messagebox.showerror("Erro ao remover colaborador", f"{resp}\n\nVerifique dependências no banco.")

        btn_frame = ttk.Frame(win, padding=6)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Remover selecionado", command=remover_selecionado_colab).pack(side="right", padx=6)
        ttk.Button(btn_frame, text="Fechar", command=win.destroy).pack(side="right")

    def abrir_tv_display(self):
        if self.tv_display:
            messagebox.showinfo("TV", "O painel TV já está aberto.")
            return

        # permite escolher velocidade (opcional)
        speed = simpledialog.askstring("Velocidade do painel", "Escolha velocidade (low / medium / fast):", initialvalue="medium")
        if speed not in ("low", "medium", "fast"):
            speed = "medium"

        self.tv_display = TVDisplay(self.root, refresh_seconds=60, alerta_dias=30, speed=speed)
        def on_close_tv(e=None):
            try:
                self.tv_display.close()
            except Exception:
                pass
            self.tv_display = None
        self.root.bind("<F12>", lambda e: on_close_tv())

    def remover_selecionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um item na lista.")
            return
        vals = self.tree.item(sel[0])['values']
        pid = vals[0]
        nome = vals[2] if len(vals) > 2 else str(pid)
        if not messagebox.askyesno("Confirmar remoção", f"Remover o produto {nome} (ID {pid})?"):
            return
        ok, resp = remover_produto_db(pid)
        if ok:
            messagebox.showinfo("Removido", f"Produto ID {pid} removido.")
            self.mostrar_lista()
        else:
            messagebox.showerror("Erro", f"Não foi possível remover: {resp}")


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # esconde janela principal até login ser concluído

    # abre janela de login (modal)
    login = LoginWindow(root)
    root.wait_window(login.top)

    if not login.result:
        # usuário cancelou ou falhou no login -> encerra
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    # se login ok, mostra app principal
    root.deiconify()
    app = App(root, current_admin=login.admin)
    root.mainloop()
