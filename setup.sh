# Instala as dependências de JS apenas se a pasta node_modules não existir
if [ ! -d "node_modules" ]; then
  pnpm install
fi

# Roda o JS em segundo plano (substitua pelo nome real do seu arquivo JS)
node sistema_omint.js & 

# Roda o bot principal em Python
python bot.py