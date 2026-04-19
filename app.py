 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 8e215023585f65cc6283d8c9c0c1ba563aaef9d2..a369176358f4e63b9ec2e986013f8a3d8b80e5b8 100644
--- a/app.py
+++ b/app.py
@@ -1,127 +1,783 @@
 import os
+from dataclasses import dataclass
 from datetime import date, datetime
-from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
+from math import ceil
+
+from flask import Flask, flash, redirect, render_template, request, url_for
 from flask_sqlalchemy import SQLAlchemy
 from flask_wtf.csrf import CSRFProtect
 from werkzeug.utils import secure_filename
 
 app = Flask(__name__)
 
 # --- CONFIGURAÇÕES ---
 app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "boi-minas-2026-super-secret")
 app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///boi_de_minas.db")
 app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
 app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads", "desperdicio")
 
-# Garante que a pasta de fotos exista
 os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
 
+ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic"}
+AREAS = ["Cozinha", "Bar", "Depósito", "Limpeza", "Salão"]
+SETORES = ["Cozinha Quente", "Cozinha Fria", "Padaria", "Bar", "Estoque"]
+MEAL_TYPES = ["Marmitex", "Self-Service", "Prato Feito", "Bebidas", "Sobremesas"]
+ROLES = ["admin", "gerente", "operador"]
+
+
 db = SQLAlchemy(app)
 csrf = CSRFProtect(app)
 
-# --- MODELOS DE BANCO DE DADOS ---
 
