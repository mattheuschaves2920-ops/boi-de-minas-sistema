import os
import io
from datetime import date, datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, send_file)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

# Exportação
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ─── APP & CONFIG ────────────────────────────────────────────────────────────

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(32))

uri = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# ─── MODELOS ─────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(30), nullable=False, default="operador")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Item(db.Model):
    __tablename__ = "items"
    id        = db.Column(db.Integer, primary_key=True)
    area      = db.Column(db.String(80))
    code      = db.Column(db.String(60))
    name      = db.Column(db.String(120), nullable=False)
    category  = db.Column(db.String(80))
    unit      = db.Column(db.String(20), default="un")
    cost      = db.Column(db.Float, default=0.0)
    stock     = db.Column(db.Float, default=0.0)
    min_stock = db.Column(db.Float, default=0.0)


class Waste(db.Model):
    __tablename__ = "wastes"
    id         = db.Column(db.Integer, primary_key=True)
    waste_date = db.Column(db.Date, nullable=False, default=date.today)
    item_id    = db.Column(db.Integer, db.ForeignKey("items.id"))
    item_name  = db.Column(db.String(120))
    quantity   = db.Column(db.Float, default=0.0)
    reason     = db.Column(db.String(80))
    value      = db.Column(db.Float, default=0.0)
    photo_path = db.Column(db.String(255))
    item       = db.relationship("Item", backref="wastes")


class Movement(db.Model):
    __tablename__ = "movements"
    id       = db.Column(db.Integer, primary_key=True)
    mov_date = db.Column(db.Date, nullable=False, default=date.today)
    mov_type = db.Column(db.String(20))          # Entrada | Saida | Perda
    area     = db.Column(db.String(80))
    setor    = db.Column(db.String(80))
    item_id  = db.Column(db.Integer, db.ForeignKey("items.id"))
    item_name= db.Column(db.String(120))
    quantity = db.Column(db.Float, default=0.0)
    value    = db.Column(db.Float, default=0.0)
    detail   = db.Column(db.String(255))
    item     = db.relationship("Item", backref="movements")


class Production(db.Model):
    __tablename__ = "productions"
    id        = db.Column(db.Integer, primary_key=True)
    prod_date = db.Column(db.Date, nullable=False, default=date.today)
    setor     = db.Column(db.String(80))
    item_id   = db.Column(db.Integer, db.ForeignKey("items.id"))
    item_name = db.Column(db.String(120))
    quantity  = db.Column(db.Float, default=0.0)
    cost      = db.Column(db.Float, default=0.0)
    item      = db.relationship("Item", backref="productions")


class Sale(db.Model):
    __tablename__ = "sales"
    id         = db.Column(db.Integer, primary_key=True)
    sale_date  = db.Column(db.Date, nullable=False, default=date.today)
    period     = db.Column(db.String(20))         # Almoço | Janta
    meal_type  = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity   = db.Column(db.Float, default=0.0)
    notes      = db.Column(db.String(255))


class DailyControl(db.Model):
    __tablename__ = "daily_controls"
    id           = db.Column(db.Integer, primary_key=True)
    control_date = db.Column(db.Date, nullable=False, default=date.today)
    group_name   = db.Column(db.String(80))
    item_name    = db.Column(db.String(120))
    input_qty    = db.Column(db.Float, default=0.0)
    output_qty   = db.Column(db.Float, default=0.0)
    sold_qty     = db.Column(db.Float, default=0.0)
    unit_value   = db.Column(db.Float, default=0.0)
    notes        = db.Column(db.String(255))

# ─── CONSTANTES ──────────────────────────────────────────────────────────────

AREAS      = ["Cozinha", "Bar", "Confeitaria", "Açougue", "Estoque Geral"]
CATEGORIES = ["Carnes", "Bebidas", "Laticínios", "Hortifruti", "Grãos", "Temperos", "Descartáveis", "Outros"]
SETORES    = ["Cozinha", "Bar", "Salão", "Confeitaria", "Açougue"]
MEAL_TYPES = ["Buffet Kg", "Executivo", "À La Carte", "Rodízio", "Marmita"]
DAILY_GROUPS = ["Salgados", "Bolos", "Doces", "Bebidas", "Outros"]
ROLES      = ["admin", "gerente", "operador"]

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def get_selected_date():
    raw = request.args.get("data") or request.form.get("data")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()


