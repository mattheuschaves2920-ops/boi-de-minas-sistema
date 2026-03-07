VERSÃO V7 - PWA CORRIGIDO

O que foi corrigido:
- usa a logo enviada pelo usuário como static/logo.png
- cabeçalho com a logo correta
- manifest.webmanifest ajustado
- service worker servido pela rota /service-worker.js
- mantém leitor de código de barras e preenchimento automático

Como publicar:
1. Extraia o ZIP
2. No GitHub, substitua:
   - app.py
   - requirements.txt
   - pasta templates
   - pasta static
3. No Render:
   - Manual Deploy
   - Clear build cache & deploy

Se aparecer erro no navegador depois do deploy:
- abra no celular
- segure o recarregar ou use atualizar
- limpe os dados do site ou abra em aba anônima
Isso evita cache da versão anterior.
