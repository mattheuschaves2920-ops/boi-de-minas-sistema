import os
from dataclasses import dataclass
from datetime import date, datetime
from math import ceil

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

app = Flask(__name__)

# CONFIG
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "boi-minas-2026-super-secret"
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///boi_de_minas.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_FOLDER"] = os.path.join(
    "static",
    "uploads",
    "desperdicio"
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

AREAS = [
    "Cozinha",
    "Bar",
    "Depósito",
    "Limpeza",
    "Salão"
]

SETORES = [
    "Cozinha Quente",
    "Cozinha Fria",
    "Padaria",
    "Bar",
    "Estoque"
]

MEAL_TYPES = [
    "Marmitex",
    "Self-Service",
    "Prato Feito",
    "Bebidas",
    "Sobremesas"
]

ROLES = [
    "admin",
    "gerente",
    "operador"
]


# MODELOS
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(
        db.String(100),
        nullable=False
    )

    codigo_barras = db.Column(
        db.String(50),
        unique=True
    )

    categoria = db.Column(db.String(50))

    estoque_atual = db.Column(
        db.Float,
        default=0.0
    )

    estoque_minimo = db.Column(
        db.Float,
        default=5.0
    )

    custo_unidade = db.Column(
        db.Float,
        default=0.0
    )

    preco_venda = db.Column(
        db.Float,
        default=0.0
    )


class Venda(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    data = db.Column(
        db.Date,
        default=date.today
    )

    periodo = db.Column(db.String(20))

    tipo_refeicao = db.Column(
        db.String(50)
    )

    valor_total = db.Column(
        db.Float,
        nullable=False
    )

    custo_estimado = db.Column(
        db.Float,
        default=0.0
    )


class Desperdicio(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    data = db.Column(
        db.DateTime,
        default=datetime.now
    )

    item_id = db.Column(
        db.Integer,
        db.ForeignKey("item.id")
    )

    quantidade = db.Column(db.Float)

    foto_path = db.Column(
        db.String(255)
    )

    motivo = db.Column(
        db.String(200)
    )


with app.app_context():
    db.create_all()


@dataclass
class SimpleLog:
    timestamp: datetime
    username: str
    action: str
    resource: str
    detail: str
    ip_address: str
    resource_id: int | None = None


@dataclass
class SimplePagination:
    items: list
    page: int
    pages: int

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return max(1, self.page - 1)

    @property
    def next_num(self):
        return min(
            self.pages,
            self.page + 1
        )


USERS = [
    {
        "id": 1,
        "name": "Administrador",
        "username": "admin",
        "role": "admin"
    }
]

AUDITORIA_LOGS = []


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


@app.context_processor
def inject_globals():
    return {
        "n_criticos": 0,
        "current_user": USERS[0],
        "now": datetime.now
    }


@app.route("/")
@app.route("/dashboard")
def dashboard():
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


@app.route("/vendas")
def vendas():
    return render_template(
        "vendas.html",
        vendas=[],
        meal_types=MEAL_TYPES,
        total_hoje=0,
        data_ref=date.today(),
        venda_edicao=None
    )


@app.route("/itens")
def itens():
    return render_template(
        "itens.html",
        itens=[],
        areas=AREAS
    )


@app.route("/desperdicio")
def desperdicio():
    return render_template(
        "desperdicio.html",
        items=[],
        lista=[],
        desperdicio_edicao=None,
        data_ref=date.today(),
        error=None
    )


@app.route("/controle")
def controle():
    return render_template(
        "controle.html",
        daily_groups=AREAS,
        totais={}
    )


@app.route("/movimentos")
def movimentos():
    return render_template(
        "movimentos.html",
        data_ref=date.today(),
        mov_edicao=None,
        areas=AREAS,
        setores=SETORES,
        items=[],
        movimentos=[]
    )


@app.route("/producao")
def producao():
    return render_template(
        "producao.html",
        data_ref=date.today(),
        setores=SETORES,
        items=[],
        lista=[]
    )


@app.route("/lista_compras")
def lista_compras():
    return render_template(
        "lista_compras.html",
        lista=[],
        total_custo=0
    )


@app.route("/relatorio_gerencial")
def relatorio_gerencial():
    return render_template(
        "relatorios.html",
        data_ref=date.today(),
        mes_ref=date.today(),
        faturamento=0,
        refeicoes=0,
        custo=0,
        lucro=0,
        cmv=0,
        total_perdas=0,
        total_diario=0,
        por_periodo={},
        ranking_vendas=[],
        resumo_setores=[]
    )


@app.route("/metas")
def metas():
    return render_template(
        "metas.html",
        metas=[]
    )


@app.route("/usuarios")
def usuarios():
    return render_template(
        "usuarios.html",
        usuarios=USERS,
        roles=ROLES
    )


@app.route("/auditoria")
def auditoria():
    logs = SimplePagination(
        items=[],
        page=1,
        pages=1
    )

    return render_template(
        "auditoria.html",
        logs=logs,
        get_badge_class=lambda x: "success"
    )


@app.route("/logout")
def logout():
    flash("Sessão encerrada")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
