import os
import io
import time
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, send_file, abort)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ─── APP & CONFIG ────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"]                     = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"]             = 16 * 1024 * 1024
# CORRIGIDO: SESSION_COOKIE_HTTPONLY e SAMESITE para maior segurança
app.config["SESSION_COOKIE_HTTPONLY"]        = True
app.config["SESSION_COOKIE_SAMESITE"]        = "Lax"
# Em produção com HTTPS, ative: app.config["SESSION_COOKIE_SECURE"] = True

uri = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# CORRIGIDO: extensões de imagem permitidas para upload
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

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
    id        = db.Column(db.Integer, primary_key=True)
    mov_date  = db.Column(db.Date, nullable=False, default=date.today)
    mov_type  = db.Column(db.String(20))
    area      = db.Column(db.String(80))
    setor     = db.Column(db.String(80))
    item_id   = db.Column(db.Integer, db.ForeignKey("items.id"))
    item_name = db.Column(db.String(120))
    quantity  = db.Column(db.Float, default=0.0)
    value     = db.Column(db.Float, default=0.0)
    detail    = db.Column(db.String(255))
    item      = db.relationship("Item", backref="movements")


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
    period     = db.Column(db.String(20))
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


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id          = db.Column(db.Integer, primary_key=True)
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username    = db.Column(db.String(80))
    action      = db.Column(db.String(80), nullable=False)
    resource    = db.Column(db.String(80))
    resource_id = db.Column(db.Integer, nullable=True)
    detail      = db.Column(db.String(255))
    ip_address  = db.Column(db.String(45))


class StockAlert(db.Model):
    __tablename__ = "stock_alerts"
    id          = db.Column(db.Integer, primary_key=True)
    item_id     = db.Column(db.Integer, db.ForeignKey("items.id"), unique=True)
    whatsapp    = db.Column(db.String(20))
    notified_at = db.Column(db.DateTime)
    item        = db.relationship("Item", backref="alert")


class MonthlyGoal(db.Model):
    __tablename__ = "monthly_goals"
    id    = db.Column(db.Integer, primary_key=True)
    year  = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    goal  = db.Column(db.Float, default=0.0)
    __table_args__ = (db.UniqueConstraint("year", "month"),)


# ─── CONSTANTES ──────────────────────────────────────────────────────────────

AREAS        = ["Cozinha", "Bar", "Confeitaria", "Açougue", "Estoque Geral"]
CATEGORIES   = ["Carnes", "Bebidas", "Laticínios", "Hortifruti", "Grãos",
                "Temperos", "Descartáveis", "Outros"]
SETORES      = ["Cozinha", "Bar", "Salão", "Confeitaria", "Açougue"]
MEAL_TYPES   = ["Buffet Kg", "Executivo", "À La Carte", "Rodízio", "Marmita"]
DAILY_GROUPS = ["Salgados", "Bolos", "Doces", "Bebidas", "Outros"]
ROLES        = ["admin", "gerente", "operador"]

# CORRIGIDO: tipos e áreas válidos para validação de formulários
_VALID_MOV_TYPES  = {"Entrada", "Saida", "Perda"}
_VALID_AREAS      = set(AREAS)
_VALID_SETORES    = set(SETORES)
_VALID_MEAL_TYPES = set(MEAL_TYPES)
_VALID_GROUPS     = set(DAILY_GROUPS)
_VALID_ROLES      = set(ROLES)

# ─── RATE LIMITING ───────────────────────────────────────────────────────────

_login_attempts: dict = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 10
BLOCK_WINDOW       = 300  # 5 minutos


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < BLOCK_WINDOW]
    _login_attempts[ip].append(now)
    return len(_login_attempts[ip]) > MAX_LOGIN_ATTEMPTS


def _reset_rate_limit(ip: str):
    _login_attempts.pop(ip, None)


# ─── CSRF ────────────────────────────────────────────────────────────────────

def _gen_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


@app.before_request
def _csrf_protect():
    if request.method == "POST":
        exempt = getattr(app.view_functions.get(request.endpoint), "_csrf_exempt", False)
        if not exempt:
            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not token or token != session.get("csrf_token"):
                abort(403)


def csrf_exempt(f):
    f._csrf_exempt = True
    return f


app.jinja_env.globals["csrf_token"] = _gen_csrf
# CORRIGIDO: expõe now() para os templates (usado em metas.html)
app.jinja_env.globals["now"] = datetime.now

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


