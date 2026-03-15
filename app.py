import os
import csv
from io import StringIO, BytesIO
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque-esta-chave")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db").replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads", "desperdicio")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

db = SQLAlchemy(app)

MEAL_TYPES = [
    "Self-service HG",
    "Self-service sem balança",
    "Marmitex",
    "Comida a quilo",
    "Churrasco a quilo",
]

AREAS = ["Estoque Geral", "Bebidas", "Freezer", "Cozinha", "Padaria", "Confeitaria"]
ROLES = ["admin", "estoquista", "operador", "proprietario"]

CATEGORIES = [
    "Arroz e Grãos", "Massas", "Carnes", "Frango", "Peixes", "Churrasco",
    "Saladas", "Temperos", "Bebidas", "Freezer", "Limpeza", "Descartáveis",
    "Salgados", "Bolos", "Sobremesas", "Tortas", "Pão de Queijo", "Outros"
]

DAILY_GROUPS = ["Salgados", "Bolos", "Sobremesas", "Tortas", "Pão de Queijo", "Outros"]
SETORES = ["Almoço", "Janta", "Churrasco", "Confeitaria", "Padaria", "Bebidas", "Geral"]
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="operador")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(40), nullable=False)
    code = db.Column(db.String(80), nullable=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    unit = db.Column(db.String(20), nullable=False, default="kg")
    cost = db.Column(db.Float, nullable=False, default=0)
    stock = db.Column(db.Float, nullable=False, default=0)
    min_stock = db.Column(db.Float, nullable=False, default=0)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date, nullable=False, default=date.today)
    meal_type = db.Column(db.String(80), nullable=False)
    period = db.Column(db.String(20), nullable=False)
    unit_value = db.Column(db.Float, nullable=False, default=0)
    quantity = db.Column(db.Float, nullable=False, default=0)
    notes = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.String(120), nullable=True)


class Movement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mov_date = db.Column(db.Date, nullable=False, default=date.today)
    mov_type = db.Column(db.String(20), nullable=False)
    area = db.Column(db.String(40), nullable=False)
    setor = db.Column(db.String(40), nullable=False, default="Geral")
    item_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    detail = db.Column(db.String(255), nullable=True)
    value = db.Column(db.Float, nullable=False, default=0)
    created_by = db.Column(db.String(120), nullable=True)


class Waste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    waste_date = db.Column(db.Date, nullable=False, default=date.today)
    item_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    reason = db.Column(db.String(255), nullable=True)
    value = db.Column(db.Float, nullable=False, default=0)
    photo_filename = db.Column(db.String(255), nullable=True)


