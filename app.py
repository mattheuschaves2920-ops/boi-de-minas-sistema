import os
import csv
from io import StringIO, BytesIO
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque-esta-chave")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db").replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads", "desperdicio")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

db = SQLAlchemy(app)


def corrigir_banco():
    with app.app_context():
        try:
            db.session.execute(text("""
                ALTER TABLE waste
                ADD COLUMN IF NOT EXISTS photo_filename VARCHAR(255);
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()


corrigir_banco()

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
    quantity = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.String(120), nullable=True)


class Movement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mov_date = db.Column(db.Date, nullable=False, default=date.today)
    mov_type = db.Column(db.String(20), nullable=False)
    area = db.Column(db.String(40), nullable=False)
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


def render_desperdicio_page(error=None):
    items = Item.query.order_by(Item.name).all()
    lista = Waste.query.order_by(Waste.id.desc()).limit(200).all()
    return render_template("desperdicio.html", user=current_user(), items=items, lista=lista, error=error)


@app.route("/setup")
def setup():
    ensure_upload_folder()
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        user = User(name="Administrador", username="admin", role="admin")
        user.set_password("123456")
        db.session.add(user)
        db.session.commit()

    return "Sistema criado. Login inicial: admin / 123456"


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

    today = date.today()
    sales_today = Sale.query.filter_by(sale_date=today).all()
    moves_today = Movement.query.filter_by(mov_date=today).all()
    items = Item.query.order_by(Item.area, Item.name).all()
    waste_today = Waste.query.filter_by(waste_date=today).all()
    production_today = Production.query.filter_by(prod_date=today).all()
    bakery_today = DailyBakeryControl.query.filter_by(control_date=today).all()

    faturamento = sum(s.unit_value * s.quantity for s in sales_today)
    faturamento_padaria = sum(b.unit_value * b.sold_qty for b in bakery_today)
    refeicoes = sum(s.quantity for s in sales_today)
    custo = sum(m.value for m in moves_today if m.mov_type in ["Saida", "Perda"]) + sum(w.value for w in waste_today)
    lucro = faturamento + faturamento_padaria - custo
    alertas = [i for i in items if i.stock <= i.min_stock]
    producao_custo = sum(p.cost for p in production_today)
    desperdicio_valor = sum(w.value for w in waste_today)
    vendidos_diarios = sum(b.sold_qty for b in bakery_today)

    por_periodo = {"Almoço": {"q": 0, "v": 0}, "Janta": {"q": 0, "v": 0}}
    for s in sales_today:
        if s.period in por_periodo:
            por_periodo[s.period]["q"] += s.quantity
            por_periodo[s.period]["v"] += s.unit_value * s.quantity

    vendas_almoco = [s for s in sales_today if s.period == "Almoço"]
    faturamento_almoco = sum(s.unit_value * s.quantity for s in vendas_almoco)
    custo_almoco = producao_custo + desperdicio_valor
    lucro_bruto_almoco = faturamento_almoco - custo_almoco

    labels_grafico = []
    valores_grafico = []

    for i in range(6, -1, -1):
        dia = today - timedelta(days=i)
        vendas_dia = Sale.query.filter_by(sale_date=dia).all()
        total_dia = sum(v.unit_value * v.quantity for v in vendas_dia)
        labels_grafico.append(dia.strftime("%d/%m"))
        valores_grafico.append(round(total_dia, 2))

    return render_template(
        "dashboard.html",
        user=current_user(),
        faturamento=faturamento,
        faturamento_padaria=faturamento_padaria,
        refeicoes=refeicoes,
        custo=custo,
        lucro=lucro,
        alertas=alertas,
        por_periodo=por_periodo,
        producao_custo=producao_custo,
        desperdicio_valor=desperdicio_valor,
        vendidos_diarios=vendidos_diarios,
        faturamento_almoco=faturamento_almoco,
        custo_almoco=custo_almoco,
        lucro_bruto_almoco=lucro_bruto_almoco,
        labels_grafico=labels_grafico,
        valores_grafico=valores_grafico
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
            unit_value=float(request.form.get("unit_value") or 0),
            quantity=int(request.form.get("quantity") or 0),
            notes=request.form.get("notes", "").strip(),
            created_by=current_user().name if current_user() else "",
        ))
        db.session.commit()
        return redirect(url_for("vendas"))

    vendas_lista = Sale.query.order_by(Sale.id.desc()).limit(200).all()
    return render_template("vendas.html", user=current_user(), vendas=vendas_lista, meal_types=MEAL_TYPES)


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
            item_name=item.name,
            quantity=qty,
            detail=request.form.get("detail", "").strip(),
            value=qty * item.cost,
            created_by=current_user().name if current_user() else "",
        ))
        db.session.commit()
        return redirect(url_for("movimentos"))

    movimentos_lista = Movement.query.order_by(Movement.id.desc()).limit(300).all()
    return render_template("movimentos.html", user=current_user(), movimentos=movimentos_lista, items=items, areas=AREAS)


@app.route("/producao", methods=["GET", "POST"])
def producao():
    if not require_login():
        return redirect(url_for("login"))

    items = Item.query.order_by(Item.name).all()

    if request.method == "POST":
        item = db.session.get(Item, int(request.form["item_id"]))
        qty = float(request.form.get("quantity") or 0)

        if item and qty:
            item.stock -= qty
            db.session.add(Production(
                prod_date=datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date(),
                item_name=item.name,
                quantity=qty,
                cost=qty * item.cost
            ))
            db.session.commit()

        return redirect(url_for("producao"))

    lista = Production.query.order_by(Production.id.desc()).limit(200).all()
    return render_template("producao.html", user=current_user(), items=items, lista=lista)


@app.route("/desperdicio", methods=["GET", "POST"])
def desperdicio():
    if not require_login():
        return redirect(url_for("login"))

    ensure_upload_folder()

    if request.method == "POST":
        photo = request.files.get("photo")

        if not photo or not photo.filename:
            return render_desperdicio_page("Para salvar a perda, é obrigatório tirar ou enviar uma foto do desperdício.")

        if not allowed_image(photo.filename):
            return render_desperdicio_page("Formato de foto inválido. Use PNG, JPG, JPEG ou WEBP.")

        item = db.session.get(Item, int(request.form["item_id"]))
        qty = float(request.form.get("quantity") or 0)

        if not item or qty <= 0:
            return render_desperdicio_page("Selecione um item válido e informe uma quantidade maior que zero.")

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
        return redirect(url_for("desperdicio"))

    return render_desperdicio_page()


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
        return redirect(url_for("controle_diario"))

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

    total_items = Item.query.count()
    total_alertas = Item.query.filter(Item.stock <= Item.min_stock).count()
    total_perdas = db.session.query(db.func.sum(Waste.value)).scalar() or 0
    total_vendas = db.session.query(db.func.sum(Sale.unit_value * Sale.quantity)).scalar() or 0
    total_refeicoes = db.session.query(db.func.sum(Sale.quantity)).scalar() or 0
    ticket_medio = (total_vendas / total_refeicoes) if total_refeicoes else 0
    total_producao = db.session.query(db.func.sum(Production.cost)).scalar() or 0
    total_diario = db.session.query(db.func.sum(DailyBakeryControl.sold_qty * DailyBakeryControl.unit_value)).scalar() or 0
    total_perdas_com_foto = Waste.query.filter(Waste.photo_filename.isnot(None)).count()

    por_periodo = {"Almoço": {"q": 0, "v": 0}, "Janta": {"q": 0, "v": 0}}
    for s in Sale.query.all():
        if s.period in por_periodo:
            por_periodo[s.period]["q"] += s.quantity
            por_periodo[s.period]["v"] += s.unit_value * s.quantity

    return render_template(
        "relatorios.html",
        user=current_user(),
        total_items=total_items,
        total_alertas=total_alertas,
        total_perdas=total_perdas,
        total_vendas=total_vendas,
        total_refeicoes=total_refeicoes,
        ticket_medio=ticket_medio,
        total_producao=total_producao,
        total_diario=total_diario,
        total_perdas_com_foto=total_perdas_com_foto,
        por_periodo=por_periodo
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
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="vendas.csv")


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
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="controle_diario.csv")


if __name__ == "__main__":
    ensure_upload_folder()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
