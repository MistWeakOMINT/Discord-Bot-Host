# ================================================================================
#  HSIS — Hillenkoetter Security Intelligence System  v2.0
#  Módulo de Segurança Avançada para Discord
# ================================================================================

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import datetime
import sqlite3
import re
import time
import random
import string
import json
from collections import defaultdict, deque
from typing import Optional, Literal

# ────────────────────────────────────────────────────────────────────────────────
#  CONSTANTES GLOBAIS
# ────────────────────────────────────────────────────────────────────────────────
LOG_SEGURANCA   = 1499872179234541791
GUILD_PRINCIPAL = 1135558598857068564
GUILD_SIEX      = 1499872178039029792
GUILDS_WATCHED  = {GUILD_PRINCIPAL, GUILD_SIEX}

RAID_THRESHOLD  = 8     # joins em RAID_WINDOW segundos = raid
RAID_WINDOW     = 30
NUKE_THRESHOLD  = 3     # ações em NUKE_WINDOW segundos = nuke
NUKE_WINDOW     = 30
SPAM_RATE       = 6     # mensagens em SPAM_WINDOW segundos = spam
SPAM_WINDOW     = 5
MIN_ACCOUNT_DAYS = 7    # conta nova se < N dias
WARN_KICK_AT    = 3     # warns → kick automático
WARN_BAN_AT     = 5     # warns → ban automático