def get_selected_month():
    raw = request.args.get("mes") or request.form.get("mes")
    try:
        return datetime.strptime(raw, "%Y-%m").date()
    except (ValueError, TypeError):
        return date.today().replace(day=1)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        u = current_user()
        if not u:
            return redirect(url_for("index"))
        if u.role not in ("admin", "gerente"):
            flash("Acesso restrito a administradores.")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


def _pdf_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.HexColor("#8b0000"),
        spaceAfter=12,
    )
    return styles, title_style


def _xlsx_header(ws, headers, fill_color="8B0000"):
    fill = PatternFill("solid", fgColor=fill_color)
    font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center")


# ─── SETUP ───────────────────────────────────────────────────────────────────

@app.route("/setup")
def setup():
    """Inicializa o banco. Só funciona se não houver nenhum usuário cadastrado."""
    if User.query.first():
        return "Sistema já inicializado.", 403
    db.create_all()
    admin = User(name="Administrador", username="admin", role="admin")
    admin.set_password("admin@2026!")
    db.session.add(admin)
    db.session.commit()
    return "Sistema inicializado! Acesse /. Login: admin | Senha: admin@2026!"


# ─── AUTH ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"], endpoint="index")
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username")).first()
        if u and u.check_password(request.form.get("password")):
            session["user_id"] = u.id
            return redirect(url_for("dashboard"))
        error = "Usuário ou senha inválidos."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user     = current_user()
    data_ref = get_selected_date()
    mes_ref  = get_selected_month()

    # Faturamento do dia (vendas)
    faturamento = db.session.query(
        func.sum(Sale.unit_value * Sale.quantity)
    ).filter(Sale.sale_date == data_ref).scalar() or 0.0

    # Faturamento do mês
    faturamento_mes = db.session.query(
        func.sum(Sale.unit_value * Sale.quantity)
    ).filter(
        func.strftime("%Y-%m", Sale.sale_date) == mes_ref.strftime("%Y-%m")
    ).scalar() or 0.0

    # Refeições do dia
    refeicoes = db.session.query(
        func.sum(Sale.quantity)
    ).filter(Sale.sale_date == data_ref).scalar() or 0.0

    # Custo do dia (movimentos de entrada)
    custo = db.session.query(
        func.sum(Movement.value)
    ).filter(
        Movement.mov_date == data_ref,
        Movement.mov_type == "Entrada"
    ).scalar() or 0.0

    # Desperdício do dia
    desperdicio = db.session.query(
        func.sum(Waste.value)
    ).filter(Waste.waste_date == data_ref).scalar() or 0.0

    # Desperdício do mês
    desperdicio_mes = db.session.query(
        func.sum(Waste.value)
    ).filter(
        func.strftime("%Y-%m", Waste.waste_date) == mes_ref.strftime("%Y-%m")
    ).scalar() or 0.0

    lucro = faturamento - custo - desperdicio
    cmv   = round((custo / faturamento * 100), 1) if faturamento else 0.0

    # Últimas vendas do dia para gráfico
    vendas_dia    = Sale.query.filter(Sale.sale_date == data_ref).all()
    producao_dia  = Production.query.filter(Production.prod_date == data_ref).all()

    return render_template("dashboard.html",
        user=user,
        data_ref=data_ref, mes_ref=mes_ref,
        faturamento=faturamento,
        faturamento_mes=faturamento_mes,
        refeicoes=refeicoes,
        custo=custo,
        lucro=lucro,
        cmv=cmv,
        desperdicio=desperdicio,
        desperdicio_mes=desperdicio_mes,
        vendas_dia=vendas_dia,
        producao_dia=producao_dia,
        # zeros para compatibilidade com template antigo
        clientes_almoco=0, venda_almoco=0.0,
        clientes_janta=0,  venda_janta=0.0,
    )


# ─── CONTROLE DIÁRIO ─────────────────────────────────────────────────────────

