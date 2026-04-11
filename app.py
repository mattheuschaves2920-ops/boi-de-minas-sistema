import os
from io import BytesIO
from datetime import date, datetime

from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave-secreta-boi-minas")
uri = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads", "desperdicio")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

db = SQLAlchemy(app)

# --- CONSTANTES ---
MEAL_TYPES = ["Self-service HG", "Self-service sem balança", "Marmitex", "Comida a quilo", "Churrasco a quilo"]
AREAS = ["Estoque Geral", "Bebidas", "Freezer", "Cozinha", "Padaria", "Confeitaria"]
CATEGORIES = ["Arroz e Grãos", "Massas", "Carnes", "Frango", "Peixes", "Churrasco", "Saladas", "Temperos", "Bebidas", "Freezer", "Limpeza", "Descartáveis", "Salgados", "Bolos", "Sobremesas", "Tortas", "Pão de Queijo", "Outros"]
SETORES = ["Almoço", "Janta", "Churrasco", "Confeitaria", "Padaria", "Bebidas", "Geral"]

# --- MODELOS ---
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
    item_name = db.Column(db.String(150), nullable=False)
    input_qty = db.Column(db.Integer, nullable=False, default=0)
    sold_qty = db.Column(db.Integer, nullable=False, default=0)
    unit_value = db.Column(db.Float, nullable=False, default=0)

# --- FUNÇÕES DE SUPORTE ---
def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def require_login():
    return current_user() is not None

def get_selected_date():
    raw = request.args.get("data") or request.form.get("data")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except:
        return date.today()

# --- ROTAS PRINCIPAIS ---

@app.route("/setup")
def setup():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()
    # Migração manual de colunas
    with app.app_context():
        for stmt in ["ALTER TABLE waste ADD COLUMN IF NOT EXISTS photo_filename VARCHAR(255)", 
                     "ALTER TABLE production ADD COLUMN IF NOT EXISTS setor VARCHAR(40) DEFAULT 'Geral'"]:
            try: db.session.execute(text(stmt)); db.session.commit()
            except: db.session.rollback()
            
    if not User.query.filter_by(username="admin").first():
        u = User(name="Admin", username="admin", role="admin")
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()
    return "Setup concluído!"

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username")).first()
        if u and u.check_password(request.form.get("password")):
            session["user_id"] = u.id
            return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not require_login(): return redirect(url_for("login"))
    return render_template("dashboard.html", user=current_user(), data_ref=get_selected_date())

# ROTA QUE ESTAVA CAUSANDO O ERRO (CORRIGIDA)
@app.route("/controle-diario", methods=["GET", "POST"])
def controle_diario():
    if not require_login(): return redirect(url_for("login"))
    if request.method == "POST":
        db.session.add(DailyBakeryControl(
            control_date=datetime.strptime(request.form["control_date"], "%Y-%m-%d").date(),
            item_name=request.form["item_name"],
            input_qty=int(request.form["input_qty"]),
            sold_qty=int(request.form["sold_qty"]),
            unit_value=float(request.form["unit_value"])
        ))
        db.session.commit()
    
    data_ref = get_selected_date()
    lista = DailyBakeryControl.query.filter_by(control_date=data_ref).all()
    return render_template("controle_diario.html", user=current_user(), lista=lista, data_ref=data_ref)

@app.route("/producao", methods=["GET", "POST"])
def producao():
    if not require_login(): return redirect(url_for("login"))
    if request.method == "POST":
        item = db.session.get(Item, int(request.form["item_id"]))
        qty = float(request.form["quantity"])
        if item and qty > 0:
            item.stock -= qty
            db.session.add(Production(
                prod_date=datetime.strptime(request.form["prod_date"], "%Y-%m-%d").date(),
                setor=request.form.get("setor", "Geral"),
                item_name=item.name,
                quantity=qty,
                cost=qty * item.cost
            ))
            db.session.commit()
        return redirect(url_for("producao", data=request.form["prod_date"]))
    
    data_ref = get_selected_date()
    items = Item.query.order_by(Item.name).all()
    lista = Production.query.filter_by(prod_date=data_ref).all()
    return render_template("producao.html", user=current_user(), items=items, lista=lista, data_ref=data_ref, setores=SETORES)

@app.route("/desperdicio", methods=["GET", "POST"])
def desperdicio():
    if not require_login(): return redirect(url_for("login"))
    if request.method == "POST":
        item = db.session.get(Item, int(request.form["item_id"]))
        qty = float(request.form["quantity"])
        file = request.files.get("photo")
        fname = None
        if file and file.filename != '':
            fname = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
        
        if item and qty > 0:
            item.stock -= qty
            db.session.add(Waste(
                waste_date=datetime.strptime(request.form["waste_date"], "%Y-%m-%d").date(),
                item_name=item.name,
                quantity=qty,
                reason=request.form.get("reason"),
                value=qty * item.cost,
                photo_filename=fname
            ))
            db.session.commit()
    
    data_ref = get_selected_date()
    items = Item.query.order_by(Item.name).all()
    lista = Waste.query.filter_by(waste_date=data_ref).all()
    return render_template("desperdicio.html", user=current_user(), items=items, lista=lista, data_ref=data_ref)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
