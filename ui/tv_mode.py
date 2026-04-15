import tkinter as tk
from datetime import datetime, timedelta
from database.database import conectar

class TVDisplay:
    def __init__(self, master, refresh_seconds=60, alerta_dias=30, speed='medium'):
        self.win = tk.Toplevel(master)
        self.win.title("Painel TV")
        self.win.attributes("-fullscreen", True)
        self.win.config(bg="black")
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
