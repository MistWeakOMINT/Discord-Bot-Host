from keep_alive import keep_alive
import discord
from discord.ext import commands
import os
import json
from datetime import datetime

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

# ================== EVENTS ==================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online como {bot.user} • {len(bot.guilds)} servidores")

    # Carregar cogs
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"✅ Cog carregado: {filename}")

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN"))
