import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY","troque-esta-chave")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL","sqlite:///boi.db").replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

AREAS=["Estoque Geral","Bebidas","Freezer"]
CATEGORIES=["Arroz e Grãos","Massas","Carnes","Frango","Peixes","Churrasco","Saladas","Temperos","Bebidas","Freezer","Limpeza","Descartáveis","Outros"]
MEAL_TYPES=["Self-service HG","Self-service sem balança","Marmitex","Comida a quilo","Churrasco a quilo"]
ROLES=["admin","estoquista","operador","proprietario"]

class User(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(120), nullable=False)
    username=db.Column(db.String(80), unique=True, nullable=False)
    password_hash=db.Column(db.String(255), nullable=False)
    role=db.Column(db.String(30), nullable=False, default="operador")
    def set_password(self, p): self.password_hash=generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash,p)

class Item(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    area=db.Column(db.String(40), nullable=False)
    code=db.Column(db.String(80))
    name=db.Column(db.String(150), nullable=False)
    category=db.Column(db.String(80))
    unit=db.Column(db.String(20), nullable=False, default="kg")
    cost=db.Column(db.Float, nullable=False, default=0)
    stock=db.Column(db.Float, nullable=False, default=0)
    min_stock=db.Column(db.Float, nullable=False, default=0)

class Sale(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    sale_date=db.Column(db.Date, nullable=False, default=date.today)
    meal_type=db.Column(db.String(80), nullable=False)
    period=db.Column(db.String(20), nullable=False)
    unit_value=db.Column(db.Float, nullable=False, default=0)
    quantity=db.Column(db.Integer, nullable=False, default=0)

class Movement(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    mov_date=db.Column(db.Date, nullable=False, default=date.today)
    mov_type=db.Column(db.String(20), nullable=False)
    area=db.Column(db.String(40), nullable=False)
    item_name=db.Column(db.String(150), nullable=False)
    quantity=db.Column(db.Float, nullable=False, default=0)
    detail=db.Column(db.String(255))
    value=db.Column(db.Float, nullable=False, default=0)

def current_user():
    uid=session.get("user_id")
    return db.session.get(User, uid) if uid else None

def logged():
    return current_user() is not None

@app.route("/setup")
def setup():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        u=User(name="Administrador", username="admin", role="admin")
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()
    return "Sistema criado. Login inicial: admin / 123456"

@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form.get("username","").strip()
        password=request.form.get("password","").strip()
        user=User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"]=user.id
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Usuário ou senha inválidos.")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if not logged(): return redirect(url_for("login"))
    today=date.today()
    sales=Sale.query.filter_by(sale_date=today).all()
    moves=Movement.query.filter_by(mov_date=today).all()
    items=Item.query.order_by(Item.area, Item.name).all()
    faturamento=sum(s.unit_value*s.quantity for s in sales)
    refeicoes=sum(s.quantity for s in sales)
    custo=sum(m.value for m in moves if m.mov_type in ["Saida","Perda"])
    lucro=faturamento-custo
    alertas=[i for i in items if i.stock<=i.min_stock]
    return render_template("dashboard.html", user=current_user(), faturamento=faturamento, refeicoes=refeicoes, custo=custo, lucro=lucro, alertas=alertas)

@app.route("/buscar-item")
def buscar_item():
    if not logged(): return jsonify({"ok":False}),401
    code=request.args.get("code","").strip()
    item=Item.query.filter_by(code=code).first()
    if not item:
        return jsonify({"ok":False,"message":"Produto não cadastrado"})
    return jsonify({"ok":True,"item":{
        "id":item.id,"name":item.name,"area":item.area,"category":item.category,
        "unit":item.unit,"cost":item.cost,"stock":item.stock,"min_stock":item.min_stock,"code":item.code
    }})

@app.route("/itens", methods=["GET","POST"])
def itens():
    if not logged(): return redirect(url_for("login"))
    if request.method=="POST":
        code=request.form.get("code","").strip()
        name=request.form["name"].strip()
        area=request.form["area"]
        existing = Item.query.filter_by(code=code).first() if code else None
        if not existing:
            existing = Item.query.filter_by(name=name, area=area).first()
        if existing:
            existing.code=code or existing.code
            existing.name=name
            existing.area=area
            existing.category=request.form.get("category","")
            existing.unit=request.form["unit"]
            existing.cost=float(request.form.get("cost") or 0)
            existing.stock=float(request.form.get("stock") or 0)
            existing.min_stock=float(request.form.get("min_stock") or 0)
        else:
            db.session.add(Item(
                area=area, code=code, name=name,
                category=request.form.get("category",""), unit=request.form["unit"],
                cost=float(request.form.get("cost") or 0), stock=float(request.form.get("stock") or 0),
                min_stock=float(request.form.get("min_stock") or 0)
            ))
        db.session.commit()
        return redirect(url_for("itens"))
    return render_template("itens.html", user=current_user(), itens=Item.query.order_by(Item.area, Item.name).all(), areas=AREAS, categories=CATEGORIES)

@app.route("/movimentos", methods=["GET","POST"])
def movimentos():
    if not logged(): return redirect(url_for("login"))
    items=Item.query.order_by(Item.name).all()
    if request.method=="POST":
        item=None
        item_id=request.form.get("item_id")
        barcode=request.form.get("barcode","").strip()
        if item_id: item=db.session.get(Item, int(item_id))
        elif barcode: item=Item.query.filter_by(code=barcode).first()
        if not item: return redirect(url_for("movimentos"))
        qty=float(request.form.get("quantity") or 0)
        if request.form["mov_type"]=="Entrada":
            item.stock += qty
            if request.form.get("unit_cost"): item.cost=float(request.form.get("unit_cost") or 0)
        else:
            item.stock -= qty
        db.session.add(Movement(
            mov_date=datetime.strptime(request.form["mov_date"], "%Y-%m-%d").date(),
            mov_type=request.form["mov_type"], area=request.form["area"],
            item_name=item.name, quantity=qty, detail=request.form.get("detail",""),
            value=qty*item.cost
        ))
        db.session.commit()
        return redirect(url_for("movimentos"))
    return render_template("movimentos.html", user=current_user(), movimentos=Movement.query.order_by(Movement.id.desc()).limit(300).all(), items=items, areas=AREAS)

@app.route("/vendas", methods=["GET","POST"])
def vendas():
    if not logged(): return redirect(url_for("login"))
    if request.method=="POST":
        db.session.add(Sale(
            sale_date=datetime.strptime(request.form["sale_date"], "%Y-%m-%d").date(),
            meal_type=request.form["meal_type"], period=request.form["period"],
            unit_value=float(request.form.get("unit_value") or 0), quantity=int(request.form.get("quantity") or 0)
        ))
        db.session.commit()
        return redirect(url_for("vendas"))
    return render_template("vendas.html", user=current_user(), vendas=Sale.query.order_by(Sale.id.desc()).limit(200).all(), meal_types=MEAL_TYPES)

@app.route("/usuarios", methods=["GET","POST"])
def usuarios():
    if not logged() or current_user().role!="admin": return redirect(url_for("dashboard"))
    if request.method=="POST":
        u=User(name=request.form["name"], username=request.form["username"], role=request.form["role"])
        u.set_password(request.form["password"])
        db.session.add(u); db.session.commit()
        return redirect(url_for("usuarios"))
    return render_template("usuarios.html", user=current_user(), usuarios=User.query.order_by(User.name).all(), roles=ROLES)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
