import discord
from discord.ext import commands
import json
import io

# ====================== MODALS ======================
class EmbedFieldModal(discord.ui.Modal, title="Adicionar/Editar Field"):
    name = discord.ui.TextInput(label="Nome do Field", max_length=256)
    value = discord.ui.TextInput(label="Valor", style=discord.TextStyle.paragraph, max_length=1024)
    inline = discord.ui.TextInput(label="Inline (True/False)", default="True")

    def __init__(self, view, index=None):
        super().__init__()
        self.view_ref = view
        self.index = index

    async def on_submit(self, interaction: discord.Interaction):
        try:
            embed = self.view_ref.embeds[self.view_ref.current]
            inline = self.inline.value.lower() == "true"
            
            if self.index is not None:
                embed.set_field_at(self.index, name=self.name.value, value=self.value.value, inline=inline)
            else:
                embed.add_field(name=self.name.value, value=self.value.value, inline=inline)
                
            await self.view_ref.update(interaction)
        except:
            await interaction.response.send_message("❌ Erro ao adicionar field.", ephemeral=True)


class EmbedEditModal(discord.ui.Modal):
    def __init__(self, field: str, view):
        super().__init__(title=f"Editar {field}")
        self.field = field
        self.view_ref = view
        self.input = discord.ui.TextInput(label=field, style=discord.TextStyle.paragraph, max_length=4000)
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.view_ref.embeds[self.view_ref.current]
        val = self.input.value.strip()

        if self.field == "Título":
            embed.title = val
        elif self.field == "Descrição":
            embed.description = val
        elif self.field == "Cor":
            try:
                embed.color = discord.Color.from_str(val)
            except:
                embed.color = discord.Color.blurple()
        elif self.field == "Rodapé":
            embed.set_footer(text=val)
        elif self.field == "Thumbnail":
            embed.set_thumbnail(url=val)
        elif self.field == "Imagem":
            embed.set_image(url=val)

        await self.view_ref.update(interaction)


# ====================== VIEW PRINCIPAL ======================
class EmbedPanel(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=3600)
        self.owner = interaction.user.id
        self.current = 0
        self.embeds = [self.create_base_embed(interaction.guild)]
        self.public_buttons = []
        self.add_item(EmbedSelector(self))

    def create_base_embed(self, guild):
        embed = discord.Embed(
            title="Nova Embed",
            description="Clique nos botões para editar...",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        
        # === AUTOR FIXO ===
        embed.set_author(
            name="6° D Sup - Sexto Depósito de Suprimentos",
            icon_url=guild.icon.url if guild.icon else None
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(text="Sistema de Embeds")
        return embed

    def refresh_selector(self):
        for child in self.children[:]:
            if isinstance(child, EmbedSelector):
                self.remove_item(child)
        self.add_item(EmbedSelector(self))

    async def update(self, interaction: discord.Interaction):
        self.refresh_selector()
        await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

    # ====================== BOTÕES ======================
    @discord.ui.button(label="Nova Embed", emoji="➕", style=discord.ButtonStyle.green, row=0)
    async def add_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner: return
        self.embeds.append(self.create_base_embed(interaction.guild))
        self.current = len(self.embeds) - 1
        await self.update(interaction)

    @discord.ui.button(label="Adicionar Field", emoji="📌", style=discord.ButtonStyle.blurple, row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner: return
        await interaction.response.send_modal(EmbedFieldModal(self))

    @discord.ui.button(label="Título", emoji="📝", style=discord.ButtonStyle.gray, row=2)
    async def edit_title(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EmbedEditModal("Título", self))

    @discord.ui.button(label="Descrição", emoji="📄", style=discord.ButtonStyle.gray, row=2)
    async def edit_desc(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EmbedEditModal("Descrição", self))

    @discord.ui.button(label="Cor", emoji="🎨", style=discord.ButtonStyle.gray, row=2)
    async def edit_color(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EmbedEditModal("Cor", self))

    @discord.ui.button(label="Imagem", emoji="🖼", style=discord.ButtonStyle.gray, row=3)
    async def edit_image(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EmbedEditModal("Imagem", self))

    @discord.ui.button(label="Thumbnail", emoji="🖼", style=discord.ButtonStyle.gray, row=3)
    async def edit_thumbnail(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EmbedEditModal("Thumbnail", self))

    @discord.ui.button(label="Rodapé", emoji="📌", style=discord.ButtonStyle.gray, row=3)
    async def edit_footer(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EmbedEditModal("Rodapé", self))

    @discord.ui.button(label="Enviar", emoji="📤", style=discord.ButtonStyle.red, row=4)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner: return
        
        public_view = discord.ui.View()
        for btn in self.public_buttons:
            public_view.add_item(btn)

        await interaction.channel.send(
            embeds=self.embeds,
            view=public_view if self.public_buttons else None
        )
        await interaction.response.send_message("✅ Embed enviada com sucesso!", ephemeral=True)


class EmbedSelector(discord.ui.Select):
    def __init__(self, view: EmbedPanel):
        options = [discord.SelectOption(
            label=f"Embed {i+1}", 
            description=embed.title[:50] or "Sem título", 
            value=str(i)
        ) for i, embed in enumerate(view.embeds)]
        
        super().__init__(placeholder="Escolha um embed...", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.owner:
            return await interaction.response.send_message("❌ Apenas o dono pode usar.", ephemeral=True)
        self.view_ref.current = int(self.values[0])
        await self.view_ref.update(interaction)


# ====================== COG ======================
class EmbedBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="criar", description="Sistema Avançado de Embeds")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def criar(self, interaction: discord.Interaction):
        view = EmbedPanel(interaction)
        await interaction.response.send_message(embed=view.embeds[0], view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
