import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
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

# --- FUNÇÕES DE APOIO ---
def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def get_selected_date():
    raw = request.args.get("data") or request.form.get("data")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()

# --- ROTAS PRINCIPAIS ---

@app.route("/setup")
def setup():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(name="Administrador", username="admin", role="admin")
        admin.set_password("123456")
        db.session.add(admin)
        db.session.commit()
    return "Sistema Inicializado! <a href='/'>Ir para Login</a>"

@app.route("/", methods=["GET", "POST"], endpoint="index")
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username")).first()
        if u and u.check_password(request.form.get("password")):
            session["user_id"] = u.id
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha inválidos.")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user: return redirect(url_for("index"))
    return render_template("dashboard.html", user=user, clientes_almoco=0, venda_almoco=0.0)

# --- ROTAS DE CONTROLE (Para evitar erro 500 nos links) ---

@app.route("/controle", methods=["GET", "POST"])
def controle():
    user = current_user()
    if not user: return redirect(url_for("index"))
    data_ref = get_selected_date()
    # Mock de dados para renderizar o template que você enviou
    return render_template("controle.html", user=user, data_ref=data_ref, daily_groups=["Salgados", "Bolos"], totais={}, lista=[])

@app.route("/relatorios")
def relatorios():
    user = current_user()
    if not user: return redirect(url_for("index"))
    return render_template("relatorio_estoque.html", user=user, itens=[], total_itens=0, itens_baixos=0, valor_total=0.0)

@app.route("/desperdicio", methods=["GET", "POST"])
def desperdicio():
    user = current_user()
    if not user: return redirect(url_for("index"))
    data_ref = get_selected_date()
    return render_template("desperdicio.html", user=user, data_ref=data_ref, items=[], lista=[])

@app.route("/itens")
def itens():
    user = current_user()
    if not user: return redirect(url_for("index"))
    return render_template("cadastro_itens.html", user=user, areas=["Cozinha", "Bar"], categories=["Carnes", "Bebidas"], itens=[])

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# Rotas auxiliares para não quebrar o HTML de edição
@app.route("/editar-desperdicio/<int:waste_id>", methods=["POST"])
def editar_desperdicio(waste_id): return redirect(url_for("desperdicio"))

@app.route("/excluir-desperdicio/<int:waste_id>", methods=["POST"])
def excluir_desperdicio(waste_id): return redirect(url_for("desperdicio"))

if __name__ == "__main__":
    app.run(debug=True)
