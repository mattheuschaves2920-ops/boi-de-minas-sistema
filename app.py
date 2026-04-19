 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 8e215023585f65cc6283d8c9c0c1ba563aaef9d2..cebc21d4e696a60d004330c046b50374886b86b2 100644
--- a/app.py
+++ b/app.py
@@ -1,127 +1,298 @@
 import os
 from datetime import date, datetime
-from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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
 
 # Garante que a pasta de fotos exista
 os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
 
+ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic"}
+
 db = SQLAlchemy(app)
 csrf = CSRFProtect(app)
 
-# --- MODELOS DE BANCO DE DADOS ---
 
+# --- MODELOS DE BANCO DE DADOS ---
 class Item(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     nome = db.Column(db.String(100), nullable=False)
     codigo_barras = db.Column(db.String(50), unique=True)
     categoria = db.Column(db.String(50))  # Consumo (Cozinha) ou Revenda (Bebidas)
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
+    periodo = db.Column(db.String(20))  # Almoço ou Janta
+    tipo_refeicao = db.Column(db.String(50))  # Marmitex, Self-Service, etc.
     valor_total = db.Column(db.Float, nullable=False)
-    custo_estimado = db.Column(db.Float, default=0.0) # Para o cálculo de CMV
+    custo_estimado = db.Column(db.Float, default=0.0)  # Para o cálculo de CMV
+
 
 class Desperdicio(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     data = db.Column(db.DateTime, default=datetime.now)
-    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
+    item_id = db.Column(db.Integer, db.ForeignKey("item.id"))
     quantidade = db.Column(db.Float)
-    foto_path = db.Column(db.String(255)) # Validação obrigatória
+    foto_path = db.Column(db.String(255))  # Validação obrigatória
     motivo = db.Column(db.String(200))
 
+
+def _allowed_file(filename: str) -> bool:
+    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
+
+
+def _parse_data_ref(data_texto: str | None) -> date:
+    if not data_texto:
+        return date.today()
+
+    try:
+        return datetime.strptime(data_texto, "%Y-%m-%d").date()
+    except ValueError:
+        return date.today()
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
 # --- PROCESSADOR DE CONTEXTO (Para o base.html funcionar) ---
 @app.context_processor
 def inject_globals():
     # Isso impede que o base.html quebre se não houver usuário logado
     criticos = Item.query.filter(Item.estoque_atual <= Item.estoque_minimo).count()
     return {
-        'n_criticos': criticos,
-        'current_user': {'name': 'Gestor Boi de Minas', 'role': 'admin'}
+        "n_criticos": criticos,
+        "current_user": {"name": "Gestor Boi de Minas", "role": "admin"},
     }
 
-# --- ROTAS DE NAVEGAÇÃO ---
 
+# --- ROTAS DE NAVEGAÇÃO ---
 @app.route("/")
 @app.route("/dashboard")
 def dashboard():
     # Cálculo de CMV Simples: (Custo / Vendas) * 100
-    vendas_total = db.session.query(db.func.sum(Venda.valor_total)).scalar() or 0.1
+    vendas_total = db.session.query(db.func.sum(Venda.valor_total)).scalar() or 0
     custo_total = db.session.query(db.func.sum(Venda.custo_estimado)).scalar() or 0
-    porcentagem_custo = (custo_total / vendas_total) * 100
-    
+    porcentagem_custo = (custo_total / vendas_total) * 100 if vendas_total > 0 else 0
+
     return render_template("dashboard.html", cmv=round(porcentagem_custo, 2))
 
+
 @app.route("/vendas", methods=["GET", "POST"])
 def vendas():
     if request.method == "POST":
         # Lógica para salvar venda e calcular CMV será inserida aqui
         flash("Venda registrada!")
-        return redirect(url_for('vendas'))
+        return redirect(url_for("vendas"))
     return render_template("vendas.html")
 
+
 @app.route("/itens")
 def itens():
     lista_itens = Item.query.all()
     return render_template("itens.html", itens=lista_itens)
 
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
+
+        if not quantity or quantity <= 0:
+            flash("Quantidade deve ser maior que zero.", "error")
+            return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+
+        if not photo or not photo.filename:
+            flash("A foto é obrigatória para registrar desperdício.", "error")
+            return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+
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
+    itens, lista = _dados_desperdicio(data_ref)
+    items_template = [{"id": i.id, "name": i.nome, "area": i.categoria or "-"} for i in itens]
+
+    return render_template(
+        "desperdicio.html",
+        data_ref=data_ref,
+        desperdicio_edicao=desperdicio_edicao,
+        error=None,
+        items=items_template,
+        lista=lista,
+    )
+
+
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
+
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
+
+    flash("Registro excluído.", "success")
+    return redirect(url_for("desperdicio", data=data_ref.strftime("%Y-%m-%d")))
+
 
 # Rotas Complementares (Mapeando todos os botões do seu menu)
 @app.route("/controle")
-def controle(): return render_template("controle.html")
+def controle():
+    return render_template("controle.html")
+
 
 @app.route("/movimentos")
-def movimentos(): return render_template("movimentos.html")
+def movimentos():
+    return render_template("movimentos.html")
+
 
 @app.route("/producao")
-def producao(): return render_template("producao.html")
+def producao():
+    return render_template("producao.html")
+
 
 @app.route("/lista_compras")
-def lista_compras(): return render_template("lista-compras.html")
+def lista_compras():
+    return render_template("lista-compras.html")
+
 
 @app.route("/relatorio_gerencial")
-def relatorio_gerencial(): return render_template("relatorios.html")
+def relatorio_gerencial():
+    return render_template("relatorios.html")
+
 
 @app.route("/metas")
-def metas(): return render_template("metas.html")
+def metas():
+    return render_template("metas.html")
+
 
 @app.route("/usuarios")
-def usuarios(): return render_template("usuarios.html")
+def usuarios():
+    return render_template("usuarios.html")
+
 
 @app.route("/auditoria")
-def auditoria(): return render_template("auditoria.html")
+def auditoria():
+    return render_template("auditoria.html")
+
 
 @app.route("/logout")
 def logout():
     flash("Sessão encerrada")
-    return redirect(url_for('vendas'))
+    return redirect(url_for("vendas"))
+
 
 # --- INICIALIZAÇÃO ---
 if __name__ == "__main__":
     with app.app_context():
         # Este comando tenta criar as tabelas se elas não existirem
         db.create_all()
         print("Banco de dados verificado/criado com sucesso!")
-        
+
     port = int(os.environ.get("PORT", 10000))
     app.run(host="0.0.0.0", port=port)
 
EOF
)