@app.route("/controle", methods=["GET", "POST"])
@login_required
def controle():
    user     = current_user()
    data_ref = get_selected_date()

    if request.method == "POST":
        ctrl = DailyControl(
            control_date=datetime.strptime(request.form["control_date"], "%Y-%m-%d").date(),
            group_name=request.form.get("group_name"),
            item_name=request.form.get("item_name"),
            input_qty=float(request.form.get("input_qty") or 0),
            output_qty=float(request.form.get("output_qty") or 0),
            sold_qty=float(request.form.get("sold_qty") or 0),
            unit_value=float(request.form.get("unit_value") or 0),
            notes=request.form.get("notes"),
        )
        db.session.add(ctrl)
        db.session.commit()
        flash("Lançamento salvo com sucesso!")
        return redirect(url_for("controle", data=ctrl.control_date.strftime("%Y-%m-%d")))

    lista = DailyControl.query.filter_by(control_date=data_ref).order_by(DailyControl.group_name).all()

    # Totais por grupo
    totais = {}
    for r in lista:
        g = r.group_name or "Geral"
        if g not in totais:
            totais[g] = {"vendido": 0, "faturado": 0.0}
        totais[g]["vendido"]  += r.sold_qty
        totais[g]["faturado"] += r.sold_qty * r.unit_value

    return render_template("controle.html",
        user=user, data_ref=data_ref,
        daily_groups=DAILY_GROUPS,
        totais=totais, lista=lista,
    )


# ─── DESPERDÍCIO ─────────────────────────────────────────────────────────────

@app.route("/desperdicio", methods=["GET", "POST"])
@login_required
def desperdicio():
    user     = current_user()
    data_ref = get_selected_date()
    error    = None

    # Edição
    desperdicio_edicao = None
    editar_id = request.args.get("editar", type=int)
    if editar_id:
        desperdicio_edicao = db.session.get(Waste, editar_id)

    if request.method == "POST":
        waste_date = datetime.strptime(request.form["waste_date"], "%Y-%m-%d").date()
        qty        = float(request.form.get("quantity") or 0)
        reason     = request.form.get("reason")

        if desperdicio_edicao:
            desperdicio_edicao.waste_date = waste_date
            desperdicio_edicao.quantity   = qty
            desperdicio_edicao.reason     = reason
            # Recalcula valor com custo do item
            if desperdicio_edicao.item:
                desperdicio_edicao.value = qty * desperdicio_edicao.item.cost
            db.session.commit()
            flash("Desperdício atualizado.")
            return redirect(url_for("desperdicio", data=waste_date.strftime("%Y-%m-%d")))
        else:
            item_id = request.form.get("item_id", type=int)
            item    = db.session.get(Item, item_id)
            if not item:
                error = "Item não encontrado."
            else:
                # Salvar foto
                photo_path = None
                photo = request.files.get("photo")
                if photo and photo.filename:
                    ext  = os.path.splitext(photo.filename)[1]
                    fname = f"waste_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                    photo.save(os.path.join(UPLOAD_FOLDER, fname))
                    photo_path = f"uploads/{fname}"

                w = Waste(
                    waste_date=waste_date,
                    item_id=item.id,
                    item_name=item.name,
                    quantity=qty,
                    reason=reason,
                    value=qty * item.cost,
                    photo_path=photo_path,
                )
                # Desconta do estoque
                item.stock = max(0, item.stock - qty)
                db.session.add(w)
                db.session.commit()
                flash("Desperdício registrado.")
                return redirect(url_for("desperdicio", data=waste_date.strftime("%Y-%m-%d")))

    items = Item.query.order_by(Item.name).all()
    lista = Waste.query.filter_by(waste_date=data_ref).order_by(Waste.id.desc()).all()

    return render_template("desperdicio.html",
        user=user, data_ref=data_ref,
        items=items, lista=lista,
        desperdicio_edicao=desperdicio_edicao,
        error=error,
    )


@app.route("/editar-desperdicio/<int:waste_id>", methods=["POST"])
@login_required
def editar_desperdicio(waste_id):
    return redirect(url_for("desperdicio", editar=waste_id))


@app.route("/excluir-desperdicio/<int:waste_id>", methods=["POST"])
@login_required
def excluir_desperdicio(waste_id):
    w = db.session.get(Waste, waste_id)
    if w:
        # Devolve ao estoque
        if w.item:
            w.item.stock += w.quantity
        db.session.delete(w)
        db.session.commit()
        flash("Desperdício excluído e estoque restaurado.")
    return redirect(url_for("desperdicio"))


# ─── ITENS / ESTOQUE ─────────────────────────────────────────────────────────

