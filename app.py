import os
import secrets
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)

# Configurações de Segurança
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# --- MODELO DE DADOS ---
class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.Date, nullable=False)
    period = db.Column(db.String(20))
    meal_type = db.Column(db.String(80))
    unit_value = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=1.0)
    notes = db.Column(db.String(255))

# --- FUNÇÃO PARA EVITAR ERRO NO MENU ---
# Isso garante que 'current_user' e 'n_criticos' existam em todas as páginas
@app.context_processor
def inject_globals():
    return {
        'current_user': None, # Ou um objeto de usuário se tiver login
        'n_criticos': 0
    }

# --- ROTAS ---

@app.route("/")
def home():
    return redirect(url_for("vendas"))

@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    data_str = request.args.get("data")
    data_ref = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else date.today()

    if request.method == "POST":
        try:
            s_date = datetime.strptime(request.form.get("sale_date"), "%Y-%m-%d").date()
            u_val = float(request.form.get("unit_value", "0").replace(",", "."))
            qty = float(request.form.get("quantity", "1").replace(",", "."))
            
            nova_venda = Sale(
                sale_date=s_date,
                meal_type=request.form.get("meal_type"),
                unit_value=u_val,
                quantity=qty
            )
            db.session.add(nova_venda)
            db.session.commit()
            return redirect(url_for("vendas", data=s_date.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            return f"Erro ao salvar: {e}", 500

    vendas_dia = Sale.query.filter_by(sale_date=data_ref).all()
    total_hoje = sum((v.unit_value * v.quantity) for v in vendas_dia)

    return render_template("vendas.html",
                           vendas=vendas_dia,
                           total_hoje=total_hoje,
                           data_ref=data_ref,
                           meal_types=["Marmitex P", "Marmitex G", "Self-Service", "Bebida"])

# Criar rotas vazias para os outros botões não darem erro 404
@app.route("/dashboard")
@app.route("/controle")
@app.route("/desperdicio")
@app.route("/movimentos")
@app.route("/producao")
@app.route("/itens")
@app.route("/lista_compras")
@app.route("/relatorio_gerencial")
@app.route("/metas")
@app.route("/usuarios")
@app.route("/auditoria")
@app.route("/logout")
def placeholder():
    return "<h1>Em construção</h1><p>Esta tela será implementada em breve.</p><a href='/vendas'>Voltar</a>"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
