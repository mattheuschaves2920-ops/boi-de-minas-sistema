import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave-secreta-boi-minas")
uri = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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

# --- FUNÇÕES AUXILIARES ---
def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def get_selected_date():
    raw = request.args.get("data") or request.form.get("data")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except:
        return date.today()

# --- ROTAS PRINCIPAIS ---

@app.route("/setup")
def setup():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        u = User(name="Admin", username="admin", role="admin")
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()
    return "Banco de dados pronto! Login: admin | Senha: 123456"

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
    user = current_user()
    if not user: return redirect(url_for("login"))
    
    data_ref = get_selected_date()
    
    # Adicionando 'var_faturamento' e outras variáveis de variação comuns
    # para satisfazer as condições do seu template HTML
    contexto = {
        "user": user,
        "data_ref": data_ref,
        "mes_ref": data_ref,
        "faturamento": 0.0,
        "total_vendas": 0,
        "total_producao": 0,
        "total_desperdicio": 0.0,
        # Variáveis de variação (setinhas para cima/baixo no HTML)
        "var_faturamento": 0.0,
        "var_vendas": 0.0,
        "var_producao": 0.0,
        "var_desperdicio": 0.0
    }
    
    return render_template("dashboard.html", **contexto)

# --- ROTAS DO MENU ---

@app.route("/usuarios")
def usuarios():
    u = current_user()
    if not u: return redirect(url_for("login"))
    return render_template("usuarios.html", user=u, lista=User.query.all())

@app.route("/itens")
def itens():
    u = current_user()
