import os
import secrets
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)

# Configurações
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# --- MODELO ---
class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=1.0)

# --- CONTEXTO GLOBAL (Evita erro de variáveis faltando no base.html) ---
@app.context_processor
def inject_globals():
    return {
        'current_user': None,
        'n_criticos': 0
    }

# --- ROTAS OBRIGATÓRIAS (Uma para cada link do seu menu) ---

@app.route("/")
def home():
    return redirect(url_for("vendas"))

@app.route("/dashboard")
def dashboard():
    return "<h1>Dashboard</h1><a href='/vendas'>Voltar</a>"

@app.route("/controle")
def controle():
    return "<h1>Controle</h1><a href='/vendas'>Voltar</a>"

@app.route("/desperdicio")
def desperdicio():
    return "<h1>Desperdício</h1><a href='/vendas'>Voltar</a>"

@app.route("/movimentos")
def movimentos():
    return "<h1>Movimentos</h1><a href='/vendas'>Voltar</a>"

@app.route("/producao")
def producao():
    return "<h1>Produção</h1><a href='/vendas'>Voltar</a>"

@app.route("/itens")
def itens():
    return "<h1>Estoque</h1><a href='/vendas'>Voltar</a>"

@app.route("/lista_compras")
def lista_compras():
    return "<h1>Lista de Compras</h1><a href='/vendas'>Voltar</a>"

@app.route("/relatorio_gerencial")
def relatorio_gerencial():
    return "<h1>Relatório</h1><a href='/vendas'>Voltar</a>"

@app.route("/metas")
def metas():
    return "<h1>Metas</h1><a href='/vendas'>Voltar</a>"

@app.route("/usuarios")
def usuarios():
    return "<h1>Usuários</h1><a href='/vendas'>Voltar</a>"

@app.route("/auditoria")
def auditoria():
    return "<h1>Auditoria</h1><a href='/vendas'>Voltar</a>"

@app.route("/logout")
def logout():
    return redirect(url_for("vendas"))

# --- ROTA DE VENDAS ---
@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    data_str = request.args.get("data")
    try:
        data_ref = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()
    except:
        data_ref = date.today()

    if request.method == "POST":
        try:
            s_date = datetime.strptime(request.form.get("sale_date"), "%Y-%m-%d").date()
            u_val = float(request.form.get("unit_value", "0").replace(",", "."))
            qty = float(request.form.get("quantity", "1").replace(",", "."))
            
            nova_venda = Sale(
                sale_date=s_date,
                meal_type=request.form.get("meal_type"),
                unit_value=u_val,
                quantity=qty
            )
            db.session.add(nova_venda)
            db.session.commit()
            return redirect(url_for("vendas", data=s_date.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            return f"Erro ao salvar: {e}", 500

    vendas_dia = Sale.query.filter_by(sale_date=data_ref).all()
    total_hoje = sum((v.unit_value * v.quantity) for v in vendas_dia)

    return render_template("vendas.html",
                           vendas=vendas_dia,
                           total_hoje=total_hoje,
                           data_ref=data_ref,
                           meal_types=["Marmitex P", "Marmitex G", "Self-Service", "Bebida"])

@app.route("/vendas/excluir/<int:sale_id>", methods=["POST"])
def excluir_venda(sale_id):
    venda = db.session.get(Sale, sale_id)
    if venda:
        db.session.delete(venda)
        db.session.commit()
    return redirect(url_for("vendas"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