class Production(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prod_date = db.Column(db.Date, nullable=False, default=date.today)
    setor = db.Column(db.String(40), nullable=False, default="Geral")
    item_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    cost = db.Column(db.Float, nullable=False, default=0)


class DailyBakeryControl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    control_date = db.Column(db.Date, nullable=False, default=date.today)
    group_name = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    input_qty = db.Column(db.Integer, nullable=False, default=0)
    output_qty = db.Column(db.Integer, nullable=False, default=0)
    sold_qty = db.Column(db.Integer, nullable=False, default=0)
    unit_value = db.Column(db.Float, nullable=False, default=0)
    notes = db.Column(db.String(255), nullable=True)


def migrate_schema():
    with app.app_context():
        db.create_all()
        stmts = [
            "ALTER TABLE waste ADD COLUMN IF NOT EXISTS photo_filename VARCHAR(255)",
            "ALTER TABLE movement ADD COLUMN IF NOT EXISTS setor VARCHAR(40) DEFAULT 'Geral'",
            "ALTER TABLE production ADD COLUMN IF NOT EXISTS setor VARCHAR(40) DEFAULT 'Geral'",
            "ALTER TABLE sale ALTER COLUMN quantity TYPE DOUBLE PRECISION USING quantity::double precision",
        ]
        for stmt in stmts:
            try:
                db.session.execute(text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()


migrate_schema()


def ensure_upload_folder():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def require_login():
    return current_user() is not None


def require_admin():
    user = current_user()
    return user and user.role == "admin"


def get_selected_date():
    raw = request.args.get("data") or request.form.get("data")
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def get_selected_month():
    raw = request.args.get("mes") or request.form.get("mes")
    if raw:
        try:
            return datetime.strptime(raw + "-01", "%Y-%m-%d").date()
        except ValueError:
            pass
    today = date.today()
    return date(today.year, today.month, 1)


def get_selected_area():
    return (request.args.get("area") or "").strip()


def get_selected_category():
    return (request.args.get("categoria") or "").strip()


def get_selected_status():
    return (request.args.get("status") or "").strip()


def _sum_sales_total(sales):
    return sum(s.unit_value * s.quantity for s in sales)


def _sum_sales_qty(sales):
    return sum(s.quantity for s in sales)


def _sum_moves_cost(moves):
    return sum(m.value for m in moves if m.mov_type in ["Saida", "Perda"])


def _weekly_range(ref_date):
    start = ref_date - timedelta(days=ref_date.weekday())
    end = start + timedelta(days=7)
    return start, end


def render_desperdicio_page(error=None, data_ref=None):
    items = Item.query.order_by(Item.name).all()
    query = Waste.query.order_by(Waste.id.desc())
    if data_ref:
        query = Waste.query.filter_by(waste_date=data_ref).order_by(Waste.id.desc())
    lista = query.limit(200).all()
    return render_template(
        "desperdicio.html",
        user=current_user(),
        items=items,
        lista=lista,
        error=error,
        data_ref=data_ref or date.today()
    )


@app.route("/setup")
def setup():
    ensure_upload_folder()
    migrate_schema()

    if not User.query.filter_by(username="admin").first():
        user = User(name="Administrador", username="admin", role="admin")
        user.set_password("123456")
        db.session.add(user)
        db.session.commit()

    return "Sistema criado/atualizado. Login inicial: admin / 123456"


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Usuário ou senha inválidos.")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not require_login():
        return redirect(url_for("login"))

    data_ref = get_selected_date()
    mes_ref = get_selected_month()

    sales_day = Sale.query.filter_by(sale_date=data_ref).all()
    moves_day = Movement.query.filter_by(mov_date=data_ref).all()
    waste_day = Waste.query.filter_by(waste_date=data_ref).all()
    prod_day = Production.query.filter_by(prod_date=data_ref).all()
    bakery_day = DailyBakeryControl.query.filter_by(control_date=data_ref).all()
    items = Item.query.order_by(Item.area, Item.name).all()

    dia_anterior = data_ref - timedelta(days=1)
    sales_prev = Sale.query.filter_by(sale_date=dia_anterior).all()
    moves_prev = Movement.query.filter_by(mov_date=dia_anterior).all()
    waste_prev = Waste.query.filter_by(waste_date=dia_anterior).all()
    prod_prev = Production.query.filter_by(prod_date=dia_anterior).all()

    faturamento = _sum_sales_total(sales_day)
    faturamento_padaria = sum(b.unit_value * b.sold_qty for b in bakery_day)
    faturamento_prev = _sum_sales_total(sales_prev)
    refeicoes = _sum_sales_qty(sales_day)
    refeicoes_prev = _sum_sales_qty(sales_prev)

    custo = _sum_moves_cost(moves_day) + sum(w.value for w in waste_day) + sum(p.cost for p in prod_day)
    custo_prev = _sum_moves_cost(moves_prev) + sum(w.value for w in waste_prev) + sum(p.cost for p in prod_prev)
    lucro = faturamento + faturamento_padaria - custo
    lucro_prev = faturamento_prev - custo_prev
    desperdicio = sum(w.value for w in waste_day)
    vendidos_diarios = sum(b.sold_qty for b in bakery_day)
    cmv = round((custo / faturamento) * 100, 2) if faturamento else 0
    alertas = [i for i in items if i.stock <= i.min_stock]

    por_periodo = {"Almoço": {"q": 0, "v": 0}, "Janta": {"q": 0, "v": 0}}
    for s in sales_day:
        if s.period in por_periodo:
            por_periodo[s.period]["q"] += s.quantity
            por_periodo[s.period]["v"] += s.unit_value * s.quantity

    comparativo_dias = []
    for i in range(6, -1, -1):
        dia = data_ref - timedelta(days=i)
        vendas_dia = Sale.query.filter_by(sale_date=dia).all()
        comparativo_dias.append({
            "data": dia.strftime("%d/%m/%Y"),
            "qtd": _sum_sales_qty(vendas_dia),
            "total": round(_sum_sales_total(vendas_dia), 2),
            "almoco": round(sum(v.unit_value * v.quantity for v in vendas_dia if v.period == "Almoço"), 2),
            "janta": round(sum(v.unit_value * v.quantity for v in vendas_dia if v.period == "Janta"), 2),
        })

    comparativo_meses = []
    for i in range(5, -1, -1):
        y = mes_ref.year
        m = mes_ref.month - i
        while m <= 0:
            m += 12
            y -= 1

        inicio = date(y, m, 1)
        fim = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)

        vendas_mes = Sale.query.filter(Sale.sale_date >= inicio, Sale.sale_date < fim).all()
        comparativo_meses.append({
            "mes": inicio.strftime("%m/%Y"),
            "qtd": _sum_sales_qty(vendas_mes),
            "total": round(_sum_sales_total(vendas_mes), 2)
        })

    resumo_setores = []
    for setor in SETORES:
        prod_setor = [p for p in prod_day if p.setor == setor]
        mov_setor = [m for m in moves_day if m.setor == setor and m.mov_type in ["Saida", "Perda"]]
        custo_setor = sum(p.cost for p in prod_setor) + sum(m.value for m in mov_setor)
        venda_setor = sum(s.unit_value * s.quantity for s in sales_day if s.period == setor)
        resumo_setores.append({
            "setor": setor,
            "producao": sum(p.cost for p in prod_setor),
            "movimentacao": sum(m.value for m in mov_setor),
            "venda": venda_setor,
            "lucro": venda_setor - custo_setor
        })

    custo_almoco = sum(p.cost for p in prod_day if p.setor == "Almoço") + sum(
        m.value for m in moves_day if m.setor == "Almoço" and m.mov_type in ["Saida", "Perda"]
    )
    custo_janta = sum(p.cost for p in prod_day if p.setor == "Janta") + sum(
        m.value for m in moves_day if m.setor == "Janta" and m.mov_type in ["Saida", "Perda"]
    )

    venda_almoco = por_periodo["Almoço"]["v"]
    venda_janta = por_periodo["Janta"]["v"]
    lucro_almoco = venda_almoco - custo_almoco
    lucro_janta = venda_janta - custo_janta
    margem_almoco = round((lucro_almoco / venda_almoco) * 100, 2) if venda_almoco else 0
    margem_janta = round((lucro_janta / venda_janta) * 100, 2) if venda_janta else 0

    ranking_vendas = []
    for meal in MEAL_TYPES:
        vendas_tipo = [s for s in sales_day if s.meal_type == meal]
        total_tipo = _sum_sales_total(vendas_tipo)
        qtd_tipo = _sum_sales_qty(vendas_tipo)
        if total_tipo or qtd_tipo:
            ranking_vendas.append({"tipo": meal, "qtd": qtd_tipo, "total": total_tipo})
    ranking_vendas.sort(key=lambda x: x["total"], reverse=True)

    ranking_produtos = {}
    for p in prod_day:
        ranking_produtos[p.item_name] = ranking_produtos.get(p.item_name, 0) + p.quantity
    for m in moves_day:
        if m.mov_type in ["Saida", "Perda"]:
            ranking_produtos[m.item_name] = ranking_produtos.get(m.item_name, 0) + m.quantity

    ranking_produtos = [{"item": k, "qtd": v} for k, v in ranking_produtos.items()]
    ranking_produtos.sort(key=lambda x: x["qtd"], reverse=True)
    ranking_produtos = ranking_produtos[:10]

    alertas_compra = []
    for item in items:
        consumo = 0
        for i in range(6, -1, -1):
            dia = data_ref - timedelta(days=i)
            prod = Production.query.filter_by(prod_date=dia, item_name=item.name).all()
            movs = Movement.query.filter_by(mov_date=dia, item_name=item.name).all()
            consumo += sum(p.quantity for p in prod)
            consumo += sum(m.quantity for m in movs if m.mov_type in ["Saida", "Perda"])

        consumo_medio = consumo / 7 if consumo else 0
        dias_restantes = (item.stock / consumo_medio) if consumo_medio > 0 else 999

        if consumo_medio > 0 and dias_restantes <= 3:
            alertas_compra.append({
                "item": item.name,
                "estoque": item.stock,
                "consumo_medio": round(consumo_medio, 2),
                "dias_restantes": round(dias_restantes, 1)
            })
    alertas_compra.sort(key=lambda x: x["dias_restantes"])

    sem_ini, sem_fim = _weekly_range(data_ref)
    sem_ant_ini = sem_ini - timedelta(days=7)
    sem_ant_fim = sem_ini

    vendas_semana = Sale.query.filter(Sale.sale_date >= sem_ini, Sale.sale_date < sem_fim).all()
    vendas_semana_ant = Sale.query.filter(Sale.sale_date >= sem_ant_ini, Sale.sale_date < sem_ant_fim).all()
    desperdicio_semana = Waste.query.filter(Waste.waste_date >= sem_ini, Waste.waste_date < sem_fim).all()
    desperdicio_semana_ant = Waste.query.filter(Waste.waste_date >= sem_ant_ini, Waste.waste_date < sem_ant_fim).all()

    def variacao(atual, anterior):
        if anterior == 0:
            return 100.0 if atual > 0 else 0.0
        return round(((atual - anterior) / anterior) * 100, 2)

    semanal = {
        "faturamento_atual": _sum_sales_total(vendas_semana),
        "faturamento_anterior": _sum_sales_total(vendas_semana_ant),
        "qtd_atual": _sum_sales_qty(vendas_semana),
        "qtd_anterior": _sum_sales_qty(vendas_semana_ant),
        "desperdicio_atual": sum(w.value for w in desperdicio_semana),
        "desperdicio_anterior": sum(w.value for w in desperdicio_semana_ant),
    }
    semanal["var_faturamento"] = variacao(semanal["faturamento_atual"], semanal["faturamento_anterior"])
    semanal["var_qtd"] = variacao(semanal["qtd_atual"], semanal["qtd_anterior"])
    semanal["var_desperdicio"] = variacao(semanal["desperdicio_atual"], semanal["desperdicio_anterior"])

    return render_template(
        "dashboard.html",
        user=current_user(),
        data_ref=data_ref,
        mes_ref=mes_ref,
        total_itens=len(items),
        faturamento=faturamento,
        faturamento_padaria=faturamento_padaria,
        refeicoes=refeicoes,
        custo=custo,
        lucro=lucro,
        desperdicio=desperdicio,
        vendidos_diarios=vendidos_diarios,
        cmv=cmv,
        alertas=alertas,
        var_faturamento=variacao(faturamento, faturamento_prev),
        var_refeicoes=variacao(refeicoes, refeicoes_prev),
        var_custo=variacao(custo, custo_prev),
        var_lucro=variacao(lucro, lucro_prev),
        por_periodo=por_periodo,
        comparativo_dias=comparativo_dias,
        comparativo_meses=comparativo_meses,
        resumo_setores=resumo_setores,
        custo_almoco=custo_almoco,
        custo_janta=custo_janta,
        venda_almoco=venda_almoco,
        venda_janta=venda_janta,
        lucro_almoco=lucro_almoco,
        lucro_janta=lucro_janta,
        margem_almoco=margem_almoco,
        margem_janta=margem_janta,
        ranking_vendas=ranking_vendas,
        ranking_produtos=ranking_produtos,
        alertas_compra=alertas_compra[:10],
        semanal=semanal
    )


@app.route("/itens", methods=["GET", "POST"])
def itens():
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form["name"].strip()
        area = request.form["area"]

        existing = Item.query.filter_by(code=code).first() if code else None
        if not existing:
            existing = Item.query.filter_by(name=name, area=area).first()

        if existing:
            existing.code = code or existing.code
            existing.name = name
            existing.area = area
            existing.category = request.form.get("category", "").strip()
            existing.unit = request.form["unit"]
            existing.cost = float(request.form.get("cost") or 0)
            existing.stock = float(request.form.get("stock") or 0)
            existing.min_stock = float(request.form.get("min_stock") or 0)
        else:
            db.session.add(Item(
                area=area,
                code=code,
                name=name,
                category=request.form.get("category", "").strip(),
                unit=request.form["unit"],
                cost=float(request.form.get("cost") or 0),
                stock=float(request.form.get("stock") or 0),
                min_stock=float(request.form.get("min_stock") or 0),
            ))

        db.session.commit()
        return redirect(url_for("itens"))

    busca = request.args.get("busca", "").strip()
    editar_id = request.args.get("editar", type=int)

    if busca:
        itens_lista = Item.query.filter(
            or_(
                Item.name.ilike(f"%{busca}%"),
                Item.category.ilike(f"%{busca}%"),
                Item.area.ilike(f"%{busca}%"),
                Item.code.ilike(f"%{busca}%")
            )
        ).order_by(Item.area, Item.name).all()
    else:
        itens_lista = Item.query.order_by(Item.area, Item.name).all()

    item_edicao = db.session.get(Item, editar_id) if editar_id else None

    return render_template(
        "itens.html",
        user=current_user(),
        itens=itens_lista,
        areas=AREAS,
        categories=CATEGORIES,
        busca=busca,
        item_edicao=item_edicao
    )


@app.route("/editar-item/<int:item_id>", methods=["POST"])
def editar_item(item_id):
    if not require_login():
        return redirect(url_for("login"))

    item = db.session.get(Item, item_id)
    if not item:
        return redirect(url_for("itens"))

    item.area = request.form["area"]
    item.code = request.form.get("code", "").strip()
    item.name = request.form["name"].strip()
    item.category = request.form.get("category", "").strip()
    item.unit = request.form["unit"]
    item.cost = float(request.form.get("cost") or 0)
    item.stock = float(request.form.get("stock") or 0)
    item.min_stock = float(request.form.get("min_stock") or 0)

    db.session.commit()
    return redirect(url_for("itens"))


@app.route("/buscar-item")
def buscar_item():
    if not require_login():
        return jsonify({"ok": False}), 401

    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"ok": False, "message": "Código vazio"})

    item = Item.query.filter_by(code=code).first()
    if not item:
        return jsonify({"ok": False, "message": "Produto não cadastrado"})

    return jsonify({
        "ok": True,
        "item": {
            "id": item.id,
            "name": item.name,
            "area": item.area,
            "category": item.category,
            "unit": item.unit,
            "cost": item.cost,
            "stock": item.stock,
            "min_stock": item.min_stock,
            "code": item.code,
        }
    })


