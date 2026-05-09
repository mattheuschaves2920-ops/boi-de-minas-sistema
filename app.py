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

# ─────────────────────────────
# APP
# ─────────────────────────────

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "boi-minas-2026"
)

# ─────────────────────────────
# DADOS MOCK
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
# USUÁRIOS
# ─────────────────────────────

USERS = [
    {
        "id": 1,
        "name": "Administrador",
        "username": "admin",
        "password": "123456",
        "role": "admin"
    }
]

# ─────────────────────────────
# CONTEXTO GLOBAL
# ─────────────────────────────

@app.context_processor
def inject_globals():

    current_user = None

    if session.get("user"):

        current_user = {
            "id": 1,
            "name": session.get("user"),
            "role": session.get("role", "admin")
        }

    return {
        "n_criticos": 0,
        "current_user": current_user,
        "now": datetime.now
    }

# ─────────────────────────────
# FUNÇÃO LOGIN
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
        return redirect(url_for("dashboard"))

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

    flash("Sessão encerrada.")

    return redirect(url_for("login"))

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
# VENDAS
# ─────────────────────────────

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

# ─────────────────────────────
# ITENS
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

# ─────────────────────────────
# CONTROLE
# ─────────────────────────────

@app.route("/controle")
def controle():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "controle.html",

        daily_groups=[
            "Cozinha",
            "Churrasco",
            "Bar"
        ],

        totais={}
    )

# ─────────────────────────────
# DESPERDÍCIO
# ─────────────────────────────

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

# ─────────────────────────────
# MOVIMENTOS
# ─────────────────────────────

@app.route("/movimentos")
def movimentos():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "movimentos.html",

        movimentos=[],

        items=[],

        mov_edicao=None,

        data_ref=date.today(),

        areas=AREAS,

        setores=[
            "Cozinha",
            "Churrasqueira",
            "Bar"
        ]
    )

# ─────────────────────────────
# PRODUÇÃO
# ─────────────────────────────

@app.route("/producao")
def producao():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "producao.html",

        lista=[],

        items=[],

        data_ref=date.today(),

        setores=[
            "Cozinha",
            "Padaria",
            "Churrasqueira"
        ]
    )

# ─────────────────────────────
# LISTA COMPRAS
# ─────────────────────────────

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

# ─────────────────────────────
# EXPORTAÇÃO XLSX
# ─────────────────────────────

@app.route("/exportar_lista_compras_xlsx")
def exportar_lista_compras_xlsx():

    auth = verificar_login()

    if auth:
        return auth

    flash(
        "Exportação XLSX ainda não implementada."
    )

    return redirect(
        url_for("lista_compras")
    )

# ─────────────────────────────
# METAS
# ─────────────────────────────

@app.route("/metas")
def metas():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "metas.html",

        metas=[]
    )

# ─────────────────────────────
# RELATÓRIO
# ─────────────────────────────

@app.route("/relatorio_gerencial")
def relatorio_gerencial():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "relatorio_gerencial.html",

        data_ref=date.today(),

        mes_ref=date.today(),

        faturamento=0,

        custo=0,

        lucro=0,

        cmv=0,

        refeicoes=0,

        total_perdas=0,

        total_diario=0,

        por_periodo={},

        ranking_vendas=[],

        resumo_setores=[]
    )

# ─────────────────────────────
# USUÁRIOS
# ─────────────────────────────

@app.route("/usuarios")
def usuarios():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "usuarios.html",

        usuarios=USERS,

        roles=[
            "admin",
            "gerente",
            "funcionario"
        ]
    )

# ─────────────────────────────
# AUDITORIA
# ─────────────────────────────

@app.route("/auditoria")
def auditoria():

    auth = verificar_login()

    if auth:
        return auth

    class Logs:
        items = []
        page = 1
        pages = 1
        has_prev = False
        has_next = False

    return render_template(
        "auditoria.html",

        logs=Logs(),

        get_badge_class=lambda x: "success"
    )

# ─────────────────────────────
# EXECUÇÃO
# ─────────────────────────────

if __name__ == "__main__":

    app.run(
        debug=True
    )
