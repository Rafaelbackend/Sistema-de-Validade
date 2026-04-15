# interface_gui.py
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------
# Configuração de conexão DB
# ---------------------------
# Prioridade: variáveis de ambiente -> fallback estático
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

# Mensagem útil para o usuário (opcional)
# Você pode configurar as variáveis de ambiente: DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT

# ---------- Conexão ----------
def conectar():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        # Em ambiente sem GUI (teste), evitar crash; se houver GUI, showerror.
        try:
            messagebox.showerror("Erro de conexão", f"Não foi possível conectar ao banco:\n{e}")
        except Exception:
            print("Erro de conexão:", e)
        return None

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

def inserir_administrador_db(nome, email):
    conn = conectar()
    if not conn:
        return False, "Sem conexão"
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO administrador_estoque (nome, email) VALUES (%s, %s) RETURNING id_adm;
                """, (nome, email))
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

# ---------- Interface Tkinter ----------
class TVDisplay:
    def __init__(self, master, refresh_seconds=30, alerta_dias=30):
        self.win = tk.Toplevel(master)
        self.win.title("Painel TV - Notificações")
        self.win.attributes("-fullscreen", True)
        self.win.config(bg="black")
        self.refresh_seconds = refresh_seconds
        self.alerta_dias = alerta_dias

        self.frame = tk.Frame(self.win, bg="black")
        self.frame.pack(fill="both", expand=True)

        self.header = tk.Label(self.frame, text="NOTIFICAÇÕES DE VALIDADE", font=("Arial", 44, "bold"), bg="black", fg="white")
        self.header.pack(pady=20)

        self.txt = tk.Text(self.frame, bg="black", fg="white", font=("Arial", 28), bd=0, highlightthickness=0)
        self.txt.pack(fill="both", expand=True, padx=40, pady=20)

        self.footer = tk.Label(self.frame, text="Pressione ESC para sair do modo TV", font=("Arial", 18), bg="black", fg="white")
        self.footer.pack(pady=10)

        self.win.bind("<Escape>", lambda e: self.close())

        self.running = True
        self.update_once()
        self._job = self.win.after(self.refresh_seconds * 1000, self._periodic)

    def _periodic(self):
        if not self.running:
            return
        self.update_once()
        self._job = self.win.after(self.refresh_seconds * 1000, self._periodic)

    def update_once(self):
        hoje = datetime.now().date()
        limite = hoje + timedelta(days=self.alerta_dias)
        conn = conectar()
        lines = []
        if conn:
            try:
                with conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        # busca produtos que vencem até o limite
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
                                dias = (r['validade'] - hoje).days if r['validade'] else "?"
                                setor = r.get('nome_setor') or "—"
                                # buscar colaboradores responsáveis pelo setor (id_setor)
                                colaboradores = []
                                if r.get('id_setor'):
                                    cur.execute("""
                                        SELECT nome FROM colaborador WHERE id_setor = %s ORDER BY nome;
                                    """, (r['id_setor'],))
                                    cols = cur.fetchall()
                                    colaboradores = [c['nome'] for c in cols] if cols else []
                                # se não houver colaborador no setor, fallback para administrador (se houver)
                                if colaboradores:
                                    responsaveis_text = ", ".join(colaboradores)
                                else:
                                    responsaveis_text = r.get('nome_adm') or "—"

                                lines.append(f"Produto: {r['nome_produto']}  |  Validade: {r['validade']}  ({dias} dias)")
                                lines.append(f"Qtd: {r['qtd_estoque']}  |  Lote: {r.get('lote') or '—'}  |  Setor: {setor}  |  Responsável(s): {responsaveis_text}")
                                lines.append("-" * 120)
            except Exception as e:
                lines = [f"Erro ao carregar notificações: {e}"]
            finally:
                conn.close()
        else:
            lines = ["Sem conexão com o banco."]

        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("end", "\n\n".join(lines))
        self.txt.config(state="disabled")

    def close(self):
        self.running = False
        try:
            if self._job:
                self.win.after_cancel(self._job)
        except Exception:
            pass
        self.win.destroy()

class App:
    def __init__(self, root):
        self.root = root
        root.title("Controle de Validade - Interface Local")
        root.geometry("1200x700")

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

        # carrega lista inicial
        self.mostrar_lista()
        self.tv_display = None

    def atualizar_tudo(self):
        # recarrega tudo
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
                            # buscar colaboradores do setor para mostrar na coluna "Responsável" da lista
                            if r.get('id_setor'):
                                cur.execute("SELECT nome FROM colaborador WHERE id_setor = %s ORDER BY nome", (r['id_setor'],))
                                cols = cur.fetchall()
                                if cols:
                                    responsavel = ", ".join([c['nome'] for c in cols])
                                else:
                                    # fallback para admin
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

        labels = ["Código de barras", "Nome do produto", "Validade (YYYY-MM-DD)", "Quantidade", "Preço", "Lote", "ID do Setor (opcional)", "ID do Admin (opcional)"]
        entries = {}
        for i, lbl in enumerate(labels):
            ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w", pady=4)
            ent = ttk.Entry(frm, width=40)
            ent.grid(row=i, column=1, pady=4, padx=6)
            entries[i] = ent

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
                    validade = datetime.strptime(validade_text, "%Y-%m-%d").date()
                except Exception:
                    messagebox.showwarning("Atenção", "Formato de validade inválido. Use YYYY-MM-DD.")
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

            # converte ids vazios para None para evitar inserir strings vazias no DB
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
            dias = (p['validade'] - hoje).days if p['validade'] else "?"
            txt.insert("end", f"ID {p['id_produto']} - {p['nome_produto']} - Vence em {dias} dias ({p['validade']})\n")
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
            txt.insert("end", f"[{n['data_envio']}] ID {n['id_notificacao']} - {n['nome_produto']} - {n['tipo_notificacao']}\n{n['mensagem']}\n\n")
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
        def salvar_admin():
            n = nome.get().strip(); e = email.get().strip()
            if not n:
                messagebox.showwarning("Atenção", "Nome obrigatório"); return
            ok, resp = inserir_administrador_db(n, e)
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

        # Refresh admins and setores quando abrir o formulário
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
        self.tv_display = TVDisplay(self.root, refresh_seconds=30, alerta_dias=30)
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
    app = App(root)
    root.mainloop()