@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        db.session.add(Sale(
            sale_date=datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date(),
            meal_type=request.form["meal_type"],
            period=request.form["period"],
            unit_value=float(str(request.form.get("unit_value") or 0).replace(",", ".")),
            quantity=float(str(request.form.get("quantity") or 0).replace(",", ".")),
            notes=request.form.get("notes", "").strip(),
            created_by=current_user().name if current_user() else "",
        ))
        db.session.commit()
        return redirect(url_for("vendas", data=request.form["sale_date"]))

    data_ref = get_selected_date()
    editar_id = request.args.get("editar", type=int)
    venda_edicao = db.session.get(Sale, editar_id) if editar_id else None
    vendas_lista = Sale.query.filter_by(sale_date=data_ref).order_by(Sale.id.desc()).limit(200).all()
    total_dia = sum(v.unit_value * v.quantity for v in vendas_lista)

    return render_template(
        "vendas.html",
        user=current_user(),
        vendas=vendas_lista,
        meal_types=MEAL_TYPES,
        total_hoje=total_dia,
        data_ref=data_ref,
        venda_edicao=venda_edicao
    )


@app.route("/editar-venda/<int:sale_id>", methods=["POST"])
def editar_venda(sale_id):
    if not require_login():
        return redirect(url_for("login"))

    venda = db.session.get(Sale, sale_id)
    if not venda:
        return redirect(url_for("vendas"))

    venda.sale_date = datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date()
    venda.meal_type = request.form["meal_type"]
    venda.period = request.form["period"]
    venda.unit_value = float(str(request.form.get("unit_value") or 0).replace(",", "."))
    venda.quantity = float(str(request.form.get("quantity") or 0).replace(",", "."))
    venda.notes = request.form.get("notes", "").strip()

    db.session.commit()
    return redirect(url_for("vendas", data=venda.sale_date.strftime("%Y-%m-%d")))