@app.route("/itens", methods=["GET", "POST"])
@login_required
def itens():
    user  = current_user()
    busca = request.args.get("busca", "")

    if request.method == "POST":
        item = Item(
            area=request.form.get("area"),
            code=request.form.get("code"),
            name=request.form.get("name"),
            category=request.form.get("category"),
            unit=request.form.get("unit", "un"),
            cost=float(request.form.get("cost") or 0),
            stock=float(request.form.get("stock") or 0),
            min_stock=float(request.form.get("min_stock") or 0),
        )
        db.session.add(item)
        db.session.commit()
        flash(f"Item '{item.name}' cadastrado com sucesso!")
        return redirect(url_for("itens"))

    query = Item.query
    if busca:
        like = f"%{busca}%"
        query = query.filter(
            db.or_(Item.name.ilike(like), Item.category.ilike(like), Item.code.ilike(like))
        )
    lista = query.order_by(Item.name).all()

    item_edicao = None
    editar_id   = request.args.get("editar", type=int)
    if editar_id:
        item_edicao = db.session.get(Item, editar_id)

    return render_template("cadastro_itens.html",
        user=user, areas=AREAS,
        categories=CATEGORIES,
        itens=lista, busca=busca,
        item_edicao=item_edicao,
    )


@app.route("/editar-item/<int:item_id>", methods=["POST"])
@login_required
def editar_item(item_id):
    item = db.session.get(Item, item_id)
    if item:
        item.area      = request.form.get("area")
        item.code      = request.form.get("code")
        item.name      = request.form.get("name")
        item.category  = request.form.get("category")
        item.cost      = float(request.form.get("cost") or 0)
        item.stock     = float(request.form.get("stock") or 0)
        item.min_stock = float(request.form.get("min_stock") or 0)
        db.session.commit()
        flash(f"Item '{item.name}' atualizado.")
    return redirect(url_for("itens"))


@app.route("/buscar-item")
@login_required
def buscar_item():
    code = request.args.get("code", "")
    item = Item.query.filter(db.or_(Item.code == code, Item.name.ilike(f"%{code}%"))).first()
    if item:
        return jsonify(ok=True, item=dict(
            id=item.id, name=item.name, area=item.area,
            category=item.category, unit=item.unit,
            cost=item.cost, stock=item.stock, min_stock=item.min_stock,
        ))
    return jsonify(ok=False)


# ─── RELATÓRIO DE ESTOQUE ────────────────────────────────────────────────────

@app.route("/relatorios")
@login_required
def relatorios():
    user         = current_user()
    area_ref     = request.args.get("area", "")
    categoria_ref= request.args.get("categoria", "")
    status_ref   = request.args.get("status", "")

    query = Item.query
    if area_ref:
        query = query.filter_by(area=area_ref)
    if categoria_ref:
        query = query.filter_by(category=categoria_ref)

    lista = query.order_by(Item.name).all()

    if status_ref == "baixo":
        lista = [i for i in lista if i.stock <= i.min_stock]
    elif status_ref == "normal":
        lista = [i for i in lista if i.stock > i.min_stock]

    total_itens  = len(lista)
    itens_baixos = sum(1 for i in lista if i.stock <= i.min_stock)
    valor_total  = sum((i.stock or 0) * (i.cost or 0) for i in lista)

    return render_template("relatorio_estoque.html",
        user=user, itens=lista,
        areas=AREAS, categories=CATEGORIES,
        area_ref=area_ref, categoria_ref=categoria_ref, status_ref=status_ref,
        total_itens=total_itens, itens_baixos=itens_baixos, valor_total=valor_total,
    )


# ─── MOVIMENTOS ──────────────────────────────────────────────────────────────

