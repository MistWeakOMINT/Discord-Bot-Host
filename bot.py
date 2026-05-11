from keep_alive import keep_alive
from ponto import setup_ponto
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
    setup_ponto(bot)
    await bot.tree.sync()
    print(f"✅ Bot online como {bot.user}")
    print(f"✅ Slash commands sincronizados")
    print(f"Conectado em: {[g.name for g in bot.guilds]}")
    guild = bot.get_guild(GUILD_SIEX)
    if guild:
        try:
            invites = await guild.invites()
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

    # ================== RASTREAMENTO DE CONVITES ==================
    if member.guild.id == GUILD_SIEX:
        try:
            invites_antes = invite_cache.get(GUILD_SIEX, {})
            invites_agora = await member.guild.invites()
            invite_cache[GUILD_SIEX] = {inv.code: inv.uses for inv in invites_agora}

            invite_usado = None
            inviter = None
            for inv in invites_agora:
                uses_antes = invites_antes.get(inv.code, 0)
                if inv.uses > uses_antes:
                    invite_usado = inv
                    inviter = inv.inviter
                    break

            canal_convites = bot.get_channel(LOG_CONVITES)
            if canal_convites:
                em = discord.Embed(
                    title="📨 Novo Membro por Convite",
                    color=0x5865F2,
                    timestamp=datetime.datetime.utcnow()
                )
                em.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                em.add_field(
                    name="👤 Membro Convidado",
                    value=f"{member.mention}\n`{member}`\nID: `{member.id}`",
                    inline=True
                )
                em.add_field(
                    name="📩 Convidado por",
                    value=f"{inviter.mention}\n`{inviter}`\nID: `{inviter.id}`" if inviter else "Desconhecido",
                    inline=True
                )
                em.add_field(
                    name="🔗 Código do Convite",
                    value=f"`{invite_usado.code}`\nUsos: `{invite_usado.uses}`" if invite_usado else "Desconhecido",
                    inline=False
                )
                em.add_field(
                    name="📅 Conta Criada em",
                    value=member.created_at.strftime("%d/%m/%Y às %H:%M"),
                    inline=True
                )
                em.set_footer(text=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
                await canal_convites.send(embed=em)
        except Exception as e:
            print(f"Erro no rastreamento de convite: {e}")


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

# =========================================================
# SISTEMA ULTRA AVANÇADO DE EMBEDS
# COLE ACIMA DO:
# # ================== RODAR O BOT ================
# =========================================================

import json
import io

# =========================================================
# SESSÕES
# =========================================================

embed_sessions = {}

# =========================================================
# MODAL EDITOR
# =========================================================

class EmbedEditModal(discord.ui.Modal):

    def __init__(self, field, view):
        super().__init__(title=f"Editar {field}")

        self.field = field
        self.view_ref = view

        self.input = discord.ui.TextInput(
            label=field,
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):

        embed = self.view_ref.embeds[self.view_ref.current]

        if self.field == "Título":
            embed.title = self.input.value

        elif self.field == "Descrição":
            embed.description = self.input.value

        elif self.field == "Cor":

            try:
                embed.color = discord.Color.from_str(self.input.value)
            except:
                embed.color = discord.Color.dark_embed()

        elif self.field == "Rodapé":
            embed.set_footer(text=self.input.value)

        elif self.field == "Thumbnail":
            embed.set_thumbnail(url=self.input.value)

        await self.view_ref.update_embed(interaction)

# =========================================================
# MODAL BOTÃO
# =========================================================

class ButtonModal(discord.ui.Modal, title="Adicionar Botão"):

    label = discord.ui.TextInput(
        label="Texto do botão",
        required=True,
        max_length=80
    )

    url = discord.ui.TextInput(
        label="URL",
        required=True
    )

    def __init__(self, view):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):

        button = discord.ui.Button(
            label=self.label.value,
            style=discord.ButtonStyle.link,
            url=self.url.value
        )

        self.view_ref.public_buttons.append(button)

        await self.view_ref.update_embed(interaction)

# =========================================================
# MODAL IMPORT JSON
# =========================================================

class ImportJsonModal(discord.ui.Modal, title="Importar JSON"):

    json_input = discord.ui.TextInput(
        label="Cole o JSON da Embed",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    def __init__(self, view):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):

        try:

            data = json.loads(self.json_input.value)

            self.view_ref.embeds = [
                discord.Embed.from_dict(embed)
                for embed in data
            ]

            self.view_ref.current = 0

            await self.view_ref.update_embed(interaction)

        except Exception as e:

            await interaction.response.send_message(
                f"❌ JSON inválido.\n```py\n{e}\n```",
                ephemeral=True
            )

