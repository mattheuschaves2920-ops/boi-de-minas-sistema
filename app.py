import os

from datetime import datetime, date

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for
)

from flask_sqlalchemy import SQLAlchemy

from flask_wtf.csrf import CSRFProtect

# ─────────────────────────────
# APP
# ─────────────────────────────

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "boi-minas-2026"
)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///boi_de_minas.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ─────────────────────────────
# EXTENSÕES
# ─────────────────────────────

db = SQLAlchemy(app)

csrf = CSRFProtect(app)

# ─────────────────────────────
# DADOS
# ─────────────────────────────

MEAL_TYPES = [
    "Almoço",
    "Janta",
    "Marmita",
    "Bebidas"
]

AREAS = [
    "Cozinha",
    "Churrasqueira",
    "Bar",
    "Estoque",
    "Limpeza"
]

# ─────────────────────────────
# MODEL USUÁRIO
# ─────────────────────────────

class User(db.Model):

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
        nullable=False
    )

# ─────────────────────────────
# BANCO
# ─────────────────────────────

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

# ─────────────────────────────
# CONTEXTO
# ─────────────────────────────

@app.context_processor
def inject_globals():

    current_user = None

    if session.get("user"):

        current_user = {
            "id": session.get("user_id"),
            "name": session.get("user"),
            "role": session.get("role")
        }

    return {
        "current_user": current_user,
        "n_criticos": 0,
        "now": datetime.now
    }

# ─────────────────────────────
# LOGIN
# ─────────────────────────────

def verificar_login():

    if not session.get("user"):
        return redirect(url_for("login"))

    return None

# ─────────────────────────────
# LOGIN
# ─────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user"):
        return redirect(
            url_for("dashboard")
        )

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        user = User.query.filter_by(
            username=username,
            password=password
        ).first()

        if user:

            session["user_id"] = user.id

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

# ─────────────────────────────
# LOGOUT
# ─────────────────────────────

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )

# ─────────────────────────────
# DASHBOARD
# ─────────────────────────────

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

# ─────────────────────────────
# USUÁRIOS
# ─────────────────────────────

@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():

    auth = verificar_login()

    if auth:
        return auth

    if request.method == "POST":

        name = request.form.get("name")

        username = request.form.get("username")

        password = request.form.get("password")

        role = request.form.get("role")

        existe = User.query.filter_by(
            username=username
        ).first()

        if existe:

            flash("Usuário já existe.")

        else:

            novo = User(
                name=name,
                username=username,
                password=password,
                role=role
            )

            db.session.add(novo)

            db.session.commit()

            flash("Usuário criado.")

            return redirect(
                url_for("usuarios")
            )

    usuarios = User.query.all()

    return render_template(
        "usuarios.html",

        usuarios=usuarios,

        roles=[
            "admin",
            "gerente",
            "funcionario"
        ]
    )

# ─────────────────────────────
# EXCLUIR USUÁRIO
# ─────────────────────────────

@app.route("/excluir_usuario/<int:user_id>", methods=["POST"])
def excluir_usuario(user_id):

    auth = verificar_login()

    if auth:
        return auth

    if session.get("user_id") == user_id:

        flash(
            "Você não pode excluir seu próprio usuário."
        )

        return redirect(
            url_for("usuarios")
        )

    user = User.query.get(user_id)

    if user:

        db.session.delete(user)

        db.session.commit()

        flash("Usuário removido.")

    return redirect(
        url_for("usuarios")
    )

# ─────────────────────────────
# ROTAS BÁSICAS
# ─────────────────────────────

@app.route("/itens")
def itens():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "itens.html",
        itens=[],
        areas=AREAS
    )

@app.route("/lista_compras")
def lista_compras():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "lista_compras.html",
        lista=[],
        total_custo=0
    )

@app.route("/exportar_lista_compras_xlsx")
def exportar_lista_compras_xlsx():

    flash(
        "Exportação ainda não implementada."
    )

    return redirect(
        url_for("lista_compras")
    )

# ─────────────────────────────
# EXECUÇÃO
# ─────────────────────────────

if __name__ == "__main__":

    app.run(
        debug=True
    )
