import os
import secrets
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect 
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# --- MODELOS ---
class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date)
    period = db.Column(db.String(20))
    meal_type = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(255))

# --- HELPERS ---
def _parse_float(value, default=0.0):
    try:
        return float(str(value or "0").replace(",", "."))
    except:
        return default

# --- ROTAS NOVAS (Para evitar BuildError) ---

@app.route("/")
def home():
    return redirect(url_for("vendas"))

@app.route("/dashboard")
def dashboard():
    # Rota temporária para o erro sumir
    return "<h1>Dashboard em desenvolvimento</h1><a href='/vendas'>Voltar para Vendas</a>"

@app.route("/estoque")
def estoque():
    return "<h1>Estoque em desenvolvimento</h1><a href='/vendas'>Voltar para Vendas</a>"

# --- ROTA DE VENDAS ---

@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    data_str = request.args.get("data")
    if data_str:
        try:
            data_ref = datetime.strptime(data_str, "%Y-%m-%d").date()
        except:
            data_ref = date.today()
    else:
        data_ref = date.today()

    venda_edicao = None
    editar_id = request.args.get("editar", type=int)
    if editar_id:
        venda_edicao = db.session.get(Sale, editar_id)

    tipos_refeicao = ["Marmitex P", "Marmitex G", "Self-Service", "Bebida", "Sobremesa"]

    if request.method == "POST":
        sale_date = datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date()
        unit_val = _parse_float(request.form.get("unit_value"))
        qty = _parse_float(request.form.get("quantity"))

        if venda_edicao:
            venda_edicao.sale_date = sale_date
            venda_edicao.period = request.form.get("period")
            venda_edicao.meal_type = request.form.get("meal_type")
            venda_edicao.unit_value = unit_val
            venda_edicao.quantity = qty
            venda_edicao.notes = request.form.get("notes")
        else:
            nova_venda = Sale(
                sale_date=sale_date,
                period=request.form.get("period"),
                meal_type=request.form.get("meal_type"),
                unit_value=unit_val,
                quantity=qty,
                notes=request.form.get("notes"),
            )
            db.session.add(nova_venda)

        db.session.commit()
        return redirect(url_for("vendas", data=sale_date.strftime('%Y-%m-%d')))

    vendas_dia = Sale.query.filter_by(sale_date=data_ref).all()
    total_hoje = sum((v.unit_value or 0) * (v.quantity or 0) for v in vendas_dia)

    return render_template("vendas.html",
                           vendas=vendas_dia,
                           total_hoje=total_hoje,
                           venda_edicao=venda_edicao,
                           data_ref=data_ref,
                           meal_types=tipos_refeicao)

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
