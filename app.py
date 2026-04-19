import os
import secrets
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# ─────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────

class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date)
    period = db.Column(db.String(20))
    meal_type = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(255))

# ─────────────────────────────────────────────
# ROTAS DO MENU (Para evitar BuildError)
# ─────────────────────────────────────────────

@app.route("/")
def home():
    return redirect(url_for("vendas"))

@app.route("/dashboard")
def dashboard():
    return "<h1>Dashboard</h1><p>Página em construção</p><a href='/vendas'>Voltar</a>"

@app.route("/controle")
def controle():
    return "<h1>Controle</h1><p>Página em construção</p><a href='/vendas'>Voltar</a>"

@app.route("/desperdicio")
def desperdicio():
    return "<h1>Desperdício</h1><p>Página em construção</p><a href='/vendas'>Voltar</a>"

@app.route("/movimentos")
def movimentos():
    return "<h1>Movimentos</h1><p>Página em construção</p><a href='/vendas'>Voltar</a>"

@app.route("/producao")
def producao():
    return "<h1>Produção</h1><p>Página em construção</p><a href='/vendas'>Voltar</a>"

@app.route("/itens")
def itens():
    return "<h1>Estoque</h1><p>Página em construção</p><a href='/vendas'>Voltar</a>"

@app.route("/compras")
def lista_compras():
    return "<h1>Lista de Compras</h1><p>Página em construção</p><a href='/vendas'>Voltar</a>"

@app.route("/relatorio-gerencial")
def relatorio_gerencial():
    return "<h1>Relatório</h1>"

@app.route("/metas")
def metas(): return "<h1>Metas</h1>"

@app.route("/usuarios")
def usuarios(): return "<h1>Usuários</h1>"

@app.route("/auditoria")
def auditoria(): return "<h1>Auditoria</h1>"

@app.route("/logout")
def logout():
    return redirect(url_for("vendas"))

# ─────────────────────────────────────────────
# VENDAS (A Rota que você está usando)
# ─────────────────────────────────────────────

@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    data_str = request.args.get("data")
    data_ref = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()

    venda_edicao = None
    editar_id = request.args.get("editar", type=int)
    if editar_id:
        venda_edicao = db.session.get(Sale, editar_id)

    tipos_refeicao = ["Marmitex P", "Marmitex G", "Self-Service", "Bebida", "Sobremesa"]

    if request.method == "POST":
        try:
            sale_date = datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date()
            val = float(request.form.get("unit_value", 0))
            qty = float(request.form.get("quantity", 0))

            if venda_edicao:
                venda_edicao.sale_date = sale_date
                venda_edicao.period = request.form.get("period")
                venda_edicao.meal_type = request.form.get("meal_type")
                venda_edicao.unit_value = val
                venda_edicao.quantity = qty
                venda_edicao.notes = request.form.get("notes")
            else:
                db.session.add(Sale(
                    sale_date=sale_date,
                    period=request.form.get("period"),
                    meal_type=request.form.get("meal_type"),
                    unit_value=val,
                    quantity=qty,
                    notes=request.form.get("notes")
                ))
            db.session.commit()
            return redirect(url_for("vendas", data=sale_date.strftime('%Y-%m-%d')))
        except Exception as e:
            return f"Erro ao salvar: {e}"

    vendas_dia = Sale.query.filter_by(sale_date=data_ref).all()
    total_hoje = sum(v.unit_value * v.quantity for v in vendas_dia)

    return render_template("vendas.html",
                           vendas=vendas_dia,
                           total_hoje=total_hoje,
                           venda_edicao=venda_edicao,
                           data_ref=data_ref,
                           meal_types=tipos_refeicao,
                           n_criticos=0) # Evita erro no banner de estoque

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
