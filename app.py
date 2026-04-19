import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "boi-minas-2026-super-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads", "desperdicio")

# Garante que a pasta de fotos exista
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# --- MODELOS DE BANCO DE DADOS ---

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    codigo_barras = db.Column(db.String(50), unique=True)
    categoria = db.Column(db.String(50))  # Consumo (Cozinha) ou Revenda (Bebidas)
    estoque_atual = db.Column(db.Float, default=0.0)
    estoque_minimo = db.Column(db.Float, default=5.0)
    custo_unidade = db.Column(db.Float, default=0.0)
    preco_venda = db.Column(db.Float, default=0.0)

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, default=date.today)
    periodo = db.Column(db.String(20)) # Almoço ou Janta
    tipo_refeicao = db.Column(db.String(50)) # Marmitex, Self-Service, etc.
    valor_total = db.Column(db.Float, nullable=False)
    custo_estimado = db.Column(db.Float, default=0.0) # Para o cálculo de CMV

class Desperdicio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    quantidade = db.Column(db.Float)
    foto_path = db.Column(db.String(255)) # Validação obrigatória
    motivo = db.Column(db.String(200))

# --- PROCESSADOR DE CONTEXTO (Para o base.html funcionar) ---
@app.context_processor
def inject_globals():
    # Isso impede que o base.html quebre se não houver usuário logado
    criticos = Item.query.filter(Item.estoque_atual <= Item.estoque_minimo).count()
    return {
        'n_criticos': criticos,
        'current_user': {'name': 'Gestor Boi de Minas', 'role': 'admin'}
    }

# --- ROTAS DE NAVEGAÇÃO ---

@app.route("/")
@app.route("/dashboard")
def dashboard():
    # Cálculo de CMV Simples: (Custo / Vendas) * 100
    vendas_total = db.session.query(db.func.sum(Venda.valor_total)).scalar() or 0.1
    custo_total = db.session.query(db.func.sum(Venda.custo_estimado)).scalar() or 0
    porcentagem_custo = (custo_total / vendas_total) * 100
    
    return render_template("dashboard.html", cmv=round(porcentagem_custo, 2))

@app.route("/vendas", methods=["GET", "POST"])
def vendas():
    if request.method == "POST":
        # Lógica para salvar venda e calcular CMV será inserida aqui
        flash("Venda registrada!")
        return redirect(url_for('vendas'))
    return render_template("vendas.html")

@app.route("/itens")
def itens():
    lista_itens = Item.query.all()
    return render_template("itens.html", itens=lista_itens)

@app.route("/desperdicio", methods=["GET", "POST"])
def desperdicio():
    return render_template("desperdicio.html")

# Rotas Complementares (Mapeando todos os botões do seu menu)
@app.route("/controle")
def controle(): return render_template("controle.html")

@app.route("/movimentos")
def movimentos(): return render_template("movimentos.html")

@app.route("/producao")
def producao(): return render_template("producao.html")

@app.route("/lista_compras")
def lista_compras(): return render_template("lista-compras.html")

@app.route("/relatorio_gerencial")
def relatorio_gerencial(): return render_template("relatorios.html")

@app.route("/metas")
def metas(): return render_template("metas.html")

@app.route("/usuarios")
def usuarios(): return render_template("usuarios.html")

@app.route("/auditoria")
def auditoria(): return render_template("auditoria.html")

@app.route("/logout")
def logout():
    flash("Sessão encerrada")
    return redirect(url_for('vendas'))

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    with app.app_context():
        # Este comando tenta criar as tabelas se elas não existirem
        db.create_all()
        print("Banco de dados verificado/criado com sucesso!")
        
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
