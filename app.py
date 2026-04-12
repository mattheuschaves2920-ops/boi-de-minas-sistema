from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# =========================
# DADOS TEMPORÁRIOS (MEMÓRIA)
# =========================
dados = {
    "venda_almoco": 0.0,
    "venda_janta": 0.0,
    "clientes_almoco": 0,
    "clientes_janta": 0
}

# =========================
# HOME / LOGIN SIMPLES
# =========================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return redirect(url_for("dashboard"))
    return render_template("index.html")


# =========================
# DASHBOARD (CORRIGIDO)
# =========================
@app.route("/dashboard")
def dashboard():
    try:
        contexto = {
            "venda_almoco": float(dados.get("venda_almoco", 0.0)),
            "venda_janta": float(dados.get("venda_janta", 0.0)),
            "clientes_almoco": int(dados.get("clientes_almoco", 0)),
            "clientes_janta": int(dados.get("clientes_janta", 0))
        }

        return render_template("dashboard.html", **contexto)

    except Exception as e:
        return f"Erro no dashboard: {str(e)}"


# =========================
# CONTROLE DIÁRIO (CRIADO)
# =========================
@app.route("/controle", methods=["GET", "POST"])
def controle():
    if request.method == "POST":
        try:
            dados["venda_almoco"] = float(request.form.get("venda_almoco") or 0)
            dados["venda_janta"] = float(request.form.get("venda_janta") or 0)
            dados["clientes_almoco"] = int(request.form.get("clientes_almoco") or 0)
            dados["clientes_janta"] = int(request.form.get("clientes_janta") or 0)

            return redirect(url_for("dashboard"))

        except Exception as e:
            return f"Erro ao salvar dados: {str(e)}"

    return render_template("controle.html")


# =========================
# RELATÓRIOS (EVITA ERRO)
# =========================
@app.route("/relatorios")
def relatorios():
    return "<h2>Relatórios em construção</h2>"


# =========================
# SETUP
# =========================
@app.route("/setup")
def setup():
    return "Sistema funcionando!"


# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(debug=True)