@app.route("/excluir-venda/<int:sale_id>", methods=["POST"])
def excluir_venda(sale_id):
    if not require_login():
        return redirect(url_for("login"))

    venda = db.session.get(Sale, sale_id)
    if not venda:
        return redirect(url_for("vendas"))

    data_venda = venda.sale_date.strftime("%Y-%m-%d")
    db.session.delete(venda)
    db.session.commit()

    return redirect(url_for("vendas", data=data_venda))


@app.route("/movimentos", methods=["GET", "POST"])
def movimentos():
    if not require_login():
        return redirect(url_for("login"))

    items = Item.query.order_by(Item.name).all()

    if request.method == "POST":
        item = None
        item_id = request.form.get("item_id")
        barcode = request.form.get("barcode", "").strip()

        if item_id:
            item = db.session.get(Item, int(item_id))
        elif barcode:
            item = Item.query.filter_by(code=barcode).first()

        if not item:
            return redirect(url_for("movimentos"))

        qty = float(request.form.get("quantity") or 0)
        mov_type = request.form["mov_type"]
        setor = request.form.get("setor", "Geral")

        if mov_type == "Entrada":
            item.stock += qty
            if request.form.get("unit_cost"):
                item.cost = float(request.form.get("unit_cost") or 0)
        else:
            item.stock -= qty

        db.session.add(Movement(
            mov_date=datetime.strptime(request.form["mov_date"], "%Y-%m-%d").date(),
            mov_type=mov_type,
            area=request.form["area"],
            setor=setor,
            item_name=item.name,
            quantity=qty,
            detail=request.form.get("detail", "").strip(),
            value=qty * item.cost,
            created_by=current_user().name if current_user() else "",
        ))
        db.session.commit()
        return redirect(url_for("movimentos", data=request.form["mov_date"]))

    editar_id = request.args.get("editar", type=int)
    mov_edicao = db.session.get(Movement, editar_id) if editar_id else None
    data_ref = get_selected_date()

    movimentos_lista = Movement.query.filter_by(mov_date=data_ref).order_by(Movement.id.desc()).limit(300).all()

    return render_template(
        "movimentos.html",
        user=current_user(),
        movimentos=movimentos_lista,
        items=items,
        areas=AREAS,
        setores=SETORES,
        mov_edicao=mov_edicao,
        data_ref=data_ref
    )


