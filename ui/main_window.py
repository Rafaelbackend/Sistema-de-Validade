import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime
from database import database as db
from psycopg2.extras import RealDictCursor
from ui.tv_mode import TVDisplay
from ui.forms import FormManager
from ui.views import ViewManager

class AppMainWindow:
    def __init__(self, root, current_admin=None):
        self.root = root
        self.current_admin = current_admin
        self.tv_display = None
        
        self.root.title("Controle de Validade - Interface Local")
        self.root.geometry("1200x700")

        self.forms = FormManager(self)
        self.views = ViewManager(self)

        self._setup_ui()
        self.mostrar_lista()

    def _setup_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(side="top", fill="x")

        ttk.Button(top, text="Listar produtos", command=self.mostrar_lista).pack(side="left", padx=4)
        ttk.Button(top, text="Adicionar produto", command=self.forms.abrir_form_adicionar).pack(side="left", padx=4)
        ttk.Button(top, text="Verificar validade (30d)", command=self.views.acao_verificar_validade).pack(side="left", padx=4)
        ttk.Button(top, text="Listar notificações", command=self.views.mostrar_notificacoes).pack(side="left", padx=4)

        ttk.Button(top, text="Cadastrar Admin", command=self.forms.abrir_form_admin).pack(side="left", padx=8)
        ttk.Button(top, text="Cadastrar Setor", command=self.forms.abrir_form_setor).pack(side="left", padx=4)
        ttk.Button(top, text="Cadastrar Colaborador", command=self.forms.abrir_form_colab).pack(side="left", padx=4)

        ttk.Button(top, text="Ver Administradores", command=self.views.mostrar_administradores).pack(side="left", padx=8)
        ttk.Button(top, text="Ver Colaboradores", command=self.views.mostrar_colaboradores).pack(side="left", padx=4)
        ttk.Button(top, text="Abrir modo TV (fullscreen)", command=self.abrir_tv_display).pack(side="right", padx=4)
        ttk.Button(top, text="Atualizar", command=self.mostrar_lista).pack(side="right", padx=4)

        middle = ttk.Frame(self.root, padding=8)
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

        self.tree.tag_configure('perigo', background='#ffcccc')
        self.tree.tag_configure('vencido', background='#ff9999')

        vsb = ttk.Scrollbar(middle, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, side="left")

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(side="bottom", fill="x")
        
        ttk.Button(bottom, text="Remover selecionado", command=self.remover_selecionado).pack(side="right", padx=4)
        self.status = ttk.Label(bottom, text="Pronto")
        self.status.pack(side="left")

    def atualizar_status(self, texto):
        self.status.config(text=texto)

    def mostrar_lista(self):
        self.atualizar_status("Carregando lista...")
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        rows = db.listar_produtos_db()
        for r in rows:
            validade = r['validade']
            validade_str = validade.strftime("%d/%m/%Y") if validade else "-"
            preco = f"R$ {float(r['preco']):.2f}" if r.get('preco') is not None else "-"
            setor = "-"
            responsavel = "-"
            
            try:
                conn = db.conectar()
                if conn:
                    with conn:
                        with conn.cursor(cursor_factory=RealDictCursor) as cur:
                            if r.get('id_setor'):
                                cur.execute("SELECT nome_setor FROM setor WHERE id_setor = %s", (r['id_setor'],))
                                s = cur.fetchone()
                                setor = s['nome_setor'] if s else "-"
                                
                                cur.execute("SELECT nome FROM colaborador WHERE id_setor = %s ORDER BY nome", (r['id_setor'],))
                                cols_db = cur.fetchall()
                                if cols_db:
                                    responsavel = ", ".join([c['nome'] for c in cols_db])
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
                messagebox.showerror("Erro", "Ocorreu um erro ao carregar os dados do banco.")
            finally:
                try:
                    if conn:
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
            
        ok, resp = db.remover_produto_db(pid)
        if ok:
            messagebox.showinfo("Removido", f"Produto ID {pid} removido.")
            self.mostrar_lista()
        else:
            messagebox.showerror("Erro", f"Não foi possível remover: {resp}")

    def abrir_tv_display(self):
        if self.tv_display:
            messagebox.showinfo("TV", "O painel TV já está aberto.")
            return
        self.tv_display = TVDisplay(self.root, refresh_seconds=30, alerta_dias=30)
        
        def on_close_tv(e=None):
            try:
                self.tv_display.close()
            except Exception:
                messagebox.showwarning("Aviso", "Ocorreu um erro ao fechar o painel TV. Tente novamente.")
            self.tv_display = None
            
        self.root.bind("<F12>", lambda e: on_close_tv())