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

    @discord.ui.button(label="Título", emoji="📝", style=discord.ButtonStyle.gray