@app.route("/editar-movimento/<int:mov_id>", methods=["POST"])
def editar_movimento(mov_id):
    if not require_login():
        return redirect(url_for("login"))

    mov = db.session.get(Movement, mov_id)
    if not mov:
        return redirect(url_for("movimentos"))

    mov.mov_date = datetime.strptime(request.form["mov_date"], "%Y-%m-%d").date()
    mov.mov_type = request.form["mov_type"]
    mov.area = request.form["area"]
    mov.setor = request.form.get("setor", "Geral")
    mov.item_name = request.form["item_name"].strip()
    mov.quantity = float(request.form.get("quantity") or 0)
    mov.detail = request.form.get("detail", "").strip()
    mov.value = float(request.form.get("value") or 0)

    db.session.commit()
    return redirect(url_for("movimentos", data=mov.mov_date.strftime("%Y-%m-%d")))


@app.route("/excluir-movimento/<int:mov_id>", methods=["POST"])
def excluir_movimento(mov_id):
    if not require_login():
        return redirect(url_for("login"))

    mov = db.session.get(Movement, mov_id)
    if not mov:
        return redirect(url_for("movimentos"))

    item = Item.query.filter_by(name=mov.item_name, area=mov.area).first()
    if item:
        if mov.mov_type in ["Saida", "Perda"]:
            item.stock += mov.quantity
        elif mov.mov_type == "Entrada":
            item.stock -= mov.quantity
            if item.stock < 0:
                item.stock = 0

    data_mov = mov.mov_date.strftime("%Y-%m-%d")
    db.session.delete(mov)
    db.session.commit()

    return redirect(url_for("movimentos", data=data_mov))


@app.route("/producao", methods=["GET", "POST"])
def producao():
    if not require_login():
        return redirect(url_for("login"))

    items = Item.query.order_by(Item.name).all()

    if request.method == "POST":
        item = db.session.get(Item, int(request.form["item_id"]))
        qty = float(request.form.get("quantity") or 0)
        setor = request.form.get("setor", "Geral")

        if item and qty:
            item.stock -= qty
            db.session.add(Production(
                prod_date=datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date(),
                setor=setor,
                item_name=item.name,
                quantity=qty,
                cost=qty * item.cost
            ))
            db.session.commit()

        return redirect(url_for("producao", data=request.form["prod_date"]))

    data_ref = get_selected_date()
    editar_id = request.args.get("editar", type=int)
    producao_edicao = db.session.get(Production, editar_id) if editar_id else None
    lista = Production.query.filter_by(prod_date=data_ref).order_by(Production.id.desc()).limit(200).all()

    return render_template(
        "producao.html",
        user=current_user(),
        items=items,
        lista=lista,
        setores=SETORES,
        data_ref=data_ref,
        producao_edicao=producao_edicao
    )


@app.route("/editar-producao/<int:prod_id>", methods=["POST"])
def editar_producao(prod_id):
    if not require_login():
        return redirect(url_for("login"))

    prod = db.session.get(Production, prod_id)
    if not prod:
        return redirect(url_for("producao"))

    prod.prod_date = datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date()
    prod.setor = request.form.get("setor", "Geral")
    prod.item_name = request.form["item_name"].strip()
    prod.quantity = float(request.form.get("quantity") or 0)
    prod.cost = float(request.form.get("cost") or 0)

    db.session.commit()
    return redirect(url_for("producao", data=prod.prod_date.strftime("%Y-%m-%d")))


@app.route("/excluir-producao/<int:prod_id>", methods=["POST"])
def excluir_producao(prod_id):
    if not require_login():
        return redirect(url_for("login"))

    prod = db.session.get(Production, prod_id)
    if not prod:
        return redirect(url_for("producao"))

    item = Item.query.filter_by(name=prod.item_name).first()
    if item:
        item.stock += prod.quantity

    data_prod = prod.prod_date.strftime("%Y-%m-%d")
    db.session.delete(prod)
    db.session.commit()

    return redirect(url_for("producao", data=data_prod))


