from keep_alive import keep_alive
import discord
from discord.ext import commands
import datetime


# ================== CONFIG ==================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.moderation = True
intents.auto_moderation = True  # Para logs de AutoMod


bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ================== IDs ==================
GUILD_PRINCIPAL = 1135558598857068564   # ← Troque: Vila Militar • Roleplay
GUILD_SIEX = 1499872178039029792        # ← Troque: 6° D Sup - SIEx


# Canais de Logs no SIEx
LOG_TEXTO = 1499872178986942539       # registro-op-texto
LOG_CARGOS = 1499872178986942541      # registro-op-cargos
LOG_ENTRADA = 1499872178986942543     # registro-op-entrada
LOG_CONVITES = 1499872178986942544    # registro-op-convites
LOG_PUNICOES = 1499872179234541788    # registro-op-punições
LOG_CHAMADAS = 1499872179234541789    # registro-op-chamadas
LOG_SEGURANCA = 1499872179234541791   # registro-op-segurança


message_cache = {}
invite_cache = {}


@bot.event
async def on_ready():
    print(f"✅ Bot online como {bot.user}")
    print(f"Conectado em: {[g.name for g in bot.guilds]}")
    guild = bot.get_guild(GUILD_SIEX)
    if guild:
        try:
            invites = await guild.fetch_invites()
            invite_cache[GUILD_SIEX] = {inv.code: inv.uses for inv in invites}
        except Exception as e:
            print(f"Erro ao cachear convites: {e}")


@bot.event
async def on_invite_create(invite):
    if invite.guild.id == GUILD_SIEX:
        invite_cache.setdefault(GUILD_SIEX, {})[invite.code] = invite.uses


@bot.event
async def on_invite_delete(invite):
    if invite.guild.id == GUILD_SIEX:
        invite_cache.get(GUILD_SIEX, {}).pop(invite.code, None)


# ================== MENSAGENS ==================
@bot.event
async def on_message(message):
    if message.guild and message.guild.id in (GUILD_PRINCIPAL, GUILD_SIEX):
        message_cache[message.id] = message
        if len(message_cache) > 5000:  # Limita memória
            for old_id in list(message_cache.keys())[:-4000]:
                message_cache.pop(old_id, None)


@bot.event
async def on_raw_message_delete(payload):
    msg = message_cache.pop(payload.message_id, None)
    if not msg or msg.author.bot:
        return
    if payload.guild_id not in (GUILD_PRINCIPAL, GUILD_SIEX):
        return


    embed = discord.Embed(title="🗑 Mensagem Apagada", description=msg.content[:1000] or "*Sem conteúdo*", color=0xFF0000, timestamp=datetime.datetime.utcnow())
    embed.set_author(name=str(msg.author), icon_url=msg.author.avatar.url if msg.author.avatar else None)
    embed.add_field(name="Autor", value=msg.author.mention, inline=True)
    embed.add_field(name="Canal", value=msg.channel.mention, inline=True)
    embed.set_footer(text=f"{msg.guild.name} • ID: {msg.author.id}")

    channel = bot.get_channel(LOG_TEXTO)
    if channel: await channel.send(embed=embed)


@bot.event
async def on_message_edit(before, after):
    if before.content == after.content or before.author.bot:
        return
    if before.guild.id not in (GUILD_PRINCIPAL, GUILD_SIEX):
        return


    embed = discord.Embed(title="✏️ Mensagem Editada", color=0xFFD700, timestamp=datetime.datetime.utcnow())
    embed.set_author(name=str(before.author), icon_url=before.author.avatar.url if before.author.avatar else None)
    embed.add_field(name="Autor", value=before.author.mention, inline=True)
    embed.add_field(name="Canal", value=before.channel.mention, inline=True)
    embed.add_field(name="Antes", value=before.content[:500] or "*Vazio*", inline=False)
    embed.add_field(name="Depois", value=after.content[:500] or "*Vazio*", inline=False)
    embed.set_footer(text=before.guild.name)


    channel = bot.get_channel(LOG_TEXTO)
    if channel: await channel.send(embed=embed)


