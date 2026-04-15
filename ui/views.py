import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime
from database import database as db

class ViewManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.root = main_app.root

    def acao_verificar_validade(self):
        produtos = db.verificar_validade_db(30)
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
        self.main_app.mostrar_lista()

    def mostrar_notificacoes(self):
        rows = db.listar_notificacoes_db()
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

    def mostrar_administradores(self):
        rows = db.listar_administradores_db()
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
                
            ok, resp = db.remover_administrador_db(id_adm)
            if ok:
                messagebox.showinfo("Removido", f"Administrador ID {id_adm} removido.")
                tree.delete(sel[0])
                self.main_app.mostrar_lista()
            else:
                messagebox.showerror("Erro ao remover administrador", f"{resp}\n\nVerifique se existem dependências.")

        btn_frame = ttk.Frame(win, padding=6)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Remover selecionado", command=remover_selecionado_admin).pack(side="right", padx=6)
        ttk.Button(btn_frame, text="Fechar", command=win.destroy).pack(side="right")

    def mostrar_colaboradores(self):
        rows = db.listar_colaboradores_db()
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
            tree.insert("", "end", values=(
                r['id_colaborador'], 
                r['nome'], 
                r.get('email_celular') or '-', 
                r.get('cargo') or '-', 
                r.get('nome_adm') or '-', 
                r.get('nome_setor') or '-'
            ))

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
                
            ok, resp = db.remover_colaborador_db(id_col)
            if ok:
                messagebox.showinfo("Removido", f"Colaborador ID {id_col} removido.")
                tree.delete(sel[0])
                self.main_app.mostrar_lista()
            else:
                messagebox.showerror("Erro ao remover colaborador", f"{resp}\n\nVerifique dependências no banco.")

        btn_frame = ttk.Frame(win, padding=6)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Remover selecionado", command=remover_selecionado_colab).pack(side="right", padx=6)
        ttk.Button(btn_frame, text="Fechar", command=win.destroy).pack(side="right")