@app.route("/desperdicio", methods=["GET", "POST"])
def desperdicio():
    if not require_login():
        return redirect(url_for("login"))

    ensure_upload_folder()
    data_ref = get_selected_date()

    if request.method == "POST":
        photo = request.files.get("photo")

        if not photo or not photo.filename:
            return render_desperdicio_page(
                "Para salvar a perda, é obrigatório tirar ou enviar uma foto do desperdício.",
                data_ref
            )

        if not allowed_image(photo.filename):
            return render_desperdicio_page(
                "Formato de foto inválido. Use PNG, JPG, JPEG ou WEBP.",
                data_ref
            )

        item = db.session.get(Item, int(request.form["item_id"]))
        qty = float(request.form.get("quantity") or 0)

        if not item or qty <= 0:
            return render_desperdicio_page(
                "Selecione um item válido e informe uma quantidade maior que zero.",
                data_ref
            )

        original_name = secure_filename(photo.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{original_name}"
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        photo.save(photo_path)

        item.stock -= qty

        db.session.add(Waste(
            waste_date=datetime.strptime(request.form["waste_date"], "%Y-%m-%d").date(),
            item_name=item.name,
            quantity=qty,
            reason=request.form.get("reason", "").strip(),
            value=qty * item.cost,
            photo_filename=filename
        ))

        db.session.commit()

        return redirect(url_for("desperdicio", data=request.form["waste_date"]))

    editar_id = request.args.get("editar", type=int)
    desperdicio_edicao = db.session.get(Waste, editar_id) if editar_id else None

    items = Item.query.order_by(Item.name).all()
    lista = Waste.query.filter_by(waste_date=data_ref).order_by(Waste.id.desc()).limit(200).all()

    return render_template(
        "desperdicio.html",
        user=current_user(),
        items=items,
        lista=lista,
        error=None,
        data_ref=data_ref,
        desperdicio_edicao=desperdicio_edicao
    )


@app.route("/editar-desperdicio/<int:waste_id>", methods=["POST"])
def editar_desperdicio(waste_id):
    if not require_login():
        return redirect(url_for("login"))

    waste = db.session.get(Waste, waste_id)
    if not waste:
        return redirect(url_for("desperdicio"))

    item = Item.query.filter_by(name=waste.item_name).first()
    nova_qtd = float(request.form.get("quantity") or 0)

    if item:
        diferenca = nova_qtd - waste.quantity
        item.stock -= diferenca
        if item.stock < 0:
            item.stock = 0

    waste.waste_date = datetime.strptime(request.form["waste_date"], "%Y-%m-%d").date()
    waste.quantity = nova_qtd
    waste.reason = request.form.get("reason", "").strip()

    if item:
        waste.value = nova_qtd * item.cost
    else:
        waste.value = 0

    db.session.commit()

    return redirect(url_for("desperdicio", data=waste.waste_date.strftime("%Y-%m-%d")))


@app.route("/excluir-desperdicio/<int:waste_id>", methods=["POST"])
def excluir_desperdicio(waste_id):
    if not require_login():
        return redirect(url_for("login"))

    waste = db.session.get(Waste, waste_id)
    if not waste:
        return redirect(url_for("desperdicio"))

    item = Item.query.filter_by(name=waste.item_name).first()
    if item:
        item.stock += waste.quantity

    data_waste = waste.waste_date.strftime("%Y-%m-%d")
    db.session.delete(waste)
    db.session.commit()

    return redirect(url_for("desperdicio", data=data_waste))


@app.route("/controle-diario", methods=["GET", "POST"])
def controle_diario():
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        db.session.add(DailyBakeryControl(
            control_date=datetime.strptime(request.form["control_date"], "%Y-%m-%d").date(),
            group_name=request.form["group_name"],
            item_name=request.form["item_name"].strip(),
            input_qty=int(request.form.get("input_qty") or 0),
            output_qty=int(request.form.get("output_qty") or 0),
            sold_qty=int(request.form.get("sold_qty") or 0),
            unit_value=float(request.form.get("unit_value") or 0),
            notes=request.form.get("notes", "").strip()
        ))
        db.session.commit()
        return redirect(url_for("controle_diario", data=request.form["control_date"]))

    filtro = request.args.get("data")
    if filtro:
        data_ref = datetime.strptime(filtro, "%Y-%m-%d").date()
    else:
        data_ref = date.today()

    lista = DailyBakeryControl.query.filter_by(control_date=data_ref).order_by(
        DailyBakeryControl.group_name,
        DailyBakeryControl.item_name
    ).all()

    totais = {}
    for grupo in DAILY_GROUPS:
        registros = [x for x in lista if x.group_name == grupo]
        totais[grupo] = {
            "entrada": sum(x.input_qty for x in registros),
            "saida": sum(x.output_qty for x in registros),
            "vendido": sum(x.sold_qty for x in registros),
            "faturado": sum(x.sold_qty * x.unit_value for x in registros),
        }

    return render_template(
        "controle_diario.html",
        user=current_user(),
        lista=lista,
        daily_groups=DAILY_GROUPS,
        data_ref=data_ref,
        totais=totais
    )


@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if not require_admin():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        user = User(
            name=request.form["name"].strip(),
            username=request.form["username"].strip(),
            role=request.form["role"]
        )
        user.set_password(request.form["password"].strip())
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("usuarios"))

    usuarios_lista = User.query.order_by(User.name).all()
    return render_template("usuarios.html", user=current_user(), usuarios=usuarios_lista, roles=ROLES)


