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

            "id": session.get("user_id"),

            "name": session.get("user"),

            "role": session.get("role")
        }

    return {

        "current_user": current_user,

        "now": datetime.now
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

    return render_template(
        "dashboard.html",
        faturamento=faturamento,
        meta_pct=0
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

    if session.get("role") != "admin":

        return redirect(
            url_for("dashboard")
        )

    error = None
    success = None

    if request.method == "POST":

        try:

            name = request.form.get(
                "name"
            ).strip()

            username = request.form.get(
                "username"
            ).strip()

            password = request.form.get(
                "password"
            ).strip()

            role = request.form.get(
                "role"
            )

            if not name or not username or not password or not role:

                error = "Preencha todos os campos."

            elif len(password) < 6:

                error = "A senha deve ter no mínimo 6 caracteres."

            else:

                usuario_existente = User.query.filter_by(
                    username=username
                ).first()

                if usuario_existente:

                    error = "Já existe um usuário com esse login."

                else:

                    novo_usuario = User(

                        name=name,

                        username=username,

                        password=password,

                        role=role
                    )

                    db.session.add(
                        novo_usuario
                    )

                    db.session.commit()

                    success = "Usuário cadastrado com sucesso."

        except Exception as e:

            db.session.rollback()

            error = str(e)

    lista = User.query.order_by(
        User.name.asc()
    ).all()

    return render_template(

        "usuarios.html",

        usuarios=lista,

        error=error,

        success=success
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

    usuario = User.query.get_or_404(
        user_id
    )

    if usuario.id == session.get("user_id"):

        flash(
            "Você não pode excluir seu próprio usuário.",
            "error"
        )

        return redirect(
            url_for("usuarios")
        )

    db.session.delete(usuario)

    db.session.commit()

    flash(
        "Usuário removido com sucesso.",
        "success"
    )

    return redirect(
        url_for("usuarios")
    )

# =====================================================
# VENDAS
# =====================================================

@app.route("/vendas", methods=["GET", "POST"])
@login_required
def vendas():

    error = None
    success = None

    itens = ItemVenda.query.order_by(
        ItemVenda.nome.asc()
    ).all()

    if request.method == "POST":

        try:

            data = request.form.get("data")
            tipo = request.form.get("tipo")
            turno = request.form.get("turno")

            valor_unitario = float(
                request.form.get("valor_unitario", 0)
            )

            quantidade = float(
                request.form.get("quantidade", 0)
            )

            total = valor_unitario * quantidade

            nova_venda = Venda(
                data=datetime.strptime(data, "%Y-%m-%d"),
                tipo=tipo,
                turno=turno,
                valor_unitario=valor_unitario,
                quantidade=quantidade,
                total=total
            )

            db.session.add(nova_venda)
            db.session.commit()

            success = "Venda registrada com sucesso."

        except Exception as e:

            db.session.rollback()
            error = f"Erro ao salvar venda: {str(e)}"

    vendas = Venda.query.order_by(
        Venda.id.desc()
    ).all()

    total_vendas = sum(
        venda.total for venda in vendas
    )

    return render_template(
        "vendas.html",
        vendas=vendas,
        total_vendas=total_vendas,
        itens=itens,
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

    return redirect(
        url_for("vendas")
    )

# =====================================================
# ITENS
# =====================================================

@app.route("/itens")
def itens():

    auth = verificar_login()

    if auth:
        return auth

    lista = Item.query.order_by(
        Item.name.asc()
    ).all()

    return render_template(
        "itens.html",
        itens=lista
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

    return redirect(
        url_for("compras")
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
        "movimentos.html"
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
        "desperdicio.html"
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
        "producao.html"
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

    return render_template(
        "auditoria.html"
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
        db.func.sum(Venda.total)
    ).scalar() or 0

    quantidade_vendas = Venda.query.count()

    ticket_medio = 0

    if quantidade_vendas > 0:

        ticket_medio = faturamento / quantidade_vendas

    vendas = Venda.query.order_by(
        Venda.sale_date.desc()
    ).all()

    return render_template(

        "relatorio_gerencial.html",

        faturamento=faturamento,

        quantidade_vendas=quantidade_vendas,

        ticket_medio=ticket_medio,

        vendas=vendas
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
