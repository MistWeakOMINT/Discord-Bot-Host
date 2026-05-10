# ================================================================================
#  HSIS — OSINT Engine v2.0
#  Investigação de inteligência multi-fonte para Discord
# ================================================================================

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import aiohttp
import datetime
import hashlib
import random
import string
import re
from typing import Optional

LOG_SEGURANCA = 1499872179234541791

# Plataformas para verificação de presença (HTTP GET)
PLATFORMS = [
    ("GitHub",    "https://github.com/{}"),
    ("Reddit",    "https://www.reddit.com/user/{}"),
    ("Instagram", "https://www.instagram.com/{}"),
    ("Twitter",   "https://twitter.com/{}"),
    ("TikTok",    "https://www.tiktok.com/@{}"),
    ("Twitch",    "https://www.twitch.tv/{}"),
    ("Pinterest", "https://www.pinterest.com/{}"),
    ("Steam",     "https://steamcommunity.com/id/{}"),
    ("Roblox",    "https://www.roblox.com/user.aspx?username={}"),
    ("Spotify",   "https://open.spotify.com/user/{}"),
]

def op_code(prefix: str = "INTEL") -> str:
    return f"OP-{prefix}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

def risk_color(score: int) -> int:
    if score < 20: return 0x57F287
    if score < 45: return 0xFEE75C
    if score < 70: return 0xFF6B35
    return                 0xED4245

def risk_label(score: int) -> str:
    if score < 20: return "🟢 BAIXO"
    if score < 45: return "🟡 MÉDIO"
    if score < 70: return "🟠 ALTO"
    return                 "🔴 CRÍTICO"

def acct_age_days(user: discord.User) -> int:
    return (datetime.datetime.utcnow() - user.created_at.replace(tzinfo=None)).days


