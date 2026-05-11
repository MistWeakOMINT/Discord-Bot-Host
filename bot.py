from keep_alive import keep_alive
import discord
from discord.ext import commands
import os
import traceback

# ================== CONFIG ==================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.moderation = True
intents.auto_moderation = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ================== IDS ==================
GUILD_PRINCIPAL = 1135558598857068564
GUILD_SIEX = 1499872178039029792

LOG_CHANNELS = {
    "text": 1499872178986942539,
    "roles": 1499872178986942541,
    "join": 1499872178986942543,
    "invites": 1499872178986942544,
    "punishments": 1499872179234541788,
    "voice": 1499872179234541789,
    "security": 1499872179234541791,
}

# ================== ON READY ==================
@bot.event
async def on_ready():
    print(f"✅ Bot online como {bot.user}")

    # Sincroniza comandos
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

    # Carrega os Cogs com erro visível
    print("\n🔄 Carregando Cogs...")
    if not os.path.exists("./cogs"):
        print("❌ Pasta 'cogs' não encontrada!")
        return

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ Cog carregado com sucesso: {filename}")
            except Exception as e:
                print(f"❌ ERRO ao carregar {filename}")
                print(traceback.format_exc())

    print("\n🚀 Bot carregado completamente!\n")

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))
