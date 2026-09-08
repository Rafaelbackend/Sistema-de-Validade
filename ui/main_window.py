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
        # Container principal do topo (agora sem padding interno para os subframes controlarem o espaço)
        top = ttk.Frame(self.root)
        top.pack(side="top", fill="x", padx=8, pady=4)

        # ----------------------------------------------------
        # LINHA 1: Operações de Produtos e Modos de Visualização
        # ----------------------------------------------------
        linha1 = ttk.Frame(top, padding=4)
        linha1.pack(side="top", fill="x")

        ttk.Button(linha1, text="Listar produtos", command=self.mostrar_lista).pack(side="left", padx=4)
        ttk.Button(linha1, text="Adicionar produto", command=self.forms.abrir_form_adicionar).pack(side="left", padx=4)
        ttk.Button(linha1, text="Enviar para área de venda", command=self.forms.abrir_form_area_venda).pack(side="left",
                                                                                                            padx=4)
        ttk.Button(linha1, text="Área de venda", command=self.views.mostrar_area_venda).pack(side="left", padx=4)
        ttk.Button(linha1, text="Verificar validade (30d)", command=self.views.acao_verificar_validade).pack(
            side="left", padx=4)
        ttk.Button(linha1, text="Listar notificações", command=self.views.mostrar_notificacoes).pack(side="left",
                                                                                                     padx=4)

        # Botões do lado direito da Linha 1
        ttk.Button(linha1, text="Atualizar", command=self.mostrar_lista).pack(side="right", padx=4)
        ttk.Button(linha1, text="Abrir modo TV (fullscreen)", command=self.abrir_tv_display).pack(side="right", padx=4)

        # ----------------------------------------------------
        # LINHA 2: Cadastros Administrativos e Gerenciamento
        # ----------------------------------------------------
        linha2 = ttk.Frame(top, padding=4)
        linha2.pack(side="top", fill="x", pady=(4, 0))  # Adiciona um pequeno espaçamento vertical acima da linha 2

        ttk.Button(linha2, text="Cadastrar Admin", command=self.forms.abrir_form_admin).pack(side="left", padx=4)
        ttk.Button(linha2, text="Cadastrar Setor", command=self.forms.abrir_form_setor).pack(side="left", padx=4)
        ttk.Button(linha2,text="Ver Setores",command=self.views.mostrar_setores).pack(side="left", padx=4)
        ttk.Button(linha2,text="Remover Setor",command=self.views.remover_setor).pack(side="left", padx=4)
        ttk.Button(linha2, text="Cadastrar Colaborador", command=self.forms.abrir_form_colab).pack(side="left", padx=4)

        ttk.Button(linha2, text="Ver Administradores", command=self.views.mostrar_administradores).pack(side="left",
                                                                                                        padx=12)
        ttk.Button(linha2, text="Ver Colaboradores", command=self.views.mostrar_colaboradores).pack(side="left", padx=4)

        # ----------------------------------------------------
        # MEIO DA TELA (Treeview) - Mantido igual ao seu original
        # ----------------------------------------------------
        middle = ttk.Frame(self.root, padding=8)
        middle.pack(fill="both", expand=True)

        cols = ("ID", "Codigo", "Nome", "Validade", "Qtd", "Preco", "Lote", "Prateleira","Corredor", "Setor", "Responsavel")
        self.tree = ttk.Treeview(middle, columns=cols, show="headings")
        headers = ["ID", "Código", "Nome", "Validade", "Qtd", "Preço", "Lote", "Prateleira","Corredor", "Setor", "Responsável"]

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

        # ----------------------------------------------------
        # PARTE INFERIOR (Status) - Mantido igual ao seu original
        # ----------------------------------------------------
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

            conn = None

            try:
                conn = db.db_manager.get_connection()
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
                if conn:
                    db.db_manager.put_connection(conn)
                

            tag = ''
            if validade:
                dias = (validade - datetime.now().date()).days
                if dias < 0:
                    tag = 'vencido'
                elif dias <= 7:
                    tag = 'perigo'

            self.tree.insert("", "end",
                             values=(r['id_produto'], r.get('codigo_barra'), r.get('nome_produto'),
                                     validade_str, r.get('qtd_estoque'), preco, r.get('lote'), r.get('prateleira'),
                                     r.get('corredor'), setor, responsavel),
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
        
        self.tv_display.win.bind("<Destroy>", lambda e: self.reset_tv_ref())

    def reset_tv_ref(self):
        self.tv_display = None