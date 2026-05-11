import discord
from discord.ext import commands
from keep_alive import keep_alive
import os
from ponto import setup_ponto
from security import setup_security

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print(f"{bot.user} is now running!")

setup_ponto(bot)
setup_security(bot)

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
