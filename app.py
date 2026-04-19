import os
import io
import time
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps
from decimal import Decimal

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, send_file, abort)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ─── APP & CONFIG ────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

uri = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = uri

db = SQLAlchemy(app)

# ─── HELPERS CORRIGIDOS ──────────────────────────────────────────────────────

def _parse_float(value, default=0.0):
    try:
        return float(str(value or "0").replace(",", "."))
    except:
        return default


def _parse_money(value, default=0):
    try:
        return Decimal(str(value or "0").replace(",", "."))
    except:
        return Decimal(default)


def _ajustar_estoque(item, mov_type, qty):
    qty = float(qty or 0)

    if mov_type == "Entrada":
        item.stock += qty
    else:
        item.stock = max(0.0, item.stock - qty)


# ─── MODELOS (mantidos) ─────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="operador")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(80))
    code = db.Column(db.String(60))
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80))
    unit = db.Column(db.String(20), default="un")
    cost = db.Column(db.Float, default=0.0)
    stock = db.Column(db.Float, default=0.0)
    min_stock = db.Column(db.Float, default=0.0)


class Movement(db.Model):
    __tablename__ = "movements"
    id = db.Column(db.Integer, primary_key=True)
    mov_date = db.Column(db.Date, nullable=False)
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
    prod_date = db.Column(db.Date, nullable=False)
    setor = db.Column(db.String(80))
    item_id = db.Column(db.Integer)
    item_name = db.Column(db.String(120))
    quantity = db.Column(db.Float, default=0.0)
    cost = db.Column(db.Float, default=0.0)


class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date, nullable=False)
    period = db.Column(db.String(20))
    meal_type = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(255))


class Waste(db.Model):
    __tablename__ = "wastes"
    id = db.Column(db.Integer, primary_key=True)
    waste_date = db.Column(db.Date, nullable=False)
    item_id = db.Column(db.Integer)
    item_name = db.Column(db.String(120))
    quantity = db.Column(db.Float, default=0.0)
    reason = db.Column(db.String(80))
    value = db.Column(db.Float, default=0.0)
    photo_path = db.Column(db.String(255))


# ─── VENDAS (CORRIGIDO) ──────────────────────────────────────────────────────

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

        meal_type = request.form.get("meal_type")

        if venda_edicao:
            venda_edicao.sale_date = sale_date
            venda_edicao.period = request.form.get("period")
            venda_edicao.meal_type = meal_type
            venda_edicao.unit_value = unit_value
            venda_edicao.quantity = quantity
            venda_edicao.notes = request.form.get("notes")
        else:
            v = Sale(
                sale_date=sale_date,
                period=request.form.get("period"),
                meal_type=meal_type,
                unit_value=unit_value,
                quantity=quantity,
                notes=request.form.get("notes"),
            )
            db.session.add(v)

        db.session.commit()
        return redirect(url_for("vendas"))

    vendas = Sale.query.filter_by(sale_date=data_ref).all()
    total_hoje = sum((v.unit_value or 0) * (v.quantity or 0) for v in vendas)

    return render_template("vendas.html",
                           vendas=vendas,
                           total_hoje=total_hoje,
                           venda_edicao=venda_edicao)


# ─── MOVIMENTOS (CORRIGIDO PRINCIPAL) ────────────────────────────────────────

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

        if mov_edicao:

            old_item = mov_edicao.item_id
            old_type = mov_edicao.mov_type
            old_qty = mov_edicao.quantity or 0

            item = Item.query.get(old_item) if old_item else None
            if item:
                _ajustar_estoque(item, old_type, -old_qty)

            mov_edicao.mov_date = mov_date
            mov_edicao.mov_type = mov_type
            mov_edicao.quantity = qty
            mov_edicao.value = _parse_float(request.form.get("value"))
            mov_edicao.detail = request.form.get("detail")

            item_new = Item.query.get(old_item) if old_item else None
            if item_new:
                _ajustar_estoque(item_new, mov_type, qty)

        else:
            item_id = request.form.get("item_id", type=int)
            item = Item.query.get(item_id)

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


# ─── PRODUÇÃO (CORRIGIDO) ────────────────────────────────────────────────────

@app.route("/producao", methods=["POST"])
def producao():

    item_id = request.form.get("item_id", type=int)
    item = Item.query.get(item_id)

    if not item:
        return redirect(url_for("producao"))

    qty = _parse_float(request.form.get("quantity"))

    p = Production(
        prod_date=datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date(),
        setor=request.form.get("setor"),
        item_id=item.id,
        item_name=item.name,
        quantity=qty,
        cost=qty * (item.cost or 0),
    )

    item.stock += qty

    db.session.add(p)
    db.session.commit()

    return redirect(url_for("producao"))


# ─── WASTE (CORRIGIDO) ──────────────────────────────────────────────────────

@app.route("/desperdicio", methods=["POST"])
def desperdicio():

    qty = _parse_float(request.form.get("quantity"))

    item_id = request.form.get("item_id", type=int)
    item = Item.query.get(item_id)

    if item:
        w = Waste(
            waste_date=datetime.strptime(request.form["waste_date"], "%Y-%m-%d").date(),
            item_id=item.id,
            item_name=item.name,
            quantity=qty,
            reason=request.form.get("reason"),
            value=qty * (item.cost or 0),
        )

        item.stock = max(0.0, item.stock - qty)

        db.session.add(w)
        db.session.commit()

    return redirect(url_for("desperdicio"))


# ─── APP RUN ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
