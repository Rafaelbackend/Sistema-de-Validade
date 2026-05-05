import tkinter as tk
from datetime import datetime
from database import database as db

class TVDisplay:
    def __init__(self, master, refresh_seconds=60, alerta_dias=30, speed='medium'):
        self.win = tk.Toplevel(master)
        self.win.title("Painel de Monitoramento de Estoque")
        self.win.attributes("-fullscreen", True)
        self.win.config(bg="#000000")
        self.cores_colaboradores = {}
        self.paleta = ["#BD93F9", "#FF79C6", "#8BE9FD", "#50FA7B", "#F1FA8C", "#FFB86C"]
        self.cor_index = 0
        
        self.refresh_seconds = refresh_seconds
        self.alerta_dias = alerta_dias
        self.running = True

        # Configurações de Rolagem (Scroll)
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

        # Interface Principal
        self.frame = tk.Frame(self.win, bg="black")
        self.frame.pack(fill="both", expand=True)

        self.header = tk.Label(
            self.frame, text="ALERTAS DE VALIDADE", 
            font=("Arial", 48, "bold"), bg="black", foreground="#F8F8F2", pady=20
        )
        self.header.pack()

        # Widget de Texto com suporte a Cores (Tags)
        self.txt = tk.Text(
            self.frame, bg="black", foreground="white", font=("Arial", 28),
            bd=0, highlightthickness=0, wrap="word", cursor="none"
        )
        self.txt.pack(fill="both", expand=True, padx=50)

        # Configuração das Cores (Dracula Theme Style)
        self.txt.tag_config("vencido", foreground="#FF5555", font=("Arial", 30, "bold"))  # Vermelho
        self.txt.tag_config("alerta", foreground="#FFB86C", font=("Arial", 30, "bold"))   # Laranja
        self.txt.tag_config("normal", foreground="#50FA7B")                             # Verde
        self.txt.tag_config("info", foreground="#8BE9FD", font=("Arial", 20))            # Ciano (Detalhes)
        self.txt.tag_config("divisor", foreground="#6272A4")                            # Cinza/Roxo

        self.footer = tk.Label(
            self.frame, text="SISTEMA DE MONITORAMENTO | Pressione ESC para sair", 
            font=("Arial", 16), bg="#282A36", foreground="#BD93F9"
        )
        self.footer.pack(fill="x", side="bottom", ipady=5)

        # Atalhos e Jobs
        self.win.bind("<Escape>", lambda e: self.close())
        self._scroll_job = None
        self._refresh_job = None

        # Inicialização
        self.update_once()
        self._schedule_tasks()

    def _schedule_tasks(self):
        """Agenda a atualização de dados e o início da rolagem."""
        self._refresh_job = self.win.after(self.refresh_seconds * 1000, self._periodic_refresh)
        self.win.after(1000, self._start_scrolling)

    def _periodic_refresh(self):
        if self.running:
            self.update_once()
            self._refresh_job = self.win.after(self.refresh_seconds * 1000, self._periodic_refresh)

    def update_once(self):
        """Busca dados no banco e reconstrói o texto com cores."""
        if not self.running or not self.win.winfo_exists():
            return

        try:
            hoje = datetime.now().date()
            ok, rows = db.obter_dados_tv_db(self.alerta_dias)
            
            self.txt.config(state="normal")
            self.txt.delete("1.0", "end")

            if not ok:
                self.txt.insert("end", f"⚠️ ERRO DE CONEXÃO: {rows}\n", "vencido")
            elif not rows:
                self.txt.insert("end", "\n\n✅ TUDO EM DIA!\nNenhum produto próximo do vencimento.\n", "normal")
            else:
                for r in rows:
                    validade = r.get('validade')
                    validade_str = validade.strftime("%d/%m/%Y") if validade else "SEM DATA"
                    dias = (validade - hoje).days if validade else 999
                    
                    # Lógica de cores por urgência
                    if dias <= 0:
                        tag = "vencido"
                        status = " [PRODUTO VENCIDO]"
                    elif dias <= 7:
                        tag = "alerta"
                        status = f" [VENCE EM {dias} DIAS]"
                    else:
                        tag = "normal"
                        status = f" [Prazo: {dias} dias]"

                    # Inserção do Cabeçalho do Produto
                    self.txt.insert("end", f"• {r['nome_produto']}", tag)
                    self.txt.insert("end", f"{status}\n", tag)
                    
                    # Inserção dos Detalhes (Fonte menor e cor fria)
                    detalhes = (f"  Validade: {validade_str} | Estoque: {r['qtd_estoque']} | "
                                f"Lote: {r.get('lote') or '—'} | Setor: {r.get('nome_setor') or 'Geral'}\n")
                    self.txt.insert("end", detalhes, "info")
                    
                    # Responsáveis
                    self.txt.insert("end", "  Responsáveis: ", "info")

                    responsaveis_raw = r.get('responsaveis') or r.get('nome_adm')
                    if responsaveis_raw:
                        nomes = responsaveis_raw.split(',')
                        for i, nome in enumerate(nomes):
                            nome_limpo = nome.strip()
                            tag_colab = self.obter_tag_colaborador(nome_limpo)
                            
                            # Insere o nome com sua cor específica
                            self.txt.insert("end", nome_limpo, tag_colab)
                            
                            # Adiciona a vírgula branca entre os nomes, exceto no último
                            if i < len(nomes) - 1:
                                self.txt.insert("end", ", ", "info")
                        self.txt.insert("end", "\n")
                    else:
                        self.txt.insert("end", "Não atribuído\n", "info")
                    
                    # Divisor Visual
                    self.txt.insert("end", "—" * 48 + "\n\n", "divisor")

            self.txt.config(state="disabled")
            self.scroll_pos = 0.0
            self.txt.yview_moveto(0.0)

        except Exception as e:
            print(f"Erro ao atualizar painel TV: {e}")

    def _start_scrolling(self):
        if self._scroll_job:
            self.win.after_cancel(self._scroll_job)
        self._scroll_step_internal()

    def _scroll_step_internal(self):
        if not self.running: return
        try:
            _, last = self.txt.yview()
            
            if last >= 0.999: # Chegou ao fim
                self.scroll_pos = 0.0
                self.txt.yview_moveto(0.0)
                self._scroll_job = self.win.after(self.end_pause_ms, self._scroll_step_internal)
            else:
                self.scroll_pos += self.scroll_step
                self.txt.yview_moveto(self.scroll_pos)
                self._scroll_job = self.win.after(self.scroll_delay_ms, self._scroll_step_internal)
        except Exception:
            pass

    def obter_tag_colaborador(self, nome):
        nome_limpo = nome.strip()
        tag_name = f"colab_{nome_limpo.replace(' ', '_')}"
        
        # Se o colaborador ainda não tem uma cor, atribui uma da paleta
        if nome_limpo not in self.cores_colaboradores:
            cor = self.paleta[self.cor_index % len(self.paleta)]
            self.cores_colaboradores[nome_limpo] = tag_name
            self.txt.tag_config(tag_name, foreground=cor, font=("Arial", 20, "italic"))
            self.cor_index += 1
            
        return self.cores_colaboradores[nome_limpo]

    def close(self):
        self.running = False
        if self._scroll_job: self.win.after_cancel(self._scroll_job)
        if self._refresh_job: self.win.after_cancel(self._refresh_job)
        self.win.destroy()