# ================== AUDIT LOG (Cargos, Punições, Convites) ==================
@bot.event
async def on_audit_log_entry_create(entry):
    if entry.guild.id not in (GUILD_PRINCIPAL, GUILD_SIEX):
        return


    # CARGOS
    if entry.action == discord.AuditLogAction.member_role_update:
        embed = discord.Embed(title="🔄 Cargos Alterados", color=0x00FF88, timestamp=entry.created_at)
        embed.set_author(name=str(entry.target), icon_url=entry.target.avatar.url if entry.target and hasattr(entry.target, 'avatar') else None)
        embed.add_field(name="Usuário", value=entry.target.mention if entry.target else "?", inline=True)
        embed.add_field(name="Responsável", value=entry.user.mention if entry.user else "Desconhecido", inline=True)
        embed.set_footer(text=entry.guild.name)

        channel = bot.get_channel(LOG_CARGOS)
        if channel: await channel.send(embed=embed)


    # PUNIÇÕES
    elif entry.action in (discord.AuditLogAction.ban, discord.AuditLogAction.kick, discord.AuditLogAction.member_update):
        if entry.action == discord.AuditLogAction.ban:
            title, color = "🚫 Usuário Banido", 0x8B0000
        elif entry.action == discord.AuditLogAction.kick:
            title, color = "👢 Usuário Expulso", 0xFF4500
        else:
            title, color = "🔇 Timeout aplicado", 0xFFAA00


        embed = discord.Embed(title=title, color=color, timestamp=entry.created_at)
        embed.set_author(name=str(entry.target), icon_url=entry.target.avatar.url if entry.target and hasattr(entry.target, 'avatar') else None)
        embed.add_field(name="Usuário", value=entry.target.mention if entry.target else "?", inline=True)
        embed.add_field(name="Responsável", value=entry.user.mention if entry.user else "?", inline=True)
        embed.add_field(name="Motivo", value=entry.reason or "Sem motivo", inline=False)
        embed.set_footer(text=entry.guild.name)


        channel = bot.get_channel(LOG_PUNICOES)
        if channel: await channel.send(embed=embed)


    # CONVITES
    elif entry.action == discord.AuditLogAction.invite_create:
        embed = discord.Embed(title="📨 Convite Usado", color=0xAA00FF, timestamp=entry.created_at)
        embed.add_field(name="Novo Membro", value=entry.target.mention if entry.target else "?", inline=True)
        embed.add_field(name="Convidado por", value=entry.user.mention if entry.user else "?", inline=True)
        embed.set_footer(text=entry.guild.name)


        channel = bot.get_channel(LOG_CONVITES)
        if channel: await channel.send(embed=embed)


# ================== JOIN / LEAVE ==================
@bot.event
async def on_member_join(member):
    if member.guild.id not in (GUILD_PRINCIPAL, GUILD_SIEX): return
    embed = discord.Embed(title="✅ Novo Membro", color=0x00FF00, timestamp=datetime.datetime.utcnow())
    embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else None)
    embed.add_field(name="Usuário", value=f"{member.mention} (`{member.id}`)", inline=False)
    embed.add_field(name="Conta criada", value=member.created_at.strftime("%d/%m/%Y às %H:%M"), inline=True)
    embed.set_footer(text=member.guild.name)


    channel = bot.get_channel(LOG_ENTRADA)
    if channel: await channel.send(embed=embed)


@bot.event
async def on_member_remove(member):
    if member.guild.id not in (GUILD_PRINCIPAL, GUILD_SIEX): return
    embed = discord.Embed(title="❌ Membro Saiu", color=0xFF0000, timestamp=datetime.datetime.utcnow())
    embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else None)
    embed.add_field(name="Usuário", value=f"{member} (`{member.id}`)", inline=False)
    embed.set_footer(text=member.guild.name)


    channel = bot.get_channel(LOG_ENTRADA)
    if channel: await channel.send(embed=embed)


# ================== VOICE ==================
@bot.event
async def on_voice_state_update(member, before, after):
    if member.guild.id not in (GUILD_PRINCIPAL, GUILD_SIEX): return
    if before.channel == after.channel: return


    if before.channel is None and after.channel is not None:
        title, color = "🎙 Entrou na Call", 0x00AAFF
        canal = after.channel.name
    elif before.channel is not None and after.channel is None:
        title, color = "📴 Saiu da Call", 0xFF8800
        canal = before.channel.name
    else:
        return


    embed = discord.Embed(title=title, color=color, timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Usuário", value=member.mention, inline=True)
    embed.add_field(name="Canal", value=canal, inline=True)
    embed.set_footer(text=member.guild.name)


    channel = bot.get_channel(LOG_CHAMADAS)
    if channel: await channel.send(embed=embed)


# ================== SEGURANÇA (AutoMod + Raid) ==================
@bot.event
async def on_auto_moderation_action_execution(action):
    if action.guild_id not in (GUILD_PRINCIPAL, GUILD_SIEX):
        return


    embed = discord.Embed(title="🛡️ Ação do AutoMod", color=0xFF00FF, timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Usuário", value=action.member.mention if action.member else "?", inline=True)
    embed.add_field(name="Ação", value=action.action_type.name, inline=True)
    embed.add_field(name="Motivo", value=action.reason or "AutoMod", inline=False)
    embed.set_footer(text=action.guild.name)


    channel = bot.get_channel(LOG_SEGURANCA)
    if channel: await channel.send(embed=embed)


# ================== RODAR O BOT ==================
import os
keep_alive()
token = os.environ.get("DISCORD_TOKEN", "MTUwMjQ1MzA2OTQ5MTczMjU2Mw.G_jOz5.kiAZKehQf_o8LoiixTQp_joaqcqzx54pY2gh4s")
bot.run(token)
