import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave-secreta-boi-minas")
uri = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads", "desperdicio")

db = SQLAlchemy(app)

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
    name = db.Column(db.String(150), nullable=False)
    cost = db.Column(db.Float, nullable=False, default=0)
    stock = db.Column(db.Float, nullable=False, default=0)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date, nullable=False, default=date.today)
    meal_type = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)

class Production(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prod_date = db.Column(db.Date, nullable=False, default=date.today)
    item_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)

class DailyBakeryControl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    control_date = db.Column(db.Date, nullable=False, default=date.today)
    item_name = db.Column(db.String(150), nullable=False)
    input_qty = db.Column(db.Integer, nullable=False, default=0)
    sold_qty = db.Column(db.Integer, nullable=False, default=0)

# --- AUXILIARES ---
def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def get_selected_date():
    raw = request.args.get("data") or request.form.get("data")
    try: return datetime.strptime(raw, "%Y-%m-%d").date()
    except: return date.today()

# --- ROTAS ---

@app.route("/setup")
def setup():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        u = User(name="Admin", username="admin", role="admin")
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()
    return "Estrutura atualizada!"

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
    if not current_user(): return redirect(url_for("login"))
    return render_template("dashboard.html", user=current_user(), data_ref=get_selected_date())

# CORREÇÃO: Adicionada a rota 'itens' que o log pediu
@app.route("/itens")
def itens():
    if not current_user(): return redirect(url_for("login"))
    items = Item.query.order_by(Item.name).all()
    return render_template("itens.html", user=current_user(), items=items)

@app.route("/vendas")
def vendas():
    if not current_user(): return redirect(url_for("login"))
    sales = Sale.query.filter_by(sale_date=get_selected_date()).all()
    return render_template("vendas.html", user=current_user(), sales=sales, data_ref=get_selected_date())

@app.route("/producao")
def producao():
    if not current_user(): return redirect(url_for("login"))
    lista = Production.query.filter_by(prod_date=get_selected_date()).all()
    items = Item.query.all()
    return render_template("producao.html", user=current_user(), lista=lista, items=items, data_ref=get_selected_date())

@app.route("/controle-diario")
def controle_diario():
    if not current_user(): return redirect(url_for("login"))
    lista = DailyBakeryControl.query.filter_by(control_date=get_selected_date()).all()
    return render_template("controle_diario.html", user=current_user(), lista=lista, data_ref=get_selected_date())

@app.route("/desperdicio")
def desperdicio():
    if not current_user(): return redirect(url_for("login"))
    return render_template("desperdicio.html", user=current_user(), data_ref=get_selected_date())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
