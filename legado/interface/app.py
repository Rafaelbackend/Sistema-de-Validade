# app.py
import os
from datetime import datetime, date, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "troque_essa_chave")

# Usa DATABASE_URL do .env
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("Defina DATABASE_URL no .env")

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo do produto (ajuste campos conforme seu banco se já tiver tabela)
class Produto(db.Model):
    __tablename__ = 'produtos'
    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    lote = db.Column(db.String(50), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False, default=0)
    preco = db.Column(db.Numeric(10,2), nullable=True)
    validade = db.Column(db.Date, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def esta_vencido(self):
        if not self.validade:
            return False
        return self.validade < date.today()

    def dias_para_vencimento(self):
        if not self.validade:
            return None
        return (self.validade - date.today()).days

# Rota principal: lista produtos
@app.route('/')
def index():
    produtos = Produto.query.order_by(Produto.validade.asc().nulls_last(), Produto.nome).all()
    hoje = date.today()
    alerta_dias = 7  # produtos com <= 7 dias são alertados
    return render_template('index.html', produtos=produtos, hoje=hoje, alerta_dias=alerta_dias)

# Formulário para adicionar produto
@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        codigo_barras = request.form.get('codigo_barras', '').strip()
        nome = request.form.get('nome', '').strip()
        lote = request.form.get('lote', '').strip() or None
        quantidade = request.form.get('quantidade', '0').strip()
        preco = request.form.get('preco', '').strip()
        validade_text = request.form.get('validade', '').strip()

        # Validações básicas
        if not nome or not codigo_barras:
            flash('Nome e código de barras são obrigatórios.', 'danger')
            return redirect(url_for('add'))

        try:
            quantidade = int(quantidade)
        except ValueError:
            quantidade = 0

        # parse da data (formato YYYY-MM-DD vindo de input type=date)
        validade = None
        if validade_text:
            try:
                validade = datetime.strptime(validade_text, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de data inválido. Use YYYY-MM-DD.', 'danger')
                return redirect(url_for('add'))

        try:
            preco_val = float(preco.replace(',', '.')) if preco else None
        except ValueError:
            preco_val = None

        novo = Produto(
            codigo_barras=codigo_barras,
            nome=nome,
            lote=lote,
            quantidade=quantidade,
            preco=preco_val,
            validade=validade
        )
        db.session.add(novo)
        db.session.commit()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('index'))

    return render_template('add.html')

# Editar produto
@app.route('/edit/<int:produto_id>', methods=['GET', 'POST'])
def edit(produto_id):
    p = Produto.query.get_or_404(produto_id)
    if request.method == 'POST':
        p.codigo_barras = request.form.get('codigo_barras', p.codigo_barras).strip()
        p.nome = request.form.get('nome', p.nome).strip()
        p.lote = request.form.get('lote', p.lote).strip() or None
        quantidade = request.form.get('quantidade', str(p.quantidade)).strip()
        preco = request.form.get('preco', str(p.preco) if p.preco is not None else '').strip()
        validade_text = request.form.get('validade', '').strip()

        try:
            p.quantidade = int(quantidade)
        except ValueError:
            p.quantidade = p.quantidade

        try:
            p.preco = float(preco.replace(',', '.')) if preco else None
        except ValueError:
            pass

        if validade_text:
            try:
                p.validade = datetime.strptime(validade_text, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de data inválido.', 'danger')
                return redirect(url_for('edit', produto_id=produto_id))
        else:
            p.validade = None

        db.session.commit()
        flash('Produto atualizado.', 'success')
        return redirect(url_for('index'))

    return render_template('edit.html', produto=p)

# Deletar produto
@app.route('/delete/<int:produto_id>', methods=['POST'])
def delete(produto_id):
    p = Produto.query.get_or_404(produto_id)
    db.session.delete(p)
    db.session.commit()
    flash('Produto removido.', 'success')
    return redirect(url_for('index'))



