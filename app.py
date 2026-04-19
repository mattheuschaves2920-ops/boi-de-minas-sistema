import os
import secrets
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ─────────────────────────────────────────────
# APP CONFIG
# ─────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _parse_float(value, default=0.0):
    try:
        return float(str(value or "0").replace(",", "."))
    except:
        return default


def _ajustar_estoque(item, mov_type, qty):
    qty = float(qty or 0)

    if mov_type == "Entrada":
        item.stock += qty
    else:
        item.stock = max(0.0, item.stock - qty)

# ─────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    username = db.Column(db.String(80), unique=True)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(30), default="operador")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(80))
    code = db.Column(db.String(60))
    name = db.Column(db.String(120))
    category = db.Column(db.String(80))
    unit = db.Column(db.String(20), default="un")
    cost = db.Column(db.Float, default=0.0)
    stock = db.Column(db.Float, default=0.0)
    min_stock = db.Column(db.Float, default=0.0)


class Movement(db.Model):
    __tablename__ = "movements"
    id = db.Column(db.Integer, primary_key=True)
    mov_date = db.Column(db.Date)
    mov_type = db.Column(db.String(20))
    area = db.Column(db.String(80))
    setor = db.Column(db.String(80))
    item_id = db.Column(db.Integer)
    item_name = db.Column(db.String(120))
    quantity = db.Column(db.Float, default=0.0)
    value = db.Column(db.Float, default=0.0)
    detail = db.Column(db.String(255))


class Production(db.Model):
    __tablename__ = "productions"
    id = db.Column(db.Integer, primary_key=True)
    prod_date = db.Column(db.Date)
    setor = db.Column(db.String(80))
    item_id = db.Column(db.Integer)
    item_name = db.Column(db.String(120))
    quantity = db.Column(db.Float, default=0.0)
    cost = db.Column(db.Float, default=0.0)


class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date)
    period = db.Column(db.String(20))
    meal_type = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(255))


class Waste(db.Model):
    __tablename__ = "wastes"
    id = db.Column(db.Integer, primary_key=True)
    waste_date = db.Column(db.Date)
    item_id = db.Column(db.Integer)
    item_name = db.Column(db.String(120))
    quantity = db.Column(db.Float, default=0.0)
    reason = db.Column(db.String(80))
    value = db.Column(db.Float, default=0.0)

# ─────────────────────────────────────────────
# ROTAS PRINCIPAIS (CORREÇÃO DO ERRO 404)
# ─────────────────────────────────────────────

@app.route("/")
def home():
    return redirect(url_for("vendas"))

@app.route("/setup")
def setup():
    with app.app_context():
        db.create_all()
    return "Banco de dados criado com sucesso!"

# ─────────────────────────────────────────────
# VENDAS
# ─────────────────────────────────────────────

@app.route("/vendas", methods=["GET", "POST"])
def vendas():

    data_ref = date.today()
    venda_edicao = None

    editar_id = request.args.get("editar", type=int)
    if editar_id:
        venda_edicao = db.session.get(Sale, editar_id)

    if request.method == "POST":

        sale_date = datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date()
        unit_value = _parse_float(request.form.get("unit_value"))
        quantity = _parse_float(request.form.get("quantity"))

        if venda_edicao:
            venda_edicao.sale_date = sale_date
            venda_edicao.period = request.form.get("period")
            venda_edicao.meal_type = request.form.get("meal_type")
            venda_edicao.unit_value = unit_value
            venda_edicao.quantity = quantity
            venda_edicao.notes = request.form.get("notes")
        else:
            db.session.add(Sale(
                sale_date=sale_date,
                period=request.form.get("period"),
                meal_type=request.form.get("meal_type"),
                unit_value=unit_value,
                quantity=quantity,
                notes=request.form.get("notes"),
            ))

        db.session.commit()
        return redirect(url_for("vendas"))

    vendas = Sale.query.filter_by(sale_date=data_ref).all()
    total_hoje = sum((v.unit_value or 0) * (v.quantity or 0) for v in vendas)

    return render_template("vendas.html",
                           vendas=vendas,
                           total_hoje=total_hoje,
                           venda_edicao=venda_edicao)

# ─────────────────────────────────────────────
# MOVIMENTOS
# ─────────────────────────────────────────────

@app.route("/movimentos", methods=["GET", "POST"])
def movimentos():

    mov_edicao = None
    editar_id = request.args.get("editar", type=int)

    if editar_id:
        mov_edicao = db.session.get(Movement, editar_id)

    if request.method == "POST":

        mov_date = datetime.strptime(request.form["mov_date"], "%Y-%m-%d").date()
        mov_type = request.form.get("mov_type")
        qty = _parse_float(request.form.get("quantity"))

        item_id = request.form.get("item_id", type=int)
        item = Item.query.get(item_id)

        # EDITAR
        if mov_edicao:

            old_item = Item.query.get(mov_edicao.item_id)
            if old_item:
                _ajustar_estoque(old_item, mov_edicao.mov_type, -mov_edicao.quantity)

            mov_edicao.mov_date = mov_date
            mov_edicao.mov_type = mov_type
            mov_edicao.quantity = qty
            mov_edicao.value = _parse_float(request.form.get("value"))
            mov_edicao.detail = request.form.get("detail")

            mov_edicao.item_id = item.id if item else None
            mov_edicao.item_name = item.name if item else "—"

            if item:
                _ajustar_estoque(item, mov_type, qty)

        # NOVO
        else:

            m = Movement(
                mov_date=mov_date,
                mov_type=mov_type,
                area=request.form.get("area"),
                setor=request.form.get("setor"),
                item_id=item.id if item else None,
                item_name=item.name if item else "—",
                quantity=qty,
                value=qty * (item.cost or 0),
                detail=request.form.get("detail"),
            )

            if item:
                _ajustar_estoque(item, mov_type, qty)

            db.session.add(m)

        db.session.commit()
        return redirect(url_for("movimentos"))

    lista = Movement.query.all()
    return render_template("movimentos.html", movimentos=lista)

# ─────────────────────────────────────────────
# PRODUÇÃO
# ─────────────────────────────────────────────

@app.route("/producao", methods=["POST"])
def producao():

    item = Item.query.get(request.form.get("item_id", type=int))

    if item:
        qty = _parse_float(request.form.get("quantity"))

        db.session.add(Production(
            prod_date=datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date(),
            setor=request.form.get("setor"),
            item_id=item.id,
            item_name=item.name,
            quantity=qty,
            cost=qty * (item.cost or 0),
        ))

        _ajustar_estoque(item, "Entrada", qty)

        db.session.commit()

    return redirect(url_for("producao"))

# ─────────────────────────────────────────────
# DESPERDÍCIO
# ─────────────────────────────────────────────

@app.route("/desperdicio", methods=["POST"])
def desperdicio():

    item = Item.query.get(request.form.get("item_id", type=int))

    if item:
        qty = _parse_float(request.form.get("quantity"))

        db.session.add(Waste(
            waste_date=datetime.strptime(request.form["waste_date"], "%Y-%m-%d").date(),
            item_id=item.id,
            item_name=item.name,
            quantity=qty,
            reason=request.form.get("reason"),
            value=qty * (item.cost or 0),
        ))

        _ajustar_estoque(item, "Saida", qty)

        db.session.commit()

    return redirect(url_for("desperdicio"))

# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
