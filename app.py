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

    return {

        "current_user": current_user,

        "now": datetime.now,

        "n_criticos": 0

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

    return render_template(
        "dashboard.html",

        faturamento=0,
        custo=0,
        lucro=0,
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

    data_ref = date.today()

    return render_template(

        "vendas.html",

        vendas=[],

        total_hoje=0,

        venda_edicao=None,

        data_ref=data_ref,

        error=None,

        success=None
    )

# =====================================================
# ITENS
# =====================================================

@app.route("/itens")
def itens():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "itens.html"
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
# PRODUÇÃO
# =====================================================

@app.route(
    "/producao",
    methods=["GET", "POST"]
)
def producao():

    auth = verificar_login()

    if auth:
        return auth

    data_ref = date.today()

    return render_template(

        "producao.html",

        lista=[],

        total_qtd=0,

        total_custo=0,

        setores=[],

        items=[],

        data_ref=data_ref,

        error=None,

        success=None
    )

# =====================================================
# MOVIMENTOS
# =====================================================

@app.route(
    "/movimentos",
    methods=["GET", "POST"]
)
def movimentos():

    auth = verificar_login()

    if auth:
        return auth

    data_ref = date.today()

    return render_template(

        "movimentos.html",

        movimentos=[],

        mov_edicao=None,

        entradas=0,

        saidas=0,

        perdas=0,

        areas=[],

        setores=[],

        items=[],

        data_ref=data_ref,

        error=None,

        success=None
    )

# =====================================================
# DESPERDÍCIO
# =====================================================

@app.route("/desperdicio")
def desperdicio():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "desperdicio.html"
    )

# =====================================================
# COMPRAS
# =====================================================

@app.route("/compras")
def compras():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "compras.html"
    )

# =====================================================
# LISTA COMPRAS
# =====================================================

@app.route("/lista_compras")
def lista_compras():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "lista_compras.html"
    )

# =====================================================
# METAS
# =====================================================

@app.route("/metas")
def metas():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "metas.html"
    )

# =====================================================
# AUDITORIA
# =====================================================

@app.route("/auditoria")
def auditoria():

    auth = verificar_login()

    if auth:
        return auth

    class FakePagination:

        items = []

        page = 1

        pages = 1

        has_prev = False

        has_next = False

    return render_template(

        "auditoria.html",

        logs=FakePagination(),

        get_badge_class=lambda x: ""
    )

# =====================================================
# RELATORIO
# =====================================================

@app.route("/relatorio_gerencial")
def relatorio_gerencial():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(

        "relatorio-gerencial.html",

        faturamento=0,

        custo=0,

        lucro=0,

        cmv=0,

        refeicoes=0,

        total_perdas=0,

        total_diario=0,

        por_periodo={},

        ranking_vendas=[],

        resumo_setores=[],

        ticket_medio=0,

        margem=0,

        data_ref=date.today(),

        mes_ref=date.today()
    )

# =====================================================
# USUARIOS
# =====================================================

@app.route(
    "/usuarios",
    methods=["GET", "POST"]
)
def usuarios():

    auth = verificar_login()

    if auth:
        return auth

    roles = [

        "admin",

        "gerente",

        "caixa",

        "funcionario"

    ]

    if request.method == "POST":

        username = request.form.get(
            "username"
        )

        existe = User.query.filter_by(
            username=username
        ).first()

        if existe:

            flash(
                "Usuário já existe.",
                "error"
            )

            return redirect(
                url_for("usuarios")
            )

        novo = User(

            name=request.form.get("name"),

            username=username,

            password=request.form.get("password"),

            role=request.form.get("role")
        )

        db.session.add(novo)

        db.session.commit()

        flash(
            "Usuário criado com sucesso.",
            "success"
        )

        return redirect(
            url_for("usuarios")
        )

    lista = User.query.all()

    return render_template(

        "usuarios.html",

        usuarios=lista,

        roles=roles,

        error=None,

        success=None
    )

# =====================================================
# EXCLUIR USUARIO
# =====================================================

@app.route(
    "/excluir_usuario/<int:user_id>",
    methods=["POST"]
)
def excluir_usuario(user_id):

    auth = verificar_login()

    if auth:
        return auth

    if session.get("user_id") == user_id:

        flash(
            "Você não pode excluir seu próprio usuário.",
            "error"
        )

        return redirect(
            url_for("usuarios")
        )

    usuario = User.query.get_or_404(
        user_id
    )

    db.session.delete(usuario)

    db.session.commit()

    flash(
        "Usuário removido.",
        "success"
    )

    return redirect(
        url_for("usuarios")
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
