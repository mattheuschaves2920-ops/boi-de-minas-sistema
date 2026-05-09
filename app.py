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
            "name": session.get("user"),
            "role": session.get("role", "admin")
        }

    return {
        "n_criticos": 0,
        "current_user": current_user,
        "now": datetime.now
    }

# ─────────────────────────────
# LOGIN
# ─────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():

    # já logado
    if session.get("user"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":

        username = (
            request.form
            .get("username", "")
            .strip()
        )

        password = (
            request.form
            .get("password", "")
            .strip()
        )

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

            flash(
                "Login realizado com sucesso."
            )

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

    return redirect(
        url_for("login")
    )

# ─────────────────────────────
# PROTEÇÃO
# ─────────────────────────────

def verificar_login():

    if not session.get("user"):
        return redirect(url_for("login"))

    return None

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
