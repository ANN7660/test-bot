#!/usr/bin/env python3
# Hoshikuzu_ultra.py
# Full-featured Hoshikuzu bot (help, createvoc, anti-link, config, invites, warns, economy, role UI, keep-alive)
# Configure DISCORD_BOT_TOKEN in env before running.

import os
import re
import json
import threading
import http.server
import socketserver
import asyncio
import datetime
from typing import Optional, Dict, List, Any
import discord
from discord.ext import commands

# -------------------- Keep-alive (Render) --------------------
def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
    except Exception:
        port = 8080
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): pass
    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep-alive] HTTP server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# -------------------- DataManager --------------------
class DataManager:
    def __init__(self, filename: str = "hoshikuzu_data.json"):
        self.filename = filename
        self.lock = asyncio.Lock()
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print("DataManager load error:", e)
        return {"voc": {}, "config": {}, "economy": {}, "warns": {}, "link_warns": {}}

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # voc
    async def register_temp_vc(self, channel_id: int, owner_id: int):
        cid = str(channel_id)
        self.data.setdefault("voc", {})[cid] = {
            "owner": str(owner_id),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        await self.save()

    async def unregister_temp_vc(self, channel_id: int):
        cid = str(channel_id)
        if cid in self.data.get("voc", {}):
            del self.data["voc"][cid]
            await self.save()

    def is_temp_vc(self, channel_id: int) -> bool:
        return str(channel_id) in self.data.get("voc", {})

    # config
    async def set_config(self, guild_id: int, key: str, value):
        gid = str(guild_id)
        self.data.setdefault("config", {}).setdefault(gid, {})[key] = value
        await self.save()

    def get_config(self, guild_id: int, key: str, default=None):
        gid = str(guild_id)
        return self.data.get("config", {}).get(gid, {}).get(key, default)

    # economy
    def get_balance(self, guild_id: int, user_id: int) -> int:
        gid = str(guild_id); uid = str(user_id)
        return int(self.data.setdefault("economy", {}).setdefault(gid, {}).setdefault(uid, 0))

    async def set_balance(self, guild_id: int, user_id: int, amount: int):
        gid = str(guild_id); uid = str(user_id)
        self.data.setdefault("economy", {}).setdefault(gid, {})[uid] = int(amount)
        await self.save()

    # warns
    async def add_warn(self, guild_id: int, user_id: int, issuer_id: int, reason: str):
        gid = str(guild_id); uid = str(user_id)
        self.data.setdefault("warns", {}).setdefault(gid, {}).setdefault(uid, [])
        entry = {
            "id": int(datetime.datetime.now().timestamp()),
            "issuer": str(issuer_id),
            "reason": reason,
            "date": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self.data["warns"][gid][uid].append(entry)
        await self.save()
        return entry

    async def del_warn(self, guild_id: int, user_id: int, warn_id: int):
        gid = str(guild_id); uid = str(user_id)
        warns = self.data.get("warns", {}).get(gid, {}).get(uid, [])
        new = [w for w in warns if w.get("id") != warn_id]
        self.data.setdefault("warns", {}).setdefault(gid, {})[uid] = new
        await self.save()

    def list_warns(self, guild_id: int, user_id: int):
        gid = str(guild_id); uid = str(user_id)
        return self.data.get("warns", {}).get(gid, {}).get(uid, [])

data_manager = DataManager()

# -------------------- Bot init --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)
bot.data_manager = data_manager

# invites cache
invites_cache: Dict[int, Dict[str, int]] = {}

# -------------------- Help view (FIXED) --------------------
HELP_PAGES = [
    {"title":"🎙️ Vocaux","desc":"`+createvoc` `+lockvoc` `+renamevoc` `+limitvoc`"},
    {"title":"💰 Économie","desc":"`+balance` `+daily` `+work` `+give` `+coinflip` `+slots`"},
    {"title":"🧾 Modération","desc":"`+warn` `+warnings` `+delwarn` `+clear` `+kick` `+ban`"},
    {"title":"🎉 Fun","desc":"`+meme` `+hug` `+avatar` `+8ball` `+ship`"},
    {"title":"⚙️ Config","desc":"`+config` `+userinfo` `+serverinfo` `+say` `+role`"}
]

class HelpView(discord.ui.View):
    def __init__(self, author_id:int, timeout:int=180):
        super().__init__(timeout=timeout)
        self.page = 0
        self.author_id = author_id

    async def update_message(self, interaction: discord.Interaction):
        """Fixed signature: require interaction positional arg so callers must pass it explicitly."""
        page = HELP_PAGES[self.page]
        embed = discord.Embed(title=page["title"], description=page["desc"], color=discord.Color.blurple())
        embed.set_footer(text=f"Page {self.page+1}/{len(HELP_PAGES)} • Utilisateur: {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Tu n'es pas autorisé·e.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.page = (self.page - 1) % len(HELP_PAGES)
        await self.update_message(interaction=interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.page = (self.page + 1) % len(HELP_PAGES)
        await self.update_message(interaction=interaction)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except:
            pass
        self.stop()

@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    view = HelpView(author_id=ctx.author.id, timeout=180)
    page = HELP_PAGES[0]
    embed = discord.Embed(title=page["title"], description=page["desc"], color=discord.Color.blurple())
    embed.set_footer(text=f"Page 1/{len(HELP_PAGES)} • Utilisateur: {ctx.author.display_name}")
    await ctx.send(embed=embed, view=view)

# -------------------- createvoc --------------------
@bot.command(name="createvoc")
@commands.has_permissions(manage_channels=True)
async def create_voc(ctx: commands.Context):
    guild = ctx.guild
    category_name = "Vocaux Temporaires 🔊"
    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        try:
            category = await guild.create_category(category_name)
        except Exception as e:
            await ctx.send("❌ erreur création category")
            print("create_voc:", e)
            return
    existing = discord.utils.get(guild.voice_channels, name="Créer ton salon 🔊")
    if existing:
        await ctx.send("⚠️ 'Créer ton salon 🔊' existe déjà.")
        bot.temp_voice_lobby = existing.id
        return
    try:
        channel = await guild.create_voice_channel("Créer ton salon 🔊", category=category)
        bot.temp_voice_lobby = channel.id
        await ctx.send(f"✅ Salon créé : {channel.mention}")
    except Exception as e:
        await ctx.send("❌ impossible de créer le salon vocal")
        print("create_voc:", e)

@bot.event
async def on_voice_state_update(member: discord.Member, before: Optional[discord.VoiceState], after: Optional[discord.VoiceState]):
    try:
        if after and after.channel and hasattr(bot, "temp_voice_lobby") and after.channel.id == getattr(bot, "temp_voice_lobby"):
            guild = member.guild
            category = after.channel.category
            chan_name = f"🔊 Salon de {member.display_name}"
            temp = await guild.create_voice_channel(chan_name, category=category)
            try:
                await temp.set_permissions(member, connect=True, speak=True, manage_channels=True)
            except:
                pass
            await data_manager.register_temp_vc(temp.id, member.id)
            try:
                await member.move_to(temp)
            except:
                pass
            return
        if before and before.channel and data_manager.is_temp_vc(before.channel.id):
            ch = before.channel
            if len(ch.members) == 0:
                try:
                    await ch.delete()
                except:
                    pass
                await data_manager.unregister_temp_vc(ch.id)
    except Exception as e:
        print("on_voice_state_update error:", e)

# -------------------- Anti-link --------------------
URL_REGEX = re.compile(r"(https?://\S+)|(\bdiscord\.gg/\S+)", re.IGNORECASE)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    # admins/mods bypass
    if message.author.guild_permissions.manage_guild or message.author.guild_permissions.manage_messages or message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return
    allow_list = data_manager.get_config(message.guild.id, "allow_links", []) or []
    try:
        allow_list = [int(x) for x in allow_list]
    except:
        allow_list = []
    if message.channel.id in allow_list:
        await bot.process_commands(message)
        return
    if URL_REGEX.search(message.content):
        try:
            await message.delete()
        except:
            pass
        try:
            await message.channel.send(f"🚫 {message.author.mention} — Les liens ne sont pas autorisés ici.", delete_after=8)
        except:
            pass
        gid = str(message.guild.id); uid = str(message.author.id)
        cfg = data_manager.data.setdefault("config", {}).setdefault(gid, {})
        wc = cfg.get("link_warns", {}); wc[uid] = wc.get(uid, 0) + 1; cfg["link_warns"] = wc
        try:
            await data_manager.save()
        except:
            pass
        return
    await bot.process_commands(message)

@bot.command(name="allowlink")
@commands.has_permissions(administrator=True)
async def allowlink_cmd(ctx: commands.Context, channel: discord.TextChannel):
    cfg = data_manager.data.setdefault("config", {}).setdefault(str(ctx.guild.id), {})
    allow = cfg.get("allow_links", [])
    if channel.id in allow:
        return await ctx.send("✅ salon déjà autorisé")
    allow.append(channel.id)
    cfg["allow_links"] = allow
    await data_manager.save()
    await ctx.send(f"✅ {channel.mention} autorisé")

@bot.command(name="disallowlink")
@commands.has_permissions(administrator=True)
async def disallowlink_cmd(ctx: commands.Context, channel: discord.TextChannel):
    cfg = data_manager.data.setdefault("config", {}).setdefault(str(ctx.guild.id), {})
    allow = cfg.get("allow_links", [])
    if channel.id not in allow:
        return await ctx.send("❌ ce salon n'était pas autorisé")
    allow = [c for c in allow if c != channel.id]
    cfg["allow_links"] = allow
    await data_manager.save()
    await ctx.send(f"✅ {channel.mention} retiré")

# -------------------- Invite tracking --------------------
async def cache_guild_invites(guild: discord.Guild):
    try:
        invites = await guild.invites()
        invites_cache[guild.id] = {inv.code: inv.uses for inv in invites}
    except Exception as e:
        print("cache_invites error:", e)

@bot.event
async def on_ready():
    print(f"[BOT] connecté comme {bot.user} ({bot.user.id})")
    for g in bot.guilds:
        await cache_guild_invites(g)

@bot.event
async def on_guild_join(guild: discord.Guild):
    await cache_guild_invites(guild)

@bot.event
async def on_invite_create(invite: discord.Invite):
    try:
        invites_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses
    except:
        pass

@bot.event
async def on_invite_delete(invite: discord.Invite):
    try:
        if invite.guild.id in invites_cache and invite.code in invites_cache[invite.guild.id]:
            del invites_cache[invite.guild.id][invite.code]
    except:
        pass

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    inviter = None
    try:
        before = invites_cache.get(guild.id, {})
        after_invites = await guild.invites()
        after = {inv.code: inv.uses for inv in after_invites}
        for code, uses in after.items():
            prev = before.get(code, 0)
            if uses > prev:
                matched = [inv for inv in after_invites if inv.code == code]
                if matched:
                    inviter = matched[0].inviter
                break
        invites_cache[guild.id] = after
    except Exception as e:
        print("invite detect error:", e)
        inviter = None

    # welcome channel
    welcome_id = data_manager.get_config(guild.id, "welcome_channel")
    if welcome_id:
        ch = guild.get_channel(int(welcome_id))
        if ch:
            try:
                await ch.send(f"Bienvenue {member.mention} !")
            except:
                pass

    # invite log channel
    invlog_id = data_manager.get_config(guild.id, "invite_log")
    inv_ch = None
    if invlog_id:
        inv_ch = guild.get_channel(int(invlog_id))
    else:
        name = "📥・invites-log"
        inv_ch = discord.utils.get(guild.text_channels, name=name)
        if not inv_ch:
            try:
                inv_ch = await guild.create_text_channel(name)
                await data_manager.set_config(guild.id, "invite_log", inv_ch.id)
            except:
                inv_ch = None

    if inv_ch:
        try:
            if inviter:
                total = 0
                for inv in await guild.invites():
                    if inv.inviter and inv.inviter.id == inviter.id:
                        total += inv.uses
                await inv_ch.send(f"✨ {member.mention} a rejoint — invité par {inviter.mention} ({total} invites).")
            else:
                await inv_ch.send(f"✨ {member.mention} a rejoint — invité par : inconnu.")
        except:
            pass

    # auto-role
    autorole = data_manager.get_config(guild.id, "auto_role")
    if autorole:
        try:
            role = guild.get_role(int(autorole))
            if role:
                await member.add_roles(role, reason="Auto-role config")
        except:
            pass

# -------------------- Warn system --------------------
@bot.command(name="warn")
@commands.has_permissions(kick_members=True)
async def warn_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    entry = await data_manager.add_warn(ctx.guild.id, member.id, ctx.author.id, reason)
    await ctx.send(f"⚠️ {member.mention} averti — id `{entry['id']}`. Raison : {reason}")
    warns = data_manager.list_warns(ctx.guild.id, member.id)
    if len(warns) >= 3:
        try:
            await member.kick(reason="Atteint 3 warns auto-kick")
            await ctx.send(f"🚨 {member.mention} expulsé automatiquement (3 warns).")
        except Exception as e:
            print("auto-kick failed:", e)

@bot.command(name="warnings")
@commands.has_permissions(kick_members=True)
async def warnings_cmd(ctx: commands.Context, member: discord.Member):
    warns = data_manager.list_warns(ctx.guild.id, member.id)
    if not warns:
        return await ctx.send("Aucun avertissement pour cet utilisateur.")
    embed = discord.Embed(title=f"Avertissements — {member.display_name}", color=discord.Color.orange())
    for w in warns:
        embed.add_field(name=f"ID: {w['id']}", value=f"Auteur: <@{w['issuer']}>\nRaison: {w['reason']}\nDate: {w['date']}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="delwarn")
@commands.has_permissions(kick_members=True)
async def delwarn_cmd(ctx: commands.Context, member: discord.Member, warn_id: int):
    await data_manager.del_warn(ctx.guild.id, member.id, warn_id)
    await ctx.send(f"✅ Avertissement `{warn_id}` supprimé pour {member.mention}")

# -------------------- Economy --------------------
@bot.command(name="balance", aliases=["bal"])
async def balance_cmd(ctx: commands.Context, member: Optional[discord.Member]=None):
    member = member or ctx.author
    bal = data_manager.get_balance(ctx.guild.id, member.id)
    await ctx.send(f"💰 {member.mention} a {bal} coins.")

COOLDOWNS = {"work": 2*60*60, "daily": 24*60*60}  # seconds
_last_action: Dict[str, Dict[str, int]] = {"work": {}, "daily": {}}

@bot.command(name="work")
async def work_cmd(ctx: commands.Context):
    uid = str(ctx.author.id); gid = str(ctx.guild.id)
    now = int(datetime.datetime.now().timestamp())
    last = _last_action["work"].get(gid, {}).get(uid, 0)
    if now - last < COOLDOWNS["work"]:
        remain = COOLDOWNS["work"] - (now - last)
        return await ctx.send(f"⏳ Attends {remain//60} minutes avant de travailler à nouveau.")
    import random
    earn = random.randint(50, 150)
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + earn)
    _last_action["work"].setdefault(gid, {})[uid] = now
    await ctx.send(f"💼 Tu as gagné {earn} coins en travaillant !")

@bot.command(name="daily")
async def daily_cmd(ctx: commands.Context):
    uid = str(ctx.author.id); gid = str(ctx.guild.id)
    now = int(datetime.datetime.now().timestamp())
    last = _last_action["daily"].get(gid, {}).get(uid, 0)
    if now - last < COOLDOWNS["daily"]:
        remain = COOLDOWNS["daily"] - (now - last)
        return await ctx.send(f"⏳ Tu as déjà pris ton daily. Attends {remain//3600} heures.")
    bonus = 250
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + bonus)
    _last_action["daily"].setdefault(gid, {})[uid] = now
    await ctx.send(f"🎁 Tu as récupéré ton daily : {bonus} coins.")

@bot.command(name="give")
async def give_cmd(ctx: commands.Context, member: discord.Member, amount: int):
    if amount <= 0: return await ctx.send("Montant invalide.")
    bal_from = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    if bal_from < amount: return await ctx.send("Tu n'as pas assez d'argent.")
    await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal_from - amount)
    bal_to = data_manager.get_balance(ctx.guild.id, member.id)
    await data_manager.set_balance(ctx.guild.id, member.id, bal_to + amount)
    await ctx.send(f"✅ {ctx.author.mention} a donné {amount} coins à {member.mention}.")

@bot.command(name="coinflip")
async def coinflip_cmd(ctx: commands.Context, bet: int, guess: Optional[str] = None):
    if bet <= 0: return await ctx.send("Pari invalide.")
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    if bal < bet: return await ctx.send("Tu n'as pas assez d'argent.")
    import random
    outcome = random.choice(["pile", "face"])
    if guess and guess.lower() == outcome:
        await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + bet)
        await ctx.send(f"🎉 C'est {outcome} — tu as gagné {bet} !")
    else:
        await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal - bet)
        await ctx.send(f"😞 C'est {outcome} — tu as perdu {bet}.")