@app.route("/relatorios")
def relatorios():
    if not require_login():
        return redirect(url_for("login"))

    data_ref = get_selected_date()
    mes_ref = get_selected_month()

    sales_day = Sale.query.filter_by(sale_date=data_ref).all()
    moves_day = Movement.query.filter_by(mov_date=data_ref).all()
    waste_day = Waste.query.filter_by(waste_date=data_ref).all()
    prod_day = Production.query.filter_by(prod_date=data_ref).all()
    bakery_day = DailyBakeryControl.query.filter_by(control_date=data_ref).all()

    faturamento = _sum_sales_total(sales_day)
    refeicoes = _sum_sales_qty(sales_day)
    custo = _sum_moves_cost(moves_day) + sum(w.value for w in waste_day) + sum(p.cost for p in prod_day)
    lucro = faturamento - custo
    total_diario = sum(b.sold_qty * b.unit_value for b in bakery_day)
    cmv = round((custo / faturamento) * 100, 2) if faturamento else 0

    por_periodo = {"Almoço": {"q": 0, "v": 0}, "Janta": {"q": 0, "v": 0}}
    for s in sales_day:
        if s.period in por_periodo:
            por_periodo[s.period]["q"] += s.quantity
            por_periodo[s.period]["v"] += s.unit_value * s.quantity

    resumo_setores = []
    for setor in SETORES:
        prod_setor = [p for p in prod_day if p.setor == setor]
        mov_setor = [m for m in moves_day if m.setor == setor and m.mov_type in ["Saida", "Perda"]]
        venda_setor = sum(s.unit_value * s.quantity for s in sales_day if s.period == setor)
        custo_setor = sum(p.cost for p in prod_setor) + sum(m.value for m in mov_setor)

        resumo_setores.append({
            "setor": setor,
            "producao": sum(p.cost for p in prod_setor),
            "movimentacao": sum(m.value for m in mov_setor),
            "venda": venda_setor,
            "lucro": venda_setor - custo_setor,
        })

    ranking_vendas = []
    for meal in MEAL_TYPES:
        vendas_tipo = [s for s in sales_day if s.meal_type == meal]
        total_tipo = _sum_sales_total(vendas_tipo)
        qtd_tipo = _sum_sales_qty(vendas_tipo)
        if total_tipo or qtd_tipo:
            ranking_vendas.append({
                "tipo": meal,
                "qtd": qtd_tipo,
                "total": total_tipo
            })
    ranking_vendas.sort(key=lambda x: x["total"], reverse=True)

    return render_template(
        "relatorios.html",
        user=current_user(),
        data_ref=data_ref,
        mes_ref=mes_ref,
        faturamento=faturamento,
        refeicoes=refeicoes,
        custo=custo,
        lucro=lucro,
        cmv=cmv,
        total_diario=total_diario,
        total_perdas=sum(w.value for w in waste_day),
        por_periodo=por_periodo,
        resumo_setores=resumo_setores,
        ranking_vendas=ranking_vendas
    )


@app.route("/relatorio-estoque")
def relatorio_estoque():
    if not require_login():
        return redirect(url_for("login"))

    area = get_selected_area()
    categoria = get_selected_category()
    status = get_selected_status()

    query = Item.query
    if area:
        query = query.filter_by(area=area)
    if categoria:
        query = query.filter_by(category=categoria)

    items = query.order_by(Item.area, Item.category, Item.name).all()

    if status == "baixo":
        items = [i for i in items if i.stock <= i.min_stock]
    elif status == "normal":
        items = [i for i in items if i.stock > i.min_stock]

    total_itens = len(items)
    valor_total = sum((i.stock or 0) * (i.cost or 0) for i in items)
    itens_baixos = sum(1 for i in items if (i.stock or 0) <= (i.min_stock or 0))

    return render_template(
        "estoque_relatorio.html",
        user=current_user(),
        itens=items,
        areas=AREAS,
        categories=CATEGORIES,
        area_ref=area,
        categoria_ref=categoria,
        status_ref=status,
        total_itens=total_itens,
        valor_total=valor_total,
        itens_baixos=itens_baixos
    )


@app.route("/exportar/relatorio.xlsx")
def exportar_relatorio_xlsx():
    if not require_login():
        return redirect(url_for("login"))

    data_ref = get_selected_date()
    sales_day = Sale.query.filter_by(sale_date=data_ref).all()
    moves_day = Movement.query.filter_by(mov_date=data_ref).all()
    waste_day = Waste.query.filter_by(waste_date=data_ref).all()
    prod_day = Production.query.filter_by(prod_date=data_ref).all()

    faturamento = _sum_sales_total(sales_day)
    refeicoes = _sum_sales_qty(sales_day)
    custo = _sum_moves_cost(moves_day) + sum(w.value for w in waste_day) + sum(p.cost for p in prod_day)
    lucro = faturamento - custo
    cmv = round((custo / faturamento) * 100, 2) if faturamento else 0

    wb = Workbook()

    ws = wb.active
    ws.title = "Resumo"
    ws.append(["Relatório diário", data_ref.strftime("%d/%m/%Y")])
    ws.append(["Faturamento", faturamento])
    ws.append(["Refeições", refeicoes])
    ws.append(["Custo", custo])
    ws.append(["Lucro", lucro])
    ws.append(["CMV", cmv])
    ws.append(["Desperdício", sum(w.value for w in waste_day)])

    ws2 = wb.create_sheet("Vendas")
    ws2.append(["Data", "Tipo", "Período", "Qtd", "Valor unit", "Total"])
    for s in sales_day:
        ws2.append([
            s.sale_date.strftime("%d/%m/%Y"),
            s.meal_type,
            s.period,
            s.quantity,
            s.unit_value,
            s.unit_value * s.quantity
        ])

    ws3 = wb.create_sheet("Movimentos")
    ws3.append(["Data", "Tipo", "Área", "Setor", "Item", "Qtd", "Valor"])
    for m in moves_day:
        ws3.append([
            m.mov_date.strftime("%d/%m/%Y"),
            m.mov_type,
            m.area,
            m.setor,
            m.item_name,
            m.quantity,
            m.value
        ])

    out = BytesIO()
    wb.save(out)
    out.seek(0)

    return send_file(
        out,
        as_attachment=True,
        download_name=f"relatorio_v44_{data_ref.strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/exportar/relatorio.pdf")