@app.route("/movimentos", methods=["GET", "POST"])
@login_required
def movimentos():
    user     = current_user()
    data_ref = get_selected_date()

    mov_edicao = None
    editar_id  = request.args.get("editar", type=int)
    if editar_id:
        mov_edicao = db.session.get(Movement, editar_id)

    if request.method == "POST":
        mov_date = datetime.strptime(request.form["mov_date"], "%Y-%m-%d").date()
        mov_type = request.form.get("mov_type")
        qty      = float(request.form.get("quantity") or 0)

        if mov_edicao:
            old_qty  = mov_edicao.quantity
            old_type = mov_edicao.mov_type
            # Reverte estoque anterior
            if mov_edicao.item:
                _ajustar_estoque(mov_edicao.item, old_type, -old_qty)
            mov_edicao.mov_date = mov_date
            mov_edicao.mov_type = mov_type
            mov_edicao.area     = request.form.get("area")
            mov_edicao.setor    = request.form.get("setor")
            mov_edicao.quantity = qty
            mov_edicao.value    = float(request.form.get("value") or 0)
            mov_edicao.detail   = request.form.get("detail")
            if mov_edicao.item:
                _ajustar_estoque(mov_edicao.item, mov_type, qty)
            db.session.commit()
            flash("Movimento atualizado.")
        else:
            item_id   = request.form.get("item_id", type=int)
            item      = db.session.get(Item, item_id)
            unit_cost = float(request.form.get("unit_cost") or (item.cost if item else 0))
            m = Movement(
                mov_date=mov_date, mov_type=mov_type,
                area=request.form.get("area"), setor=request.form.get("setor"),
                item_id=item.id if item else None,
                item_name=item.name if item else "—",
                quantity=qty, value=qty * unit_cost,
                detail=request.form.get("detail"),
            )
            if item:
                _ajustar_estoque(item, mov_type, qty)
            db.session.add(m)
            db.session.commit()
            flash("Movimento registrado.")

        return redirect(url_for("movimentos", data=mov_date.strftime("%Y-%m-%d")))

    items_list = Item.query.order_by(Item.name).all()
    lista      = Movement.query.filter_by(mov_date=data_ref).order_by(Movement.id.desc()).all()

    return render_template("movimentos.html",
        user=user, data_ref=data_ref,
        areas=AREAS, setores=SETORES,
        items=items_list, movimentos=lista,
        mov_edicao=mov_edicao,
    )


def _ajustar_estoque(item, mov_type, qty):
    if mov_type == "Entrada":
        item.stock += qty
    else:  # Saida | Perda
        item.stock = max(0, item.stock - qty)


@app.route("/excluir-movimento/<int:mov_id>", methods=["POST"])
@login_required
def excluir_movimento(mov_id):
    m = db.session.get(Movement, mov_id)
    if m:
        if m.item:
            _ajustar_estoque(m.item, m.mov_type, -m.quantity)
        db.session.delete(m)
        db.session.commit()
        flash("Movimento excluído e estoque ajustado.")
    return redirect(url_for("movimentos"))


@app.route("/editar-movimento/<int:mov_id>", methods=["POST"])
@login_required
def editar_movimento(mov_id):
    return redirect(url_for("movimentos", editar=mov_id))


# ─── PRODUÇÃO ────────────────────────────────────────────────────────────────

@app.route("/producao", methods=["GET", "POST"])
@login_required
def producao():
    user     = current_user()
    data_ref = get_selected_date()

    if request.method == "POST":
        item_id = request.form.get("item_id", type=int)
        item    = db.session.get(Item, item_id)
        qty     = float(request.form.get("quantity") or 0)

        p = Production(
            prod_date=datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date(),
            setor=request.form.get("setor"),
            item_id=item.id if item else None,
            item_name=item.name if item else "—",
            quantity=qty,
            cost=qty * item.cost if item else 0.0,
        )
        if item:
            item.stock += qty
        db.session.add(p)
        db.session.commit()
        flash("Produção registrada e estoque atualizado.")
        return redirect(url_for("producao", data=p.prod_date.strftime("%Y-%m-%d")))

    items_list = Item.query.order_by(Item.name).all()
    lista      = Production.query.filter_by(prod_date=data_ref).order_by(Production.id.desc()).all()

    return render_template("producao.html",
        user=user, data_ref=data_ref,
        setores=SETORES, items=items_list, lista=lista,
    )


@app.route("/excluir-producao/<int:prod_id>", methods=["POST"])
@login_required
def excluir_producao(prod_id):
    p = db.session.get(Production, prod_id)
    if p:
        if p.item:
            p.item.stock = max(0, p.item.stock - p.quantity)
        db.session.delete(p)
        db.session.commit()
        flash("Produção excluída e estoque ajustado.")
    return redirect(url_for("producao"))


# ─── VENDAS ──────────────────────────────────────────────────────────────────

