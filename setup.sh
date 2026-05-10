# Instalar dependências (se necessário)
pip install -r requirements.txt
pnpm install

# Rodar o sistema de segurança JS em segundo plano
node sistema_seguranca.js & 

# Rodar o bot principal Python
python bot.py