class OsintCog(commands.Cog, name="OsintCog"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=aiohttp.ClientTimeout(total=8)
            )
        return self._session

    def cog_unload(self):
        if self._session and not self._session.closed:
            asyncio.create_task(self._session.close())

    # ── Análise de perfil Discord ─────────────────────────────────────────────

    async def _analyze_discord(self, user: discord.User, guild: discord.Guild) -> dict:
        age   = acct_age_days(user)
        badges = [f.name for f in user.public_flags.all()] if user.public_flags else []
        member = guild.get_member(user.id)

        score = 0
        if age < 1:    score += 65
        elif age < 7:  score += 45
        elif age < 30: score += 25
        if not user.avatar:                                     score += 20
        if re.search(r'\d{6,}', user.name):                    score += 10
        if re.fullmatch(r'[a-z]+\d{4,}', user.name.lower()):   score += 10
        if user.bot:                                            score -= 20
        if "staff" in badges or "verified_bot" in badges:      score -= 40
        score = max(0, min(100, score))

        return {
            "id":          user.id,
            "tag":         str(user),
            "bot":         user.bot,
            "age_days":    age,
            "created_at":  user.created_at,
            "has_avatar":  user.avatar is not None,
            "avatar_url":  str(user.display_avatar.url),
            "badges":      badges,
            "is_member":   member is not None,
            "joined_at":   member.joined_at if member else None,
            "roles":       len(member.roles) - 1 if member else 0,
            "nick":        member.nick if member else None,
            "in_voice":    member.voice is not None if member else False,
            "risk_score":  score,
        }

    # ── GitHub lookup (API pública, sem chave) ────────────────────────────────

    async def _github(self, username: str) -> dict:
        session = await self._get_session()
        try:
            async with session.get(
                f"https://api.github.com/users/{username}",
                headers={"Accept": "application/vnd.github+json"},
            ) as r:
                if r.status == 200:
                    d = await r.json()
                    return {
                        "found":     True,
                        "name":      d.get("name"),
                        "bio":       d.get("bio"),
                        "location":  d.get("location"),
                        "company":   d.get("company"),
                        "repos":     d.get("public_repos", 0),
                        "followers": d.get("followers", 0),
                        "following": d.get("following", 0),
                        "created":   d.get("created_at", "")[:10],
                        "blog":      d.get("blog"),
                        "twitter":   d.get("twitter_username"),
                        "url":       f"https://github.com/{username}",
                        "avatar":    d.get("avatar_url"),
                    }
                return {"found": False, "status": r.status}
        except Exception as e:
            return {"found": False, "error": str(e)}

    # ── Reddit lookup (API pública) ───────────────────────────────────────────

    async def _reddit(self, username: str) -> dict:
        session = await self._get_session()
        try:
            async with session.get(
                f"https://www.reddit.com/user/{username}/about.json",
                headers={"User-Agent": "HSIS-OSINT/2.0"},
            ) as r:
                if r.status == 200:
                    d = (await r.json()).get("data", {})
                    created = datetime.datetime.utcfromtimestamp(d.get("created_utc", 0))
                    return {
                        "found":    True,
                        "name":     d.get("name"),
                        "post_k":   d.get("link_karma", 0),
                        "comm_k":   d.get("comment_karma", 0),
                        "created":  created,
                        "verified": d.get("verified", False),
                        "is_mod":   d.get("is_mod", False),
                        "url":      f"https://reddit.com/u/{username}",
                    }
                return {"found": False, "status": r.status}
        except Exception as e:
            return {"found": False, "error": str(e)}

    # ── HaveIBeenPwned — email (requer chave paga v3) ─────────────────────────

    async def _hibp_email(self, email: str, api_key: str = None) -> dict:
        if not api_key:
            return {
                "available": False,
                "note": "HaveIBeenPwned v3 requer chave de API paga. Defina HIBP_API_KEY no .env."
            }
        session = await self._get_session()
        try:
            async with session.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                headers={"hibp-api-key": api_key, "User-Agent": "HSIS-OSINT/2.0"},
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return {
                        "available": True,
                        "breached":  True,
                        "count":     len(data),
                        "sites":     [b["Name"] for b in data[:6]],
                    }
                elif r.status == 404:
                    return {"available": True, "breached": False}
                else:
                    return {"available": False, "note": f"HTTP {r.status}"}
        except Exception as e:
            return {"available": False, "note": str(e)}

    # ── Verificação de presença em plataformas ────────────────────────────────

    async def _check_presence(self, username: str) -> list:
        session = await self._get_session()
        results = []

        async def _check(name, url_tmpl):
            url = url_tmpl.format(username)
            try:
                async with session.get(url, allow_redirects=True) as r:
                    found = r.status == 200
                    results.append({"platform": name, "url": url, "found": found})
            except Exception:
                results.append({"platform": name, "url": url, "found": False})

        await asyncio.gather(*[_check(n, u) for n, u in PLATFORMS])
        return results

    # ── Embed builder ─────────────────────────────────────────────────────────

    def _make_embed(self, op: str, alvo: str, score: int) -> discord.Embed:
        em = discord.Embed(
            color=risk_color(score),
            timestamp=datetime.datetime.utcnow()
        )
        em.title = "🔍  OSINT — INTELLIGENCE REPORT"
        em.description = (
            f"```ansi\n\u001b[1;35m● INVESTIGAÇÃO INTEL INICIADA\u001b[0m\n```\n"
            f"> **Operação:** `{op}`\n"
            f"> **Alvo:** `{alvo}`\n"
            f"> **Classificação:** `RESTRITO`"
        )
        em.set_footer(text=f"🔐 {op}  •  HSIS OSINT Engine v2.0")
        return em

    # ────────────────────────────────────────────────────────────────────────────
    #  COMANDOS
    # ────────────────────────────────────────────────────────────────────────────

    async def _run_investigate(self, interaction: discord.Interaction,
                                alvo: str, github: Optional[str]):
        await interaction.response.defer()
        op  = op_code("INTEL")
        now = datetime.datetime.utcnow()

        import os
        hibp_key = os.environ.get("HIBP_API_KEY")

        # ── Identifica o tipo de alvo ─────────────────────────────────────
        is_email = bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', alvo)) and not alvo.startswith("<@")
        discord_user: Optional[discord.User] = None

        if not is_email:
            clean = re.sub(r'[<@!>]', '', alvo)
            if clean.isdigit():
                try:
                    discord_user = await self.bot.fetch_user(int(clean))
                except Exception:
                    pass

        # username para busca em plataformas
        uname = github or (discord_user.name if discord_user else (None if is_email else alvo))

        # ── Coleta em paralelo ────────────────────────────────────────────
        disc_coro     = self._analyze_discord(discord_user, interaction.guild) if discord_user else asyncio.sleep(0)
        gh_coro       = self._github(uname)          if uname else asyncio.sleep(0)
        rd_coro       = self._reddit(uname)           if uname else asyncio.sleep(0)
        pres_coro     = self._check_presence(uname)   if uname else asyncio.sleep(0)
        hibp_coro     = self._hibp_email(alvo, hibp_key) if is_email else asyncio.sleep(0)

        raw = await asyncio.gather(disc_coro, gh_coro, rd_coro, pres_coro, hibp_coro,
                                   return_exceptions=True)

        disc_info  = raw[0] if discord_user   and not isinstance(raw[0], Exception) and isinstance(raw[0], dict) else None
        gh_info    = raw[1] if uname          and not isinstance(raw[1], Exception) and isinstance(raw[1], dict) else None
        rd_info    = raw[2] if uname          and not isinstance(raw[2], Exception) and isinstance(raw[2], dict) else None
        pres_list  = raw[3] if uname          and not isinstance(raw[3], Exception) and isinstance(raw[3], list) else None
        hibp_info  = raw[4] if is_email       and not isinstance(raw[4], Exception) and isinstance(raw[4], dict) else None

        # ── Score global ──────────────────────────────────────────────────
        score = disc_info.get("risk_score", 0) if disc_info else 0
        if hibp_info and hibp_info.get("breached"):
            score = min(score + 25 + hibp_info.get("count", 1) * 5, 100)

        em = self._make_embed(op, alvo, score)

        # ── Seção Discord ─────────────────────────────────────────────────
        if disc_info and discord_user:
            em.set_thumbnail(url=disc_info["avatar_url"])
            em.add_field(name="━━━━━ DISCORD ━━━━━", value="\u200b", inline=False)
            em.add_field(name="👤 Tag", value=f"`{disc_info['tag']}`", inline=True)
            em.add_field(name="🆔 ID", value=f"`{disc_info['id']}`", inline=True)
            em.add_field(name="🤖 Bot", value="`Sim`" if disc_info['bot'] else "`Não`", inline=True)
            em.add_field(name="📅 Conta Criada",
                          value=f"<t:{int(discord_user.created_at.timestamp())}:f>", inline=True)
            em.add_field(name="⏱️ Idade", value=f"`{disc_info['age_days']}` dias", inline=True)
            em.add_field(name="🖼️ Avatar",
                          value="`Personalizado`" if disc_info['has_avatar'] else "`Padrão`", inline=True)
            if disc_info['badges']:
                em.add_field(name="🏅 Badges",
                              value=", ".join(f"`{b}`" for b in disc_info['badges']), inline=True)
            if disc_info['is_member']:
                jts = int(disc_info['joined_at'].timestamp()) if disc_info['joined_at'] else None
                em.add_field(name="📥 Entrou no Servidor",
                              value=f"<t:{jts}:R>" if jts else "`?`", inline=True)
                em.add_field(name="🎭 Cargos", value=f"`{disc_info['roles']}`", inline=True)
            if disc_info.get('nick'):
                em.add_field(name="📝 Apelido", value=f"`{disc_info['nick']}`", inline=True)
            em.add_field(name="🔥 Risk Score Discord", value=f"`{disc_info['risk_score']}/100`", inline=True)

        # ── Seção GitHub ──────────────────────────────────────────────────
        if gh_info:
            em.add_field(name="━━━━━ GITHUB ━━━━━", value="\u200b", inline=False)
            if gh_info.get("found"):
                em.add_field(name="🐙 Perfil", value=f"[{uname}]({gh_info['url']})", inline=True)
                em.add_field(name="📦 Repos", value=f"`{gh_info['repos']}`", inline=True)
                em.add_field(name="👥 Seguidores", value=f"`{gh_info['followers']}`", inline=True)
                if gh_info.get("name"):
                    em.add_field(name="📛 Nome Real", value=f"`{gh_info['name']}`", inline=True)
                if gh_info.get("location"):
                    em.add_field(name="📍 Localização", value=f"`{gh_info['location']}`", inline=True)
                if gh_info.get("company"):
                    em.add_field(name="🏢 Empresa", value=f"`{gh_info['company']}`", inline=True)
                if gh_info.get("twitter"):
                    em.add_field(name="🐦 Twitter vinculado", value=f"`@{gh_info['twitter']}`", inline=True)
                if gh_info.get("created"):
                    em.add_field(name="📅 Conta GitHub", value=f"`{gh_info['created']}`", inline=True)
                if gh_info.get("bio"):
                    em.add_field(name="📝 Bio", value=f"`{gh_info['bio'][:120]}`", inline=False)
            else:
                em.add_field(name="🐙 GitHub", value=f"`{uname}` — não encontrado", inline=True)

        # ── Seção Reddit ──────────────────────────────────────────────────
        if rd_info and rd_info.get("found"):
            em.add_field(name="━━━━━ REDDIT ━━━━━", value="\u200b", inline=False)
            em.add_field(name="👽 Username", value=f"[u/{rd_info['name']}]({rd_info['url']})", inline=True)
            em.add_field(name="🔼 Post Karma", value=f"`{rd_info['post_k']}`", inline=True)
            em.add_field(name="💬 Comment Karma", value=f"`{rd_info['comm_k']}`", inline=True)
            em.add_field(name="📅 Criado em", value=f"`{rd_info['created'].strftime('%d/%m/%Y')}`", inline=True)
            em.add_field(name="✅ Verificado", value="`Sim`" if rd_info['verified'] else "`Não`", inline=True)
            em.add_field(name="🛡️ Moderador", value="`Sim`" if rd_info['is_mod'] else "`Não`", inline=True)

        # ── Seção HIBP ────────────────────────────────────────────────────
        if hibp_info:
            em.add_field(name="━━━━━ VAZAMENTOS (HIBP) ━━━━━", value="\u200b", inline=False)
            if not hibp_info.get("available"):
                em.add_field(name="ℹ️ HIBP", value=f"`{hibp_info.get('note', 'Indisponível')}`", inline=False)
            elif hibp_info.get("breached"):
                em.add_field(name="🚨 Vazamentos",
                              value=f"`{hibp_info['count']}` site(s) comprometido(s)!", inline=True)
                em.add_field(name="📋 Sites",
                              value=" • ".join(f"`{s}`" for s in hibp_info['sites']), inline=False)
            else:
                em.add_field(name="✅ HIBP", value="`Nenhum vazamento encontrado`", inline=False)

        # ── Seção Presença ────────────────────────────────────────────────
        if pres_list:
            found_list    = [p for p in pres_list if p['found']]
            missing_list  = [p for p in pres_list if not p['found']]
            em.add_field(name="━━━━━ PRESENÇA NAS REDES ━━━━━", value="\u200b", inline=False)
            if found_list:
                em.add_field(
                    name=f"✅ Encontrado ({len(found_list)})",
                    value="\n".join(f"[{p['platform']}]({p['url']})" for p in found_list),
                    inline=True
                )
            if missing_list:
                em.add_field(
                    name=f"❌ Ausente ({len(missing_list)})",
                    value="  ".join(f"`{p['platform']}`" for p in missing_list),
                    inline=True
                )

        # ── Avaliação final ───────────────────────────────────────────────
        em.add_field(name="━━━━━ AVALIAÇÃO FINAL ━━━━━", value="\u200b", inline=False)
        em.add_field(name="🔥 Risk Score Global", value=f"`{score}/100`", inline=True)
        em.add_field(name="⚠️ Nível de Risco",    value=f"**{risk_label(score)}**", inline=True)
        em.add_field(name="🛡️ Solicitante",       value=interaction.user.mention, inline=True)

        await interaction.followup.send(embed=em)

        # Log no canal de segurança
        log_ch = self.bot.get_channel(LOG_SEGURANCA)
        if log_ch:
            try:
                await log_ch.send(embed=em)
            except Exception:
                pass

    @app_commands.command(
        name="investigate",
        description="Investigacao OSINT completa: ID Discord, username ou email"
    )
    @app_commands.describe(
        alvo="ID/mencao Discord, username ou email para investigar",
        github="Username do GitHub (opcional, se diferente do alvo)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def investigate(self, interaction: discord.Interaction,
                           alvo: str, github: Optional[str] = None):
        await self._run_investigate(interaction, alvo, github)

    @app_commands.command(
        name="osint",
        description="Investigacao OSINT completa (alias de /investigate)"
    )
    @app_commands.describe(
        alvo="ID/mencao Discord, username ou email",
        github="Username GitHub opcional"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def osint(self, interaction: discord.Interaction,
                    alvo: str, github: Optional[str] = None):
        await self._run_investigate(interaction, alvo, github)
