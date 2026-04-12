import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "boi-minas-2026-seguro")

uri = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- MODELO DE USUÁRIO ---
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

# --- FUNÇÕES DE APOIO ---
def current_user():
    uid = session.get("user_id")
    if uid:
        try:
            return db.session.get(User, uid)
        except:
            return None
    return None

def get_selected_date():
    raw = request.args.get("data") or request.form.get("data")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()

# --- ROTAS ---

@app.route("/setup")
def setup():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(name="Administrador", username="admin", role="admin")
        admin.set_password("123456")
        db.session.add(admin)
        db.session.commit()
    return "Banco de dados inicializado! <br><a href='/'>Ir para Login</a>"

@app.route("/", methods=["GET", "POST"], endpoint="index")
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
    if not user: return redirect(url_for("index"))
    
    data_ref = get_selected_date()
    contexto = {
        "user": user, "data_ref": data_ref, "mes_ref": data_ref,
        "faturamento": 0.0, "faturamento_mes": 0.0, "faturamento_total": 0.0,
        "lucro_mes": 0.0, "lucro_total": 0.0, "gastos_mes": 0.0,
        "refeicoes": 0.0, "total_refeicoes": 0.0, "total_vendas": 0, "total_producao": 0,
        "desperdicio": 0.0, "desperdicio_mes": 0.0, "total_desperdicio": 0.0, "total_desperdicio_mes": 0.0,
        "var_faturamento": 0.0, "var_vendas": 0.0, "var_producao": 0.0, "var_desperdicio": 0.0, "var_lucro": 0.0,
        "meta_atingida": 0, "vendas_dia": [], "producao_dia": [], "labels_grafico": []
    }
    return render_template("dashboard.html", **contexto)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