@app.route("/vendas", methods=["GET", "POST"])
@login_required
def vendas():
    user     = current_user()
    data_ref = get_selected_date()

    venda_edicao = None
    editar_id    = request.args.get("editar", type=int)
    if editar_id:
        venda_edicao = db.session.get(Sale, editar_id)

    if request.method == "POST":
        sale_date  = datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date()
        unit_value = float(str(request.form.get("unit_value") or "0").replace(",", "."))
        quantity   = float(str(request.form.get("quantity") or "0").replace(",", "."))

        if venda_edicao:
            venda_edicao.sale_date  = sale_date
            venda_edicao.period     = request.form.get("period")
            venda_edicao.meal_type  = request.form.get("meal_type")
            venda_edicao.unit_value = unit_value
            venda_edicao.quantity   = quantity
            venda_edicao.notes      = request.form.get("notes")
            db.session.commit()
            flash("Venda atualizada.")
        else:
            v = Sale(
                sale_date=sale_date,
                period=request.form.get("period"),
                meal_type=request.form.get("meal_type"),
                unit_value=unit_value,
                quantity=quantity,
                notes=request.form.get("notes"),
            )
            db.session.add(v)
            db.session.commit()
            flash("Venda registrada.")

        return redirect(url_for("vendas", data=sale_date.strftime("%Y-%m-%d")))

    lista_vendas = Sale.query.filter_by(sale_date=data_ref).order_by(Sale.id.desc()).all()
    total_hoje   = sum(v.unit_value * v.quantity for v in lista_vendas)

    return render_template("vendas.html",
        user=user, data_ref=data_ref,
        meal_types=MEAL_TYPES,
        vendas=lista_vendas,
        total_hoje=total_hoje,
        venda_edicao=venda_edicao,
    )


@app.route("/editar-venda/<int:sale_id>", methods=["POST"])
@login_required
def editar_venda(sale_id):
    return redirect(url_for("vendas", editar=sale_id))


@app.route("/excluir-venda/<int:sale_id>", methods=["POST"])
@login_required
def excluir_venda(sale_id):
    v = db.session.get(Sale, sale_id)
    if v:
        db.session.delete(v)
        db.session.commit()
        flash("Venda excluída.")
    return redirect(url_for("vendas"))


# ─── RELATÓRIO GERENCIAL ─────────────────────────────────────────────────────

@app.route("/relatorio-gerencial")
@login_required
def relatorio_gerencial():
    user     = current_user()
    data_ref = get_selected_date()
    mes_ref  = get_selected_month()

    # Dia
    fat_dia = db.session.query(
        func.sum(Sale.unit_value * Sale.quantity)
    ).filter(Sale.sale_date == data_ref).scalar() or 0.0

    ref_dia = db.session.query(func.sum(Sale.quantity)).filter(Sale.sale_date == data_ref).scalar() or 0.0

    custo_dia = db.session.query(func.sum(Movement.value)).filter(
        Movement.mov_date == data_ref, Movement.mov_type == "Entrada"
    ).scalar() or 0.0

    perdas_dia = db.session.query(func.sum(Waste.value)).filter(Waste.waste_date == data_ref).scalar() or 0.0

    diario_dia = db.session.query(
        func.sum(DailyControl.sold_qty * DailyControl.unit_value)
    ).filter(DailyControl.control_date == data_ref).scalar() or 0.0

    lucro   = fat_dia - custo_dia - perdas_dia
    cmv     = round(custo_dia / fat_dia * 100, 1) if fat_dia else 0.0

    # Por período (Almoço / Janta)
    por_periodo = {}
    rows = db.session.query(
        Sale.period,
        func.sum(Sale.quantity),
        func.sum(Sale.unit_value * Sale.quantity),
    ).filter(Sale.sale_date == data_ref).group_by(Sale.period).all()
    for period, q, v in rows:
        por_periodo[period or "Outros"] = {"q": q or 0, "v": v or 0}

    # Top vendas
    ranking_rows = db.session.query(
        Sale.meal_type,
        func.sum(Sale.quantity),
        func.sum(Sale.unit_value * Sale.quantity),
    ).filter(Sale.sale_date == data_ref).group_by(Sale.meal_type).order_by(
        func.sum(Sale.unit_value * Sale.quantity).desc()
    ).limit(5).all()
    ranking_vendas = [{"tipo": r[0], "qtd": r[1] or 0, "total": r[2] or 0} for r in ranking_rows]

    # Setores (mock simplificado — pode expandir com setor nas vendas)
    resumo_setores = []

    return render_template("relatorio_gerencial.html",
        user=user, data_ref=data_ref, mes_ref=mes_ref,
        faturamento=fat_dia, refeicoes=ref_dia,
        custo=custo_dia, lucro=lucro, cmv=cmv,
        total_perdas=perdas_dia, total_diario=diario_dia,
        por_periodo=por_periodo, ranking_vendas=ranking_vendas,
        resumo_setores=resumo_setores,
    )