@bot.command(name="slots")
async def slots_cmd(ctx: commands.Context, bet: int):
    if bet <= 0: return await ctx.send("Pari invalide.")
    bal = data_manager.get_balance(ctx.guild.id, ctx.author.id)
    if bal < bet: return await ctx.send("Tu n'as pas assez d'argent.")
    import random
    symbols = ["🍒","🍋","🔔","⭐","7️⃣"]
    res = [random.choice(symbols) for _ in range(3)]
    if len(set(res)) == 1:
        win = bet * 5
        await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + win)
        await ctx.send(f"🎰 {' '.join(res)} — JACKPOT! Tu gagnes {win}.")
    elif len(set(res)) == 2:
        win = int(bet * 1.5)
        await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal + win)
        await ctx.send(f"🎰 {' '.join(res)} — Tu gagnes {win}.")
    else:
        await data_manager.set_balance(ctx.guild.id, ctx.author.id, bal - bet)
        await ctx.send(f"🎰 {' '.join(res)} — Tu perds {bet}.")

# -------------------- Role UI --------------------
class RoleView(discord.ui.View):
    def __init__(self, guild: discord.Guild, member: discord.Member, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.guild = guild; self.member = member
        role_opts = [discord.SelectOption(label=r.name, value=str(r.id)) for r in guild.roles if r.name != "@everyone"][:25]
        if not role_opts:
            role_opts = [discord.SelectOption(label="Aucun rôle", value="0")]
        self.role_select = discord.ui.Select(placeholder="Choisis un rôle", options=role_opts, min_values=1, max_values=1)
        self.role_select.callback = self.role_chosen
        self.add_item(self.role_select)

    async def role_chosen(self, interaction: discord.Interaction):
        role_id = int(self.role_select.values[0])
        role = self.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("Rôle introuvable.", ephemeral=True)
            return
        # add/remove buttons -- to keep simple we provide quick admin commands after selection
        await interaction.response.send_message(f"Rôle choisi : **{role.name}**\nUtilise `/roleadd @user {role.name}` ou `/roleremove @user {role.name}` (ou utilise les commandes +roleadd / +roleremove).", ephemeral=True)

@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
async def role_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    view = RoleView(ctx.guild, member)
    embed = discord.Embed(title="🎭 Gestion de rôles", description=f"Sélectionne un rôle pour {member.display_name}", color=discord.Color.blurple())
    await ctx.send(embed=embed, view=view)

@bot.command(name="roleadd")
@commands.has_permissions(manage_roles=True)
async def roleadd_cmd(ctx: commands.Context, member: discord.Member, role: discord.Role):
    try:
        await member.add_roles(role, reason=f"Ajouté par {ctx.author}")
        await ctx.send(f"✅ {role.name} ajouté à {member.mention}")
    except Exception as e:
        await ctx.send("Erreur lors de l'ajout de rôle.")

@bot.command(name="roleremove")
@commands.has_permissions(manage_roles=True)
async def roleremove_cmd(ctx: commands.Context, member: discord.Member, role: discord.Role):
    try:
        await member.remove_roles(role, reason=f"Retiré par {ctx.author}")
        await ctx.send(f"✅ {role.name} retiré à {member.mention}")
    except Exception:
        await ctx.send("Erreur lors du retrait de rôle.")

# -------------------- Utilities --------------------
@bot.command(name="ping")
async def ping_cmd(ctx: commands.Context):
    await ctx.send(f"🏓 Pong — {round(bot.latency * 1000)} ms")

@bot.command(name="userinfo")
async def userinfo_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"👤 {member.display_name}", color=member.color)
    embed.add_field(name="ID", value=str(member.id))
    if member.created_at:
        embed.add_field(name="Compte créé", value=member.created_at.strftime("%d/%m/%Y %H:%M"))
    if member.joined_at:
        embed.add_field(name="A rejoint", value=member.joined_at.strftime("%d/%m/%Y %H:%M"))
    roles = [r.name for r in member.roles if r.name != "@everyone"]
    embed.add_field(name="Rôles", value=", ".join(roles) or "Aucun", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="botinfo")
async def botinfo_cmd(ctx: commands.Context):
    embed = discord.Embed(title="🤖 Bot info", color=discord.Color.green())
    embed.add_field(name="Serveurs", value=str(len(bot.guilds)))
    await ctx.send(embed=embed)

# -------------------- Run --------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini — ajoute la variable d'environnement et relance.")
else:
    bot.run(TOKEN)
