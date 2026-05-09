from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from datetime import datetime, date

import os

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "boi-minas-2026"
)

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
    "Estoque"
]

SETORES = [
    "Produção",
    "Compras",
    "Administrativo"
]

MEAL_TYPES = [
    "Almoço",
    "Janta"
]

ITENS = []

MOVIMENTOS = []

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
            "name": session.get("user"),
            "role": session.get("role")
        }

    return {
        "current_user": current_user,
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

            session["user"] = user["name"]
            session["role"] = user["role"]

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
# CONTROLE
# =====================================================

@app.route("/controle")
def controle():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "controle.html",

        grupos=[
            "Buffet",
            "Lanches",
            "Bebidas",
            "Marmitas"
        ],

        resumo=[],

        data_ref=date.today()
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
        "lista-compras.html",

        lista=[],

        total_custo=0
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

        items=[],

        areas=AREAS,

        setores=SETORES,

        mov_edicao=None,

        data_ref=date.today()
    )

# =====================================================
# PRODUÇÃO
# =====================================================

@app.route("/producao")
def producao():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "producao.html",

        lista=[],

        items=[],

        setores=SETORES,

        data_ref=date.today()
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
        "desperdicio.html",

        lista=[],

        items=[],

        desperdicio_edicao=None,

        data_ref=date.today()
    )

# =====================================================
# USUÁRIOS
# =====================================================

@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():

    auth = verificar_login()

    if auth:
        return auth

    if request.method == "POST":

        USERS.append({

            "id": len(USERS) + 1,

            "name": request.form.get("name"),

            "username": request.form.get("username"),

            "password": request.form.get("password"),

            "role": request.form.get("role")
        })

        flash("Usuário criado com sucesso.")

        return redirect(url_for("usuarios"))

    return render_template(
        "usuarios.html",

        usuarios=USERS,

        roles=[
            "admin",
            "gerente",
            "operador"
        ]
    )

# =====================================================
# EXPORTAÇÃO
# =====================================================

@app.route("/exportar_lista_compras_xlsx")
def exportar_lista_compras_xlsx():

    auth = verificar_login()

    if auth:
        return auth

    flash("Exportação em desenvolvimento.")

    return redirect(url_for("lista_compras"))

# =====================================================
# EXECUÇÃO
# =====================================================

if __name__ == "__main__":

    app.run(debug=True)