# =========================================================
# SELECT MENU
# =========================================================

class EmbedSelector(discord.ui.Select):

    def __init__(self, view):

        options = []

        for i, embed in enumerate(view.embeds):

            options.append(
                discord.SelectOption(
                    label=f"Embed {i+1}",
                    description=embed.title or "Sem título",
                    value=str(i),
                    emoji="📦"
                )
            )

        super().__init__(
            placeholder="Selecione um Embed para editar",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):

        if interaction.user.id != self.view_ref.owner:
            return await interaction.response.send_message(
                "❌ Apenas o criador pode usar.",
                ephemeral=True
            )

        self.view_ref.current = int(self.values[0])

        await self.view_ref.update_embed(interaction)

# =========================================================
# VIEW PRINCIPAL
# =========================================================

class EmbedPanel(discord.ui.View):

    def __init__(self, interaction):

        super().__init__(timeout=1800)

        self.owner = interaction.user.id
        self.guild = interaction.guild

        self.current = 0

        self.public_buttons = []

        self.embeds = [self.generate_embed()]

        self.refresh_selector()

    # =====================================================

    def generate_embed(self):

        embed = discord.Embed(
            title="🎖 Nova Embed",
            description="Descrição da embed...",
            color=discord.Color.dark_green()
        )

        embed.set_author(
            name="6° D Sup - Sexto Depósito de Suprimentos",
            icon_url=self.guild.icon.url if self.guild.icon else None
        )

        embed.set_footer(
            text="Sistema de Embeds"
        )

        embed.timestamp = datetime.datetime.utcnow()

        return embed

    # =====================================================

    def refresh_selector(self):

        for item in self.children:
            if isinstance(item, EmbedSelector):
                self.remove_item(item)

        self.add_item(EmbedSelector(self))

    # =====================================================

    async def update_embed(self, interaction):

        self.refresh_selector()

        await interaction.response.edit_message(
            embed=self.embeds[self.current],
            view=self
        )

    # =====================================================
    # ADICIONAR EMBED
    # =====================================================

    @discord.ui.button(
        label="Adicionar Embed",
        emoji="➕",
        style=discord.ButtonStyle.green,
        row=1
    )
    async def add_embed(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.owner:
            return

        self.embeds.append(self.generate_embed())

        self.current = len(self.embeds) - 1

        await self.update_embed(interaction)

    # =====================================================
    # ADICIONAR BOTÃO
    # =====================================================

    @discord.ui.button(
        label="Adicionar Botão",
        emoji="🔗",
        style=discord.ButtonStyle.blurple,
        row=1
    )
    async def add_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.owner:
            return

        await interaction.response.send_modal(
            ButtonModal(self)
        )

    # =====================================================
    # ENVIAR
    # =====================================================

    @discord.ui.button(
        label="Enviar",
        emoji="📨",
        style=discord.ButtonStyle.red,
        row=1
    )
    async def send_embed(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.owner:
            return

        public_view = discord.ui.View()

        for btn in self.public_buttons:
            public_view.add_item(btn)

        await interaction.channel.send(
            embeds=self.embeds,
            view=public_view if self.public_buttons else None
        )

        await interaction.response.send_message(
            "✅ Embed enviada com sucesso.",
            ephemeral=True
        )

    # =====================================================
    # EDITORES
    # =====================================================

    @discord.ui.button(
        label="Título",
        emoji="📝",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def edit_title(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            EmbedEditModal("Título", self)
        )

    # =====================================================

    @discord.ui.button(
        label="Descrição",
        emoji="📄",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def edit_desc(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            EmbedEditModal("Descrição", self)
        )

    # =====================================================

    @discord.ui.button(
        label="Cor",
        emoji="🎨",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def edit_color(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            EmbedEditModal("Cor", self)
        )

    # =====================================================

    @discord.ui.button(
        label="Rodapé",
        emoji="📌",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def edit_footer(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            EmbedEditModal("Rodapé", self)
        )

    # =====================================================

    @discord.ui.button(
        label="Thumbnail",
        emoji="🖼",
        style=discord.ButtonStyle.secondary,
        row=2
    )
    async def edit_thumb(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            EmbedEditModal("Thumbnail", self)
        )

    # =====================================================
    # IMPORT JSON
    # =====================================================

    @discord.ui.button(
        label="Importar JSON",
        emoji="📥",
        style=discord.ButtonStyle.primary,
        row=3
    )
    async def import_json(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            ImportJsonModal(self)
        )

    # =====================================================
    # EXPORT JSON
    # =====================================================

    @discord.ui.button(
        label="Exportar JSON",
        emoji="📤",
        style=discord.ButtonStyle.green,
        row=3
    )
    async def export_json(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        data = json.dumps(
            [embed.to_dict() for embed in self.embeds],
            indent=4,
            ensure_ascii=False
        )

        buffer = io.BytesIO(data.encode())

        file = discord.File(
            buffer,
            filename="embed.json"
        )

        await interaction.response.send_message(
            file=file,
            ephemeral=True
        )

    # =====================================================
    # TIMEOUT
    # =====================================================

    async def on_timeout(self):

        for item in self.children:
            item.disabled = True

# =========================================================
# SLASH COMMAND
# =========================================================

@bot.tree.command(
    name="criar",
    description="Sistema avançado de embeds"
)
async def criar(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:

        return await interaction.response.send_message(
            "❌ Apenas administradores podem usar.",
            ephemeral=True
        )

    view = EmbedPanel(interaction)

    await interaction.response.send_message(
        embed=view.embeds[0],
        view=view,
        ephemeral=True
    )

# =========================================================
# SISTEMA ULTRA AVANÇADO DE CLEAR
# COMANDO: /limpar quantidade
# MÍNIMO: 10
# MÁXIMO: 100000
# =========================================================

@bot.tree.command(
    name="limpar",
    description="Limpa mensagens do chat"
)
@app_commands.describe(
    quantidade="Quantidade de mensagens para apagar"
)
async def limpar(
    interaction: discord.Interaction,
    quantidade: int
):

    # =====================================================
    # PERMISSÃO
    # =====================================================

    if not interaction.user.guild_permissions.manage_messages:

        embed = discord.Embed(
            title="❌ Sem Permissão",
            description="Você precisa da permissão `Gerenciar Mensagens`.",
            color=0xFF0000
        )

        return await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # VALIDAÇÃO
    # =====================================================

    if quantidade < 10:

        embed = discord.Embed(
            title="⚠ Quantidade inválida",
            description="O mínimo permitido é **10 mensagens**.",
            color=0xFFAA00
        )

        return await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    if quantidade > 100000:

        embed = discord.Embed(
            title="⚠ Limite excedido",
            description="O máximo permitido é **100000 mensagens**.",
            color=0xFF0000
        )

        return await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # INÍCIO
    # =====================================================

    await interaction.response.defer(ephemeral=True)

    apagadas = 0

    try:

        while apagadas < quantidade:

            restante = quantidade - apagadas

            pegar = min(restante, 100)

            mensagens = [
                message async for message in interaction.channel.history(
                    limit=pegar
                )
            ]

            if not mensagens:
                break

            try:
                await interaction.channel.delete_messages(mensagens)
                apagadas += len(mensagens)

            except:

                for msg in mensagens:
                    try:
                        await msg.delete()
                        apagadas += 1
                    except:
                        pass

        # =================================================
        # SUCESSO
        # =================================================

        embed = discord.Embed(
            title="🧹 Chat Limpo",
            description=(
                f"✅ Foram apagadas "
                f"**{apagadas} mensagens**."
            ),
            color=0x00FF88
        )

        embed.set_footer(
            text=f"Ação executada por {interaction.user}"
        )

        embed.timestamp = datetime.datetime.utcnow()

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

    except Exception as e:

        erro = discord.Embed(
            title="❌ Erro ao limpar",
            description=f"```py\n{e}\n```",
            color=0xFF0000
        )

        await interaction.followup.send(
            embed=erro,
            ephemeral=True
        )

# =========================================================
# SISTEMA DE CALL PRIVADA AUTOMÁTICA
# =========================================================

# ID DA CALL GERADORA
CALL_CREATE_ID = 1502511323185938552

# CALLS CRIADAS
temporary_calls = {}

# =========================================================
# GERADOR DE NOMES
# =========================================================

def gerar_nome_call(guild):

    numeros = [
        "¹","²","³","⁴","⁵",
        "⁶","⁷","⁸","⁹","¹⁰",
        "¹¹","¹²","¹³","¹⁴","¹⁵",
        "¹⁶","¹⁷","¹⁸","¹⁹","²⁰",
        "²¹","²²","²³","²⁴","²⁵",
        "²⁶","²⁷","²⁸","²⁹","³⁰",
        "³¹","³²","³³","³⁴","³⁵",
        "³⁶","³⁷","³⁸","³⁹","⁴⁰",
        "⁴¹","⁴²","⁴³","⁴⁴","⁴⁵",
        "⁴⁶","⁴⁷","⁴⁸","⁴⁹","⁵⁰",
        "⁵¹","⁵²","⁵³","⁵⁴","⁵⁵",
        "⁵⁶","⁵⁷","⁵⁸","⁵⁹","⁶⁰",
        "⁶¹","⁶²","⁶³","⁶⁴","⁶⁵",
        "⁶⁶","⁶⁷","⁶⁸","⁶⁹","⁷⁰",
        "⁷¹","⁷²","⁷³","⁷⁴","⁷⁵",
        "⁷⁶","⁷⁷","⁷⁸","⁷⁹","⁸⁰",
        "⁸¹","⁸²","⁸³","⁸⁴","⁸⁵",
        "⁸⁶","⁸⁷","⁸⁸","⁸⁹","⁹⁰",
        "⁹¹","⁹²","⁹³","⁹⁴","⁹⁵",
        "⁹⁶","⁹⁷","⁹⁸","⁹⁹","¹⁰⁰"
    ]

    usados = []

    for channel in guild.voice_channels:

        if channel.name.startswith("Call"):

            usados.append(channel.name)

    for numero in numeros:

        nome = f"Call{numero}"

        if nome not in usados:
            return nome

    return "Call Extra"

# =========================================================
# CRIAR CALL
# =========================================================

@bot.event
async def on_voice_state_update(member, before, after):

    # =====================================================
    # ENTRAR NA CALL GERADORA
    # =====================================================

    if after.channel and after.channel.id == CALL_CREATE_ID:

        categoria = after.channel.category

        nome_call = gerar_nome_call(member.guild)

        overwrites = {

            member.guild.default_role: discord.PermissionOverwrite(
                connect=True,
                view_channel=True
            ),

            member: discord.PermissionOverwrite(
                manage_channels=True,
                move_members=True,
                mute_members=True,
                deafen_members=True
            )
        }

        call = await member.guild.create_voice_channel(
            name=nome_call,
            category=categoria,
            overwrites=overwrites,
            bitrate=64000,
            user_limit=0
        )

        temporary_calls[call.id] = member.id

        await member.move_to(call)

        try:

            embed = discord.Embed(
                title="🎙 Call Criada",
                description=(
                    f"Sua call privada foi criada.\n\n"
                    f"🔒 Use `/fechar` para trancar a call."
                ),
                color=0x00FF88
            )

            embed.add_field(
                name="📞 Canal",
                value=call.mention
            )

            embed.timestamp = datetime.datetime.utcnow()

            await member.send(embed=embed)

        except:
            pass

    # =====================================================
    # DELETAR CALL VAZIA
    # =====================================================

    if before.channel:

        if before.channel.id in temporary_calls:

            if len(before.channel.members) == 0:

                try:
                    del temporary_calls[before.channel.id]
                except:
                    pass

                await before.channel.delete()

# =========================================================
# FECHAR CALL
# =========================================================

@bot.tree.command(
    name="fechar",
    description="Fecha sua call privada"
)
async def fechar(interaction: discord.Interaction):

    canal = interaction.user.voice.channel if interaction.user.voice else None

    if not canal:

        embed = discord.Embed(
            title="❌ Você não está em uma call",
            color=0xFF0000
        )

        return await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    if canal.id not in temporary_calls:

        embed = discord.Embed(
            title="❌ Esta call não é temporária",
            color=0xFF0000
        )

        return await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    dono = temporary_calls[canal.id]

    if interaction.user.id != dono:

        embed = discord.Embed(
            title="❌ Apenas o dono da call pode fechar",
            color=0xFF0000
        )

        return await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    await canal.set_permissions(
        interaction.guild.default_role,
        connect=False
    )

    embed = discord.Embed(
        title="🔒 Call Fechada",
        description=(
            "A call foi trancada.\n"
            "Quando todos saírem, ela será deletada."
        ),
        color=0x5865F2
    )

    embed.timestamp = datetime.datetime.utcnow()

    await interaction.response.send_message(
        embed=embed
        )

# ================== RODAR O BOT ================
import os
token = os.environ.get("DISCORD_TOKEN")

keep_alive()
bot.run(token)
