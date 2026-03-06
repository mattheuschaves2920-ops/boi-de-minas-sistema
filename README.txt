
Boi de Minas – Ravena
=====================

Esta é a versão pronta para publicação online e uso por várias pessoas ao mesmo tempo.

O que já está incluído
----------------------
- Login por usuário
- Cadastro de usuários com perfis:
  - admin
  - estoquista
  - operador
  - proprietario
- Estoque Geral, Bebidas e Freezer
- Entrada, saída e perdas
- Refeições:
  - Self-service HG
  - Self-service sem balança
  - Marmitex
  - Comida a quilo
  - Churrasco a quilo
- Comparativo almoço x janta
- Relatórios CSV de vendas e movimentos
- Preparado para PostgreSQL
- Arquivo render.yaml para publicar mais fácil

Publicação no Render
--------------------
1. Crie uma conta no Render.
2. Suba este projeto no GitHub.
3. No Render, crie um novo Blueprint e conecte ao repositório.
4. O Render vai ler o arquivo render.yaml e criar:
   - 1 web service
   - 1 banco PostgreSQL
5. Depois da publicação, abra:
   /setup
6. Faça login com:
   admin / 123456
7. Troque a senha.

Rodando localmente
------------------
pip install -r requirements.txt
python app.py

Observações importantes
-----------------------
- A leitura real por câmera de código de barras não está implementada nesta entrega.
  O sistema já tem campo para código de barras e está pronto para receber essa evolução.
- Para produção real, troque a SECRET_KEY.
- Se quiser, você pode publicar e usar no celular como site. Depois, o navegador permite criar atalho na tela inicial.

Arquivos principais
-------------------
- app.py
- templates/
- static/
- Dockerfile
- render.yaml