+# --- MODELOS DE BANCO DE DADOS ---
 class Item(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     nome = db.Column(db.String(100), nullable=False)
     codigo_barras = db.Column(db.String(50), unique=True)
-    categoria = db.Column(db.String(50))  # Consumo (Cozinha) ou Revenda (Bebidas)
+    categoria = db.Column(db.String(50))
     estoque_atual = db.Column(db.Float, default=0.0)
     estoque_minimo = db.Column(db.Float, default=5.0)
     custo_unidade = db.Column(db.Float, default=0.0)
     preco_venda = db.Column(db.Float, default=0.0)
 
+
 class Venda(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     data = db.Column(db.Date, default=date.today)
-    periodo = db.Column(db.String(20)) # Almoço ou Janta
-    tipo_refeicao = db.Column(db.String(50)) # Marmitex, Self-Service, etc.
+    periodo = db.Column(db.String(20))
+    tipo_refeicao = db.Column(db.String(50))
     valor_total = db.Column(db.Float, nullable=False)
-    custo_estimado = db.Column(db.Float, default=0.0) # Para o cálculo de CMV
+    custo_estimado = db.Column(db.Float, default=0.0)
+
 
 class Desperdicio(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     data = db.Column(db.DateTime, default=datetime.now)
-    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
+    item_id = db.Column(db.Integer, db.ForeignKey("item.id"))
     quantidade = db.Column(db.Float)
-    foto_path = db.Column(db.String(255)) # Validação obrigatória
+    foto_path = db.Column(db.String(255))
     motivo = db.Column(db.String(200))
 
-# --- PROCESSADOR DE CONTEXTO (Para o base.html funcionar) ---
+
+@dataclass
+class SimpleLog:
+    timestamp: datetime
+    username: str
+    action: str
+    resource: str
+    detail: str
+    ip_address: str
+    resource_id: int | None = None
+
+
+@dataclass
+class SimplePagination:
+    items: list
+    page: int
+    pages: int
+
+    @property
+    def has_prev(self):
+        return self.page > 1
+
+    @property
+    def has_next(self):
+        return self.page < self.pages
+
+    @property
+    def prev_num(self):
+        return max(1, self.page - 1)
+
+    @property
+    def next_num(self):
+        return min(self.pages, self.page + 1)
+
+
+USERS = [{"id": 1, "name": "Gestor Boi de Minas", "username": "admin", "role": "admin"}]
+MOVIMENTOS_DATA = []
+PRODUCOES_DATA = []
+METAS_DATA = []
+AUDITORIA_LOGS = []
+
+
+# --- HELPERS ---
+def _allowed_file(filename: str) -> bool:
+    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
+
+
+def _parse_data_ref(data_texto: str | None) -> date:
+    if not data_texto:
+        return date.today()
+    try:
+        return datetime.strptime(data_texto, "%Y-%m-%d").date()
+    except ValueError:
+        return date.today()
+
+
+def _parse_mes_ref(mes_texto: str | None) -> date:
+    if not mes_texto:
+        hoje = date.today()
+        return date(hoje.year, hoje.month, 1)
+    try:
+        dt = datetime.strptime(mes_texto, "%Y-%m")
+        return date(dt.year, dt.month, 1)
+    except ValueError:
+        hoje = date.today()
+        return date(hoje.year, hoje.month, 1)
+
+
+def _item_view(item: Item):
+    return {
+        "id": item.id,
+        "name": item.nome,
+        "area": item.categoria or "-",
+        "category": item.categoria or "-",
+        "code": item.codigo_barras or "",
+        "stock": item.estoque_atual or 0,
+        "min_stock": item.estoque_minimo or 0,
+        "unit": "kg",
+        "cost": item.custo_unidade or 0,
+    }
+
+
+def _log_action(action: str, resource: str, detail: str, resource_id: int | None = None):
+    AUDITORIA_LOGS.insert(
+        0,
+        SimpleLog(
+            timestamp=datetime.now(),
+            username="admin",
+            action=action,
+            resource=resource,
+            detail=detail,
+            ip_address=request.remote_addr or "127.0.0.1",
+            resource_id=resource_id,
+        ),
+    )
+
+
+def _dados_desperdicio(data_ref: date):
+    itens = Item.query.order_by(Item.nome.asc()).all()
+    inicio = datetime.combine(data_ref, datetime.min.time())
+    fim = datetime.combine(data_ref, datetime.max.time())
+
+    registros = (
+        db.session.query(Desperdicio, Item)
+        .join(Item, Item.id == Desperdicio.item_id)
+        .filter(Desperdicio.data >= inicio, Desperdicio.data <= fim)
+        .order_by(Desperdicio.data.desc())
+        .all()
+    )
+
+    lista = []
+    for desperdicio, item in registros:
+        lista.append(
+            {
+                "id": desperdicio.id,
+                "item_name": item.nome,
+                "quantity": desperdicio.quantidade,
+                "reason": desperdicio.motivo,
+                "value": (desperdicio.quantidade or 0) * (item.custo_unidade or 0),
+            }
+        )
+
+    return itens, lista
+
+
+def _badge_class(action: str) -> str:
+    action = (action or "").lower()
+    if any(t in action for t in ["exclu", "delete", "remove"]):
+        return "error"
+    if any(t in action for t in ["edit", "atual", "update"]):
+        return "info"
+    return "success"
+
+
+# --- CONTEXTO GLOBAL ---
 @app.context_processor
 def inject_globals():
-    # Isso impede que o base.html quebre se não houver usuário logado
     criticos = Item.query.filter(Item.estoque_atual <= Item.estoque_minimo).count()
     return {
-        'n_criticos': criticos,
-        'current_user': {'name': 'Gestor Boi de Minas', 'role': 'admin'}
+        "n_criticos": criticos,
+        "current_user": USERS[0],
+        "now": datetime.now,
     }
 
-# --- ROTAS DE NAVEGAÇÃO ---
 
+# --- ROTAS ---
 @app.route("/")
 @app.route("/dashboard")
 def dashboard():
-    # Cálculo de CMV Simples: (Custo / Vendas) * 100
-    vendas_total = db.session.query(db.func.sum(Venda.valor_total)).scalar() or 0.1
-    custo_total = db.session.query(db.func.sum(Venda.custo_estimado)).scalar() or 0
-    porcentagem_custo = (custo_total / vendas_total) * 100
-    
-    return render_template("dashboard.html", cmv=round(porcentagem_custo, 2))
+    data_ref = _parse_data_ref(request.args.get("data"))
+    mes_ref = _parse_mes_ref(request.args.get("mes"))
+
+    vendas = Venda.query.filter(Venda.data == data_ref).all()
+    faturamento = sum(v.valor_total or 0 for v in vendas)
+    custo = sum(v.custo_estimado or 0 for v in vendas)
+    refeicoes = len(vendas)
+    lucro = faturamento - custo
+    cmv = round((custo / faturamento) * 100, 2) if faturamento > 0 else 0
+
+    desperdicios_hoje = db.session.query(Desperdicio, Item).join(Item, Item.id == Desperdicio.item_id).filter(
+        db.func.date(Desperdicio.data) == data_ref
+    ).all()
+    desperdicio = sum((d.quantidade or 0) * (i.custo_unidade or 0) for d, i in desperdicios_hoje)
+
+    desperdicios_mes = db.session.query(Desperdicio, Item).join(Item, Item.id == Desperdicio.item_id).filter(
+        db.extract("year", Desperdicio.data) == mes_ref.year,
+        db.extract("month", Desperdicio.data) == mes_ref.month,
+    ).all()
+    desperdicio_mes = sum((d.quantidade or 0) * (i.custo_unidade or 0) for d, i in desperdicios_mes)
+
+    labels_grafico = [data_ref.strftime("%d/%m")]
+    valores_grafico = [faturamento]
+
+    por_periodo = {}
+    for v in vendas:
+        chave = v.periodo or "Geral"
+        atual = por_periodo.get(chave, {"q": 0, "v": 0.0})
+        atual["q"] += 1
+        atual["v"] += v.valor_total or 0
+        por_periodo[chave] = atual
+
+    meta_valor = next((m["goal"] for m in METAS_DATA if m["year"] == mes_ref.year and m["month"] == mes_ref.month), 0)
+    meta_pct = round((faturamento / meta_valor) * 100, 2) if meta_valor else 0
+
+    return render_template(
+        "dashboard.html",
+        data_ref=data_ref,
+        mes_ref=mes_ref,
+        faturamento=faturamento,
+        custo=custo,
+        refeicoes=refeicoes,
+        lucro=lucro,
+        cmv=cmv,
+        desperdicio=desperdicio,
+        desperdicio_mes=desperdicio_mes,
+        meta_valor=meta_valor,
+        meta_pct=meta_pct,
+        labels_grafico=labels_grafico,
+        valores_grafico=valores_grafico,
+        vendas_por_periodo_labels=list(por_periodo.keys()),
+        vendas_por_periodo_values=[v["v"] for v in por_periodo.values()],
+    )
+
 
 @app.route("/vendas", methods=["GET", "POST"])
 def vendas():
+    data_ref = _parse_data_ref(request.args.get("data"))
+    editar_id = request.args.get("editar", type=int)
+
     if request.method == "POST":
-        # Lógica para salvar venda e calcular CMV será inserida aqui
-        flash("Venda registrada!")
-        return redirect(url_for('vendas'))
-    return render_template("vendas.html")
+        sale_date = _parse_data_ref(request.form.get("sale_date"))
+        meal_type = request.form.get("meal_type") or "Marmitex"
+        unit_value = request.form.get("unit_value", type=float) or 0
+        quantity = request.form.get("quantity", type=float) or 0
+        total = unit_value * quantity
+        periodo = "Almoço" if datetime.now().hour < 16 else "Janta"
+
+        if editar_id:
+            venda = Venda.query.get_or_404(editar_id)
+            venda.data = sale_date
+            venda.tipo_refeicao = meal_type
+            venda.valor_total = total
+            venda.periodo = periodo
+            venda.custo_estimado = total * 0.35
+            _log_action("Atualização", "Venda", f"Venda {editar_id} atualizada", editar_id)
+            flash("Venda atualizada.", "success")
+        else:
+            venda = Venda(
+                data=sale_date,
+                tipo_refeicao=meal_type,
+                valor_total=total,
+                periodo=periodo,
+                custo_estimado=total * 0.35,
+            )
+            db.session.add(venda)
+            _log_action("Criação", "Venda", f"Venda criada: {meal_type}")
+            flash("Venda registrada!", "success")
+
+        db.session.commit()
+        return redirect(url_for("vendas", data=sale_date.strftime("%Y-%m-%d")))
 
-@app.route("/itens")
+    vendas_dia = Venda.query.filter(Venda.data == data_ref).order_by(Venda.id.desc()).all()
+    venda_edicao = None
+    if editar_id:
+        v = Venda.query.get_or_404(editar_id)
+        venda_edicao = {
+            "id": v.id,
+            "sale_date": v.data,
+            "meal_type": v.tipo_refeicao,
+            "unit_value": v.valor_total,
+            "quantity": 1,
+        }
+
+    vendas_template = [
+        {
+            "id": v.id,
+            "meal_type": v.tipo_refeicao or "-",
+            "quantity": 1,
+            "unit_value": v.valor_total or 0,
+        }
+        for v in vendas_dia
+    ]
+
+    return render_template(
+        "vendas.html",
+        data_ref=data_ref,
+        venda_edicao=venda_edicao,
+        meal_types=MEAL_TYPES,
+        vendas=vendas_template,
+        total_hoje=sum(v.valor_total or 0 for v in vendas_dia),
+    )
+
+
+@app.route("/vendas/<int:sale_id>/excluir", methods=["POST"])
+def excluir_venda(sale_id: int):
+    venda = Venda.query.get_or_404(sale_id)
+    data_ref = venda.data
+    db.session.delete(venda)
+    db.session.commit()
+    _log_action("Exclusão", "Venda", f"Venda {sale_id} excluída", sale_id)
+    flash("Venda excluída.", "success")
+    return redirect(url_for("vendas", data=data_ref.strftime("%Y-%m-%d")))
+
+
+@app.route("/itens", methods=["GET", "POST"])
 def itens():
-    lista_itens = Item.query.all()
-    return render_template("itens.html", itens=lista_itens)
+    if request.method == "POST":
+        novo = Item(
+            nome=request.form.get("name", "Item sem nome"),
+            codigo_barras=request.form.get("code") or None,
+            categoria=request.form.get("area") or "Cozinha",
+            estoque_atual=request.form.get("stock", type=float) or 0,
+            estoque_minimo=request.form.get("min_stock", type=float) or 0,
+            custo_unidade=request.form.get("cost", type=float) or 0,
+        )
+        db.session.add(novo)
+        db.session.commit()
+        _log_action("Criação", "Item", f"Item {novo.nome} criado", novo.id)
+        flash("Item cadastrado com sucesso.", "success")
+        return redirect(url_for("itens"))
+
+    lista_itens = Item.query.order_by(Item.nome.asc()).all()
+    return render_template("itens.html", itens=[_item_view(i) for i in lista_itens], areas=AREAS)
+
 
 @app.route("/desperdicio", methods=["GET", "POST"])
 def desperdicio():
-    return render_template("desperdicio.html")
+    data_ref = _parse_data_ref(request.args.get("data"))
+    desperdicio_edicao = None
+
+    if request.method == "POST":
+        item_id = request.form.get("item_id", type=int)
+        quantity = request.form.get("quantity", type=float)
+        reason = request.form.get("reason", "Outros")
+        waste_date = _parse_data_ref(request.form.get("waste_date"))
+        photo = request.files.get("photo")
+
+        if not item_id:
+            flash("Selecione um item.", "error")
+            return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+        if not quantity or quantity <= 0:
+            flash("Quantidade deve ser maior que zero.", "error")
+            return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+        if not photo or not photo.filename:
+            flash("A foto é obrigatória para registrar desperdício.", "error")
+            return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+        if not _allowed_file(photo.filename):
+            flash("Formato de foto inválido.", "error")
+            return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+
+        filename = secure_filename(photo.filename)
+        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
+        destino = os.path.join(app.config["UPLOAD_FOLDER"], filename)
+        photo.save(destino)
+
+        registro = Desperdicio(
+            data=datetime.combine(waste_date, datetime.utcnow().time()),
+            item_id=item_id,
+            quantidade=quantity,
+            foto_path=os.path.join("uploads", "desperdicio", filename),
+            motivo=reason,
+        )
+        db.session.add(registro)
+        db.session.commit()
+        _log_action("Criação", "Desperdício", f"Desperdício registrado para item {item_id}", registro.id)
+        flash("Desperdício registrado com foto.", "success")
+        return redirect(url_for("desperdicio", data=waste_date.strftime("%Y-%m-%d")))
+
+    editar_id = request.args.get("editar", type=int)
+    if editar_id:
+        registro = Desperdicio.query.get_or_404(editar_id)
+        item = Item.query.get(registro.item_id)
+        desperdicio_edicao = {
+            "id": registro.id,
+            "waste_date": registro.data.date(),
+            "quantity": registro.quantidade,
+            "reason": registro.motivo,
+            "item_name": item.nome if item else "Item removido",
+        }
+
+    itens_db, lista = _dados_desperdicio(data_ref)
+    items_template = [{"id": i.id, "name": i.nome, "area": i.categoria or "-"} for i in itens_db]
 
-# Rotas Complementares (Mapeando todos os botões do seu menu)
-@app.route("/controle")
-def controle(): return render_template("controle.html")
+    return render_template(
+        "desperdicio.html",
+        data_ref=data_ref,
+        desperdicio_edicao=desperdicio_edicao,
+        error=None,
+        items=items_template,
+        lista=lista,
+    )
 
-@app.route("/movimentos")
-def movimentos(): return render_template("movimentos.html")
 
-@app.route("/producao")
-def producao(): return render_template("producao.html")
+@app.route("/desperdicio/<int:waste_id>/editar", methods=["POST"])
+def editar_desperdicio(waste_id: int):
+    registro = Desperdicio.query.get_or_404(waste_id)
+    quantity = request.form.get("quantity", type=float)
+    reason = request.form.get("reason", "Outros")
+    waste_date = _parse_data_ref(request.form.get("waste_date"))
+
+    if not quantity or quantity <= 0:
+        flash("Quantidade deve ser maior que zero.", "error")
+        return redirect(url_for("desperdicio", editar=waste_id, data=waste_date.strftime("%Y-%m-%d")))
+
+    registro.quantidade = quantity
+    registro.motivo = reason
+    registro.data = datetime.combine(waste_date, registro.data.time())
+    db.session.commit()
+    _log_action("Atualização", "Desperdício", f"Desperdício {waste_id} atualizado", waste_id)
+    flash("Desperdício atualizado.", "success")
+    return redirect(url_for("desperdicio", data=waste_date.strftime("%Y-%m-%d")))
+
+
+@app.route("/desperdicio/<int:waste_id>/excluir", methods=["POST"])
+def excluir_desperdicio(waste_id: int):
+    registro = Desperdicio.query.get_or_404(waste_id)
+    data_ref = registro.data.date()
+
+    if registro.foto_path:
+        caminho_foto = os.path.join("static", registro.foto_path)
+        if os.path.exists(caminho_foto):
+            os.remove(caminho_foto)
+
+    db.session.delete(registro)
+    db.session.commit()
+    _log_action("Exclusão", "Desperdício", f"Desperdício {waste_id} excluído", waste_id)
+    flash("Registro excluído.", "success")
+    return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+
+
+@app.route("/controle", methods=["GET", "POST"])
+def controle():
+    if request.method == "POST":
+        flash("Controle diário salvo.", "success")
+        _log_action("Criação", "Controle", "Lançamento diário registrado")
+        return redirect(url_for("controle"))
+
+    totais = {}
+    return render_template("controle.html", daily_groups=AREAS, totais=totais)
+
+
+@app.route("/movimentos", methods=["GET", "POST"])
+def movimentos():
+    data_ref = _parse_data_ref(request.args.get("data"))
+
+    if request.method == "POST":
+        mov = {
+            "id": (MOVIMENTOS_DATA[-1]["id"] + 1) if MOVIMENTOS_DATA else 1,
+            "mov_date": _parse_data_ref(request.form.get("mov_date")),
+            "mov_type": request.form.get("mov_type") or "Saida",
+            "area": request.form.get("area") or "Cozinha",
+            "setor": request.form.get("setor") or "Cozinha",
+            "item_name": next((i.nome for i in Item.query.all() if str(i.id) == request.form.get("item_id")), "Item"),
+            "quantity": request.form.get("quantity", type=float) or 0,
+            "value": (request.form.get("quantity", type=float) or 0) * (request.form.get("unit_cost", type=float) or 0),
+            "detail": request.form.get("detail") or "",
+        }
+        MOVIMENTOS_DATA.append(mov)
+        _log_action("Criação", "Movimento", f"Movimento {mov['mov_type']} registrado", mov["id"])
+        flash("Movimentação registrada.", "success")
+        return redirect(url_for("movimentos", data=mov["mov_date"].strftime("%Y-%m-%d")))
+
+    editar_id = request.args.get("editar", type=int)
+    mov_edicao = next((m for m in MOVIMENTOS_DATA if m["id"] == editar_id), None)
+    movimentos_dia = [m for m in MOVIMENTOS_DATA if m["mov_date"] == data_ref]
+    items_template = [{"id": i.id, "name": i.nome, "area": i.categoria or "-"} for i in Item.query.order_by(Item.nome.asc())]
+
+    return render_template(
+        "movimentos.html",
+        data_ref=data_ref,
+        mov_edicao=mov_edicao,
+        areas=AREAS,
+        setores=SETORES,
+        items=items_template,
+        movimentos=movimentos_dia,
+    )
+
+
+@app.route("/movimentos/<int:mov_id>/editar", methods=["POST"])
+def editar_movimento(mov_id: int):
+    mov = next((m for m in MOVIMENTOS_DATA if m["id"] == mov_id), None)
+    if not mov:
+        flash("Movimento não encontrado.", "error")
+        return redirect(url_for("movimentos"))
+
+    mov["quantity"] = request.form.get("quantity", type=float) or mov["quantity"]
+    mov["value"] = request.form.get("value", type=float) or mov["value"]
+    mov["detail"] = request.form.get("detail") or mov["detail"]
+    mov["mov_date"] = _parse_data_ref(request.form.get("mov_date"))
+    _log_action("Atualização", "Movimento", f"Movimento {mov_id} atualizado", mov_id)
+    flash("Movimentação atualizada.", "success")
+    return redirect(url_for("movimentos", data=mov["mov_date"].strftime("%Y-%m-%d")))
+
+
+@app.route("/movimentos/<int:mov_id>/excluir", methods=["POST"])
+def excluir_movimento(mov_id: int):
+    idx = next((i for i, m in enumerate(MOVIMENTOS_DATA) if m["id"] == mov_id), None)
+    if idx is None:
+        flash("Movimento não encontrado.", "error")
+        return redirect(url_for("movimentos"))
+
+    data_ref = MOVIMENTOS_DATA[idx]["mov_date"]
+    MOVIMENTOS_DATA.pop(idx)
+    _log_action("Exclusão", "Movimento", f"Movimento {mov_id} excluído", mov_id)
+    flash("Movimentação excluída.", "success")
+    return redirect(url_for("movimentos", data=data_ref.strftime("%Y-%m-%d")))
+
+
+@app.route("/producao", methods=["GET", "POST"])
+def producao():
+    data_ref = _parse_data_ref(request.args.get("data"))
+
+    if request.method == "POST":
+        item_id = request.form.get("item_id", type=int)
+        item = Item.query.get(item_id)
+        quantity = request.form.get("quantity", type=float) or 0
+        setor = request.form.get("setor") or "Cozinha"
+
+        novo = {
+            "id": (PRODUCOES_DATA[-1]["id"] + 1) if PRODUCOES_DATA else 1,
+            "data": _parse_data_ref(request.form.get("prod_date")),
+            "item_name": item.nome if item else "Item",
+            "setor": setor,
+            "quantity": quantity,
+            "cost": quantity * ((item.custo_unidade if item else 0) or 0),
+        }
+        PRODUCOES_DATA.append(novo)
+        _log_action("Criação", "Produção", f"Produção registrada em {setor}", novo["id"])
+        flash("Produção registrada.", "success")
+        return redirect(url_for("producao", data=novo["data"].strftime("%Y-%m-%d")))
+
+    lista = [p for p in PRODUCOES_DATA if p["data"] == data_ref]
+    items_template = [{"id": i.id, "name": i.nome} for i in Item.query.order_by(Item.nome.asc())]
+    return render_template("producao.html", data_ref=data_ref, setores=SETORES, items=items_template, lista=lista)
+
+
+@app.route("/producao/<int:prod_id>/excluir", methods=["POST"])
+def excluir_producao(prod_id: int):
+    idx = next((i for i, p in enumerate(PRODUCOES_DATA) if p["id"] == prod_id), None)
+    if idx is None:
+        flash("Produção não encontrada.", "error")
+        return redirect(url_for("producao"))
+
+    data_ref = PRODUCOES_DATA[idx]["data"]
+    PRODUCOES_DATA.pop(idx)
+    _log_action("Exclusão", "Produção", f"Produção {prod_id} excluída", prod_id)
+    flash("Produção excluída.", "success")
+    return redirect(url_for("producao", data=data_ref.strftime("%Y-%m-%d")))
+
 
 @app.route("/lista_compras")
-def lista_compras(): return render_template("lista-compras.html")
+def lista_compras():
+    itens = Item.query.order_by(Item.nome.asc()).all()
+    lista = []
+    for i in itens:
+        item_v = _item_view(i)
+        falta = max(0.0, (item_v["min_stock"] - item_v["stock"]))
+        sugestao = round(falta * 1.2, 3) if falta > 0 else 0
+        lista.append(
+            {
+                "item": item_v,
+                "falta": round(falta, 3),
+                "sugestao": sugestao,
+                "custo_est": sugestao * (item_v["cost"] or 0),
+            }
+        )
+
+    total_custo = sum(r["custo_est"] for r in lista)
+    return render_template("lista-compras.html", lista=lista, total_custo=total_custo)
+
 
 @app.route("/relatorio_gerencial")
-def relatorio_gerencial(): return render_template("relatorios.html")
+def relatorio_gerencial():
+    data_ref = _parse_data_ref(request.args.get("data"))
+    mes_ref = _parse_mes_ref(request.args.get("mes"))
+
+    vendas_dia = Venda.query.filter(Venda.data == data_ref).all()
+    faturamento = sum(v.valor_total or 0 for v in vendas_dia)
+    custo = sum(v.custo_estimado or 0 for v in vendas_dia)
+    lucro = faturamento - custo
+    cmv = round((custo / faturamento) * 100, 2) if faturamento else 0
+
+    por_periodo = {}
+    for v in vendas_dia:
+        periodo = v.periodo or "Geral"
+        por_periodo.setdefault(periodo, {"q": 0, "v": 0.0})
+        por_periodo[periodo]["q"] += 1
+        por_periodo[periodo]["v"] += v.valor_total or 0
+
+    ranking = []
+    por_tipo = {}
+    for v in vendas_dia:
+        t = v.tipo_refeicao or "Outros"
+        por_tipo.setdefault(t, {"tipo": t, "qtd": 0, "total": 0.0})
+        por_tipo[t]["qtd"] += 1
+        por_tipo[t]["total"] += v.valor_total or 0
+    ranking = sorted(por_tipo.values(), key=lambda x: x["total"], reverse=True)[:5]
+
+    return render_template(
+        "relatorios.html",
+        data_ref=data_ref,
+        mes_ref=mes_ref,
+        faturamento=faturamento,
+        refeicoes=len(vendas_dia),
+        custo=custo,
+        lucro=lucro,
+        cmv=cmv,
+        total_perdas=0,
+        total_diario=faturamento,
+        por_periodo=por_periodo,
+        ranking_vendas=ranking,
+        resumo_setores=[],
+    )
+
+
+@app.route("/relatorios/exportar/pdf")
+def exportar_relatorio_pdf():
+    flash("Exportação em PDF será disponibilizada em breve.", "info")
+    return redirect(url_for("relatorio_gerencial", data=request.args.get("data"), mes=request.args.get("mes")))
+
+
+@app.route("/relatorios/exportar/xlsx")
+def exportar_relatorio_xlsx():
+    flash("Exportação em Excel será disponibilizada em breve.", "info")
+    return redirect(url_for("relatorio_gerencial", data=request.args.get("data"), mes=request.args.get("mes")))
+
+
+@app.route("/lista_compras/exportar/xlsx")
+def exportar_lista_compras_xlsx():
+    flash("Exportação da lista de compras será disponibilizada em breve.", "info")
+    return redirect(url_for("lista_compras"))
+
+
+@app.route("/metas", methods=["GET", "POST"])
+def metas():
+    if request.method == "POST":
+        year = request.form.get("year", type=int) or date.today().year
+        month = request.form.get("month", type=int) or date.today().month
+        goal = request.form.get("goal", type=float) or 0
+
+        existente = next((m for m in METAS_DATA if m["year"] == year and m["month"] == month), None)
+        if existente:
+            existente["goal"] = goal
+            flash("Meta atualizada.", "success")
+            _log_action("Atualização", "Meta", f"Meta {month}/{year} atualizada")
+        else:
+            METAS_DATA.append({"year": year, "month": month, "goal": goal})
+            flash("Meta cadastrada.", "success")
+            _log_action("Criação", "Meta", f"Meta {month}/{year} cadastrada")
 
-@app.route("/metas")
-def metas(): return render_template("metas.html")
+        return redirect(url_for("metas"))
+
+    metas_view = []
+    hoje = date.today()
+    for m in sorted(METAS_DATA, key=lambda x: (x["year"], x["month"]), reverse=True):
+        faturamento_mes = (
+            db.session.query(db.func.sum(Venda.valor_total))
+            .filter(db.extract("year", Venda.data) == m["year"], db.extract("month", Venda.data) == m["month"])
+            .scalar()
+            or 0
+        )
+        percentual = round((faturamento_mes / m["goal"]) * 100, 2) if m["goal"] else 0
+        dias_no_mes = 30
+        meta_dia = m["goal"] / dias_no_mes if dias_no_mes else 0
+        dias_passados = hoje.day if (m["year"] == hoje.year and m["month"] == hoje.month) else dias_no_mes
+        projecao = (faturamento_mes / max(1, dias_passados)) * dias_no_mes
+
+        metas_view.append(
+            {
+                "year": m["year"],
+                "month": m["month"],
+                "goal": m["goal"],
+                "meta_dia": meta_dia,
+                "percentual": percentual,
+                "projecao": projecao,
+            }
+        )
+
+    return render_template("metas.html", metas=metas_view)
+
+
+@app.route("/usuarios", methods=["GET", "POST"])
+def usuarios():
+    if request.method == "POST":
+        novo = {
+            "id": (USERS[-1]["id"] + 1) if USERS else 1,
+            "name": request.form.get("name") or "Usuário",
+            "username": request.form.get("username") or f"user{len(USERS)+1}",
+            "role": request.form.get("role") or "operador",
+        }
+        USERS.append(novo)
+        _log_action("Criação", "Usuário", f"Usuário {novo['username']} criado", novo["id"])
+        flash("Usuário criado.", "success")
+        return redirect(url_for("usuarios"))
+
+    return render_template("usuarios.html", usuarios=USERS, roles=ROLES)
+
+
+@app.route("/usuarios/<int:user_id>/excluir", methods=["POST"])
+def excluir_usuario(user_id: int):
+    if user_id == USERS[0]["id"]:
+        flash("Não é possível excluir o usuário atual.", "error")
+        return redirect(url_for("usuarios"))
+
+    idx = next((i for i, u in enumerate(USERS) if u["id"] == user_id), None)
+    if idx is None:
+        flash("Usuário não encontrado.", "error")
+        return redirect(url_for("usuarios"))
+
+    username = USERS[idx]["username"]
+    USERS.pop(idx)
+    _log_action("Exclusão", "Usuário", f"Usuário {username} removido", user_id)
+    flash("Usuário excluído.", "success")
+    return redirect(url_for("usuarios"))
 
-@app.route("/usuarios")
-def usuarios(): return render_template("usuarios.html")
 
 @app.route("/auditoria")
-def auditoria(): return render_template("auditoria.html")
+def auditoria():
+    page = request.args.get("page", default=1, type=int)
+    per_page = 10
+    total = len(AUDITORIA_LOGS)
+    pages = max(1, ceil(total / per_page))
+    page = min(max(1, page), pages)
+    start = (page - 1) * per_page
+    end = start + per_page
+
+    logs = SimplePagination(items=AUDITORIA_LOGS[start:end], page=page, pages=pages)
+    return render_template("auditoria.html", logs=logs, get_badge_class=_badge_class)
+
 
 @app.route("/logout")
 def logout():
     flash("Sessão encerrada")
-    return redirect(url_for('vendas'))
+    return redirect(url_for("vendas"))
+
 
-# --- INICIALIZAÇÃO ---
 if __name__ == "__main__":
     with app.app_context():
-        # Este comando tenta criar as tabelas se elas não existirem
         db.create_all()
         print("Banco de dados verificado/criado com sucesso!")
-        
+
     port = int(os.environ.get("PORT", 10000))
     app.run(host="0.0.0.0", port=port)
 
EOF
)
