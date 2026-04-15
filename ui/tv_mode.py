import tkinter as tk
from datetime import datetime
from database import database as db

class TVDisplay:
    def __init__(self, master, refresh_seconds=60, alerta_dias=30, speed='medium'):
        self.win = tk.Toplevel(master)
        self.win.title("Painel TV")
        self.win.attributes("-fullscreen", True)
        self.win.config(bg="black")
        self.refresh_seconds = refresh_seconds
        self.alerta_dias = alerta_dias

        if speed == 'low':
            self.scroll_step = 0.0010
            self.scroll_delay_ms = 130
            self.end_pause_ms = 5000
        elif speed == 'fast':
            self.scroll_step = 0.006
            self.scroll_delay_ms = 60
            self.end_pause_ms = 1200
        else:
            self.scroll_step = 0.0035
            self.scroll_delay_ms = 90
            self.end_pause_ms = 2500

        self.frame = tk.Frame(self.win, bg="black")
        self.frame.pack(fill="both", expand=True)

        self.header = tk.Label(self.frame, text="NOTIFICAÇÕES DE VALIDADE", font=("Arial", 44, "bold"), bg="black", fg="white")
        self.header.pack(pady=20)

        self.txt = tk.Text(self.frame, bg="black", fg="white", font=("Arial", 28), bd=0, highlightthickness=0, wrap="word")
        self.txt.pack(fill="both", expand=True, padx=40, pady=10)

        self.footer = tk.Label(self.frame, text="Pressione ESC para sair do modo TV", font=("Arial", 18), bg="black", fg="white")
        self.footer.pack(pady=10)

        self.win.bind("<Escape>", lambda e: self.close())

        self.scroll_pos = 0.0
        self._scroll_job = None
        self._refresh_job = None
        self.running = True

        self.update_once()
        self._refresh_job = self.win.after(self.refresh_seconds * 1000, self._periodic_refresh)
        self.win.after(600, self._start_scrolling)

    def _periodic_refresh(self):
        if not self.running:
            return
        self.update_once()
        self._refresh_job = self.win.after(self.refresh_seconds * 1000, self._periodic_refresh)

    def update_once(self):
        if not self.running or not self.win.winfo_exists():
            return

        try:
            hoje = datetime.now().date()
            ok, rows = db.obter_dados_tv_db(self.alerta_dias)
            
            lines = []
            if not ok:
                lines = [f"Erro ao carregar dados: {rows}"]
            elif not rows:
                lines = ["Nenhum produto próximo do vencimento."]
            else:
                for r in rows:
                    validade = r.get('validade')
                    validade_str = validade.strftime("%d/%m/%Y") if validade else "—"
                    dias = (validade - hoje).days if validade else "?"
                    setor = r.get('nome_setor') or "—"
                    responsaveis_text = r.get('responsaveis') or r.get('nome_adm') or "—"

                    lines.append(f"Produto: {r['nome_produto']}  |  Validade: {validade_str}  ({dias} dias)")
                    lines.append(f"Qtd: {r['qtd_estoque']}  |  Lote: {r.get('lote') or '—'}  |  Setor: {setor}  |  Responsável(s): {responsaveis_text}")
                    lines.append("-" * 100)

            if self.txt.winfo_exists():
                self.txt.config(state="normal")
                self.txt.delete("1.0", "end")
                content = "\n\n".join(lines) + "\n\n\n\n"
                self.txt.insert("end", content)
                self.txt.config(state="disabled")

                self.scroll_pos = 0.0
                self.txt.yview_moveto(0.0)

        except Exception as e:
            print(f"Erro silencioso no update_once: {e}")

    def _start_scrolling(self):
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

        if last >= 0.999:
            self.scroll_pos = 0.0
            try:
                self.txt.yview_moveto(0.0)
            except Exception:
                pass
            self._scroll_job = self.win.after(self.end_pause_ms, self._scroll_step_internal)
            return

        self.scroll_pos = min(1.0, self.scroll_pos + self.scroll_step)
        try:
            self.txt.yview_moveto(self.scroll_pos)
        except Exception:
            pass

        self._scroll_job = self.win.after(self.scroll_delay_ms, self._scroll_step_internal)

    def close(self):
        self.running = False
        
        if self._scroll_job:
            self.win.after_cancel(self._scroll_job)
            self._scroll_job = None
    
        if self._refresh_job:
            self.win.after_cancel(self._refresh_job)
            self._refresh_job = None
    
        self.win.destroy()