# ────────────────────────────────────────────────────────────────────────────────
#  DATABASE
# ────────────────────────────────────────────────────────────────────────────────
def sec_db() -> sqlite3.Connection:
    conn = sqlite3.connect('security.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_sec_db():
    conn = sec_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS warnings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     INTEGER NOT NULL,
            user_id      INTEGER NOT NULL,
            user_tag     TEXT,
            moderator_id INTEGER,
            reason       TEXT DEFAULT 'Sem motivo',
            timestamp    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS blacklist (
            guild_id   INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            user_tag   TEXT,
            added_by   INTEGER,
            reason     TEXT DEFAULT 'Sem motivo',
            timestamp  TEXT,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS whitelist_users (
            guild_id INTEGER NOT NULL,
            user_id  INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS whitelist_roles (
            guild_id INTEGER NOT NULL,
            role_id  INTEGER NOT NULL,
            PRIMARY KEY (guild_id, role_id)
        );
        CREATE TABLE IF NOT EXISTS quarantine_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     INTEGER NOT NULL,
            user_id      INTEGER NOT NULL,
            user_tag     TEXT,
            moderator_id INTEGER,
            reason       TEXT,
            timestamp    TEXT NOT NULL,
            active       INTEGER DEFAULT 1,
            saved_roles  TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS security_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            user_id    INTEGER,
            details    TEXT,
            timestamp  TEXT NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

# ────────────────────────────────────────────────────────────────────────────────
#  FUNÇÕES UTILITÁRIAS
# ────────────────────────────────────────────────────────────────────────────────
def op_code(prefix: str = "SEC") -> str:
    return f"OP-{prefix}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

def threat_color(score: float) -> int:
    if score < 20: return 0x57F287   # verde
    if score < 45: return 0xFEE75C   # amarelo
    if score < 70: return 0xFF6B35   # laranja
    return                 0xED4245  # vermelho crítico

def threat_label(score: float) -> str:
    if score < 20: return "🟢 BAIXO"
    if score < 45: return "🟡 MÉDIO"
    if score < 70: return "🟠 ALTO"
    return                 "🔴 CRÍTICO"

def acct_age_days(user: discord.User) -> int:
    return (datetime.datetime.utcnow() - user.created_at.replace(tzinfo=None)).days

def calc_heat(member: discord.Member, extra: int = 0) -> float:
    score = float(extra)
    age = acct_age_days(member)
    if age < 1:    score += 65
    elif age < 7:  score += 45
    elif age < 30: score += 25
    elif age < 90: score += 12
    if not member.avatar:                                    score += 20
    if re.fullmatch(r'[a-z]+\d{4,}', member.name.lower()): score += 15
    if re.search(r'\d{6,}', member.name):                   score += 10
    return min(score, 100.0)

def heat_bar(score: float, length: int = 10) -> str:
    filled = int(score / 100 * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"`{bar}` **{score:.1f}/100**"

def sec_embed(title: str, score: float = 0, op: str = None) -> discord.Embed:
    em = discord.Embed(color=threat_color(score), timestamp=datetime.datetime.utcnow())
    em.title = title
    footer = f"🔐 {op}  •  HSIS v2.0" if op else "🔐 HSIS — Hillenkoetter Security Intelligence System"
    em.set_footer(text=footer)
    return em

def log_event(guild_id: int, event_type: str, user_id: int = None, details: str = None):
    try:
        conn = sec_db()
        conn.execute(
            "INSERT INTO security_events (guild_id, event_type, user_id, details, timestamp) VALUES (?,?,?,?,?)",
            (guild_id, event_type, user_id, details, datetime.datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

# ────────────────────────────────────────────────────────────────────────────────
#  COG PRINCIPAL
# ────────────────────────────────────────────────────────────────────────────────
class SecurityCog(commands.Cog, name="SecurityCog"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_sec_db()

        # Estado em memória — altamente eficiente, sem I/O por evento
        self.join_times:    dict[int, deque] = defaultdict(lambda: deque(maxlen=60))
        self.msg_times:     dict[int, deque] = defaultdict(lambda: deque(maxlen=30))
        self.msg_contents:  dict[int, deque] = defaultdict(lambda: deque(maxlen=15))
        self.nuke_tracker:  dict[int, dict]  = defaultdict(lambda: defaultdict(lambda: deque(maxlen=30)))
        self.heat_scores:   dict[int, float] = {}
        self.raid_mode:     dict[int, int]   = {}   # 0=off 1=low 2=high 3=lockdown
        self.nuke_alert:    set[int]         = set()
        self.last_msg_ts:   dict[int, float] = {}
        self.action_queue                    = asyncio.Queue()

        self._cleanup_task.start()
        self._process_queue.start()

    def cog_unload(self):
        self._cleanup_task.cancel()
        self._process_queue.cancel()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def is_whitelisted(self, guild_id: int, member: discord.Member) -> bool:
        if member.guild_permissions.administrator:
            return True
        conn = sec_db()
        wu = conn.execute("SELECT 1 FROM whitelist_users WHERE guild_id=? AND user_id=?",
                          (guild_id, member.id)).fetchone()
        if wu:
            conn.close(); return True
        for role in member.roles:
            wr = conn.execute("SELECT 1 FROM whitelist_roles WHERE guild_id=? AND role_id=?",
                              (guild_id, role.id)).fetchone()
            if wr:
                conn.close(); return True
        conn.close()
        return False

    def is_blacklisted(self, guild_id: int, user_id: int):
        conn = sec_db()
        row = conn.execute("SELECT * FROM blacklist WHERE guild_id=? AND user_id=?",
                           (guild_id, user_id)).fetchone()
        conn.close()
        return row

    async def log_channel(self) -> Optional[discord.TextChannel]:
        return self.bot.get_channel(LOG_SEGURANCA)

    async def send_log(self, embed: discord.Embed):
        ch = await self.log_channel()
        if ch:
            try:
                await ch.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def get_or_create_quarantine_role(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name="🔒 Quarentena")
        if not role:
            role = await guild.create_role(
                name="🔒 Quarentena",
                color=discord.Color.dark_gray(),
                reason="HSIS — Criação automática do cargo de Quarentena"
            )
            for ch in guild.channels:
                try:
                    await ch.set_permissions(role,
                        view_channel=False, send_messages=False,
                        speak=False, add_reactions=False,
                        reason="HSIS — Setup Quarentena"
                    )
                    await asyncio.sleep(0.25)   # respeita rate limit
                except (discord.Forbidden, discord.HTTPException):
                    pass
        return role

    async def quarantine_member(self, guild: discord.Guild, member: discord.Member,
                                 mod_id: int, reason: str) -> bool:
        try:
            role = await self.get_or_create_quarantine_role(guild)
            saved = [r.id for r in member.roles if not r.is_default()]
            await member.edit(roles=[role], reason=f"HSIS Quarentena: {reason}")
            conn = sec_db()
            conn.execute(
                "INSERT INTO quarantine_log (guild_id, user_id, user_tag, moderator_id, reason, timestamp, saved_roles) VALUES (?,?,?,?,?,?,?)",
                (guild.id, member.id, str(member), mod_id, reason,
                 datetime.datetime.utcnow().isoformat(), json.dumps(saved))
            )
            conn.commit(); conn.close()
            return True
        except Exception:
            return False

    # ── Background Tasks ──────────────────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _cleanup_task(self):
        # Limpa filas antigas e decai heat score lentamente
        cutoff = time.time() - 180
        for uid in list(self.msg_times.keys()):
            while self.msg_times[uid] and self.msg_times[uid][0] < cutoff:
                self.msg_times[uid].popleft()
        for uid in list(self.heat_scores.keys()):
            if self.heat_scores[uid] > 0:
                self.heat_scores[uid] = max(0.0, self.heat_scores[uid] - 1.5)

    @tasks.loop(seconds=1)
    async def _process_queue(self):
        # Processa ações em fila com proteção de rate limit
        try:
            while not self.action_queue.empty():
                coro = await self.action_queue.get()
                try:
                    await coro
                except discord.HTTPException:
                    await asyncio.sleep(2)
        except Exception:
            pass

    @_cleanup_task.before_loop
    @_process_queue.before_loop
    async def _before_tasks(self):
        await self.bot.wait_until_ready()

    # ── LISTENER: Anti-Raid + Alt Detection ──────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id not in GUILDS_WATCHED:
            return

        guild_id = member.guild.id
        now = time.time()
        self.join_times[guild_id].append(now)

        recent_joins = sum(1 for t in self.join_times[guild_id] if now - t <= RAID_WINDOW)

        # ── Blacklist: ban imediato ──────────────────────────────────────
        bl = self.is_blacklisted(guild_id, member.id)
        if bl:
            try:
                await member.ban(reason=f"HSIS — Blacklist: {bl['reason']}", delete_message_days=1)
            except Exception:
                pass
            em = sec_embed("⛔  BLACKLIST — ENTRADA NEGADA", 100, op_code("BL"))
            em.description = "```ansi\n\u001b[1;31m● ACESSO NEGADO — ENTIDADE NA BLACKLIST\u001b[0m\n```"
            em.set_thumbnail(url=member.display_avatar.url)
            em.add_field(name="👤 Usuário", value=f"{member.mention}\n`{member}` — `{member.id}`", inline=True)
            em.add_field(name="📅 Conta", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
            em.add_field(name="📋 Motivo BL", value=f"`{bl['reason']}`", inline=False)
            log_event(guild_id, "BLACKLIST_JOIN", member.id, str(member))
            await self.send_log(em)
            return

        if self.is_whitelisted(guild_id, member):
            return

        # ── Score de risco do membro ─────────────────────────────────────
        extra = 0
        if self.raid_mode.get(guild_id, 0) > 0: extra += 30
        if recent_joins >= RAID_THRESHOLD:       extra += 25
        score = calc_heat(member, extra)
        self.heat_scores[member.id] = score

        # ── Detecção de onda de raid ─────────────────────────────────────
        if recent_joins >= RAID_THRESHOLD and not self.raid_mode.get(guild_id, 0):
            self.raid_mode[guild_id] = 2
            log_event(guild_id, "RAID_DETECTED", details=f"Joins recentes: {recent_joins}")
            em = sec_embed("🚨  RAID DETECTADO — CONTENÇÃO AUTOMÁTICA", 95, op_code("RAID"))
            em.description = (
                "```ansi\n\u001b[1;31m● ALERTA CRÍTICO — WAVE DE RAID\u001b[0m\n```\n"
                f"> **{recent_joins}** entradas nos últimos **{RAID_WINDOW}s**\n"
                f"> Modo de contenção automático ativado."
            )
            em.add_field(name="🛡️ Modo", value="`NÍVEL 2 — ALTO`", inline=True)
            em.add_field(name="⚙️ Ação", value="`Quarentena automática ativa`", inline=True)
            em.add_field(name="📊 Joins detectados", value=f"`{recent_joins}` em `{RAID_WINDOW}s`", inline=True)
            await self.send_log(em)

        # ── Conta nova — alerta ──────────────────────────────────────────
        age = acct_age_days(member)
        if age < MIN_ACCOUNT_DAYS:
            log_event(guild_id, "NEW_ACCOUNT_JOIN", member.id, f"Score:{score:.0f} Age:{age}d")
            em = sec_embed("⚠️  CONTA NOVA DETECTADA", score, op_code("ALT"))
            em.set_thumbnail(url=member.display_avatar.url)
            em.add_field(name="👤 Usuário", value=f"{member.mention}\n`{member}` — `{member.id}`", inline=True)
            em.add_field(name="📅 Idade da Conta", value=f"`{age}` dias", inline=True)
            em.add_field(name="🔥 Heat Score", value=heat_bar(score), inline=False)
            em.add_field(name="⚠️ Nível de Ameaça", value=f"**{threat_label(score)}**", inline=True)
            await self.send_log(em)

        # ── Auto-quarentena durante raid_mode alto ───────────────────────
        if self.raid_mode.get(guild_id, 0) >= 2 and score >= 40:
            ok = await self.quarantine_member(member.guild, member, self.bot.user.id,
                                               f"Raid ativo — Heat:{score:.0f}")
            if ok:
                log_event(guild_id, "AUTO_QUARANTINE", member.id, f"Score:{score:.0f}")
                em = sec_embed("🔒  QUARENTENA AUTOMÁTICA — RAID MODE", score, op_code("QTN"))
                em.set_thumbnail(url=member.display_avatar.url)
                em.add_field(name="👤 Usuário", value=f"{member.mention}\n`{member}`", inline=True)
                em.add_field(name="🤖 Origem", value="`Sistema Automático — Raid Mode`", inline=True)
                em.add_field(name="🔥 Heat Score", value=heat_bar(score), inline=False)
                await self.send_log(em)

    # ── LISTENER: Anti-Spam ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.guild.id not in GUILDS_WATCHED:
            return
        if self.is_whitelisted(message.guild.id, message.author):
            return

        uid    = message.author.id
        now    = time.time()
        text   = message.content or ""

        self.msg_times[uid].append(now)
        self.msg_contents[uid].append((text, now))

        spam_type = None

        # Rate
        if sum(1 for t in self.msg_times[uid] if now - t <= SPAM_WINDOW) >= SPAM_RATE:
            spam_type = "RATE_SPAM"
        # Fast (< 0.4s)
        elif uid in self.last_msg_ts and (now - self.last_msg_ts[uid]) < 0.4:
            spam_type = "FAST_SPAM"
        # Repeat (3x mesma msg em 30s)
        elif text and len([c for c, t in self.msg_contents[uid] if c == text and now - t <= 30]) >= 3:
            spam_type = "REPEAT_SPAM"
        # Caps (>80% maiúsculas em msg > 15 chars)
        elif len(text) > 15 and sum(1 for c in text if c.isupper()) / len(text) > 0.80:
            spam_type = "CAPS_SPAM"
        # Mention (>= 4 menções únicas)
        elif len(set(m.id for m in message.mentions)) >= 4:
            spam_type = "MENTION_SPAM"
        # Emoji (> 12 emojis)
        elif len(re.findall(r'<a?:[^:]+:\d+>|[\U0001F300-\U0001FAFF]', text)) > 12:
            spam_type = "EMOJI_SPAM"
        # Invite
        elif re.search(r'discord\.(gg|com/invite)/\S+', text, re.IGNORECASE):
            spam_type = "INVITE_SPAM"

        self.last_msg_ts[uid] = now

        if not spam_type:
            return

        self.heat_scores[uid] = min(self.heat_scores.get(uid, 0) + 20, 100)
        score = self.heat_scores[uid]
        log_event(message.guild.id, spam_type, uid, f"Canal:{message.channel.id}")

        try:
            await message.delete()
            await message.channel.send(
                f"⚠️ {message.author.mention} — Comportamento suspeito detectado. Mensagem removida.",
                delete_after=6
            )
        except (discord.Forbidden, discord.NotFound):
            pass

        em = sec_embed(f"🚫  {spam_type.replace('_', ' ')}", score, op_code("SPAM"))
        em.set_thumbnail(url=message.author.display_avatar.url)
        em.add_field(name="👤 Usuário", value=f"{message.author.mention}\n`{message.author}`", inline=True)
        em.add_field(name="📍 Canal", value=message.channel.mention, inline=True)
        em.add_field(name="🔥 Heat Score", value=heat_bar(score), inline=True)
        if text:
            em.add_field(name="💬 Conteúdo", value=f"```{text[:250]}```", inline=False)
        await self.send_log(em)

        # Auto-timeout por spam crítico (score >= 80)
        if score >= 80 and isinstance(message.author, discord.Member):
            try:
                until = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
                await message.author.timeout(until, reason=f"HSIS — Auto-timeout por {spam_type}")
                log_event(message.guild.id, "AUTO_TIMEOUT", uid, f"Score:{score:.0f}")
            except Exception:
                pass

    # ── LISTENER: Anti-Nuke ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        if entry.guild.id not in GUILDS_WATCHED:
            return
        if not entry.user or entry.user.bot:
            return
        if self.is_whitelisted(entry.guild.id, entry.user):
            return

        NUKE_MAP = {
            discord.AuditLogAction.ban:            "bans",
            discord.AuditLogAction.kick:           "kicks",
            discord.AuditLogAction.channel_delete: "channel_deletes",
            discord.AuditLogAction.role_delete:    "role_deletes",
            discord.AuditLogAction.member_prune:   "prunes",
        }
        if entry.action not in NUKE_MAP:
            return

        uid        = entry.user.id
        now        = time.time()
        guild      = entry.guild
        action_key = NUKE_MAP[entry.action]

        self.nuke_tracker[uid][action_key].append(now)
        recent = sum(1 for t in self.nuke_tracker[uid][action_key] if now - t <= NUKE_WINDOW)

        if recent < NUKE_THRESHOLD or guild.id in self.nuke_alert:
            return

        self.nuke_alert.add(guild.id)
        log_event(guild.id, "NUKE_DETECTED", uid, f"{action_key}:{recent}")

        em = sec_embed("☢️  NUKE DETECTADO — AÇÃO MASSIVA EM ANDAMENTO", 100, op_code("NUKE"))
        em.description = (
            "```ansi\n\u001b[1;31m● ALERTA MÁXIMO — TENTATIVA DE NUKE\u001b[0m\n```\n"
            f"> Ação massiva detectada em **{NUKE_WINDOW}s** por um único executor."
        )
        em.set_thumbnail(url=entry.user.display_avatar.url)
        em.add_field(name="⚠️ Executor", value=f"{entry.user.mention}\n`{entry.user}` — `{uid}`", inline=True)
        em.add_field(name="🔨 Tipo", value=f"`{action_key.upper()}`", inline=True)
        em.add_field(name="📊 Quantidade", value=f"`{recent}` em `{NUKE_WINDOW}s`", inline=True)

        # Tentativa de remoção de cargos do nuke-r
        member = guild.get_member(uid)
        if member and not member.guild_permissions.administrator:
            try:
                await member.edit(roles=[], reason="HSIS — Nuke detectado: revogação emergencial de cargos")
                em.add_field(name="✅ Ação Automática", value="`Cargos do executor removidos automaticamente`", inline=False)
                log_event(guild.id, "NUKE_ROLES_REVOKED", uid)
            except Exception:
                em.add_field(name="❌ Ação Automática", value="`Falha ao revogar cargos — permissões insuficientes`", inline=False)

        em.add_field(name="🛡️ Próximo passo", value="`/blacklist add` para banir permanentemente`", inline=False)
        await self.send_log(em)

        async def reset_alert():
            await asyncio.sleep(60)
            self.nuke_alert.discard(guild.id)
        asyncio.create_task(reset_alert())

    # ────────────────────────────────────────────────────────────────────────────
    #  SLASH COMMANDS
    # ────────────────────────────────────────────────────────────────────────────

    # /threatscan
    @app_commands.command(name="threatscan", description="Analise completa de risco de um usuario")
    @app_commands.describe(usuario="Usuario para analisar")
    @app_commands.default_permissions(manage_messages=True)
    async def threatscan(self, interaction: discord.Interaction, usuario: discord.Member):
        await interaction.response.defer()
        score = self.heat_scores.get(usuario.id, calc_heat(usuario))
        self.heat_scores[usuario.id] = score

        conn = sec_db()
        warns  = conn.execute("SELECT COUNT(*) as c FROM warnings WHERE guild_id=? AND user_id=?",
                               (interaction.guild_id, usuario.id)).fetchone()['c']
        bl     = conn.execute("SELECT * FROM blacklist WHERE guild_id=? AND user_id=?",
                               (interaction.guild_id, usuario.id)).fetchone()
        qtn    = conn.execute("SELECT COUNT(*) as c FROM quarantine_log WHERE guild_id=? AND user_id=? AND active=1",
                               (interaction.guild_id, usuario.id)).fetchone()['c']
        conn.close()

        flags = []
        age   = acct_age_days(usuario)
        if age < 1:               flags.append("🚨 Conta criada hoje")
        elif age < 7:             flags.append("⚠️ Conta nova (< 7 dias)")
        if not usuario.avatar:    flags.append("⚠️ Sem avatar personalizado")
        if warns > 0:             flags.append(f"⚠️ {warns} aviso(s) registrado(s)")
        if bl:                    flags.append("🚨 ESTÁ NA BLACKLIST")
        if qtn:                   flags.append("🔒 Em Quarentena ativa")
        if self.raid_mode.get(interaction.guild_id, 0):
            flags.append("🚨 Servidor em Raid Mode")

        op = op_code("SCAN")
        em = sec_embed(f"🔍  THREATSCAN — {usuario.display_name}", score, op)
        em.description = (
            "```ansi\n\u001b[1;33m● VARREDURA DE AMEAÇA EM ANDAMENTO\u001b[0m\n```\n"
            "> Análise completa do perfil de risco do alvo."
        )
        em.set_thumbnail(url=usuario.display_avatar.url)

        em.add_field(name="👤 Alvo", value=f"{usuario.mention}\n`{usuario}` — `{usuario.id}`", inline=True)
        em.add_field(name="📅 Conta", value=f"`{age}` dias", inline=True)
        em.add_field(name="🖼️ Avatar", value="`✅ Personalizado`" if usuario.avatar else "`⚠️ Padrão`", inline=True)
        em.add_field(name="🔥 Heat Score", value=heat_bar(score), inline=False)
        em.add_field(name="⚠️ Nível de Ameaça", value=f"**{threat_label(score)}**", inline=True)
        em.add_field(name="📋 Warnings", value=f"`{warns}`", inline=True)
        em.add_field(name="🔒 Quarentena", value=f"`{'Ativa' if qtn else 'Não'}`", inline=True)
        em.add_field(name="⛔ Blacklist", value=f"`{'Sim — ' + bl['reason'] if bl else 'Não'}`", inline=False)
        em.add_field(name="🚩 Fatores de Risco",
                      value="\n".join(flags) if flags else "✅ Nenhum flag detectado", inline=False)

        log_event(interaction.guild_id, "THREATSCAN", usuario.id, f"by:{interaction.user.id}")
        await interaction.followup.send(embed=em)
        await self.send_log(em)

    # /intelligence
    @app_commands.command(name="intelligence", description="Relatorio detalhado de inteligencia de um usuario")
    @app_commands.describe(usuario="Usuario para gerar relatorio")
    @app_commands.default_permissions(manage_guild=True)
    async def intelligence(self, interaction: discord.Interaction, usuario: discord.Member):
        await interaction.response.defer()
        score = self.heat_scores.get(usuario.id, calc_heat(usuario))

        conn = sec_db()
        warns  = conn.execute("SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 5",
                               (interaction.guild_id, usuario.id)).fetchall()
        bl     = conn.execute("SELECT * FROM blacklist WHERE guild_id=? AND user_id=?",
                               (interaction.guild_id, usuario.id)).fetchone()
        qtns   = conn.execute("SELECT * FROM quarantine_log WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 3",
                               (interaction.guild_id, usuario.id)).fetchall()
        events = conn.execute("SELECT * FROM security_events WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 5",
                               (interaction.guild_id, usuario.id)).fetchall()
        conn.close()

        op = op_code("INTEL")
        em = sec_embed(f"📡  INTELLIGENCE — {usuario.display_name}", score, op)
        em.description = (
            f"```ansi\n\u001b[1;34m● RELATÓRIO DE INTELIGÊNCIA — ACESSO RESTRITO\u001b[0m\n```\n"
            f"> **Operação:** `{op}`\n> **Nível:** `CLASSIFICADO`"
        )
        em.set_thumbnail(url=usuario.display_avatar.url)

        badges = [str(f.name) for f in usuario.public_flags.all()] if usuario.public_flags else []

        em.add_field(name="━━━ IDENTIDADE ━━━", value="\u200b", inline=False)
        em.add_field(name="👤 Tag", value=f"`{usuario}`", inline=True)
        em.add_field(name="🆔 ID", value=f"`{usuario.id}`", inline=True)
        em.add_field(name="🤖 Bot", value="`Sim`" if usuario.bot else "`Não`", inline=True)
        em.add_field(name="📅 Conta Criada", value=f"<t:{int(usuario.created_at.timestamp())}:f>", inline=True)
        em.add_field(name="⏱️ Idade", value=f"`{acct_age_days(usuario)}` dias", inline=True)
        em.add_field(name="🏅 Badges", value=", ".join(f"`{b}`" for b in badges) if badges else "`Nenhuma`", inline=True)

        em.add_field(name="━━━ PRESENÇA NO SERVIDOR ━━━", value="\u200b", inline=False)
        em.add_field(name="📥 Entrou", value=f"<t:{int(usuario.joined_at.timestamp())}:f>" if usuario.joined_at else "`?`", inline=True)
        em.add_field(name="🎭 Cargos", value=f"`{len(usuario.roles) - 1}`", inline=True)
        em.add_field(name="🔊 Voz", value="`Em chamada`" if usuario.voice else "`Offline`", inline=True)

        em.add_field(name="━━━ SEGURANÇA ━━━", value="\u200b", inline=False)
        em.add_field(name="🔥 Heat Score", value=heat_bar(score), inline=False)
        em.add_field(name="⚠️ Ameaça", value=f"**{threat_label(score)}**", inline=True)
        em.add_field(name="⛔ Blacklist", value=f"`{'Sim' if bl else 'Não'}`", inline=True)
        em.add_field(name="🔒 Quarentenas", value=f"`{len(qtns)}` registros", inline=True)

        if warns:
            em.add_field(name="━━━ HISTÓRICO DE WARNS ━━━", value="\u200b", inline=False)
            for w in warns:
                ts = int(datetime.datetime.fromisoformat(w['timestamp']).timestamp())
                em.add_field(name=f"⚠️ Warn #{w['id']}", value=f"`{w['reason']}`\n<t:{ts}:R>", inline=True)

        if events:
            em.add_field(name="━━━ EVENTOS RECENTES ━━━", value="\u200b", inline=False)
            for ev in events:
                ts = int(datetime.datetime.fromisoformat(ev['timestamp']).timestamp())
                em.add_field(name=f"📌 {ev['event_type']}", value=f"`{ev['details'] or '-'}`\n<t:{ts}:R>", inline=True)

        log_event(interaction.guild_id, "INTELLIGENCE", usuario.id, f"by:{interaction.user.id}")
        await interaction.followup.send(embed=em)
        await self.send_log(em)

    # /quarantine
    @app_commands.command(name="quarantine", description="Coloca um usuario em quarentena isolada")
    @app_commands.describe(usuario="Alvo", motivo="Motivo da quarentena")
    @app_commands.default_permissions(manage_roles=True)
    async def quarantine_cmd(self, interaction: discord.Interaction,
                              usuario: discord.Member, motivo: str = "Sem motivo"):
        await interaction.response.defer()
        ok = await self.quarantine_member(interaction.guild, usuario, interaction.user.id, motivo)
        if not ok:
            await interaction.followup.send("❌ Falha ao quarentenar. Verifique as permissões do bot.")
            return
        score = self.heat_scores.get(usuario.id, 50)
        em = sec_embed("🔒  QUARENTENA ATIVADA", score, op_code("QTN"))
        em.set_thumbnail(url=usuario.display_avatar.url)
        em.add_field(name="👤 Alvo", value=f"{usuario.mention}\n`{usuario}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=interaction.user.mention, inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        log_event(interaction.guild_id, "QUARANTINE", usuario.id, motivo)
        await interaction.followup.send(embed=em)
        await self.send_log(em)

    # /unquarantine
    @app_commands.command(name="unquarantine", description="Libera usuario da quarentena")
    @app_commands.describe(usuario="Usuario para liberar")
    @app_commands.default_permissions(manage_roles=True)
    async def unquarantine_cmd(self, interaction: discord.Interaction, usuario: discord.Member):
        await interaction.response.defer()
        conn = sec_db()
        row = conn.execute(
            "SELECT * FROM quarantine_log WHERE guild_id=? AND user_id=? AND active=1 ORDER BY id DESC LIMIT 1",
            (interaction.guild_id, usuario.id)
        ).fetchone()
        if not row:
            conn.close()
            await interaction.followup.send("❌ Este usuário não está em quarentena ativa.")
            return

        saved_ids   = json.loads(row['saved_roles'])
        roles       = [interaction.guild.get_role(rid) for rid in saved_ids if interaction.guild.get_role(rid)]
        try:
            await usuario.edit(roles=roles, reason=f"HSIS — Quarentena encerrada por {interaction.user}")
        except Exception:
            pass
        conn.execute("UPDATE quarantine_log SET active=0 WHERE id=?", (row['id'],))
        conn.commit(); conn.close()

        em = sec_embed("🔓  QUARENTENA ENCERRADA", 10, op_code("QTN"))
        em.add_field(name="👤 Liberado", value=f"{usuario.mention}\n`{usuario}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=interaction.user.mention, inline=True)
        em.add_field(name="✅ Cargos Restaurados", value=f"`{len(roles)}` cargos", inline=True)
        log_event(interaction.guild_id, "UNQUARANTINE", usuario.id, str(interaction.user))
        await interaction.followup.send(embed=em)
        await self.send_log(em)

    # /raidmode
    @app_commands.command(name="raidmode", description="Ativa ou desativa o modo raid")
    @app_commands.describe(acao="on ou off", nivel="Nivel 1=baixo 2=alto 3=lockdown (padrao: 2)")
    @app_commands.default_permissions(manage_guild=True)
    async def raidmode_cmd(self, interaction: discord.Interaction,
                            acao: Literal["on", "off"], nivel: Optional[int] = 2):
        guild_id = interaction.guild_id
        if acao == "on":
            nivel = max(1, min(3, nivel or 2))
            self.raid_mode[guild_id] = nivel
            labels = {1: "🟡 NÍVEL 1 — BAIXO", 2: "🟠 NÍVEL 2 — ALTO", 3: "🔴 NÍVEL 3 — LOCKDOWN"}
            colors = {1: 0xFEE75C, 2: 0xFF6B35, 3: 0xED4245}
            em = discord.Embed(title=f"🚨  RAID MODE — {labels[nivel]}",
                               color=colors[nivel], timestamp=datetime.datetime.utcnow())
            em.description = (
                "```ansi\n\u001b[1;31m● MODO RAID ATIVADO\u001b[0m\n```\n"
                "> Todas as entradas suspeitas serão bloqueadas automaticamente."
            )
            em.add_field(name="⚙️ Ações Automáticas",
                          value="`✅ Quarentena automática`\n`✅ Heat score ativo`\n`✅ Alerta de alt`", inline=True)
            em.add_field(name="🛡️ Ativado por", value=interaction.user.mention, inline=True)
            em.set_footer(text=f"🔐 {op_code('RAID')}  •  HSIS v2.0")
            log_event(guild_id, "RAID_MODE_ON", interaction.user.id, f"nivel:{nivel}")
        else:
            self.raid_mode[guild_id] = 0
            em = discord.Embed(title="✅  RAID MODE — DESATIVADO", color=0x57F287,
                               timestamp=datetime.datetime.utcnow())
            em.description = "> Modo raid desativado. Operação normal retomada."
            em.add_field(name="🛡️ Desativado por", value=interaction.user.mention, inline=True)
            em.set_footer(text=f"🔐 {op_code('RAID')}  •  HSIS v2.0")
            log_event(guild_id, "RAID_MODE_OFF", interaction.user.id)

        await interaction.response.send_message(embed=em)
        await self.send_log(em)

    # /blacklist (grupo)
    bl_group = app_commands.Group(
        name="blacklist",
        description="Gerencia a blacklist de seguranca",
        default_permissions=discord.Permissions(manage_guild=True)
    )

    @bl_group.command(name="add", description="Adiciona usuario a blacklist")
    @app_commands.describe(usuario="Usuario a bloquear", motivo="Motivo")
    async def bl_add(self, interaction: discord.Interaction,
                     usuario: discord.User, motivo: str = "Sem motivo"):
        conn = sec_db()
        conn.execute(
            "INSERT OR REPLACE INTO blacklist (guild_id,user_id,user_tag,added_by,reason,timestamp) VALUES (?,?,?,?,?,?)",
            (interaction.guild_id, usuario.id, str(usuario), interaction.user.id,
             motivo, datetime.datetime.utcnow().isoformat())
        )
        conn.commit(); conn.close()
        em = sec_embed("⛔  BLACKLIST — USUÁRIO ADICIONADO", 100, op_code("BL"))
        em.add_field(name="👤 Usuário", value=f"`{usuario}` — `{usuario.id}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=interaction.user.mention, inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        log_event(interaction.guild_id, "BLACKLIST_ADD", usuario.id, motivo)
        await interaction.response.send_message(embed=em)
        await self.send_log(em)

    @bl_group.command(name="remove", description="Remove usuario da blacklist")
    @app_commands.describe(usuario="Usuario a remover")
    async def bl_remove(self, interaction: discord.Interaction, usuario: discord.User):
        conn = sec_db()
        conn.execute("DELETE FROM blacklist WHERE guild_id=? AND user_id=?", (interaction.guild_id, usuario.id))
        conn.commit(); conn.close()
        em = sec_embed("✅  BLACKLIST — USUÁRIO REMOVIDO", 0, op_code("BL"))
        em.add_field(name="👤 Usuário", value=f"`{usuario}` — `{usuario.id}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=interaction.user.mention, inline=True)
        log_event(interaction.guild_id, "BLACKLIST_REMOVE", usuario.id)
        await interaction.response.send_message(embed=em)
        await self.send_log(em)

    @bl_group.command(name="list", description="Lista os usuarios na blacklist")
    async def bl_list(self, interaction: discord.Interaction):
        conn = sec_db()
        rows = conn.execute("SELECT * FROM blacklist WHERE guild_id=? ORDER BY timestamp DESC LIMIT 20",
                             (interaction.guild_id,)).fetchall()
        conn.close()
        em = sec_embed(f"⛔  BLACKLIST — {len(rows)} ENTRADAS", 80, op_code("BL"))
        if rows:
            for r in rows:
                em.add_field(name=f"🚫 {r['user_tag'] or r['user_id']}",
                              value=f"ID: `{r['user_id']}`\nMotivo: `{r['reason']}`", inline=True)
        else:
            em.description = "> Blacklist vazia."
        await interaction.response.send_message(embed=em)

    # /security
    @app_commands.command(name="security", description="Painel completo de status de seguranca")
    @app_commands.default_permissions(manage_guild=True)
    async def security_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gid = interaction.guild_id
        conn = sec_db()
        total_warns  = conn.execute("SELECT COUNT(*) as c FROM warnings WHERE guild_id=?", (gid,)).fetchone()['c']
        total_bl     = conn.execute("SELECT COUNT(*) as c FROM blacklist WHERE guild_id=?", (gid,)).fetchone()['c']
        total_qtn    = conn.execute("SELECT COUNT(*) as c FROM quarantine_log WHERE guild_id=? AND active=1", (gid,)).fetchone()['c']
        today        = datetime.datetime.utcnow().date().isoformat()
        events_today = conn.execute("SELECT COUNT(*) as c FROM security_events WHERE guild_id=? AND date(timestamp)=?",
                                     (gid, today)).fetchone()['c']
        recent       = conn.execute("SELECT * FROM security_events WHERE guild_id=? ORDER BY id DESC LIMIT 6",
                                     (gid,)).fetchall()
        conn.close()

        raid_lvl    = self.raid_mode.get(gid, 0)
        raid_labels = {0: "🟢 Desativado", 1: "🟡 Nível 1", 2: "🟠 Nível 2", 3: "🔴 Lockdown"}
        score       = {0: 0, 1: 20, 2: 50, 3: 80}[raid_lvl]

        em = sec_embed(f"🛡️  SECURITY DASHBOARD", score, op_code("DASH"))
        em.description = (
            "```ansi\n\u001b[1;34m● PAINEL DE SEGURANÇA OPERACIONAL\u001b[0m\n```\n"
            f"> **{interaction.guild.name}** — **{interaction.guild.member_count}** membros"
        )
        if interaction.guild.icon:
            em.set_thumbnail(url=interaction.guild.icon.url)

        em.add_field(name="━━━ STATUS ━━━", value="\u200b", inline=False)
        em.add_field(name="🚨 Raid Mode", value=f"`{raid_labels[raid_lvl]}`", inline=True)
        em.add_field(name="🔒 Em Quarentena", value=f"`{total_qtn}` ativos", inline=True)
        em.add_field(name="⛔ Blacklist", value=f"`{total_bl}` usuários", inline=True)

        em.add_field(name="━━━ ESTATÍSTICAS ━━━", value="\u200b", inline=False)
        em.add_field(name="⚠️ Total Warns", value=f"`{total_warns}`", inline=True)
        em.add_field(name="📊 Eventos Hoje", value=f"`{events_today}`", inline=True)
        em.add_field(name="🔥 Perfis Monitorados", value=f"`{len(self.heat_scores)}`", inline=True)

        if recent:
            em.add_field(name="━━━ EVENTOS RECENTES ━━━", value="\u200b", inline=False)
            for ev in recent:
                ts = int(datetime.datetime.fromisoformat(ev['timestamp']).timestamp())
                em.add_field(name=f"📌 {ev['event_type']}",
                              value=f"`{ev['details'] or '-'}`\n<t:{ts}:R>", inline=True)

        await interaction.followup.send(embed=em)

    # /opsec
    @app_commands.command(name="opsec", description="Relatorio operacional de seguranca das ultimas 24h")
    @app_commands.default_permissions(manage_guild=True)
    async def opsec_report(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gid   = interaction.guild_id
        since = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).isoformat()
        conn  = sec_db()
        events = conn.execute(
            "SELECT event_type, COUNT(*) as c FROM security_events WHERE guild_id=? AND timestamp > ? GROUP BY event_type ORDER BY c DESC",
            (gid, since)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM security_events WHERE guild_id=? AND timestamp > ?",
                              (gid, since)).fetchone()['c']
        conn.close()

        op = op_code("OPSEC")
        em = sec_embed("📊  OPSEC REPORT — ÚLTIMAS 24H", min(total * 2, 80), op)
        em.description = (
            f"```ansi\n\u001b[1;34m● RELATÓRIO OPERACIONAL DE SEGURANÇA\u001b[0m\n```\n"
            f"> **Operação:** `{op}`\n> **Total de eventos:** `{total}`"
        )

        if events:
            em.add_field(name="━━━ EVENTOS POR TIPO ━━━", value="\u200b", inline=False)
            for ev in events:
                em.add_field(name=f"📌 {ev['event_type']}", value=f"`{ev['c']}` ocorrência(s)", inline=True)
        else:
            em.add_field(name="✅ Situação", value="`Nenhum evento nas últimas 24 horas`", inline=False)

        raid_ativo = self.raid_mode.get(gid, 0)
        em.add_field(name="━━━ STATUS FINAL ━━━", value="\u200b", inline=False)
        em.add_field(name="🚨 Raid Mode", value=f"`{'ATIVO' if raid_ativo else 'INATIVO'}`", inline=True)
        em.add_field(name="🔥 Perfis de Risco", value=f"`{len(self.heat_scores)}`", inline=True)
        em.add_field(name="🛡️ Solicitado por", value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=em)
        await self.send_log(em)

    # ────────────────────────────────────────────────────────────────────────────
    #  PREFIX COMMANDS — Moderação
    # ────────────────────────────────────────────────────────────────────────────

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Sem motivo"):
        conn = sec_db()
        conn.execute(
            "INSERT INTO warnings (guild_id,user_id,user_tag,moderator_id,reason,timestamp) VALUES (?,?,?,?,?,?)",
            (ctx.guild.id, membro.id, str(membro), ctx.author.id, motivo,
             datetime.datetime.utcnow().isoformat())
        )
        total = conn.execute("SELECT COUNT(*) as c FROM warnings WHERE guild_id=? AND user_id=?",
                              (ctx.guild.id, membro.id)).fetchone()['c']
        conn.commit(); conn.close()

        self.heat_scores[membro.id] = min(self.heat_scores.get(membro.id, 0) + 15, 100)
        score = self.heat_scores[membro.id]

        em = sec_embed(f"⚠️  WARN #{total} — {membro.display_name}", score, op_code("WARN"))
        em.set_thumbnail(url=membro.display_avatar.url)
        em.add_field(name="👤 Usuário", value=f"{membro.mention}\n`{membro}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=ctx.author.mention, inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        em.add_field(name="📊 Total de Warns", value=f"`{total}`", inline=True)
        em.add_field(name="🔥 Heat Score", value=heat_bar(score), inline=True)

        log_event(ctx.guild.id, "WARN", membro.id, motivo)
        await ctx.send(embed=em)
        await self.send_log(em)

        if total >= WARN_BAN_AT:
            try:
                await membro.ban(reason=f"HSIS — Limite de warns ({total}) atingido")
                log_event(ctx.guild.id, "AUTO_BAN_WARNS", membro.id, f"warns:{total}")
            except Exception: pass
        elif total >= WARN_KICK_AT:
            try:
                await membro.kick(reason=f"HSIS — {total} warns acumulados")
                log_event(ctx.guild.id, "AUTO_KICK_WARNS", membro.id, f"warns:{total}")
            except Exception: pass

    @commands.command(name="warns")
    @commands.has_permissions(manage_messages=True)
    async def warns_list(self, ctx: commands.Context, membro: discord.Member):
        conn = sec_db()
        rows = conn.execute("SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10",
                             (ctx.guild.id, membro.id)).fetchall()
        conn.close()
        score = self.heat_scores.get(membro.id, calc_heat(membro))
        em = sec_embed(f"📋  WARNS — {membro.display_name}", score, op_code("WARN"))
        em.set_thumbnail(url=membro.display_avatar.url)
        if rows:
            for w in rows:
                ts = int(datetime.datetime.fromisoformat(w['timestamp']).timestamp())
                em.add_field(name=f"⚠️ Warn #{w['id']}",
                              value=f"`{w['reason']}`\n<t:{ts}:R>", inline=True)
        else:
            em.description = f"> **{membro.display_name}** não tem warns."
        await ctx.send(embed=em)

    @commands.command(name="clearwarns")
    @commands.has_permissions(manage_guild=True)
    async def clearwarns(self, ctx: commands.Context, membro: discord.Member):
        conn = sec_db()
        conn.execute("DELETE FROM warnings WHERE guild_id=? AND user_id=?", (ctx.guild.id, membro.id))
        conn.commit(); conn.close()
        self.heat_scores[membro.id] = max(0, self.heat_scores.get(membro.id, 0) - 30)
        await ctx.send(f"✅ Warns de **{membro}** foram limpos.")
        log_event(ctx.guild.id, "CLEAR_WARNS", membro.id, str(ctx.author))

    @commands.command(name="mute")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, membro: discord.Member,
                   duracao: int = 10, *, motivo: str = "Sem motivo"):
        until = datetime.datetime.utcnow() + datetime.timedelta(minutes=duracao)
        try:
            await membro.timeout(until, reason=f"HSIS Mute: {motivo}")
        except Exception as e:
            await ctx.send(f"❌ Erro: {e}"); return
        em = sec_embed(f"🔇  MUTE — {membro.display_name}", 40, op_code("MUTE"))
        em.add_field(name="👤 Usuário", value=f"{membro.mention}\n`{membro}`", inline=True)
        em.add_field(name="⏱️ Duração", value=f"`{duracao}` minutos", inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        em.add_field(name="🛡️ Moderador", value=ctx.author.mention, inline=True)
        log_event(ctx.guild.id, "MUTE", membro.id, motivo)
        await ctx.send(embed=em)
        await self.send_log(em)

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Sem motivo"):
        try:
            await membro.kick(reason=f"HSIS Kick: {motivo}")
        except Exception as e:
            await ctx.send(f"❌ Erro: {e}"); return
        em = sec_embed(f"👢  KICK — {membro.display_name}", 50, op_code("KICK"))
        em.add_field(name="👤 Usuário", value=f"`{membro}` — `{membro.id}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=ctx.author.mention, inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        log_event(ctx.guild.id, "KICK", membro.id, motivo)
        await ctx.send(embed=em)
        await self.send_log(em)

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, membro: discord.User, *, motivo: str = "Sem motivo"):
        try:
            await ctx.guild.ban(membro, reason=f"HSIS Ban: {motivo}", delete_message_days=1)
        except Exception as e:
            await ctx.send(f"❌ Erro: {e}"); return
        em = sec_embed(f"🚫  BAN — {membro}", 80, op_code("BAN"))
        em.add_field(name="👤 Usuário", value=f"`{membro}` — `{membro.id}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=ctx.author.mention, inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        log_event(ctx.guild.id, "BAN", membro.id, motivo)
        await ctx.send(embed=em)
        await self.send_log(em)

    @commands.command(name="softban")
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx: commands.Context, membro: discord.Member, *, motivo: str = "Sem motivo"):
        try:
            await ctx.guild.ban(membro, reason=f"HSIS Softban: {motivo}", delete_message_days=7)
            await asyncio.sleep(1)
            await ctx.guild.unban(membro, reason="HSIS — Desbaneamento automático por softban")
        except Exception as e:
            await ctx.send(f"❌ Erro: {e}"); return
        em = sec_embed(f"🔨  SOFTBAN — {membro.display_name}", 60, op_code("SBAN"))
        em.add_field(name="👤 Usuário", value=f"`{membro}` — `{membro.id}`", inline=True)
        em.add_field(name="🛡️ Moderador", value=ctx.author.mention, inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        em.add_field(name="ℹ️ Info", value="`Mensagens apagadas. Usuário pode re-entrar.`", inline=False)
        log_event(ctx.guild.id, "SOFTBAN", membro.id, motivo)
        await ctx.send(embed=em)
        await self.send_log(em)

    @commands.command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    async def timeout_cmd(self, ctx: commands.Context, membro: discord.Member,
                          minutos: int = 60, *, motivo: str = "Sem motivo"):
        until = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutos)
        try:
            await membro.timeout(until, reason=f"HSIS Timeout: {motivo}")
        except Exception as e:
            await ctx.send(f"❌ Erro: {e}"); return
        em = sec_embed(f"⏱️  TIMEOUT — {membro.display_name}", 45, op_code("TIME"))
        em.add_field(name="👤 Usuário", value=f"{membro.mention}\n`{membro}`", inline=True)
        em.add_field(name="⏱️ Duração", value=f"`{minutos}` minutos", inline=True)
        em.add_field(name="📋 Motivo", value=f"`{motivo}`", inline=False)
        em.add_field(name="🛡️ Moderador", value=ctx.author.mention, inline=True)
        log_event(ctx.guild.id, "TIMEOUT", membro.id, motivo)
        await ctx.send(embed=em)
        await self.send_log(em)

    # Errors silenciosos
    @warn.error
    @mute.error
    @kick.error
    @ban.error
    @softban.error
    @timeout_cmd.error
    async def mod_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Você não tem permissão para isso.", delete_after=5)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Membro não encontrado.", delete_after=5)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Argumentos inválidos.", delete_after=5)
