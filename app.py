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

from datetime import datetime, date

import os

# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "boi-minas-2026"
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# =========================================================
# DATABASE
# =========================================================

db = SQLAlchemy(app)

# =========================================================
# RESET TEMPORÁRIO DO BANCO
# REMOVER DEPOIS DO PRIMEIRO DEPLOY
# =========================================================

with app.app_context():
    db.drop_all()
    db.create_all()

# =========================================================
# MODELS
# =========================================================

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(120),
        nullable=False
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(120),
        nullable=False
    )

    role = db.Column(
        db.String(30),
        default="funcionario"
    )

# =========================================================
# CRIAR ADMIN
# =========================================================

with app.app_context():

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

# =========================================================
# CONTEXTO GLOBAL
# =========================================================

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
        "now": datetime.now
    }

# =========================================================
# VERIFICAR LOGIN
# =========================================================

def verificar_login():

    if not session.get("user"):
        return redirect(url_for("login"))

    return None

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user"):
        return redirect(url_for("dashboard"))

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

            flash("Login realizado.")

            return redirect(
                url_for("dashboard")
            )

        error = "Usuário ou senha inválidos."

    return render_template(
        "login.html",
        error=error
    )

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("Sessão encerrada.")

    return redirect(
        url_for("login")
    )

# =========================================================
# DASHBOARD
# =========================================================

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
        refeicoes=0,
        lucro=0,
        cmv=0,

        desperdicio=0,
        desperdicio_mes=0,

        labels_grafico=[],
        valores_grafico=[],

        vendas_por_periodo_labels=[],
        vendas_por_periodo_values=[],

        meta_valor=0,
        meta_pct=0
    )

# =========================================================
# VENDAS
# =========================================================

@app.route("/vendas")
def vendas():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "vendas.html"
    )

# =========================================================
# CONTROLE
# =========================================================

@app.route("/controle")
def controle():

    auth = verificar_login()

    if auth:
        return auth

    grupos = [
        "Buffet",
        "Lanches",
        "Bebidas",
        "Sobremesas"
    ]

    resumo = []

    return render_template(
        "controle.html",
        grupos=grupos,
        resumo=resumo
    )

# =========================================================
# DESPERDÍCIO
# =========================================================

@app.route("/desperdicio")
def desperdicio():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "desperdicio.html"
    )

# =========================================================
# MOVIMENTOS
# =========================================================

@app.route("/movimentos")
def movimentos():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "movimentos.html"
    )

# =========================================================
# PRODUÇÃO
# =========================================================

@app.route("/producao")
def producao():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "producao.html"
    )

# =========================================================
# ESTOQUE
# =========================================================

@app.route("/estoque")
def estoque():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "estoque.html"
    )

# =========================================================
# COMPRAS
# =========================================================

@app.route("/compras")
def compras():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "compras.html"
    )

# =========================================================
# GERENCIAL
# =========================================================

@app.route("/relatorio_gerencial")
def relatorio_gerencial():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "relatorio-gerencial.html",

        faturamento=0,
        despesas=0,
        lucro=0,
        vendas=0,
        ticket=0,
        desperdicio=0,

        mes_ref=date.today()
    )

# =========================================================
# METAS
# =========================================================

@app.route("/metas")
def metas():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "metas.html"
    )

# =========================================================
# USUÁRIOS
# =========================================================

@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():

    auth = verificar_login()

    if auth:
        return auth

    if request.method == "POST":

        novo = User(
            name=request.form.get("name"),
            username=request.form.get("username"),
            password=request.form.get("password"),
            role=request.form.get("role")
        )

        db.session.add(novo)
        db.session.commit()

        flash("Usuário criado.")

        return redirect(
            url_for("usuarios")
        )

    usuarios_db = User.query.all()

    return render_template(
        "usuarios.html",
        usuarios=usuarios_db
    )

# =========================================================
# AUDITORIA
# =========================================================

@app.route("/auditoria")
def auditoria():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "auditoria.html"
    )

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
