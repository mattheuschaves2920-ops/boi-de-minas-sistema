 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
index fe62076f5a135354e34634db51efea0bccb51ed8..25f4e922fccb38f58695959177d5b40d185bd10f 100644
--- a/README.md
+++ b/README.md
@@ -1,24 +1,44 @@
-VERSÃO V10 - DESPERDÍCIO COM FOTO OBRIGATÓRIA
-
-Novidades:
-- Corrigido o projeto completo
-- Controle diário mantido
-- Desperdício agora só salva com foto
-- Sem foto, o sistema bloqueia o lançamento
-- A foto fica vinculada ao registro da perda
-
-Como publicar:
-1. Extraia o ZIP no computador
-2. No GitHub, substitua:
-   - app.py
-   - requirements.txt
-   - pasta templates
-   - pasta static
-3. No Render:
-   - Manual Deploy
-   - Clear build cache & deploy
-4. Abra /setup uma vez, se necessário
-
-Observação:
-A foto é enviada junto com o registro de desperdício.
-No celular, o campo usa a câmera traseira por padrão.
+VERSÃO V11 - ESTABILIZAÇÃO DE DEPLOY E ROTAS
+
+Novidades desta versão:
+- Rotas principais reconciliadas com os templates (sem erro 500 nas telas base)
+- Fluxo de desperdício com foto obrigatória mantido
+- Endpoints usados no frontend mapeados no backend
+- Ajustes para facilitar deploy no Render
+
+## Como publicar no Render
+1. Suba este projeto completo para o GitHub (não copie trechos manualmente do chat).
+2. No Render, faça **Manual Deploy** da branch correta.
+3. Start command:
+   - `gunicorn app:app`
+4. Variáveis recomendadas:
+   - `SECRET_KEY`
+   - `DATABASE_URL` (quando usar Postgres)
+
+## Verificação rápida antes do deploy
+Rode localmente:
+
+```bash
+python -m py_compile app.py
+```
+
+Se esse comando falhar, o deploy também vai falhar.
+
+## Erro conhecido: `IndentationError` com texto "git apply --3way"
+Se aparecer algo como:
+
+```text
+File "/opt/render/project/src/app.py", line 1
+(cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF'
+IndentationError: unexpected indent
+```
+
+Significa que o arquivo `app.py` publicado está corrompido (conteúdo de patch/shell foi parar dentro do arquivo Python).
+
+### Como corrigir
+- Abra o `app.py` no GitHub da branch publicada.
+- Confirme que a **linha 1 começa com import Python** (ex.: `import os`), e não com comandos shell.
+- Faça commit do arquivo correto e redeploy.
+
+## Observação
+As exportações de relatório/lista podem estar em modo inicial (stub) dependendo da versão do backend.
 
EOF
)