# ─── USUÁRIOS ────────────────────────────────────────────────────────────────

@app.route("/usuarios", methods=["GET", "POST"])
@admin_required
def usuarios():
    user = current_user()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if User.query.filter_by(username=username).first():
            flash(f"Usuário '{username}' já existe.")
        else:
            pw = request.form.get("password", "")
            if len(pw) < 6:
                flash("Senha deve ter no mínimo 6 caracteres.")
            else:
                novo = User(
                    name=request.form.get("name"),
                    username=username,
                    role=request.form.get("role", "operador"),
                )
                novo.set_password(pw)
                db.session.add(novo)
                db.session.commit()
                flash(f"Usuário '{novo.name}' criado com sucesso!")
        return redirect(url_for("usuarios"))

    lista = User.query.order_by(User.name).all()
    return render_template("usuarios.html", user=user, usuarios=lista, roles=ROLES)


@app.route("/excluir-usuario/<int:user_id>", methods=["POST"])
@admin_required
def excluir_usuario(user_id):
    u = db.session.get(User, user_id)
    if u and u.id != current_user().id:
        db.session.delete(u)
        db.session.commit()
        flash(f"Usuário '{u.name}' removido.")
    else:
        flash("Você não pode remover seu próprio usuário.")
    return redirect(url_for("usuarios"))


# ─── EXPORTAÇÕES PDF ─────────────────────────────────────────────────────────

@app.route("/exportar/estoque/pdf")
@login_required
def exportar_estoque_pdf():
    area_ref      = request.args.get("area", "")
    categoria_ref = request.args.get("categoria", "")
    status_ref    = request.args.get("status", "")

    query = Item.query
    if area_ref:      query = query.filter_by(area=area_ref)
    if categoria_ref: query = query.filter_by(category=categoria_ref)
    lista = query.order_by(Item.name).all()
    if status_ref == "baixo":  lista = [i for i in lista if i.stock <= i.min_stock]
    elif status_ref == "normal": lista = [i for i in lista if i.stock > i.min_stock]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles, title_style = _pdf_styles()

    elements = [
        Paragraph("Boi de Minas — Relatório de Estoque", title_style),
        Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        Spacer(1, 0.5*cm),
    ]

    headers = ["Item", "Área", "Categoria", "Custo Unit.", "Estoque", "Mínimo", "Subtotal", "Status"]
    rows    = [headers]
    for i in lista:
        status = "BAIXO" if i.stock <= i.min_stock else "OK"
        rows.append([
            i.name, i.area or "-", i.category or "-",
            f"R$ {i.cost:.2f}", f"{i.stock} {i.unit}",
            str(i.min_stock), f"R$ {i.stock * i.cost:.2f}", status,
        ])

    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#8b0000")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#faf7f1")]),
        ("GRID",       (0,0), (-1,-1), 0.3, colors.HexColor("#e8dfd1")),
        ("ALIGN",      (3,1), (-1,-1), "CENTER"),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"estoque_{date.today()}.pdf", as_attachment=True)


