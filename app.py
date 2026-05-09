# =========================================================
# BOI DE MINAS - APP.PY COMPLETO
# MELHORIA:
# - ÁREAS DINÂMICAS
# - SETORES DINÂMICOS
# - TIPOS DE REFEIÇÃO DINÂMICOS
# - LOGIN
# - USUÁRIOS
# - MOVIMENTAÇÃO COM ORIGEM/DESTINO
# =========================================================

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

# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "boi-minas-2026"
)

# =========================================================
# BANCO SIMPLES EM MEMÓRIA
# =========================================================

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

# =========================================================
# CONTEXTO GLOBAL
# =========================================================

@app.context_processor
def inject_globals():

    current_user = None

    if session.get("user"):

        current_user = {
            "name": session.get("user"),
            "role": session.get("role", "admin")
        }

    return {
        "current_user": current_user,
        "now": datetime.now
    }

# =========================================================
# LOGIN REQUIRED
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

        username = request.form.get("username", "").strip()

        password = request.form.get("password", "").strip()

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

            flash("Login realizado com sucesso.")

            return redirect(url_for("dashboard"))

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

    return redirect(url_for("login"))

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
        "vendas.html",

        vendas=[],

        meal_types=MEAL_TYPES,

        total_hoje=0,

        data_ref=date.today(),

        venda_edicao=None
    )

# =========================================================
# ITENS
# =========================================================

@app.route("/itens", methods=["GET", "POST"])
def itens():

    auth = verificar_login()

    if auth:
        return auth

    if request.method == "POST":

        novo_item = {
            "id": len(ITENS) + 1,
            "name": request.form.get("name"),
            "area": request.form.get("area"),
            "stock": request.form.get("stock"),
            "unit": request.form.get("unit"),
            "min_stock": request.form.get("min_stock"),
            "cost": request.form.get("cost")
        }

        ITENS.append(novo_item)

        flash("Item cadastrado com sucesso.")

        return redirect(url_for("itens"))

    return render_template(
        "itens.html",

        itens=ITENS,

        areas=AREAS
    )

# =========================================================
# LISTA COMPRAS
# =========================================================

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

# =========================================================
# MOVIMENTOS
# =========================================================

@app.route("/movimentos", methods=["GET", "POST"])
def movimentos():

    auth = verificar_login()

    if auth:
        return auth

    if request.method == "POST":

        movimento = {
            "id": len(MOVIMENTOS) + 1,

            "mov_date": request.form.get("mov_date"),

            "mov_type": request.form.get("mov_type"),

            "origem": request.form.get("origem"),

            "destino": request.form.get("destino"),

            "setor": request.form.get("setor"),

            "item_name": request.form.get("item_name"),

            "quantity": request.form.get("quantity"),

            "value": request.form.get("value"),

            "detail": request.form.get("detail")
        }

        MOVIMENTOS.append(movimento)

        flash("Movimentação registrada.")

        return redirect(url_for("movimentos"))

    return render_template(
        "movimentos.html",

        movimentos=MOVIMENTOS,

        items=ITENS,

        areas=AREAS,

        setores=SETORES,

        mov_edicao=None,

        data_ref=date.today()
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
        "producao.html",

        lista=[],

        items=ITENS,

        setores=SETORES,

        data_ref=date.today()
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
        "desperdicio.html",

        lista=[],

        items=ITENS,

        desperdicio_edicao=None,

        data_ref=date.today()
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

        novo_usuario = {
            "id": len(USERS) + 1,

            "name": request.form.get("name"),

            "username": request.form.get("username"),

            "password": request.form.get("password"),

            "role": request.form.get("role")
        }

        USERS.append(novo_usuario)

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

# =========================================================
# ESTRUTURA
# =========================================================

@app.route("/estrutura", methods=["GET", "POST"])
def estrutura():

    auth = verificar_login()

    if auth:
        return auth

    tipo = request.args.get("tipo")

    if request.method == "POST":

        nome = request.form.get("nome")

        categoria = request.form.get("categoria")

        if categoria == "area":

            if nome not in AREAS:
                AREAS.append(nome)

                flash("Área adicionada.")

        elif categoria == "setor":

            if nome not in SETORES:
                SETORES.append(nome)

                flash("Setor adicionado.")

        elif categoria == "refeicao":

            if nome not in MEAL_TYPES:
                MEAL_TYPES.append(nome)

                flash("Tipo de refeição adicionado.")

        return redirect(url_for("estrutura"))

    return render_template(
        "estrutura.html",

        areas=AREAS,

        setores=SETORES,

        refeicoes=MEAL_TYPES
    )

# =========================================================
# EXPORTAÇÃO STUB
# =========================================================

@app.route("/exportar_lista_compras_xlsx")
def exportar_lista_compras_xlsx():

    auth = verificar_login()

    if auth:
        return auth

    flash("Exportação ainda em desenvolvimento.")

    return redirect(url_for("lista_compras"))

# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