def audit(action, resource=None, resource_id=None, detail=None):
    try:
        log = AuditLog(
            user_id=session.get("user_id"),
            username=session.get("_username", "—"),
            action=action,
            resource=resource,
            resource_id=resource_id,
            detail=detail,
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass


def _ajustar_estoque(item, mov_type, qty):
    if mov_type == "Entrada":
        item.stock += qty
    else:
        item.stock = max(0.0, item.stock - qty)


def _itens_criticos():
    return [i for i in Item.query.all() if i.stock <= i.min_stock and i.min_stock > 0]


def _pdf_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=16, textColor=colors.HexColor("#8b0000"), spaceAfter=12,
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


# CORRIGIDO: validação de extensão de arquivo de upload
def _allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# CORRIGIDO: parse seguro de float vindo de formulário
def _parse_float(value, default=0.0) -> float:
    try:
        return float(str(value or "").replace(",", "."))
    except (ValueError, TypeError):
        return default


@app.context_processor
def inject_globals():
    u = current_user()
    criticos = _itens_criticos() if u else []
    return dict(
        current_user=u,
        itens_criticos=criticos,
        n_criticos=len(criticos),
    )


# ─── SETUP ───────────────────────────────────────────────────────────────────

# CORRIGIDO: rota /setup bloqueada por variável de ambiente.
# Em produção, defina ALLOW_SETUP=0 no ambiente para desativar completamente.
@app.route("/setup")
def setup():
    if os.getenv("ALLOW_SETUP", "1") != "1":
        abort(404)
    if User.query.first():
        return "Sistema já inicializado.", 403
    db.create_all()
    admin = User(name="Administrador", username="admin", role="admin")
    admin.set_password("admin@2026!")
    db.session.add(admin)
    db.session.commit()
    return "Inicializado! Login: admin | Senha: admin@2026!"


# ─── AUTH ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"], endpoint="index")
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        ip = request.remote_addr
        if _is_rate_limited(ip):
            error = "Muitas tentativas. Tente novamente em 5 minutos."
        else:
            u = User.query.filter_by(username=request.form.get("username")).first()
            if u and u.check_password(request.form.get("password")):
                session.clear()          # CORRIGIDO: limpa sessão anterior antes de criar nova
                session["user_id"]   = u.id
                session["_username"] = u.username
                _reset_rate_limit(ip)
                audit("LOGIN", resource="User", resource_id=u.id)
                return redirect(url_for("dashboard"))
            error = "Usuário ou senha inválidos."
            audit("LOGIN_FAIL", detail=request.form.get("username"))
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    audit("LOGOUT")
    session.clear()
    return redirect(url_for("index"))


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    data_ref = get_selected_date()
    mes_ref  = get_selected_month()

    faturamento = db.session.query(
        func.sum(Sale.unit_value * Sale.quantity)
    ).filter(Sale.sale_date == data_ref).scalar() or 0.0

    faturamento_mes = db.session.query(
        func.sum(Sale.unit_value * Sale.quantity)
    ).filter(
        func.strftime("%Y-%m", Sale.sale_date) == mes_ref.strftime("%Y-%m")
    ).scalar() or 0.0

    refeicoes = db.session.query(
        func.sum(Sale.quantity)
    ).filter(Sale.sale_date == data_ref).scalar() or 0.0

    custo = db.session.query(func.sum(Movement.value)).filter(
        Movement.mov_date == data_ref, Movement.mov_type == "Entrada"
    ).scalar() or 0.0

    desperdicio = db.session.query(
        func.sum(Waste.value)
    ).filter(Waste.waste_date == data_ref).scalar() or 0.0

    desperdicio_mes = db.session.query(
        func.sum(Waste.value)
    ).filter(
        func.strftime("%Y-%m", Waste.waste_date) == mes_ref.strftime("%Y-%m")
    ).scalar() or 0.0

    lucro = faturamento - custo - desperdicio
    cmv   = round(custo / faturamento * 100, 1) if faturamento else 0.0

    meta_obj   = MonthlyGoal.query.filter_by(year=mes_ref.year, month=mes_ref.month).first()
    meta_valor = meta_obj.goal if meta_obj else 0.0
    meta_pct   = round(faturamento_mes / meta_valor * 100, 1) if meta_valor else 0.0

    # Gráfico dos últimos 7 dias
    labels_grafico  = []
    valores_grafico = []
    for i in range(6, -1, -1):
        d = data_ref - timedelta(days=i)
        v = db.session.query(
            func.sum(Sale.unit_value * Sale.quantity)
        ).filter(Sale.sale_date == d).scalar() or 0.0
        labels_grafico.append(d.strftime("%d/%m"))
        valores_grafico.append(round(v, 2))

    # Por período hoje
    vendas_por_periodo = {}
    rows = db.session.query(
        Sale.period,
        func.sum(Sale.quantity),
        func.sum(Sale.unit_value * Sale.quantity),
    ).filter(Sale.sale_date == data_ref).group_by(Sale.period).all()
    for period, q, v in rows:
        vendas_por_periodo[period or "Outros"] = {"q": q or 0, "v": v or 0}

    return render_template("dashboard.html",
        data_ref=data_ref, mes_ref=mes_ref,
        faturamento=faturamento, faturamento_mes=faturamento_mes,
        refeicoes=refeicoes, custo=custo, lucro=lucro, cmv=cmv,
        desperdicio=desperdicio, desperdicio_mes=desperdicio_mes,
        meta_valor=meta_valor, meta_pct=meta_pct,
        labels_grafico=labels_grafico,
        valores_grafico=valores_grafico,
        vendas_por_periodo=vendas_por_periodo,
    )


# ─── CONTROLE DIÁRIO ─────────────────────────────────────────────────────────

@app.route("/controle", methods=["GET", "POST"])
@login_required
def controle():
    data_ref = get_selected_date()
    if request.method == "POST":
        # CORRIGIDO: validação do group_name contra lista permitida
        group = request.form.get("group_name")
        if group not in _VALID_GROUPS:
            group = "Outros"

        ctrl = DailyControl(
            control_date=datetime.strptime(request.form["control_date"], "%Y-%m-%d").date(),
            group_name=group,
            item_name=request.form.get("item_name", "").strip(),
            input_qty=_parse_float(request.form.get("input_qty")),
            output_qty=_parse_float(request.form.get("output_qty")),
            sold_qty=_parse_float(request.form.get("sold_qty")),
            unit_value=_parse_float(request.form.get("unit_value")),
            notes=request.form.get("notes"),
        )
        db.session.add(ctrl)
        db.session.commit()
        audit("CREATE", "DailyControl", ctrl.id, ctrl.item_name)
        flash("Lançamento salvo!")
        return redirect(url_for("controle", data=ctrl.control_date.strftime("%Y-%m-%d")))

    lista  = DailyControl.query.filter_by(control_date=data_ref).order_by(DailyControl.group_name).all()
    totais = {}
    for r in lista:
        g = r.group_name or "Geral"
        if g not in totais:
            totais[g] = {"vendido": 0, "faturado": 0.0}
        totais[g]["vendido"]  += r.sold_qty
        totais[g]["faturado"] += r.sold_qty * r.unit_value

    return render_template("controle.html",
        data_ref=data_ref, daily_groups=DAILY_GROUPS,
        totais=totais, lista=lista,
    )


# ─── DESPERDÍCIO ─────────────────────────────────────────────────────────────

@app.route("/desperdicio", methods=["GET", "POST"])
@login_required
def desperdicio():
    data_ref = get_selected_date()
    error    = None

    desperdicio_edicao = None
    editar_id = request.args.get("editar", type=int)
    if editar_id:
        desperdicio_edicao = db.session.get(Waste, editar_id)

    if request.method == "POST":
        waste_date = datetime.strptime(request.form["waste_date"], "%Y-%m-%d").date()
        qty        = _parse_float(request.form.get("quantity"))  # CORRIGIDO: usa _parse_float
        reason     = request.form.get("reason")

        if desperdicio_edicao:
            desperdicio_edicao.waste_date = waste_date
            desperdicio_edicao.quantity   = qty
            desperdicio_edicao.reason     = reason
            if desperdicio_edicao.item:
                desperdicio_edicao.value = qty * desperdicio_edicao.item.cost
            db.session.commit()
            audit("UPDATE", "Waste", desperdicio_edicao.id, desperdicio_edicao.item_name)
            flash("Desperdício atualizado.")
            return redirect(url_for("desperdicio", data=waste_date.strftime("%Y-%m-%d")))

        item_id = request.form.get("item_id", type=int)
        item    = db.session.get(Item, item_id)
        if not item:
            error = "Item não encontrado."
        else:
            photo_path = None
            photo = request.files.get("photo")
            # CORRIGIDO: valida extensão antes de salvar o arquivo
            if photo and photo.filename:
                if not _allowed_file(photo.filename):
                    error = "Formato de imagem inválido. Use JPG, PNG ou WEBP."
                else:
                    ext   = os.path.splitext(photo.filename)[1].lower()
                    fname = f"waste_{secrets.token_hex(8)}{ext}"   # CORRIGIDO: nome aleatório (evita colisão e path traversal)
                    photo.save(os.path.join(UPLOAD_FOLDER, fname))
                    photo_path = f"uploads/{fname}"

            if not error:
                w = Waste(
                    waste_date=waste_date, item_id=item.id, item_name=item.name,
                    quantity=qty, reason=reason, value=qty * item.cost,
                    photo_path=photo_path,
                )
                item.stock = max(0.0, item.stock - qty)
                db.session.add(w)
                db.session.commit()
                audit("CREATE", "Waste", w.id, f"{item.name} qty={qty}")
                flash("Desperdício registrado.")
                return redirect(url_for("desperdicio", data=waste_date.strftime("%Y-%m-%d")))

    items = Item.query.order_by(Item.name).all()
    lista = Waste.query.filter_by(waste_date=data_ref).order_by(Waste.id.desc()).all()
    return render_template("desperdicio.html",
        data_ref=data_ref, items=items, lista=lista,
        desperdicio_edicao=desperdicio_edicao, error=error,
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
        if w.item:
            w.item.stock += w.quantity
        audit("DELETE", "Waste", w.id, w.item_name)
        db.session.delete(w)
        db.session.commit()
        flash("Desperdício excluído e estoque restaurado.")
    return redirect(url_for("desperdicio"))


# ─── ITENS / ESTOQUE ─────────────────────────────────────────────────────────

@app.route("/itens", methods=["GET", "POST"])
@login_required
def itens():
    busca = request.args.get("busca", "")
    if request.method == "POST":
        # CORRIGIDO: valida área contra lista permitida
        area = request.form.get("area")
        if area not in _VALID_AREAS:
            area = None

        item = Item(
            area=area,
            code=request.form.get("code", "").strip(),
            name=request.form.get("name", "").strip(),
            category=request.form.get("category"),
            unit=request.form.get("unit", "un"),
            cost=_parse_float(request.form.get("cost")),
            stock=_parse_float(request.form.get("stock")),
            min_stock=_parse_float(request.form.get("min_stock")),
        )
        if not item.name:
            flash("Nome do item é obrigatório.")
            return redirect(url_for("itens"))

        db.session.add(item)
        db.session.commit()
        audit("CREATE", "Item", item.id, item.name)
        flash(f"Item '{item.name}' cadastrado!")
        return redirect(url_for("itens"))

    query = Item.query
    if busca:
        like  = f"%{busca}%"
        query = query.filter(db.or_(
            Item.name.ilike(like), Item.category.ilike(like), Item.code.ilike(like)
        ))
    lista = query.order_by(Item.name).all()

    item_edicao = None
    editar_id   = request.args.get("editar", type=int)
    if editar_id:
        item_edicao = db.session.get(Item, editar_id)

    return render_template("cadastro_itens.html",
        areas=AREAS, categories=CATEGORIES,
        itens=lista, busca=busca, item_edicao=item_edicao,
    )


@app.route("/editar-item/<int:item_id>", methods=["POST"])
@login_required
def editar_item(item_id):
    item = db.session.get(Item, item_id)
    if item:
        area = request.form.get("area")
        item.area      = area if area in _VALID_AREAS else item.area
        item.code      = request.form.get("code", "").strip()
        item.name      = request.form.get("name", "").strip() or item.name
        item.category  = request.form.get("category")
        item.cost      = _parse_float(request.form.get("cost"))
        item.stock     = _parse_float(request.form.get("stock"))
        item.min_stock = _parse_float(request.form.get("min_stock"))
        db.session.commit()
        audit("UPDATE", "Item", item.id, item.name)
        flash(f"Item '{item.name}' atualizado.")
    return redirect(url_for("itens"))


@app.route("/buscar-item")
@login_required
def buscar_item():
    code = request.args.get("code", "")
    item = Item.query.filter(
        db.or_(Item.code == code, Item.name.ilike(f"%{code}%"))
    ).first()
    if item:
        return jsonify(ok=True, item=dict(
            id=item.id, name=item.name, area=item.area,
            category=item.category, unit=item.unit,
            cost=item.cost, stock=item.stock, min_stock=item.min_stock,
        ))
    return jsonify(ok=False)


# ─── LISTA DE COMPRAS ────────────────────────────────────────────────────────

@app.route("/lista-compras")
@login_required
def lista_compras():
    criticos    = _itens_criticos()
    lista       = []
    for i in criticos:
        falta    = max(0.0, i.min_stock - i.stock)
        sugestao = max(falta, i.min_stock)
        lista.append({
            "item":     i,
            "falta":    round(falta, 3),
            "sugestao": round(sugestao, 3),
            "custo_est":round(sugestao * i.cost, 2),
        })
    total_custo = sum(l["custo_est"] for l in lista)
    return render_template("lista_compras.html", lista=lista, total_custo=total_custo)


@app.route("/exportar/lista-compras/xlsx")
@login_required
def exportar_lista_compras_xlsx():
    criticos = _itens_criticos()
    wb = Workbook()
    ws = wb.active
    ws.title = "Lista de Compras"
    _xlsx_header(ws, ["Item", "Área", "Categoria", "Unidade",
                      "Estoque Atual", "Mínimo", "Falta", "Sugestão", "Custo Est. R$"])
    for i in criticos:
        falta    = max(0.0, i.min_stock - i.stock)
        sugestao = max(falta, i.min_stock)
        ws.append([
            i.name, i.area or "", i.category or "", i.unit,
            i.stock, i.min_stock, round(falta, 3),
            round(sugestao, 3), round(sugestao * i.cost, 2),
        ])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name=f"lista_compras_{date.today()}.xlsx", as_attachment=True)


# ─── RELATÓRIO DE ESTOQUE ────────────────────────────────────────────────────

@app.route("/relatorios")
@login_required
def relatorios():
    area_ref      = request.args.get("area", "")
    categoria_ref = request.args.get("categoria", "")
    status_ref    = request.args.get("status", "")
    query = Item.query
    if area_ref:      query = query.filter_by(area=area_ref)
    if categoria_ref: query = query.filter_by(category=categoria_ref)
    lista = query.order_by(Item.name).all()
    if status_ref == "baixo":    lista = [i for i in lista if i.stock <= i.min_stock]
    elif status_ref == "normal": lista = [i for i in lista if i.stock > i.min_stock]

    total_itens  = len(lista)
    itens_baixos = sum(1 for i in lista if i.stock <= i.min_stock)
    valor_total  = sum((i.stock or 0) * (i.cost or 0) for i in lista)

    return render_template("relatorio_estoque.html",
        itens=lista, areas=AREAS, categories=CATEGORIES,
        area_ref=area_ref, categoria_ref=categoria_ref, status_ref=status_ref,
        total_itens=total_itens, itens_baixos=itens_baixos, valor_total=valor_total,
    )


# ─── MOVIMENTOS ──────────────────────────────────────────────────────────────

@app.route("/movimentos", methods=["GET", "POST"])
@login_required
def movimentos():
    data_ref   = get_selected_date()
    mov_edicao = None
    editar_id  = request.args.get("editar", type=int)
    if editar_id:
        mov_edicao = db.session.get(Movement, editar_id)

    if request.method == "POST":
        mov_date = datetime.strptime(request.form["mov_date"], "%Y-%m-%d").date()
        # CORRIGIDO: valida mov_type contra lista permitida
        mov_type = request.form.get("mov_type")
        if mov_type not in _VALID_MOV_TYPES:
            flash("Tipo de movimentação inválido.")
            return redirect(url_for("movimentos"))

        qty = _parse_float(request.form.get("quantity"))

        if mov_edicao:
            if mov_edicao.item:
                _ajustar_estoque(mov_edicao.item, mov_edicao.mov_type, -mov_edicao.quantity)
            mov_edicao.mov_date = mov_date
            mov_edicao.mov_type = mov_type
            mov_edicao.area     = request.form.get("area")
            mov_edicao.setor    = request.form.get("setor")
            mov_edicao.quantity = qty
            mov_edicao.value    = _parse_float(request.form.get("value"))
            mov_edicao.detail   = request.form.get("detail")
            if mov_edicao.item:
                _ajustar_estoque(mov_edicao.item, mov_type, qty)
            db.session.commit()
            audit("UPDATE", "Movement", mov_edicao.id)
            flash("Movimento atualizado.")
        else:
            item_id   = request.form.get("item_id", type=int)
            item      = db.session.get(Item, item_id)
            unit_cost = _parse_float(request.form.get("unit_cost")) or (item.cost if item else 0)
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
            audit("CREATE", "Movement", m.id, f"{m.item_name} {mov_type}")
            flash("Movimento registrado.")

        return redirect(url_for("movimentos", data=mov_date.strftime("%Y-%m-%d")))

    items_list = Item.query.order_by(Item.name).all()
    lista      = Movement.query.filter_by(mov_date=data_ref).order_by(Movement.id.desc()).all()
    return render_template("movimentos.html",
        data_ref=data_ref, areas=AREAS, setores=SETORES,
        items=items_list, movimentos=lista, mov_edicao=mov_edicao,
    )


@app.route("/excluir-movimento/<int:mov_id>", methods=["POST"])
@login_required
def excluir_movimento(mov_id):
    m = db.session.get(Movement, mov_id)
    if m:
        if m.item:
            _ajustar_estoque(m.item, m.mov_type, -m.quantity)
        audit("DELETE", "Movement", m.id, m.item_name)
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
    data_ref = get_selected_date()
    if request.method == "POST":
        item_id = request.form.get("item_id", type=int)
        item    = db.session.get(Item, item_id)
        # CORRIGIDO: verifica se item existe antes de usar
        if not item:
            flash("Item não encontrado.")
            return redirect(url_for("producao"))

        qty = _parse_float(request.form.get("quantity"))
        p = Production(
            prod_date=datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date(),
            setor=request.form.get("setor"),
            item_id=item.id,
            item_name=item.name,
            quantity=qty,
            cost=qty * item.cost,
        )
        item.stock += qty
        db.session.add(p)
        db.session.commit()
        audit("CREATE", "Production", p.id, p.item_name)
        flash("Produção registrada e estoque atualizado.")
        return redirect(url_for("producao", data=p.prod_date.strftime("%Y-%m-%d")))

    items_list = Item.query.order_by(Item.name).all()
    lista      = Production.query.filter_by(prod_date=data_ref).order_by(Production.id.desc()).all()
    return render_template("producao.html",
        data_ref=data_ref, setores=SETORES, items=items_list, lista=lista,
    )


@app.route("/excluir-producao/<int:prod_id>", methods=["POST"])
@login_required
def excluir_producao(prod_id):
    p = db.session.get(Production, prod_id)
    if p:
        if p.item:
            p.item.stock = max(0.0, p.item.stock - p.quantity)
        audit("DELETE", "Production", p.id, p.item_name)
        db.session.delete(p)
        db.session.commit()
        flash("Produção excluída e estoque ajustado.")
    return redirect(url_for("producao"))


# ─── VENDAS ──────────────────────────────────────────────────────────────────

@app.route("/vendas", methods=["GET", "POST"])
@login_required
def vendas():
    data_ref     = get_selected_date()
    venda_edicao = None
    editar_id    = request.args.get("editar", type=int)
    if editar_id:
        venda_edicao = db.session.get(Sale, editar_id)

    if request.method == "POST":
        sale_date  = datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date()
        unit_value = _parse_float(request.form.get("unit_value"))  # CORRIGIDO: usa _parse_float
        quantity   = _parse_float(request.form.get("quantity"))

        # CORRIGIDO: valida meal_type
        meal_type = request.form.get("meal_type")
        if meal_type not in _VALID_MEAL_TYPES:
            flash("Tipo de refeição inválido.")
            return redirect(url_for("vendas"))

        if venda_edicao:
            venda_edicao.sale_date  = sale_date
            venda_edicao.period     = request.form.get("period")
            venda_edicao.meal_type  = meal_type
            venda_edicao.unit_value = unit_value
            venda_edicao.quantity   = quantity
            venda_edicao.notes      = request.form.get("notes")
            db.session.commit()
            audit("UPDATE", "Sale", venda_edicao.id)
            flash("Venda atualizada.")
        else:
            v = Sale(
                sale_date=sale_date, period=request.form.get("period"),
                meal_type=meal_type, unit_value=unit_value, quantity=quantity,
                notes=request.form.get("notes"),
            )
            db.session.add(v)
            db.session.commit()
            audit("CREATE", "Sale", v.id, f"{v.meal_type} R${v.unit_value*v.quantity:.2f}")
            flash("Venda registrada.")

        return redirect(url_for("vendas", data=sale_date.strftime("%Y-%m-%d")))

    lista_vendas = Sale.query.filter_by(sale_date=data_ref).order_by(Sale.id.desc()).all()
    total_hoje   = sum(v.unit_value * v.quantity for v in lista_vendas)
    return render_template("vendas.html",
        data_ref=data_ref, meal_types=MEAL_TYPES,
        vendas=lista_vendas, total_hoje=total_hoje,
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
        audit("DELETE", "Sale", v.id)
        db.session.delete(v)
        db.session.commit()
        flash("Venda excluída.")
    return redirect(url_for("vendas"))


# ─── RELATÓRIO GERENCIAL ─────────────────────────────────────────────────────

@app.route("/relatorio-gerencial")
@login_required
def relatorio_gerencial():
    data_ref = get_selected_date()
    mes_ref  = get_selected_month()

    fat_dia    = db.session.query(func.sum(Sale.unit_value * Sale.quantity)).filter(Sale.sale_date == data_ref).scalar() or 0.0
    ref_dia    = db.session.query(func.sum(Sale.quantity)).filter(Sale.sale_date == data_ref).scalar() or 0.0
    custo_dia  = db.session.query(func.sum(Movement.value)).filter(Movement.mov_date == data_ref, Movement.mov_type == "Entrada").scalar() or 0.0
    perdas_dia = db.session.query(func.sum(Waste.value)).filter(Waste.waste_date == data_ref).scalar() or 0.0
    diario_dia = db.session.query(func.sum(DailyControl.sold_qty * DailyControl.unit_value)).filter(DailyControl.control_date == data_ref).scalar() or 0.0

    lucro = fat_dia - custo_dia - perdas_dia
    cmv   = round(custo_dia / fat_dia * 100, 1) if fat_dia else 0.0

    por_periodo = {}
    for period, q, v in db.session.query(
        Sale.period, func.sum(Sale.quantity), func.sum(Sale.unit_value * Sale.quantity)
    ).filter(Sale.sale_date == data_ref).group_by(Sale.period).all():
        por_periodo[period or "Outros"] = {"q": q or 0, "v": v or 0}

    ranking_rows = db.session.query(
        Sale.meal_type, func.sum(Sale.quantity),
        func.sum(Sale.unit_value * Sale.quantity),
    ).filter(Sale.sale_date == data_ref).group_by(Sale.meal_type).order_by(
        func.sum(Sale.unit_value * Sale.quantity).desc()
    ).limit(5).all()
    ranking_vendas = [{"tipo": r[0], "qtd": r[1] or 0, "total": r[2] or 0} for r in ranking_rows]

    return render_template("relatorio_gerencial.html",
        data_ref=data_ref, mes_ref=mes_ref,
        faturamento=fat_dia, refeicoes=ref_dia, custo=custo_dia,
        lucro=lucro, cmv=cmv, total_perdas=perdas_dia, total_diario=diario_dia,
        por_periodo=por_periodo, ranking_vendas=ranking_vendas, resumo_setores=[],
    )


# ─── METAS ───────────────────────────────────────────────────────────────────

@app.route("/metas", methods=["GET", "POST"])
@admin_required
def metas():
    if request.method == "POST":
        year  = int(request.form.get("year") or date.today().year)
        month = int(request.form.get("month") or date.today().month)
        # CORRIGIDO: valida intervalo de mês e ano
        if not (1 <= month <= 12) or not (2024 <= year <= 2100):
            flash("Mês ou ano inválido.")
            return redirect(url_for("metas"))
        goal = _parse_float(request.form.get("goal"))
        m = MonthlyGoal.query.filter_by(year=year, month=month).first()
        if m:
            m.goal = goal
        else:
            db.session.add(MonthlyGoal(year=year, month=month, goal=goal))
        db.session.commit()
        flash(f"Meta de {month:02d}/{year} definida em R$ {goal:,.2f}")
        return redirect(url_for("metas"))

    metas_list = MonthlyGoal.query.order_by(
        MonthlyGoal.year.desc(), MonthlyGoal.month.desc()
    ).all()
    return render_template("metas.html", metas=metas_list)


# ─── LOG DE AUDITORIA ────────────────────────────────────────────────────────

@app.route("/auditoria")
@admin_required
def auditoria():
    page = request.args.get("page", 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template("auditoria.html", logs=logs)


# ─── USUÁRIOS ────────────────────────────────────────────────────────────────

@app.route("/usuarios", methods=["GET", "POST"])
@admin_required
def usuarios():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        # CORRIGIDO: valida role contra lista permitida
        role = request.form.get("role", "operador")
        if role not in _VALID_ROLES:
            flash("Perfil inválido.")
            return redirect(url_for("usuarios"))

        if User.query.filter_by(username=username).first():
            flash(f"Usuário '{username}' já existe.")
        else:
            pw = request.form.get("password", "")
            if len(pw) < 6:
                flash("Senha deve ter no mínimo 6 caracteres.")
            else:
                novo = User(
                    name=request.form.get("name", "").strip(),
                    username=username,
                    role=role,
                )
                novo.set_password(pw)
                db.session.add(novo)
                db.session.commit()
                audit("CREATE", "User", novo.id, novo.username)
                flash(f"Usuário '{novo.name}' criado!")
        return redirect(url_for("usuarios"))

    lista = User.query.order_by(User.name).all()
    return render_template("usuarios.html", usuarios=lista, roles=ROLES)


@app.route("/excluir-usuario/<int:user_id>", methods=["POST"])
@admin_required
def excluir_usuario(user_id):
    u = db.session.get(User, user_id)
    if u and u.id != current_user().id:
        audit("DELETE", "User", u.id, u.username)
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
    if status_ref == "baixo":    lista = [i for i in lista if i.stock <= i.min_stock]
    elif status_ref == "normal": lista = [i for i in lista if i.stock > i.min_stock]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles, title_style = _pdf_styles()
    elements = [
        Paragraph("Boi de Minas — Relatório de Estoque", title_style),
        Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        Spacer(1, 0.5*cm),
    ]
    rows = [["Item", "Área", "Categoria", "Custo Unit.", "Estoque", "Mínimo", "Subtotal", "Status"]]
    for i in lista:
        rows.append([
            i.name, i.area or "-", i.category or "-",
            f"R$ {i.cost:.2f}", f"{i.stock} {i.unit}", str(i.min_stock),
            f"R$ {i.stock * i.cost:.2f}",
            "BAIXO" if i.stock <= i.min_stock else "OK",
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
    data_ref     = get_selected_date()
    vendas_list  = Sale.query.filter_by(sale_date=data_ref).all()
    wastes_list  = Waste.query.filter_by(waste_date=data_ref).all()
    faturamento  = sum(v.unit_value * v.quantity for v in vendas_list)
    total_perdas = sum(w.value for w in wastes_list)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles, title_style = _pdf_styles()
    elements = [
        Paragraph("Boi de Minas — Relatório Gerencial", title_style),
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
    if area_ref:      query = query.filter_by(area=area_ref)
    if categoria_ref: query = query.filter_by(category=categoria_ref)
    lista = query.order_by(Item.name).all()
    if status_ref == "baixo":    lista = [i for i in lista if i.stock <= i.min_stock]
    elif status_ref == "normal": lista = [i for i in lista if i.stock > i.min_stock]

    wb = Workbook()
    ws = wb.active
    ws.title = "Estoque"
    _xlsx_header(ws, ["Item","Código","Área","Categoria","Unidade",
                      "Custo Unit.","Estoque","Mínimo","Subtotal","Status"])
    for i, item in enumerate(lista, 2):
        status = "BAIXO" if item.stock <= item.min_stock else "OK"
        ws.append([item.name, item.code or "", item.area or "",
                   item.category or "", item.unit, item.cost,
                   item.stock, item.min_stock, item.stock * item.cost, status])
        if item.stock <= item.min_stock:
            for col in range(1, 11):
                ws.cell(i, col).fill = PatternFill("solid", fgColor="FFE5E5")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name=f"estoque_{date.today()}.xlsx", as_attachment=True)


@app.route("/exportar/relatorio/xlsx")
@login_required
def exportar_relatorio_xlsx():
    data_ref = get_selected_date()
    wb = Workbook()
    ws_v = wb.active
    ws_v.title = "Vendas"
    _xlsx_header(ws_v, ["Data","Período","Tipo","Qtd.","Unit. R$","Total R$","Obs."])
    for v in Sale.query.filter_by(sale_date=data_ref).all():
        ws_v.append([str(v.sale_date), v.period, v.meal_type,
                     v.quantity, v.unit_value, v.unit_value*v.quantity, v.notes or ""])
    ws_w = wb.create_sheet("Desperdícios")
    _xlsx_header(ws_w, ["Data","Item","Motivo","Qtd.","Valor R$"], "B10B0B")
    for w in Waste.query.filter_by(waste_date=data_ref).all():
        ws_w.append([str(w.waste_date), w.item_name, w.reason or "", w.quantity, w.value])
    ws_m = wb.create_sheet("Movimentos")
    _xlsx_header(ws_m, ["Data","Tipo","Área","Setor","Item","Qtd.","Valor R$","Detalhe"], "145DA0")
    for m in Movement.query.filter_by(mov_date=data_ref).all():
        ws_m.append([str(m.mov_date), m.mov_type, m.area, m.setor,
                     m.item_name, m.quantity, m.value, m.detail or ""])
    for ws in [ws_v, ws_w, ws_m]:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 16
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name=f"relatorio_{data_ref}.xlsx", as_attachment=True)


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
