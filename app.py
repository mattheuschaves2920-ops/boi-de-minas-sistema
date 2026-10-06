from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from datetime import datetime, date
from functools import wraps

import os


# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "boi-minas-2026"

database_url = os.getenv("DATABASE_URL")

if database_url:
    database_url = database_url.replace("postgres://", "postgresql://", 1)
else:
    database_url = "sqlite:///boi_minas.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)


# ============================================================
# MODELOS
# ============================================================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        nullable=False
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )

    role = db.Column(
        db.String(50),
        default="funcionario"
    )


class TipoVenda(db.Model):
    __tablename__ = "tipos_venda"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )


class Venda(db.Model):
    __tablename__ = "vendas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    meal_type = db.Column(
        db.String(120),
        nullable=False
    )

    turno = db.Column(
        db.String(50),
        nullable=False
    )

    quantity = db.Column(
        db.Float,
        nullable=False
    )

    unit_value = db.Column(
        db.Float,
        nullable=False
    )

    total = db.Column(
        db.Float,
        nullable=False
    )

    sale_date = db.Column(
        db.Date,
        default=date.today
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    area = db.Column(
        db.String(100),
        nullable=False
    )

    code = db.Column(
        db.String(120)
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    unit = db.Column(
        db.String(20),
        default="un"
    )

    cost = db.Column(
        db.Float,
        default=0
    )

    stock = db.Column(
        db.Float,
        default=0
    )

    min_stock = db.Column(
        db.Float,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class AuditLog(db.Model):
    """
    Registro de auditoria.

    Guarda quem executou a ação, quando ocorreu,
    qual recurso foi alterado e detalhes da operação.
    """

    __tablename__ = "audit_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        nullable=True
    )

    username = db.Column(
        db.String(100),
        nullable=True
    )

    action = db.Column(
        db.String(100),
        nullable=False
    )

    resource = db.Column(
        db.String(100),
        nullable=True
    )

    resource_id = db.Column(
        db.Integer,
        nullable=True
    )

    detail = db.Column(
        db.Text,
        nullable=True
    )

    ip_address = db.Column(
        db.String(100),
        nullable=True
    )


# ============================================================
# BANCO / ADMIN PADRÃO
# ============================================================

with app.app_context():

    db.create_all()

    admin = User.query.filter_by(
        username="admin"
    ).first()

    if not admin:

        admin = User(
            name="Administrador",
            username="admin",
            password="123456",
            role="admin"
        )

        db.session.add(admin)
        db.session.commit()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

@app.context_processor
def inject_globals():

    current_user = None

    if session.get("user"):

        current_user = {
            "id": session.get("user_id"),
            "name": session.get("user"),
            "role": session.get("role")
        }

    return {
        "current_user": current_user,
        "now": datetime.now
    }


def verificar_login():

    if not session.get("user"):

        return redirect(
            url_for("login")
        )

    return None


def somente_admin():

    if session.get("role") != "admin":

        flash(
            "Acesso permitido somente ao administrador.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )

    return None


def registrar_auditoria(
    action,
    resource=None,
    resource_id=None,
    detail=None
):

    """
    Registra uma ação no log de auditoria.

    Se ocorrer algum problema na gravação,
    não derruba a operação principal.
    """

    try:

        usuario_id = session.get("user_id")
        usuario_nome = session.get("user")

        ip = request.headers.get(
            "X-Forwarded-For",
            request.remote_addr
        )

        if ip and "," in ip:

            ip = ip.split(",")[0].strip()

        log = AuditLog(

            user_id=usuario_id,

            username=usuario_nome,

            action=action,

            resource=resource,

            resource_id=resource_id,

            detail=detail,

            ip_address=ip

        )

        db.session.add(log)

    except Exception:

        # A auditoria nunca deve impedir a operação principal.
        pass


def numero_formulario(valor, padrao=0):

    """
    Aceita:
    10
    10.5
    10,5
    """

    if valor is None:
        return padrao

    valor = str(valor).strip()

    if not valor:
        return padrao

    valor = valor.replace(",", ".")

    return float(valor)


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if session.get("user"):

        return redirect(
            url_for("dashboard")
        )

    error = None

    if request.method == "POST":

        username = (
            request.form.get("username") or ""
        ).strip()

        password = (
            request.form.get("password") or ""
        ).strip()

        user = User.query.filter_by(
            username=username
        ).first()

        if user and user.password == password:

            session["user"] = user.name
            session["role"] = user.role
            session["user_id"] = user.id

            registrar_auditoria(
                action="LOGIN",
                resource="usuario",
                resource_id=user.id,
                detail=f"Login realizado por {user.username}."
            )

            db.session.commit()

            return redirect(
                url_for("dashboard")
            )

        error = "Usuário ou senha inválidos."

    return render_template(
        "login.html",
        error=error
    )


@app.route("/logout")
def logout():

    if session.get("user"):

        registrar_auditoria(
            action="LOGOUT",
            resource="usuario",
            resource_id=session.get("user_id"),
            detail="Usuário encerrou a sessão."
        )

        db.session.commit()

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
@app.route("/dashboard")
def dashboard():

    auth = verificar_login()

    if auth:
        return auth

    faturamento = (
        db.session
        .query(db.func.sum(Venda.total))
        .scalar()
        or 0
    )

    return render_template(
        "dashboard.html",
        faturamento=faturamento,
        meta_pct=0
    )


# ============================================================
# USUÁRIOS
# ============================================================

@app.route(
    "/usuarios",
    methods=["GET", "POST"]
)
def usuarios():

    auth = verificar_login()

    if auth:
        return auth

    admin_auth = somente_admin()

    if admin_auth:
        return admin_auth

    error = None
    success = None

    if request.method == "POST":

        try:

            name = (
                request.form.get("name") or ""
            ).strip()

            username = (
                request.form.get("username") or ""
            ).strip()

            password = (
                request.form.get("password") or ""
            ).strip()

            role = (
                request.form.get("role") or ""
            ).strip()

            if (
                not name
                or not username
                or not password
                or not role
            ):

                error = "Preencha todos os campos."

            elif len(password) < 6:

                error = (
                    "A senha deve ter no mínimo 6 caracteres."
                )

            else:

                usuario_existente = (
                    User.query
                    .filter_by(username=username)
                    .first()
                )

                if usuario_existente:

                    error = (
                        "Já existe um usuário com esse login."
                    )

                else:

                    novo_usuario = User(

                        name=name,

                        username=username,

                        password=password,

                        role=role

                    )

                    db.session.add(
                        novo_usuario
                    )

                    db.session.flush()

                    registrar_auditoria(

                        action="CRIAR_USUARIO",

                        resource="usuario",

                        resource_id=novo_usuario.id,

                        detail=(
                            f"Usuário '{username}' criado "
                            f"com perfil '{role}'."
                        )

                    )

                    db.session.commit()

                    success = (
                        "Usuário cadastrado com sucesso."
                    )

        except Exception as e:

            db.session.rollback()

            error = str(e)

    lista = (
        User.query
        .order_by(User.name.asc())
        .all()
    )

    return render_template(
        "usuarios.html",
        usuarios=lista,
        error=error,
        success=success
    )


@app.route(
    "/excluir_usuario/<int:user_id>",
    methods=["POST"]
)
def excluir_usuario(user_id):

    auth = verificar_login()

    if auth:
        return auth

    admin_auth = somente_admin()

    if admin_auth:
        return admin_auth

    usuario = User.query.get_or_404(
        user_id
    )

    if usuario.id == session.get("user_id"):

        flash(
            "Você não pode excluir seu próprio usuário.",
            "error"
        )

        return redirect(
            url_for("usuarios")
        )

    nome = usuario.name
    username = usuario.username
    usuario_id = usuario.id

    db.session.delete(usuario)

    registrar_auditoria(

        action="EXCLUIR_USUARIO",

        resource="usuario",

        resource_id=usuario_id,

        detail=(
            f"Usuário '{username}' ({nome}) excluído."
        )

    )

    db.session.commit()

    flash(
        "Usuário removido com sucesso.",
        "success"
    )

    return redirect(
        url_for("usuarios")
    )


# ============================================================
# VENDAS
# ============================================================

@app.route(
    "/vendas",
    methods=["GET", "POST"]
)
def vendas():

    auth = verificar_login()

    if auth:
        return auth

    error = None
    success = None

    tipos_venda = (
        TipoVenda.query
        .order_by(TipoVenda.nome.asc())
        .all()
    )

    if request.method == "POST":

        try:

            data_str = (
                request.form.get("data")
                or date.today().strftime("%Y-%m-%d")
            )

            tipo = (
                request.form.get("tipo")
                or request.form.get("meal_type")
                or ""
            ).strip()

            turno = (
                request.form.get("turno")
                or ""
            ).strip()

            valor_unitario = numero_formulario(
                request.form.get("valor_unitario")
                or request.form.get("unit_value"),
                0
            )

            quantidade = numero_formulario(
                request.form.get("quantidade")
                or request.form.get("quantity"),
                0
            )

            if not tipo:

                raise ValueError(
                    "Informe o tipo da venda."
                )

            if not turno:

                raise ValueError(
                    "Informe o turno."
                )

            if quantidade <= 0:

                raise ValueError(
                    "A quantidade deve ser maior que zero."
                )

            if valor_unitario < 0:

                raise ValueError(
                    "O valor unitário não pode ser negativo."
                )

            data_venda = datetime.strptime(
                data_str,
                "%Y-%m-%d"
            ).date()

            total = (
                valor_unitario
                * quantidade
            )

            nova_venda = Venda(

                meal_type=tipo,

                turno=turno,

                unit_value=valor_unitario,

                quantity=quantidade,

                total=total,

                sale_date=data_venda

            )

            db.session.add(
                nova_venda
            )

            db.session.flush()

            registrar_auditoria(

                action="REGISTRAR_VENDA",

                resource="venda",

                resource_id=nova_venda.id,

                detail=(
                    f"Tipo: {tipo}; "
                    f"Turno: {turno}; "
                    f"Quantidade: {quantidade}; "
                    f"Valor unitário: R$ {valor_unitario:.2f}; "
                    f"Total: R$ {total:.2f}."
                )

            )

            db.session.commit()

            success = (
                "Venda registrada com sucesso."
            )

        except Exception as e:

            db.session.rollback()

            error = (
                f"Erro ao salvar venda: {str(e)}"
            )

    lista_vendas = (
        Venda.query
        .order_by(Venda.id.desc())
        .all()
    )

    total_vendas = sum(
        venda.total or 0
        for venda in lista_vendas
    )

    # Mantém "itens" para compatibilidade
    # com uma tela de vendas que já use essa variável.
    itens = tipos_venda

    return render_template(
        "vendas.html",
        vendas=lista_vendas,
        total_vendas=total_vendas,
        itens=itens,
        tipos_venda=tipos_venda,
        error=error,
        success=success
    )


@app.route(
    "/excluir_venda/<int:sale_id>",
    methods=["POST"]
)
def excluir_venda(sale_id):

    auth = verificar_login()

    if auth:
        return auth

    venda = Venda.query.get_or_404(
        sale_id
    )

    venda_id = venda.id

    detalhe = (
        f"Tipo: {venda.meal_type}; "
        f"Quantidade: {venda.quantity}; "
        f"Total: R$ {venda.total:.2f}."
    )

    db.session.delete(venda)

    registrar_auditoria(

        action="EXCLUIR_VENDA",

        resource="venda",

        resource_id=venda_id,

        detail=detalhe

    )

    db.session.commit()

    flash(
        "Venda excluída com sucesso.",
        "success"
    )

    return redirect(
        url_for("vendas")
    )


# ============================================================
# ESTOQUE / ITENS
# ============================================================

@app.route(
    "/itens",
    methods=["GET", "POST"]
)
def itens():

    auth = verificar_login()

    if auth:
        return auth

    error = None
    success = None

    # Áreas existentes no cadastro.
    areas = [
        area[0]
        for area in (
            db.session
            .query(Item.area)
            .filter(
                Item.area.isnot(None),
                Item.area != ""
            )
            .distinct()
            .order_by(Item.area.asc())
            .all()
        )
    ]

    if request.method == "POST":

        try:

            area = (
                request.form.get("area")
                or ""
            ).strip()

            code = (
                request.form.get("code")
                or ""
            ).strip()

            name = (
                request.form.get("name")
                or ""
            ).strip()

            unit = (
                request.form.get("unit")
                or "un"
            ).strip()

            cost = numero_formulario(
                request.form.get("cost"),
                0
            )

            stock = numero_formulario(
                request.form.get("stock"),
                0
            )

            min_stock = numero_formulario(
                request.form.get("min_stock"),
                0
            )

            if not area:

                raise ValueError(
                    "Informe a área do item."
                )

            if not name:

                raise ValueError(
                    "Informe o nome do produto."
                )

            if cost < 0:

                raise ValueError(
                    "O custo não pode ser negativo."
                )

            if stock < 0:

                raise ValueError(
                    "O estoque não pode ser negativo."
                )

            if min_stock < 0:

                raise ValueError(
                    "O estoque mínimo não pode ser negativo."
                )

            novo_item = Item(

                area=area,

                code=code or None,

                name=name,

                unit=unit,

                cost=cost,

                stock=stock,

                min_stock=min_stock

            )

            db.session.add(
                novo_item
            )

            db.session.flush()

            registrar_auditoria(

                action="CRIAR_ITEM",

                resource="item",

                resource_id=novo_item.id,

                detail=(
                    f"Item '{name}' criado. "
                    f"Estoque inicial: {stock} {unit}."
                )

            )

            db.session.commit()

            success = (
                "Item cadastrado com sucesso."
            )

            areas = sorted(
                set(areas + [area]),
                key=lambda x: x.lower()
            )

        except Exception as e:

            db.session.rollback()

            error = str(e)

    lista = (
        Item.query
        .order_by(Item.name.asc())
        .all()
    )

    return render_template(
        "itens.html",
        itens=lista,
        areas=areas,
        error=error,
        success=success
    )


# ============================================================
# ESTOQUE INICIAL
# ============================================================

@app.route(
    "/estoque_inicial",
    methods=["GET", "POST"]
)
def estoque_inicial():

    auth = verificar_login()

    if auth:
        return auth

    admin_auth = somente_admin()

    if admin_auth:
        return admin_auth

    error = None
    success = None

    lista = (
        Item.query
        .order_by(
            Item.area.asc(),
            Item.name.asc()
        )
        .all()
    )

    if request.method == "POST":

        try:

            alteracoes = []

            for item in lista:

                campo = (
                    f"estoque_{item.id}"
                )

                if campo not in request.form:

                    continue

                valor = numero_formulario(
                    request.form.get(campo),
                    0
                )

                if valor < 0:

                    raise ValueError(
                        f"O estoque de '{item.name}' "
                        "não pode ser negativo."
                    )

                estoque_anterior = (
                    item.stock or 0
                )

                item.stock = valor

                alteracoes.append(
                    (
                        item,
                        estoque_anterior,
                        valor
                    )
                )

            if not alteracoes:

                raise ValueError(
                    "Nenhuma quantidade foi informada."
                )

            # Auditoria geral da operação.
            quantidade_itens = len(
                alteracoes
            )

            resumo = []

            for item, anterior, novo in alteracoes:

                resumo.append(
                    f"{item.name}: "
                    f"{anterior:g} → {novo:g} {item.unit or ''}"
                )

            registrar_auditoria(

                action="ESTOQUE_INICIAL",

                resource="estoque",

                detail=(
                    f"Estoque inicial lançado para "
                    f"{quantidade_itens} item(ns). "
                    + " | ".join(resumo)
                )

            )

            db.session.commit()

            success = (
                f"Estoque inicial salvo para "
                f"{quantidade_itens} item(ns)."
            )

        except Exception as e:

            db.session.rollback()

            error = str(e)

    # Recarrega para mostrar os valores atualizados.
    lista = (
        Item.query
        .order_by(
            Item.area.asc(),
            Item.name.asc()
        )
        .all()
    )

    return render_template(
        "estoque_inicial.html",
        itens=lista,
        error=error,
        success=success
    )


# ============================================================
# ZERAR ESTOQUE
# ============================================================

@app.route(
    "/zerar_estoque",
    methods=["POST"]
)
def zerar_estoque():

    auth = verificar_login()

    if auth:
        return auth

    admin_auth = somente_admin()

    if admin_auth:
        return admin_auth

    try:

        itens = Item.query.all()

        quantidade_itens = len(itens)

        if not itens:

            flash(
                "Não existem produtos cadastrados para zerar.",
                "error"
            )

            return redirect(
                url_for("itens")
            )

        resumo = []

        for item in itens:

            anterior = item.stock or 0

            if anterior != 0:

                resumo.append(
                    f"{item.name}: "
                    f"{anterior:g} → 0 {item.unit or ''}"
                )

            item.stock = 0

        registrar_auditoria(

            action="ZERAR_ESTOQUE",

            resource="estoque",

            detail=(
                f"Estoque zerado para "
                f"{quantidade_itens} item(ns). "
                + (
                    " | ".join(resumo)
                    if resumo
                    else "Todos já estavam zerados."
                )
            )

        )

        db.session.commit()

        flash(
            "Estoque zerado com sucesso. "
            "Os produtos foram mantidos cadastrados.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Erro ao zerar estoque: {str(e)}",
            "error"
        )

    return redirect(
        url_for("itens")
    )


# ============================================================
# OUTRAS TELAS
# ============================================================

@app.route("/controle")
def controle():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "controle.html"
    )


@app.route("/compras")
def compras():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "compras.html"
    )


@app.route("/lista_compras")
def lista_compras():

    auth = verificar_login()

    if auth:
        return auth

    return redirect(
        url_for("compras")
    )


@app.route("/movimentos")
def movimentos():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "movimentos.html"
    )


