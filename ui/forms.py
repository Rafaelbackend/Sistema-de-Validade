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
        win.geometry("520x430")

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)

        labels = [
            "Código de barras", "Nome do produto", "Validade (DD-MM-YYYY)",
            "Quantidade", "Preço", "Lote", "Prateleira", "ID do Setor", "ID do Admin"
        ]
        entries = {}

        for i, lbl in enumerate(labels):
            ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w", pady=4)
            ent = ttk.Entry(frm, width=40)
            ent.grid(row=i, column=1, pady=4, padx=6)
            entries[i] = ent

        # ---------------------------------------------------------
        # FUNÇÃO PARA RECONHECER O CÓDIGO DE BARRAS
        # ---------------------------------------------------------
        def reconhecer_codigo(event=None):
            codigo = entries[0].get().strip()
            if not codigo:
                return
            encontrado, produto = db.buscar_produto_por_codigo_db(codigo)
            if encontrado:
                nome_produto = produto.get('nome_produto')
                entries[1].delete(0, tk.END)
                entries[1].insert(0, nome_produto or "")
                messagebox.showinfo("Produto encontrado",
                                    f"Produto reconhecido:\n\nNome: {nome_produto}\n\n"
                                    f"Agora informe o novo lote, quantidade, validade e prateleira.")
                entries[2].focus_set()
            else:
                entries[1].delete(0, tk.END)
                messagebox.showinfo("Novo produto",
                                    "Código de barras não encontrado.\n\nEste será cadastrado como um novo produto.")
                entries[1].focus_set()

        entries[0].bind("<Return>", reconhecer_codigo)

        # ---------------------------------------------------------
        # FUNÇÃO SALVAR (APENAS A VERSÃO COMPLETA E VALIDADA)
        # ---------------------------------------------------------
        def salvar():
            codigo = entries[0].get().strip()
            nome = entries[1].get().strip()
            validade_text = entries[2].get().strip()
            qtd_text = entries[3].get().strip()
            preco_text = entries[4].get().strip()
            lote = entries[5].get().strip() or None
            prateleira = entries[6].get().strip() or None
            id_setor = entries[7].get().strip() or None
            id_adm = entries[8].get().strip() or None

            # Validações de campos obrigatórios
            if not codigo:
                messagebox.showwarning("Atenção", "Código de barras é obrigatório.")
                entries[0].focus_set()
                return
            if not nome:
                messagebox.showwarning("Atenção", "Nome do produto é obrigatório.")
                entries[1].focus_set()
                return
            if not lote:
                messagebox.showwarning("Atenção", "Lote é obrigatório.")
                entries[5].focus_set()
                return
            if not prateleira:
                messagebox.showwarning("Atenção", "Prateleira é obrigatória.")
                entries[6].focus_set()
                return

            # Verificação de Código + Lote duplicados no banco
            lote_existente = db.verificar_codigo_lote_existente_db(codigo, lote)
            if lote_existente:
                messagebox.showerror("Lote já cadastrado",
                                     f"O lote '{lote}' já está cadastrado para este produto.\n\n"
                                     f"Código de barras: {codigo}\nLote: {lote}\n\n"
                                     f"Você deve informar outro lote.")
                entries[5].focus_set()
                return

            # Validação da Data de Validade
            validade = None
            if validade_text:
                try:
                    validade = datetime.strptime(validade_text, "%d-%m-%Y").date()
                except ValueError:
                    messagebox.showwarning("Atenção", "Formato de validade inválido.\n\nUse DD-MM-YYYY.")
                    entries[2].focus_set()
                    return

            # Validação da Quantidade
            try:
                qtd = int(qtd_text) if qtd_text else 0
            except ValueError:
                messagebox.showwarning("Atenção", "Quantidade deve ser número inteiro.")
                entries[3].focus_set()
                return

            # Validação do Preço
            try:
                preco = float(preco_text.replace(",", ".")) if preco_text else None
            except ValueError:
                messagebox.showwarning("Atenção", "Preço inválido.")
                entries[4].focus_set()
                return

            # Conversão de IDs relacionais
            id_setor_val = int(id_setor) if id_setor and id_setor.isdigit() else None
            id_adm_val = int(id_adm) if id_adm and id_adm.isdigit() else None

            # Montagem do dicionário do produto
            prod = {
                'codigo_barra': codigo,
                'nome_produto': nome,
                'validade': validade,
                'qtd_estoque': qtd,
                'preco': preco,
                'lote': lote,
                'prateleira': prateleira,
                'id_setor': id_setor_val,
                'id_adm': id_adm_val
            }

            # Envio para o Banco de Dados
            ok, resp = db.inserir_produto_db(prod)
            if ok:
                messagebox.showinfo("Sucesso",
                                    f"Produto cadastrado com sucesso!\n\nID: {resp}\nLote: {lote}\nPrateleira: {prateleira}")
                win.destroy()
                self.main_app.mostrar_lista()
            else:
                messagebox.showerror("Erro", f"Não foi possível inserir:\n\n{resp}")

        # ---------------------------------------------------------
        # VÍNCULO DO BOTÃO SALVAR À INTERFACE
        # ---------------------------------------------------------
        ttk.Button(frm, text="Salvar", command=salvar).grid(row=len(labels), column=1, sticky="e", pady=8)

        # Inicia o foco do teclado no campo de código de barras
        entries[0].focus_set()

    def abrir_form_area_venda(self):

        win = tk.Toplevel(self.root)
        win.title("Enviar produto para área de venda")
        win.geometry("500x430")

        frm = ttk.Frame(win, padding=15)
        frm.pack(fill="both", expand=True)

        # -----------------------------------------
        # CÓDIGO DE BARRAS
        # -----------------------------------------

        ttk.Label(
            frm,
            text="Código de barras:"
        ).grid(row=0, column=0, sticky="w", pady=5)

        codigo_ent = ttk.Entry(frm, width=40)
        codigo_ent.grid(row=0, column=1, pady=5)

        # -----------------------------------------
        # LOTE
        # -----------------------------------------

        ttk.Label(
            frm,
            text="Lote:"
        ).grid(row=1, column=0, sticky="w", pady=5)

        lote_ent = ttk.Entry(frm, width=40)
        lote_ent.grid(row=1, column=1, pady=5)

        # -----------------------------------------
        # INFORMAÇÕES DO PRODUTO
        # -----------------------------------------

        info = tk.Text(
            frm,
            width=55,
            height=10,
            state="disabled"
        )

        info.grid(
            row=3,
            column=0,
            columnspan=2,
            pady=10
        )

        # -----------------------------------------
        # QUANTIDADE
        # -----------------------------------------

        ttk.Label(
            frm,
            text="Quantidade para área de venda:"
        ).grid(row=4, column=0, sticky="w", pady=5)

        qtd_ent = ttk.Entry(frm, width=40)
        qtd_ent.grid(row=4, column=1, pady=5)

        produto_atual = {
            "produto": None
        }

        # -----------------------------------------
        # BUSCAR PRODUTO
        # -----------------------------------------

        def buscar():

            codigo = codigo_ent.get().strip()
            lote = lote_ent.get().strip()

            if not codigo:
                messagebox.showwarning(
                    "Atenção",
                    "Informe ou leia o código de barras."
                )
                codigo_ent.focus_set()
                return

            if not lote:
                messagebox.showwarning(
                    "Atenção",
                    "Informe o lote."
                )
                lote_ent.focus_set()
                return

            encontrado, produto = db.buscar_produto_por_codigo_lote_db(
                codigo,
                lote
            )

            if not encontrado:
                messagebox.showerror(
                    "Produto não encontrado",
                    produto
                )
                return

            produto_atual["produto"] = produto

            validade = produto["validade"]

            if validade:
                validade = validade.strftime("%d/%m/%Y")
            else:
                validade = "Sem validade"

            texto = (
                f"PRODUTO ENCONTRADO\n\n"
                f"Nome: {produto['nome_produto']}\n"
                f"Código: {produto['codigo_barra']}\n"
                f"Lote: {produto['lote']}\n"
                f"Validade: {validade}\n"
                f"Prateleira: {produto.get('prateleira') or '-'}\n"
                f"Estoque atual: {produto['qtd_estoque']}\n"
            )

            info.config(state="normal")
            info.delete("1.0", tk.END)
            info.insert("1.0", texto)
            info.config(state="disabled")

            qtd_ent.focus_set()

        # -----------------------------------------
        # SALVAR SAÍDA
        # -----------------------------------------

        def enviar():

            produto = produto_atual["produto"]

            if not produto:
                messagebox.showwarning(
                    "Atenção",
                    "Primeiro informe o código de barras e o lote."
                )
                return

            qtd_texto = qtd_ent.get().strip()

            try:
                quantidade = int(qtd_texto)
            except ValueError:
                messagebox.showwarning(
                    "Atenção",
                    "A quantidade deve ser um número inteiro."
                )
                qtd_ent.focus_set()
                return

            if quantidade <= 0:
                messagebox.showwarning(
                    "Atenção",
                    "A quantidade deve ser maior que zero."
                )
                qtd_ent.focus_set()
                return

            estoque = produto["qtd_estoque"] or 0

            if quantidade > estoque:
                messagebox.showerror(
                    "Estoque insuficiente",
                    f"Estoque disponível: {estoque}\n"
                    f"Quantidade solicitada: {quantidade}"
                )
                qtd_ent.focus_set()
                return

            confirmar = messagebox.askyesno(
                "Confirmar saída",
                f"Produto: {produto['nome_produto']}\n"
                f"Lote: {produto['lote']}\n\n"
                f"Quantidade: {quantidade}\n\n"
                f"Enviar para a área de venda?"
            )

            if not confirmar:
                return

            ok, resposta = db.enviar_produto_area_venda_db(
                produto["id_produto"],
                quantidade
            )

            if ok:

                messagebox.showinfo(
                    "Sucesso",
                    f"Produto enviado para a área de venda!\n\n"
                    f"Produto: {produto['nome_produto']}\n"
                    f"Quantidade enviada: {quantidade}\n"
                    f"Estoque restante: {resposta}"
                )

                win.destroy()

                self.main_app.mostrar_lista()

            else:

                messagebox.showerror(
                    "Erro",
                    f"Não foi possível realizar a saída:\n\n{resposta}"
                )

        # -----------------------------------------
        # BOTÕES
        # -----------------------------------------

        ttk.Button(
            frm,
            text="Buscar produto",
            command=buscar
        ).grid(
            row=2,
            column=1,
            sticky="e",
            pady=5
        )

        ttk.Button(
            frm,
            text="Enviar para área de venda",
            command=enviar
        ).grid(
            row=5,
            column=1,
            sticky="e",
            pady=10
        )

        # Leitor de código de barras
        codigo_ent.bind(
            "<Return>",
            lambda event: lote_ent.focus_set()
        )

        lote_ent.bind(
            "<Return>",
            lambda event: buscar()
        )

        codigo_ent.focus_set()
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