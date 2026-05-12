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
# VENDA MODEL
# =====================================================

class Venda(db.Model):

    __tablename__ = "vendas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    cliente = db.Column(
        db.String(120),
        nullable=False
    )

    valor = db.Column(
        db.Float,
        nullable=False
    )

    data = db.Column(
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
        db.func.sum(Venda.valor)
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

    return render_template(

        "vendas.html",

        vendas=[],

        total_hoje=0,

        venda_edicao=None,

        data_ref=date.today(),

        error=None,

        success=None
    )

# =====================================================
# ITENS
# =====================================================

@app.route(
    "/itens",
    methods=["GET", "POST"]
)
def itens():

    auth = verificar_login()

    if auth:
        return auth

    error = None

    success = None

    areas = [

        "Açougue",
        "Cozinha",
        "Bebidas",
        "Limpeza",
        "Buffet",
        "Freezer",
        "Depósito"
    ]

    if request.method == "POST":

        try:

            novo = Item(

                area=request.form.get(
                    "area"
                ),

                code=request.form.get(
                    "code"
                ),

                name=request.form.get(
                    "name"
                ),

                unit=request.form.get(
                    "unit"
                ),

                cost=float(
                    request.form.get(
                        "cost",
                        0
                    )
                ),

                stock=float(
                    request.form.get(
                        "stock",
                        0
                    )
                ),

                min_stock=float(
                    request.form.get(
                        "min_stock",
                        0
                    )
                )
            )

            db.session.add(novo)

            db.session.commit()

            success = "Item cadastrado."

        except Exception as e:

            db.session.rollback()

            error = str(e)

    itens = Item.query.order_by(
        Item.name.asc()
    ).all()

    return render_template(

        "itens.html",

        itens=itens,

        areas=areas,

        error=error,

        success=success
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

    error = None

    success = None

    data_ref = date.today()

    areas = [

        "Açougue",
        "Cozinha",
        "Bebidas",
        "Limpeza",
        "Buffet",
        "Freezer",
        "Depósito"
    ]

    setores = [

        "Estoque",
        "Produção",
        "Buffet",
        "Delivery",
        "Cozinha"
    ]

    items = Item.query.order_by(
        Item.name.asc()
    ).all()

    if request.method == "POST":

        try:

            item_id = request.form.get(
                "item_id"
            )

            item = Item.query.get(
                item_id
            )

            mov_type = request.form.get(
                "mov_type"
            )

            quantity = float(
                request.form.get(
                    "quantity",
                    0
                )
            )

            unit_cost = float(
                request.form.get(
                    "unit_cost",
                    0
                ) or 0
            )

            mov_date = datetime.strptime(

                request.form.get(
                    "mov_date"
                ),

                "%Y-%m-%d"

            ).date()

            if mov_type == "Entrada":

                item.stock += quantity

                if unit_cost > 0:

                    item.cost = unit_cost

            else:

                item.stock -= quantity

            novo = Movimento(

                mov_type=mov_type,

                item_id=item.id,

                item_name=item.name,

                area=request.form.get(
                    "area"
                ),

                setor=request.form.get(
                    "setor"
                ),

                quantity=quantity,

                value=quantity * item.cost,

                detail=request.form.get(
                    "detail"
                ),

                mov_date=mov_date
            )

            db.session.add(novo)

            db.session.commit()

            success = "Movimentação registrada."

            return redirect(
                url_for("movimentos")
            )

        except Exception as e:

            db.session.rollback()

            error = str(e)

    movimentos = Movimento.query.order_by(
        Movimento.id.desc()
    ).all()

    entradas = sum(
        m.quantity
        for m in movimentos
        if m.mov_type == "Entrada"
    )

    saidas = sum(
        m.quantity
        for m in movimentos
        if m.mov_type == "Saida"
    )

    perdas = sum(
        m.quantity
        for m in movimentos
        if m.mov_type == "Perda"
    )

    return render_template(

        "movimentos.html",

        movimentos=movimentos,

        mov_edicao=None,

        entradas=entradas,

        saidas=saidas,

        perdas=perdas,

        areas=areas,

        setores=setores,

        items=items,

        data_ref=data_ref,

        error=error,

        success=success
    )

# =====================================================
# DESPERDÍCIO
# =====================================================

@app.route(
    "/desperdicio",
    methods=["GET", "POST"]
)
def desperdicio():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(

        "desperdicio.html",

        lista=[],

        desperdicio_edicao=None,

        items=[],

        data_ref=date.today(),

        error=None
    )

# =====================================================
# EXCLUIR DESPERDICIO
# =====================================================

@app.route(
    "/excluir_desperdicio/<int:waste_id>",
    methods=["POST"]
)
def excluir_desperdicio(waste_id):

    auth = verificar_login()

    if auth:
        return auth

    flash(
        "Desperdício removido.",
        "success"
    )

    return redirect(
        url_for("desperdicio")
    )

# =====================================================
# EDITAR DESPERDICIO
# =====================================================

@app.route(
    "/editar_desperdicio/<int:waste_id>",
    methods=["POST"]
)
def editar_desperdicio(waste_id):

    return redirect(
        url_for(
            "desperdicio",
            editar=waste_id
        )
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

    return render_template(
        "producao.html"
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
# RELATORIO GERENCIAL
# =====================================================

@app.route("/relatorio_gerencial")
def relatorio_gerencial():

    auth = verificar_login()

    if auth:
        return auth

    faturamento = db.session.query(
        db.func.sum(Venda.valor)
    ).scalar() or 0

    custo = db.session.query(
        db.func.sum(
            Item.stock * Item.cost
        )
    ).scalar() or 0

    lucro = faturamento - custo

    return render_template(

        "relatorio-gerencial.html",

        faturamento=faturamento,

        custo=custo,

        lucro=lucro,

        cmv=0,

        refeicoes=0,

        total_perdas=0,

        total_diario=faturamento,

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