@app.route("/desperdicio")
def desperdicio():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "desperdicio.html"
    )


@app.route("/producao")
def producao():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "producao.html"
    )


@app.route("/metas")
def metas():

    auth = verificar_login()

    if auth:
        return auth

    return render_template(
        "metas.html"
    )


# ============================================================
# AUDITORIA
# ============================================================

@app.route("/auditoria")
def auditoria():

    auth = verificar_login()

    if auth:
        return auth

    try:

        page = int(
            request.args.get("page", 1)
        )

    except (TypeError, ValueError):

        page = 1

    if page < 1:
        page = 1

    logs = (
        AuditLog.query
        .order_by(
            AuditLog.timestamp.desc(),
            AuditLog.id.desc()
        )
        .paginate(
            page=page,
            per_page=50,
            error_out=False
        )
    )

    return render_template(
        "auditoria.html",
        logs=logs
    )


# ============================================================
# RELATÓRIO GERENCIAL
# ============================================================

@app.route("/relatorio_gerencial")
def relatorio_gerencial():

    auth = verificar_login()

    if auth:
        return auth

    faturamento = (
        db.session
        .query(db.func.sum(Venda.total))
        .scalar()
        or 0
    )

    quantidade_vendas = Venda.query.count()

    ticket_medio = 0

    if quantidade_vendas > 0:

        ticket_medio = (
            faturamento
            / quantidade_vendas
        )

    vendas = (
        Venda.query
        .order_by(
            Venda.sale_date.desc()
        )
        .all()
    )

    return render_template(
        "relatorio_gerencial.html",
        faturamento=faturamento,
        quantidade_vendas=quantidade_vendas,
        ticket_medio=ticket_medio,
        vendas=vendas
    )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
