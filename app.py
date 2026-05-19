from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from datetime import datetime, date

import os

# =====================================================
# APP
# =====================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "boi-minas-2026"

# =====================================================
# DATABASE
# =====================================================

database_url = os.getenv("DATABASE_URL")

if database_url:

    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

else:

    database_url = "sqlite:///boi_minas.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# =====================================================
# EXTENSIONS
# =====================================================

db = SQLAlchemy(app)

csrf = CSRFProtect(app)

# =====================================================
# USER MODEL
# =====================================================

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        default="funcionario"
    )

# =====================================================
# TIPO VENDA MODEL
# =====================================================

class TipoVenda(db.Model):

    __tablename__ = "tipos_venda"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

# =====================================================
# VENDA MODEL
# =====================================================

class Venda(db.Model):

    __tablename__ = "vendas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    meal_type = db.Column(
        db.String(120),
        nullable=False
    )

    turno = db.Column(
        db.String(50),
        nullable=False
    )

    quantity = db.Column(
        db.Float,
        nullable=False
    )

    unit_value = db.Column(
        db.Float,
        nullable=False
    )

    total = db.Column(
        db.Float,
        nullable=False
    )

    sale_date = db.Column(
        db.Date,
        default=date.today
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# =====================================================
# ITEM MODEL
# =====================================================

class Item(db.Model):

    __tablename__ = "items"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    area = db.Column(
        db.String(100),
        nullable=False
    )

    code = db.Column(
        db.String(120)
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    unit = db.Column(
        db.String(20),
        default="un"
    )

    cost = db.Column(
        db.Float,
        default=0
    )

    stock = db.Column(
        db.Float,
        default=0
    )

    min_stock = db.Column(
        db.Float,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# =====================================================
# MOVIMENTO MODEL
# =====================================================

class Movimento(db.Model):

    __tablename__ = "movimentos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    mov_type = db.Column(
        db.String(30),
        nullable=False
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey("items.id")
    )

    item_name = db.Column(
        db.String(150),
        nullable=False
    )

    area = db.Column(
        db.String(100)
    )

    setor = db.Column(
        db.String(100)
    )

    quantity = db.Column(
        db.Float,
        nullable=False
    )

    value = db.Column(
        db.Float,
        default=0
    )

    detail = db.Column(
        db.String(255)
    )

    mov_date = db.Column(
        db.Date,
        default=date.today
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# =====================================================
# CREATE TABLES
# =====================================================

with app.app_context():

    db.create_all()

    admin = User.query.filter_by(
        username="admin"
    ).first()

    if not admin:

        admin = User(

            name="Administrador",

            username="admin",

            password="123456",

            role="admin"
        )

        db.session.add(admin)

        db.session.commit()

# =====================================================
# CONTEXTO GLOBAL
# =====================================================

@app.context_processor
def inject_globals():

    current_user = None

    if session.get("user"):

        current_user = {

            "name": session.get("user"),

            "role": session.get("role")

        }

    n_criticos = Item.query.filter(
        Item.stock <= Item.min_stock
    ).count()

    return {

        "current_user": current_user,

        "now": datetime.now,

        "n_criticos": n_criticos

    }

# =====================================================
# LOGIN CHECK
# =====================================================

def verificar_login():

    if not session.get("user"):

        return redirect(
            url_for("login")
        )

    return None

# =====================================================
# LOGIN
# =====================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if session.get("user"):

        return redirect(
            url_for("dashboard")
        )

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username"
        )

        password = request.form.get(
            "password"
        )

        user = User.query.filter_by(
            username=username
        ).first()

        if user and user.password == password:

            session["user"] = user.name

            session["role"] = user.role

            session["user_id"] = user.id

            return redirect(
                url_for("dashboard")
            )

        error = "Usuário ou senha inválidos."

    return render_template(
        "login.html",
        error=error
    )

# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )

# =====================================================
# DASHBOARD
# =====================================================

@app.route("/")
@app.route("/dashboard")
def dashboard():

    auth = verificar_login()

    if auth:
        return auth

    faturamento = db.session.query(
        db.func.sum(Venda.total)
    ).scalar() or 0

    custo_estoque = db.session.query(
        db.func.sum(
            Item.stock * Item.cost
        )
    ).scalar() or 0

    return render_template(
        "dashboard.html",

        faturamento=faturamento,
        custo=custo_estoque,
        lucro=faturamento - custo_estoque,
        cmv=0,
        meta_pct=0
    )

# =====================================================
# VENDAS
# =====================================================

@app.route(
    "/vendas",
    methods=["GET", "POST"]
)
def vendas():

    auth = verificar_login()

    if auth:
        return auth

    error = None
    success = None

    data_str = request.args.get("data")

    if data_str:

        data_ref = datetime.strptime(
            data_str,
            "%Y-%m-%d"
        ).date()

    else:

        data_ref = date.today()

    venda_edicao = None

    editar_id = request.args.get("editar")

    if editar_id:

        venda_edicao = Venda.query.get(
            editar_id
        )

    if request.method == "POST":

        try:

            meal_type = request.form.get(
                "meal_type"
            ).strip()

            turno = request.form.get(
                "turno"
            )

            quantity = float(
                request.form.get(
                    "quantity"
                )
            )

            unit_value = float(
                request.form.get(
                    "unit_value"
                )
            )

            sale_date = datetime.strptime(

                request.form.get(
                    "sale_date"
                ),

                "%Y-%m-%d"

            ).date()

            total = quantity * unit_value

            existe_tipo = TipoVenda.query.filter_by(
                nome=meal_type
            ).first()

            if not existe_tipo:

                novo_tipo = TipoVenda(
                    nome=meal_type
                )

                db.session.add(novo_tipo)

            venda_id = request.form.get(
                "venda_id"
            )

            if venda_id:

                venda = Venda.query.get(
                    venda_id
                )

                venda.meal_type = meal_type
                venda.turno = turno
                venda.quantity = quantity
                venda.unit_value = unit_value
                venda.total = total
                venda.sale_date = sale_date

                success = "Venda atualizada."

            else:

                nova = Venda(

                    meal_type=meal_type,

                    turno=turno,

                    quantity=quantity,

                    unit_value=unit_value,

                    total=total,

                    sale_date=sale_date
                )

                db.session.add(nova)

                success = "Venda registrada."

            db.session.commit()

            return redirect(
                url_for(
                    "vendas",
                    data=data_ref.strftime("%Y-%m-%d")
                )
            )

        except Exception as e:

            db.session.rollback()

            error = str(e)

    vendas = Venda.query.filter_by(
        sale_date=data_ref
    ).order_by(
        Venda.id.desc()
    ).all()

    total_hoje = sum(
        v.total for v in vendas
    )

    tipos_venda = TipoVenda.query.order_by(
        TipoVenda.nome.asc()
    ).all()

    return render_template(

        "vendas.html",

        vendas=vendas,

        total_hoje=total_hoje,

        venda_edicao=venda_edicao,

        data_ref=data_ref,

        tipos_venda=tipos_venda,

        error=error,

        success=success
    )

# =====================================================
# EXCLUIR VENDA
# =====================================================

@app.route(
    "/excluir_venda/<int:sale_id>",
    methods=["POST"]
)
def excluir_venda(sale_id):

    auth = verificar_login()

    if auth:
        return auth

    venda = Venda.query.get_or_404(
        sale_id
    )

    db.session.delete(venda)

    db.session.commit()

    flash(
        "Venda removida.",
        "success"
    )

    return redirect(
        url_for("vendas")
    )

# =====================================================
# CONTROLE
# =====================================================

@app.route("/controle")
def controle():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "controle.html"
    )

# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True
    )
