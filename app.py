import os
import secrets
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)

# Configurações de Segurança e Banco
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave-secreta-provisoria-123")
# Se estiver no Render, ele usa a DATABASE_URL, se não, cria um arquivo local
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# --- MODELO DE DADOS ---
class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date, nullable=False)
    period = db.Column(db.String(20))
    meal_type = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=1.0)
    notes = db.Column(db.String(255))

# --- ROTAS DE NAVEGAÇÃO ---
@app.route("/")
def home():
    return redirect(url_for("vendas"))

@app.route("/dashboard")
def dashboard(): return "<h1>Dashboard</h1><a href='/vendas'>Voltar</a>"

@app.route("/controle")
def controle(): return "<h1>Controle</h1><a href='/vendas'>Voltar</a>"

@app.route("/desperdicio")
def desperdicio(): return "<h1>Desperdício</h1><a href='/vendas'>Voltar</a>"

@app.route("/movimentos")
def movimentos(): return "<h1>Movimentos</h1><a href='/vendas'>Voltar</a>"

@app.route("/producao")
def producao(): return "<h1>Produção</h1><a href='/vendas'>Voltar</a>"

@app.route("/itens")
def itens(): return "<h1>Estoque</h1><a href='/vendas'>Voltar</a>"

@app.route("/compras")
def lista_compras(): return "<h1>Lista de Compras</h1><a href='/vendas'>Voltar</a>"

@app.route("/logout")
def logout(): return redirect(url_for("vendas"))

# --- ROTA PRINCIPAL: VENDAS ---
@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    # 1. Trata a data da consulta
    data_str = request.args.get("data")
    try:
        data_ref = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()
    except:
        data_ref = date.today()

    # 2. Verifica se é edição
    venda_edicao = None
    editar_id = request.args.get("editar", type=int)
    if editar_id:
        venda_edicao = db.session.get(Sale, editar_id)

    # 3. Processa o Formulário (POST)
    if request.method == "POST":
        try:
            # Captura e limpa os valores
            s_date = datetime.strptime(request.form.get("sale_date"), "%Y-%m-%d").date()
            # Substitui vírgula por ponto para o Python entender como número
            u_val = float(request.form.get("unit_value", "0").replace(",", "."))
            qty = float(request.form.get("quantity", "1").replace(",", "."))
            m_type = request.form.get("meal_type")
            
            if venda_edicao:
                venda_edicao.sale_date = s_date
                venda_edicao.meal_type = m_type
                venda_edicao.unit_value = u_val
                venda_edicao.quantity = qty
                db.session.commit()
            else:
                nova_venda = Sale(
                    sale_date=s_date,
                    meal_type=m_type,
                    unit_value=u_val,
                    quantity=qty
                )
                db.session.add(nova_venda)
                db.session.commit()
            
            # Redireciona para a mesma data para ver o resultado
            return redirect(url_for("vendas", data=s_date.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            return f"Erro ao processar dados: {e}"

    # 4. Busca vendas para exibir na tabela
    vendas_dia = Sale.query.filter_by(sale_date=data_ref).all()
    total_hoje = sum((v.unit_value * v.quantity) for v in vendas_dia)

    return render_template("vendas.html",
                           vendas=vendas_dia,
                           total_hoje=total_hoje,
                           venda_edicao=venda_edicao,
                           data_ref=data_ref,
                           meal_types=["Marmitex P", "Marmitex G", "Self-Service", "Bebida"],
                           n_criticos=0)

@app.route("/vendas/excluir/<int:sale_id>", methods=["POST"])
def excluir_venda(sale_id):
    venda = db.session.get(Sale, sale_id)
    if venda:
        db.session.delete(venda)
        db.session.commit()
    return redirect(url_for("vendas"))

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all() # CRIA AS TABELAS CASO NÃO EXISTAM
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
