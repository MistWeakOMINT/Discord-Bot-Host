import discord
from discord.ext import commands
from datetime import datetime
from main import GUILD_PRINCIPAL, GUILD_SIEX, LOG_CHANNELS

class LogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cache = {}
        self.invite_cache = {}

    # ====================== CACHE ======================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild and message.guild.id in (GUILD_PRINCIPAL, GUILD_SIEX):
            self.message_cache[message.id] = message
            if len(self.message_cache) > 8000:
                for old in list(self.message_cache.keys())[:-6000]:
                    self.message_cache.pop(old, None)

    # ====================== LOGS ======================
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        msg = self.message_cache.pop(payload.message_id, None)
        if not msg or msg.author.bot:
            return

        embed = discord.Embed(title="🗑️ Mensagem Apagada", color=0xFF0000, timestamp=discord.utils.utcnow())
        embed.set_author(name=str(msg.author), icon_url=msg.author.display_avatar.url)
        embed.add_field(name="Autor", value=msg.author.mention, inline=True)
        embed.add_field(name="Canal", value=f"<#{payload.channel_id}>", inline=True)
        embed.add_field(name="Conteúdo", value=msg.content[:1000] or "*Sem conteúdo*", inline=False)
        embed.set_footer(text=f"ID: {msg.author.id}")

        await self.send_log("text", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.content == after.content or before.author.bot:
            return
        embed = discord.Embed(title="✏️ Mensagem Editada", color=0xFFD700, timestamp=discord.utils.utcnow())
        embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
        embed.add_field(name="Autor", value=before.author.mention)
        embed.add_field(name="Canal", value=before.channel.mention)
        embed.add_field(name="Antes", value=before.content[:500] or "*Vazio*", inline=False)
        embed.add_field(name="Depois", value=after.content[:500] or "*Vazio*", inline=False)

        await self.send_log("text", embed)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        if entry.guild.id not in (GUILD_PRINCIPAL, GUILD_SIEX):
            return

        # Cargos
        if entry.action == discord.AuditLogAction.member_role_update:
            embed = discord.Embed(title="🔄 Cargos Atualizados", color=0x00FF88, timestamp=entry.created_at)
            embed.set_author(name=str(entry.target))
            embed.add_field(name="Usuário", value=entry.target.mention)
            embed.add_field(name="Responsável", value=entry.user.mention if entry.user else "Desconhecido")
            await self.send_log("roles", embed)

        # Punições
        elif entry.action in (discord.AuditLogAction.ban, discord.AuditLogAction.kick, discord.AuditLogAction.member_update):
            colors = {discord.AuditLogAction.ban: (0x8B0000, "🚫 Ban"), 
                     discord.AuditLogAction.kick: (0xFF4500, "👢 Expulso"),
                     discord.AuditLogAction.member_update: (0xFFAA00, "🔇 Timeout")}
            color, title = colors.get(entry.action, (0xFF0000, "Punido"))
            
            embed = discord.Embed(title=title, color=color, timestamp=entry.created_at)
            embed.add_field(name="Usuário", value=entry.target.mention)
            embed.add_field(name="Responsável", value=entry.user.mention if entry.user else "?")
            embed.add_field(name="Motivo", value=entry.reason or "Não informado", inline=False)
            await self.send_log("punishments", embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(title="✅ Novo Membro", color=0x00FF00, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Usuário", value=f"{member.mention} (`{member.id}`)")
        embed.add_field(name="Conta Criada", value=member.created_at.strftime("%d/%m/%Y às %H:%M"))
        await self.send_log("join", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title="❌ Membro Saiu", color=0xFF0000, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Usuário", value=f"{member} (`{member.id}`)")
        await self.send_log("join", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel: return
        if before.channel is None:
            title = "🎙 Entrou na Call"
            canal = after.channel.name
        elif after.channel is None:
            title = "📴 Saiu da Call"
            canal = before.channel.name
        else: return

        embed = discord.Embed(title=title, color=0x00AAFF, timestamp=discord.utils.utcnow())
        embed.add_field(name="Usuário", value=member.mention)
        embed.add_field(name="Canal", value=canal)
        await self.send_log("voice", embed)

    async def send_log(self, log_type: str, embed: discord.Embed):
        channel_id = LOG_CHANNELS.get(log_type)
        channel = self.bot.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

async def setup(bot):
    await bot.add_cog(LogsCog(bot))