@app.route("/exportar/relatorio/pdf")
@login_required
def exportar_relatorio_pdf():
    data_ref = get_selected_date()

    vendas_list = Sale.query.filter_by(sale_date=data_ref).all()
    wastes_list = Waste.query.filter_by(waste_date=data_ref).all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles, title_style = _pdf_styles()

    faturamento = sum(v.unit_value * v.quantity for v in vendas_list)
    total_perdas= sum(w.value for w in wastes_list)

    elements = [
        Paragraph(f"Boi de Minas — Relatório Gerencial", title_style),
        Paragraph(f"Data: {data_ref.strftime('%d/%m/%Y')}  |  Gerado: {datetime.now().strftime('%H:%M')}", styles["Normal"]),
        Spacer(1, 0.4*cm),
        Paragraph(f"<b>Faturamento:</b> R$ {faturamento:.2f}  |  <b>Perdas:</b> R$ {total_perdas:.2f}", styles["Normal"]),
        Spacer(1, 0.4*cm),
        Paragraph("Vendas do Dia", styles["Heading2"]),
    ]

    v_rows = [["Período", "Tipo", "Qtd.", "Unit.", "Total"]]
    for v in vendas_list:
        v_rows.append([v.period, v.meal_type, f"{v.quantity:.3f}",
                       f"R$ {v.unit_value:.2f}", f"R$ {v.unit_value*v.quantity:.2f}"])

    tv = Table(v_rows, repeatRows=1, hAlign="LEFT")
    tv.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#8b0000")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#fafafa")]),
        ("GRID",       (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
    ]))
    elements += [tv, Spacer(1, 0.5*cm), Paragraph("Desperdícios", styles["Heading2"])]

    w_rows = [["Item", "Motivo", "Qtd.", "Valor"]]
    for w in wastes_list:
        w_rows.append([w.item_name, w.reason or "-", str(w.quantity), f"R$ {w.value:.2f}"])

    tw = Table(w_rows, repeatRows=1, hAlign="LEFT")
    tw.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#b10b0b")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#fff5f5")]),
        ("GRID",       (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
    ]))
    elements.append(tw)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"relatorio_{data_ref}.pdf", as_attachment=True)


# ─── EXPORTAÇÕES EXCEL ───────────────────────────────────────────────────────

@app.route("/exportar/estoque/xlsx")
@login_required
def exportar_estoque_xlsx():
    area_ref      = request.args.get("area", "")
    categoria_ref = request.args.get("categoria", "")
    status_ref    = request.args.get("status", "")

    query = Item.query
    if area_ref:       query = query.filter_by(area=area_ref)
    if categoria_ref:  query = query.filter_by(category=categoria_ref)
    lista = query.order_by(Item.name).all()
    if status_ref == "baixo":   lista = [i for i in lista if i.stock <= i.min_stock]
    elif status_ref == "normal": lista = [i for i in lista if i.stock > i.min_stock]

    wb = Workbook()
    ws = wb.active
    ws.title = "Estoque"
    headers = ["Item", "Código", "Área", "Categoria", "Unidade",
                "Custo Unit.", "Estoque", "Mínimo", "Subtotal", "Status"]
    _xlsx_header(ws, headers)

    for i, item in enumerate(lista, 2):
        status = "BAIXO" if item.stock <= item.min_stock else "OK"
        ws.append([
            item.name, item.code or "", item.area or "",
            item.category or "", item.unit,
            item.cost, item.stock, item.min_stock,
            item.stock * item.cost, status,
        ])
        if item.stock <= item.min_stock:
            for col in range(1, 11):
                ws.cell(i, col).fill = PatternFill("solid", fgColor="FFE5E5")

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     download_name=f"estoque_{date.today()}.xlsx", as_attachment=True)


@app.route("/exportar/relatorio/xlsx")
@login_required
def exportar_relatorio_xlsx():
    data_ref = get_selected_date()

    wb = Workbook()

    # Aba Vendas
    ws_v = wb.active
    ws_v.title = "Vendas"
    _xlsx_header(ws_v, ["Data", "Período", "Tipo", "Qtd.", "Unit. R$", "Total R$", "Obs."])
    for v in Sale.query.filter_by(sale_date=data_ref).all():
        ws_v.append([str(v.sale_date), v.period, v.meal_type,
                     v.quantity, v.unit_value, v.unit_value*v.quantity, v.notes or ""])

    # Aba Desperdícios
    ws_w = wb.create_sheet("Desperdícios")
    _xlsx_header(ws_w, ["Data", "Item", "Motivo", "Qtd.", "Valor R$"], "B10B0B")
    for w in Waste.query.filter_by(waste_date=data_ref).all():
        ws_w.append([str(w.waste_date), w.item_name, w.reason or "", w.quantity, w.value])

    # Aba Movimentos
    ws_m = wb.create_sheet("Movimentos")
    _xlsx_header(ws_m, ["Data", "Tipo", "Área", "Setor", "Item", "Qtd.", "Valor R$", "Detalhe"], "145DA0")
    for m in Movement.query.filter_by(mov_date=data_ref).all():
        ws_m.append([str(m.mov_date), m.mov_type, m.area, m.setor,
                     m.item_name, m.quantity, m.value, m.detail or ""])

    for ws in [ws_v, ws_w, ws_m]:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 16

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     download_name=f"relatorio_{data_ref}.xlsx", as_attachment=True)


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
