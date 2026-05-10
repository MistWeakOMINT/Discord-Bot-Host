import discord
from discord import app_commands
from discord.ui import Button, View
import sqlite3
import datetime
from typing import Optional

# ================== BANCO DE DADOS ==================
def get_db():
    conn = sqlite3.connect('pontos.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pontos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            username    TEXT    NOT NULL,
            display_name TEXT   NOT NULL,
            entrada     TEXT    NOT NULL,
            saida       TEXT,
            status      TEXT    NOT NULL DEFAULT 'aberto'
        )
    ''')
    conn.commit()
    conn.close()

# ================== UTILITÁRIOS ==================
def format_duration(td: datetime.timedelta) -> str:
    total = int(td.total_seconds())
    if total < 0: total = 0
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"`{h:02d}h {m:02d}m {s:02d}s`"

def progress_bar(percent: float, length: int = 12) -> str:
    percent = max(0, min(100, percent))
    filled = int(percent / 100 * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"`{bar}` **{percent:.1f}%**"

def ts(dt: datetime.datetime) -> int:
    return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())


# ================== VIEW DE PONTO ==================
class PontoView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Bater Ponto",
        style=discord.ButtonStyle.success,
        emoji="🟢",
        custom_id="bate_ponto:bater"
    )
    async def bater(self, interaction: discord.Interaction, button: Button):
        conn = get_db()
        user = interaction.user
        now = datetime.datetime.utcnow()

        aberto = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='aberto'",
            (interaction.guild_id, user.id)
        ).fetchone()

        if aberto:
            entrada = datetime.datetime.fromisoformat(aberto['entrada'])
            duracao = now - entrada
            conn.execute(
                "UPDATE pontos SET saida=?, status='fechado' WHERE id=?",
                (now.isoformat(), aberto['id'])
            )
            conn.commit()
            conn.close()

            em = discord.Embed(color=0xED4245, timestamp=now)
            em.set_author(name=f"⏹️  Ponto Encerrado • {user.display_name}", icon_url=user.display_avatar.url)
            em.description = (
                "```ansi\n\u001b[1;31m● SAÍDA REGISTRADA\u001b[0m\n```\n"
                f"> Seu turno foi encerrado com sucesso."
            )
            em.add_field(name="📥 Entrada", value=f"<t:{ts(entrada)}:T>\n<t:{ts(entrada)}:d>", inline=True)
            em.add_field(name="📤 Saída", value=f"<t:{ts(now)}:T>\n<t:{ts(now)}:d>", inline=True)
            em.add_field(name="⏱️ Duração", value=format_duration(duracao), inline=True)
            em.set_footer(text=f"Registro #{aberto['id']}  •  {interaction.guild.name}")
            await interaction.response.send_message(embed=em, ephemeral=True)

        else:
            conn.execute(
                "INSERT INTO pontos (guild_id, user_id, username, display_name, entrada) VALUES (?,?,?,?,?)",
                (interaction.guild_id, user.id, str(user), user.display_name, now.isoformat())
            )
            ponto_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            conn.close()

            em = discord.Embed(color=0x57F287, timestamp=now)
            em.set_author(name=f"▶️  Ponto Aberto • {user.display_name}", icon_url=user.display_avatar.url)
            em.description = (
                "```ansi\n\u001b[1;32m● EM SERVIÇO\u001b[0m\n```\n"
                f"> Seu turno foi iniciado. Clique novamente em **Bater Ponto** para encerrar."
            )
            em.add_field(name="📥 Entrada", value=f"<t:{ts(now)}:T>\n<t:{ts(now)}:d>", inline=True)
            em.add_field(name="📡 Status", value="`🟢 Em Serviço`", inline=True)
            em.add_field(name="⏱️ Duração", value="`00h 00m 00s`", inline=True)
            em.set_footer(text=f"Registro #{ponto_id}  •  {interaction.guild.name}")
            await interaction.response.send_message(embed=em, ephemeral=True)

    @discord.ui.button(
        label="Reabrir Ponto",
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        custom_id="bate_ponto:reabrir"
    )
    async def reabrir(self, interaction: discord.Interaction, button: Button):
        conn = get_db()
        user = interaction.user

        aberto = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='aberto'",
            (interaction.guild_id, user.id)
        ).fetchone()

        if aberto:
            conn.close()
            await interaction.response.send_message(
                "❌ Você já tem um ponto aberto. Encerre-o antes de reabrir outro.",
                ephemeral=True
            )
            return

        ultimo = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='fechado' ORDER BY id DESC LIMIT 1",
            (interaction.guild_id, user.id)
        ).fetchone()

        if not ultimo:
            conn.close()
            await interaction.response.send_message(
                "❌ Nenhum ponto anterior encontrado para reabrir.",
                ephemeral=True
            )
            return

        conn.execute("UPDATE pontos SET saida=NULL, status='aberto' WHERE id=?", (ultimo['id'],))
        conn.commit()
        conn.close()

        entrada = datetime.datetime.fromisoformat(ultimo['entrada'])
        now = datetime.datetime.utcnow()

        em = discord.Embed(color=0xFEE75C, timestamp=now)
        em.set_author(name=f"🔄  Ponto Reaberto • {user.display_name}", icon_url=user.display_avatar.url)
        em.description = (
            "```ansi\n\u001b[1;33m● PONTO REABERTO\u001b[0m\n```\n"
            f"> O registro foi reaberto para correção."
        )
        em.add_field(name="📥 Entrada Original", value=f"<t:{ts(entrada)}:f>", inline=True)
        em.add_field(name="📋 ID do Registro", value=f"`#{ultimo['id']}`", inline=True)
        em.set_footer(text=f"Clique em 🟢 Bater Ponto para encerrar novamente  •  {interaction.guild.name}")
        await interaction.response.send_message(embed=em, ephemeral=True)


# ================== SETUP DOS COMANDOS ==================
def setup_ponto(bot):
    init_db()

    # ── /ponto ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="ponto", description="🖥️ Painel de controle do ponto eletrônico")
    async def cmd_ponto(interaction: discord.Interaction):
        conn = get_db()
        user = interaction.user

        aberto = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='aberto'",
            (interaction.guild_id, user.id)
        ).fetchone()

        fechados = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='fechado'",
            (interaction.guild_id, user.id)
        ).fetchall()
        conn.close()

        total_s = sum(
            (datetime.datetime.fromisoformat(p['saida']) - datetime.datetime.fromisoformat(p['entrada'])).total_seconds()
            for p in fechados if p['saida']
        )

        now = datetime.datetime.utcnow()
        cor = 0x57F287 if aberto else 0x5865F2

        em = discord.Embed(color=cor, timestamp=now)
        em.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        em.set_thumbnail(url=user.display_avatar.url)
        em.description = (
            f"## 🖥️ Ponto Eletrônico\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Bem-vindo, **{user.display_name}**\n"
            f"Utilize os botões abaixo para registrar seu ponto.\n"
        )

        if aberto:
            entrada = datetime.datetime.fromisoformat(aberto['entrada'])
            em.add_field(
                name="📡 Status",
                value=f"🟢 `Em Serviço`\n> Desde <t:{ts(entrada)}:R>",
                inline=False
            )
        else:
            em.add_field(name="📡 Status", value="🔴 `Fora de Serviço`", inline=False)

        em.add_field(name="📊 Registros", value=f"`{len(fechados)}` encerrados", inline=True)
        em.add_field(name="⏱️ Total Acumulado", value=format_duration(datetime.timedelta(seconds=total_s)), inline=True)
        em.set_footer(text="🟢 Bater Ponto para entrar/sair  •  🔄 Reabrir para corrigir")

        await interaction.response.send_message(embed=em, view=PontoView(), ephemeral=True)

    # ── /relatorios ──────────────────────────────────────────────────────────
    @bot.tree.command(name="relatorios", description="📁 Relatórios de ponto de um membro")
    @app_commands.describe(membro="Membro para visualizar (padrão: você mesmo)")
    async def cmd_relatorios(interaction: discord.Interaction, membro: Optional[discord.Member] = None):
        alvo = membro or interaction.user
        conn = get_db()

        aberto = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='aberto'",
            (interaction.guild_id, alvo.id)
        ).fetchone()

        todos = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? ORDER BY id DESC",
            (interaction.guild_id, alvo.id)
        ).fetchall()
        conn.close()

        if not todos:
            await interaction.response.send_message(
                f"❌ Nenhum registro encontrado para **{alvo.display_name}**.",
                ephemeral=True
            )
            return

        fechados = [p for p in todos if p['status'] == 'fechado' and p['saida']]
        total_s = sum(
            (datetime.datetime.fromisoformat(p['saida']) - datetime.datetime.fromisoformat(p['entrada'])).total_seconds()
            for p in fechados
        )

        em = discord.Embed(color=0x5865F2, timestamp=datetime.datetime.utcnow())
        em.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        em.set_thumbnail(url=alvo.display_avatar.url)
        em.description = (
            f"## 📋 Relatório de Ponto\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"**{alvo.display_name}** • {alvo.mention}\n"
        )

        em.add_field(name="⏱️ Total Acumulado", value=format_duration(datetime.timedelta(seconds=total_s)), inline=True)
        em.add_field(name="📊 Registros", value=f"`{len(fechados)}` encerrados", inline=True)
        em.add_field(name="📡 Status", value="🟢 `Em Serviço`" if aberto else "🔴 `Fora de Serviço`", inline=True)

        ultimos = list(todos)[:10]
        if ultimos:
            em.add_field(name="━━━━━━━━━━━━━━━━━━━━━━━━━━━", value="**Últimos 10 Registros:**", inline=False)
            for p in ultimos:
                entrada = datetime.datetime.fromisoformat(p['entrada'])
                if p['status'] == 'fechado' and p['saida']:
                    saida = datetime.datetime.fromisoformat(p['saida'])
                    dur = format_duration(saida - entrada)
                    val = f"📥 <t:{ts(entrada)}:f>\n📤 <t:{ts(saida)}:f>\n⏱️ {dur}"
                    titulo = f"🔹 Registro #{p['id']}"
                else:
                    val = f"📥 <t:{ts(entrada)}:f>\n📤 `Em andamento...`\n⏱️ <t:{ts(entrada)}:R>"
                    titulo = f"🟢 Registro #{p['id']} *(aberto)*"
                em.add_field(name=titulo, value=val, inline=True)

        em.set_footer(text=f"Exibindo {len(ultimos)} de {len(todos)} registros")
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /apagar ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="apagar", description="🗑️ Apague registros de ponto de um membro")
    @app_commands.describe(
        membro="Membro cujos registros serão apagados",
        quantidade="Número de registros a apagar (vazio = apaga TODOS)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_apagar(interaction: discord.Interaction, membro: discord.Member, quantidade: Optional[int] = None):
        conn = get_db()

        total = conn.execute(
            "SELECT COUNT(*) as c FROM pontos WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, membro.id)
        ).fetchone()['c']

        if total == 0:
            conn.close()
            await interaction.response.send_message(
                f"❌ Nenhum registro encontrado para **{membro.display_name}**.",
                ephemeral=True
            )
            return

        if quantidade is None:
            conn.execute("DELETE FROM pontos WHERE guild_id=? AND user_id=?", (interaction.guild_id, membro.id))
            apagados = total
        else:
            ids = [r['id'] for r in conn.execute(
                "SELECT id FROM pontos WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT ?",
                (interaction.guild_id, membro.id, quantidade)
            ).fetchall()]
            if ids:
                conn.execute(f"DELETE FROM pontos WHERE id IN ({','.join('?'*len(ids))})", ids)
            apagados = len(ids)

        conn.commit()
        conn.close()

        em = discord.Embed(color=0xED4245, timestamp=datetime.datetime.utcnow())
        em.set_author(
            name=f"🗑️  Registros Apagados por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        em.description = (
            f"Os registros de **{membro.display_name}** foram removidos.\n"
        )
        em.add_field(name="👤 Membro", value=membro.mention, inline=True)
        em.add_field(name="🗑️ Apagados", value=f"`{apagados}` registros", inline=True)
        em.add_field(name="📋 Restantes", value=f"`{total - apagados}` registros", inline=True)
        em.set_footer(text=interaction.guild.name)
        await interaction.response.send_message(embed=em)

    # ── /meu-ponto ───────────────────────────────────────────────────────────
    @bot.tree.command(name="meu-ponto", description="👤 Veja um resumo rápido do seu ponto")
    async def cmd_meu_ponto(interaction: discord.Interaction):
        conn = get_db()
        user = interaction.user
        hoje = datetime.datetime.utcnow().date().isoformat()

        aberto = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='aberto'",
            (interaction.guild_id, user.id)
        ).fetchone()

        pontos_hoje = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND date(entrada)=? AND status='fechado'",
            (interaction.guild_id, user.id, hoje)
        ).fetchall()

        todos_fechados = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='fechado'",
            (interaction.guild_id, user.id)
        ).fetchall()
        conn.close()

        total_s = sum(
            (datetime.datetime.fromisoformat(p['saida']) - datetime.datetime.fromisoformat(p['entrada'])).total_seconds()
            for p in todos_fechados if p['saida']
        )
        hoje_s = sum(
            (datetime.datetime.fromisoformat(p['saida']) - datetime.datetime.fromisoformat(p['entrada'])).total_seconds()
            for p in pontos_hoje if p['saida']
        )

        now = datetime.datetime.utcnow()
        cor = 0x57F287 if aberto else 0x5865F2

        em = discord.Embed(color=cor, timestamp=now)
        em.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        em.set_thumbnail(url=user.display_avatar.url)
        em.description = (
            f"## 👤 Meu Ponto\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Resumo de **{user.display_name}**\n"
        )

        if aberto:
            entrada = datetime.datetime.fromisoformat(aberto['entrada'])
            em.add_field(name="📡 Status", value=f"🟢 `Em Serviço`\n> Desde <t:{ts(entrada)}:R>", inline=True)
        else:
            em.add_field(name="📡 Status", value="🔴 `Fora de Serviço`", inline=True)

        em.add_field(name="☀️ Horas Hoje", value=format_duration(datetime.timedelta(seconds=hoje_s)), inline=True)
        em.add_field(name="\u200b", value="\u200b", inline=True)
        em.add_field(name="📊 Total Acumulado", value=format_duration(datetime.timedelta(seconds=total_s)), inline=True)
        em.add_field(name="📋 Total de Registros", value=f"`{len(todos_fechados)}`", inline=True)
        em.add_field(name="\u200b", value="\u200b", inline=True)
        em.set_footer(text="Use /ponto para registrar  •  /relatorios para histórico")
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /ranking-horas ───────────────────────────────────────────────────────
    @bot.tree.command(name="ranking-horas", description="🏆 Ranking de horas trabalhadas no servidor")
    async def cmd_ranking(interaction: discord.Interaction):
        conn = get_db()
        usuarios = conn.execute(
            "SELECT DISTINCT user_id, display_name FROM pontos WHERE guild_id=?",
            (interaction.guild_id,)
        ).fetchall()

        ranking = []
        for u in usuarios:
            fechados = conn.execute(
                "SELECT * FROM pontos WHERE guild_id=? AND user_id=? AND status='fechado'",
                (interaction.guild_id, u['user_id'])
            ).fetchall()
            s = sum(
                (datetime.datetime.fromisoformat(p['saida']) - datetime.datetime.fromisoformat(p['entrada'])).total_seconds()
                for p in fechados if p['saida']
            )
            ranking.append((u['user_id'], u['display_name'], s))

        conn.close()
        ranking.sort(key=lambda x: x[2], reverse=True)
        ranking = ranking[:10]

        if not ranking:
            await interaction.response.send_message("❌ Nenhum registro encontrado.", ephemeral=True)
            return

        max_s = ranking[0][2] or 1
        medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7

        em = discord.Embed(color=0xFEE75C, timestamp=datetime.datetime.utcnow())
        em.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        em.description = (
            f"## 🏆 Ranking de Horas\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Top {len(ranking)} membros por horas trabalhadas\n"
        )

        for i, (uid, name, s) in enumerate(ranking):
            pct = (s / max_s) * 100
            em.add_field(
                name=f"{medals[i]}  {name}",
                value=f"{format_duration(datetime.timedelta(seconds=s))}\n{progress_bar(pct)}",
                inline=False
            )

        em.set_footer(text=f"Atualizado agora  •  {interaction.guild.name}")
        await interaction.response.send_message(embed=em)

    # ── /status-servidor ─────────────────────────────────────────────────────
    @bot.tree.command(name="status-servidor", description="📡 Veja quem está em serviço agora")
    async def cmd_status(interaction: discord.Interaction):
        conn = get_db()
        abertos = conn.execute(
            "SELECT * FROM pontos WHERE guild_id=? AND status='aberto' ORDER BY entrada ASC",
            (interaction.guild_id,)
        ).fetchall()
        conn.close()

        now = datetime.datetime.utcnow()
        cor = 0x57F287 if abertos else 0xED4245

        em = discord.Embed(color=cor, timestamp=now)
        em.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        em.description = (
            f"## 📡 Status do Servidor\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"**{len(abertos)}** membro(s) em serviço agora\n"
        )

        if abertos:
            for p in abertos:
                entrada = datetime.datetime.fromisoformat(p['entrada'])
                duracao = now - entrada
                em.add_field(
                    name=f"🟢 {p['display_name']}",
                    value=f"⏱️ {format_duration(duracao)}\n📥 <t:{ts(entrada)}:R>",
                    inline=True
                )
        else:
            em.add_field(name="", value="🔴 Nenhum membro em serviço no momento.", inline=False)

        em.set_footer(text="Atualizado agora")
        await interaction.response.send_message(embed=em)
