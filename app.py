from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from flask_wtf.csrf import CSRFProtect

from datetime import datetime, date

import os

# =====================================================
# APP
# =====================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "boi-minas-2026"
)

csrf = CSRFProtect(app)

# =====================================================
# DADOS
# =====================================================

USERS = [
    {
        "id": 1,
        "name": "Administrador",
        "username": "admin",
        "password": "123456",
        "role": "admin"
    }
]

AREAS = [
    "Cozinha",
    "Buffet",
    "Bar",
    "Estoque"
]

MEAL_TYPES = [
    "Almoço",
    "Janta",
    "Marmita",
    "Bebidas"
]

# =====================================================
# LOGIN
# =====================================================

def verificar_login():

    if not session.get("user"):
        return redirect(url_for("login"))

    return None

# =====================================================
# CONTEXTO GLOBAL
# =====================================================

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

# =====================================================
# LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = next(
            (
                u for u in USERS
                if u["username"] == username
                and u["password"] == password
            ),
            None
        )

        if user:

            session["user_id"] = user["id"]
            session["user"] = user["name"]
            session["role"] = user["role"]

            flash("Login realizado com sucesso.")

            return redirect(url_for("dashboard"))

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

    flash("Sessão encerrada.")

    return redirect(url_for("login"))

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

# =====================================================
# CONTROLE
# =====================================================

@app.route("/controle", methods=["GET", "POST"])
def controle():

    auth = verificar_login()

    if auth:
        return auth

    grupos = [
        "Buffet",
        "Lanches",
        "Bebidas",
        "Marmitas"
    ]

    resumo = []

    if request.method == "POST":

        flash("Registro salvo com sucesso.")

        return redirect(url_for("controle"))

    return render_template(
        "controle.html",
        grupos=grupos,
        resumo=resumo
    )

# =====================================================
# VENDAS
# =====================================================

@app.route("/vendas")
def vendas():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "vendas.html",

        vendas=[],

        meal_types=MEAL_TYPES,

        total_hoje=0,

        data_ref=date.today(),

        venda_edicao=None
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
        "itens.html",

        itens=[],

        areas=AREAS
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
        "lista_compras.html",

        lista=[],

        total_custo=0
    )

# =====================================================
# DESPERDICIO
# =====================================================

@app.route("/desperdicio")
def desperdicio():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "desperdicio.html",

        lista=[],
        items=[],
        desperdicio_edicao=None,
        error=None,
        data_ref=date.today()
    )

# =====================================================
# MOVIMENTOS
# =====================================================

@app.route("/movimentos")
def movimentos():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "movimentos.html",

        movimentos=[],
        mov_edicao=None,

        areas=AREAS,

        setores=[
            "Cozinha",
            "Buffet",
            "Bar"
        ],

        items=[],

        data_ref=date.today()
    )

# =====================================================
# PRODUCAO
# =====================================================

@app.route("/producao")
def producao():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "producao.html",

        lista=[],

        setores=[
            "Cozinha",
            "Padaria",
            "Buffet"
        ],

        items=[],

        data_ref=date.today()
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

        total_perdas=0,
        total_diario=0,

        refeicoes=0,

        por_periodo={},

        ranking_vendas=[],

        resumo_setores=[],

        data_ref=date.today(),
        mes_ref=date.today()
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
        "metas.html",
        metas=[]
    )

# =====================================================
# USUARIOS
# =====================================================

@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():

    auth = verificar_login()

    if auth:
        return auth

    if request.method == "POST":

        novo = {
            "id": len(USERS) + 1,
            "name": request.form.get("name"),
            "username": request.form.get("username"),
            "password": request.form.get("password"),
            "role": request.form.get("role")
        }

        USERS.append(novo)

        flash("Usuário cadastrado com sucesso.")

        return redirect(url_for("usuarios"))

    return render_template(
        "usuarios.html",

        usuarios=USERS,

        roles=[
            "admin",
            "gerente",
            "funcionario"
        ]
    )

# =====================================================
# EXCLUIR USUARIO
# =====================================================

@app.route("/excluir_usuario/<int:user_id>", methods=["POST"])
def excluir_usuario(user_id):

    auth = verificar_login()

    if auth:
        return auth

    global USERS

    USERS = [
        u for u in USERS
        if u["id"] != user_id
    ]

    flash("Usuário removido.")

    return redirect(url_for("usuarios"))

# =====================================================
# AUDITORIA
# =====================================================

@app.route("/auditoria")
def auditoria():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "auditoria.html",

        logs=[]
    )

# =====================================================
# START
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
