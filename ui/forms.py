import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime
from database import database as db

class FormManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.root = main_app.root

    def abrir_form_adicionar(self):
        win = tk.Toplevel(self.root)
        win.title("Adicionar produto")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        labels = ["Código de barras", "Nome do produto", "Validade (YYYY-MM-DD)", "Quantidade", "Preço", "Lote", "ID do Setor", "ID do Admin"]
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
            
            ok, resp = db.inserir_produto_db(prod)
            if ok:
                messagebox.showinfo("Sucesso", f"Produto criado. ID: {resp}")
                win.destroy()
                self.main_app.mostrar_lista()
            else:
                messagebox.showerror("Erro", f"Não foi possível inserir: {resp}")

        ttk.Button(frm, text="Salvar", command=salvar).grid(row=len(labels), column=1, sticky="e", pady=8)

    def abrir_form_admin(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Administrador")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        
        ttk.Label(frm, text="Nome:").grid(row=0, column=0, sticky="w")
        nome = ttk.Entry(frm, width=40)
        nome.grid(row=0, column=1, pady=4)
        
        ttk.Label(frm, text="E-mail:").grid(row=1, column=0, sticky="w")
        email = ttk.Entry(frm, width=40)
        email.grid(row=1, column=1, pady=4)
        
        def salvar_admin():
            n = nome.get().strip()
            e = email.get().strip()
            if not n:
                messagebox.showwarning("Atenção", "Nome obrigatório")
                return
            ok, resp = db.inserir_administrador_db(n, e)
            if ok:
                messagebox.showinfo("Sucesso", f"Administrador criado. ID {resp}")
                win.destroy()
            else:
                messagebox.showerror("Erro", resp)
                
        ttk.Button(frm, text="Salvar", command=salvar_admin).grid(row=3, column=1, sticky="e", pady=8)

    def abrir_form_setor(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Setor")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        
        ttk.Label(frm, text="Nome do setor:").grid(row=0, column=0, sticky="w")
        nome = ttk.Entry(frm, width=40)
        nome.grid(row=0, column=1, pady=4)
        
        def salvar_setor():
            n = nome.get().strip()
            if not n:
                messagebox.showwarning("Atenção", "Nome obrigatório")
                return
            ok, resp = db.inserir_setor_db(n)
            if ok:
                messagebox.showinfo("Sucesso", f"Setor criado. ID {resp}")
                win.destroy()
            else:
                messagebox.showerror("Erro", resp)
                
        ttk.Button(frm, text="Salvar", command=salvar_setor).grid(row=2, column=1, sticky="e", pady=8)

    def abrir_form_colab(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Colaborador")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Nome:").grid(row=0, column=0, sticky="w")
        nome = ttk.Entry(frm, width=40)
        nome.grid(row=0, column=1, pady=4)

        ttk.Label(frm, text="E-mail / Celular:").grid(row=1, column=0, sticky="w")
        email = ttk.Entry(frm, width=40)
        email.grid(row=1, column=1, pady=4)

        ttk.Label(frm, text="Cargo:").grid(row=2, column=0, sticky="w")
        cargo = ttk.Entry(frm, width=40)
        cargo.grid(row=2, column=1, pady=4)

        admins = db.listar_administradores_db()
        setores = db.listar_setores_db()

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
                messagebox.showwarning("Atenção", "Nome obrigatório")
                return

            id_adm = None
            if adm_sel and adm_sel != "(Nenhum)":
                id_adm = adm_sel.split(" - ")[0]

            id_setor = None
            if setor_sel and setor_sel != "(Nenhum)":
                id_setor = setor_sel.split(" - ")[0]

            id_adm_val = int(id_adm) if id_adm and str(id_adm).isdigit() else None
            id_setor_val = int(id_setor) if id_setor and str(id_setor).isdigit() else None

            ok, resp = db.inserir_colaborador_db(n, ec, c, id_adm=id_adm_val, id_setor=id_setor_val)
            if ok:
                messagebox.showinfo("Sucesso", f"Colaborador criado. ID {resp}")
                win.destroy()
            else:
                messagebox.showerror("Erro ao cadastrar colaborador", resp)

        ttk.Button(frm, text="Salvar", command=salvar_colab).grid(row=5, column=1, sticky="e", pady=8)