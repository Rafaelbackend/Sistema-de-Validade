import tkinter as tk
from tkinter import ttk, messagebox
from database.database import verificar_credenciais

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