def exportar_relatorio_pdf():
    if not require_login():
        return redirect(url_for("login"))

    data_ref = get_selected_date()
    sales_day = Sale.query.filter_by(sale_date=data_ref).all()
    moves_day = Movement.query.filter_by(mov_date=data_ref).all()
    waste_day = Waste.query.filter_by(waste_date=data_ref).all()
    prod_day = Production.query.filter_by(prod_date=data_ref).all()

    faturamento = _sum_sales_total(sales_day)
    refeicoes = _sum_sales_qty(sales_day)
    custo = _sum_moves_cost(moves_day) + sum(w.value for w in waste_day) + sum(p.cost for p in prod_day)
    lucro = faturamento - custo
    cmv = round((custo / faturamento) * 100, 2) if faturamento else 0

    out = BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    y = 800

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Boi de Minas – Relatório 4.4")
    y -= 30

    c.setFont("Helvetica", 11)
    linhas = [
        f"Data: {data_ref.strftime('%d/%m/%Y')}",
        f"Faturamento: R$ {faturamento:.2f}",
        f"Refeições: {refeicoes}",
        f"Custo: R$ {custo:.2f}",
        f"Lucro: R$ {lucro:.2f}",
        f"CMV: {cmv:.2f}%",
        f"Desperdício: R$ {sum(w.value for w in waste_day):.2f}",
    ]

    for linha in linhas:
        c.drawString(50, y, linha)
        y -= 20

    c.save()
    out.seek(0)

    return send_file(
        out,
        as_attachment=True,
        download_name=f"relatorio_v44_{data_ref.strftime('%Y%m%d')}.pdf",
        mimetype="application/pdf"
    )


@app.route("/exportar/estoque.xlsx")
def exportar_estoque_xlsx():
    if not require_login():
        return redirect(url_for("login"))

    area = get_selected_area()
    categoria = get_selected_category()
    status = get_selected_status()

    query = Item.query
    if area:
        query = query.filter_by(area=area)
    if categoria:
        query = query.filter_by(category=categoria)

    items = query.order_by(Item.area, Item.category, Item.name).all()

    if status == "baixo":
        items = [i for i in items if i.stock <= i.min_stock]
    elif status == "normal":
        items = [i for i in items if i.stock > i.min_stock]

    wb = Workbook()
    ws = wb.active
    ws.title = "Estoque"
    ws.append(["Item", "Código", "Área", "Categoria", "Unidade", "Custo", "Estoque", "Mínimo", "Valor em estoque", "Status"])

    for i in items:
        valor_estoque = (i.stock or 0) * (i.cost or 0)
        status_item = "Baixo" if (i.stock or 0) <= (i.min_stock or 0) else "Normal"
        ws.append([i.name, i.code or "", i.area, i.category or "", i.unit, i.cost, i.stock, i.min_stock, valor_estoque, status_item])

    out = BytesIO()
    wb.save(out)
    out.seek(0)

    return send_file(
        out,
        as_attachment=True,
        download_name="relatorio_estoque.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/exportar/estoque.pdf")
def exportar_estoque_pdf():
    if not require_login():
        return redirect(url_for("login"))

    area = get_selected_area()
    categoria = get_selected_category()
    status = get_selected_status()

    query = Item.query
    if area:
        query = query.filter_by(area=area)
    if categoria:
        query = query.filter_by(category=categoria)

    items = query.order_by(Item.area, Item.category, Item.name).all()

    if status == "baixo":
        items = [i for i in items if i.stock <= i.min_stock]
    elif status == "normal":
        items = [i for i in items if i.stock > i.min_stock]

    out = BytesIO()
    c = canvas.Canvas(out, pagesize=landscape(A4))
    y = 560

    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, y, "Boi de Minas – Relatório de Estoque")
    y -= 24

    c.setFont("Helvetica", 10)
    c.drawString(30, y, f"Área: {area or 'Todas'} | Categoria: {categoria or 'Todas'} | Status: {status or 'Todos'}")
    y -= 24

    c.setFont("Helvetica-Bold", 9)
    c.drawString(30, y, "Item")
    c.drawString(210, y, "Área")
    c.drawString(300, y, "Categoria")
    c.drawString(390, y, "Estoque")
    c.drawString(455, y, "Mínimo")
    c.drawString(520, y, "Valor")
    y -= 16

    c.setFont("Helvetica", 9)
    for i in items[:60]:
        valor_estoque = (i.stock or 0) * (i.cost or 0)
        c.drawString(30, y, str(i.name)[:32])
        c.drawString(210, y, str(i.area)[:14])
        c.drawString(300, y, str(i.category or "")[:14])
        c.drawRightString(435, y, f"{i.stock:.3f}")
        c.drawRightString(500, y, f"{i.min_stock:.3f}")
        c.drawRightString(575, y, f"R$ {valor_estoque:.2f}")
        y -= 14
        if y < 40:
            c.showPage()
            y = 560

    c.save()
    out.seek(0)

    return send_file(
        out,
        as_attachment=True,
        download_name="relatorio_estoque.pdf",
        mimetype="application/pdf"
    )


@app.route("/exportar/vendas.csv")
def exportar_vendas():
    if not require_login():
        return redirect(url_for("login"))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Data", "Tipo", "Período", "Valor Unitário", "Quantidade", "Total", "Criado por"])

    for s in Sale.query.order_by(Sale.sale_date.desc()).all():
        writer.writerow([
            s.sale_date,
            s.meal_type,
            s.period,
            s.unit_value,
            s.quantity,
            s.unit_value * s.quantity,
            s.created_by
        ])

    mem = BytesIO()
    mem.write(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)

    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name="vendas.csv"
    )


@app.route("/exportar/controle_diario.csv")
def exportar_controle_diario():
    if not require_login():
        return redirect(url_for("login"))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Data", "Grupo", "Item", "Entrada", "Saída", "Vendido", "Valor Unitário", "Faturado", "Observações"])

    for r in DailyBakeryControl.query.order_by(
        DailyBakeryControl.control_date.desc(),
        DailyBakeryControl.group_name,
        DailyBakeryControl.item_name
    ).all():
        writer.writerow([
            r.control_date,
            r.group_name,
            r.item_name,
            r.input_qty,
            r.output_qty,
            r.sold_qty,
            r.unit_value,
            r.sold_qty * r.unit_value,
            r.notes
        ])

    mem = BytesIO()
    mem.write(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)

    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name="controle_diario.csv"
    )


if __name__ == "__main__":
    ensure_upload_folder()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
