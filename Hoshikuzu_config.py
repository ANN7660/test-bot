#!/usr/bin/env python3
# Hoshikuzu_config.py
# Hoshikuzu — Configuration & utilitaire (single-file)
# Copie-colle ce fichier et déploie. Set DISCORD_BOT_TOKEN env var.

import os
import json
import threading
import http.server
import socketserver
import asyncio
import datetime
import traceback
from typing import Optional, Dict, Any

import discord
from discord.ext import commands

# ---------------- keep-alive (Render) ----------------
def keep_alive():
    try:
        port = int(os.environ.get("PORT", "8080"))
    except Exception:
        port = 8080
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            return
    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep_alive] running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ---------------- Persistence ----------------
DATA_FILE = "hoshikuzu_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("load_data error:", e)
    # default structure
    return {
        "config": {},      # guild_id -> config dict
        "invites": {},     # inviter_id -> count? (we store per guild)
        "tickets": {}
    }

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("save_data error:", e)

data = load_data()

def get_gconf(gid: int) -> dict:
    return data.setdefault("config", {}).setdefault(str(gid), {})

def set_gconf(gid: int, key: str, value):
    g = get_gconf(gid)
    g[key] = value
    save_data()

def get_gconf_key(gid: int, key: str, default=None):
    return get_gconf(gid).get(key, default)

# ---------------- Bot init ----------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

ARROW_EMOJI = "<a:caarrow:1433143710094196997>"
INVITE_MSG_EMOJI = "<a:caarrow:1433143710094196997>"

# Invite cache (guild_id -> {code: uses})
invites_cache: Dict[str, Dict[str, int]] = {}

# ---------------- Utilities ----------------
def human_member_count(guild: discord.Guild) -> int:
    try:
        return guild.member_count
    except Exception:
        # fallback
        return len([m for m in guild.members if not m.bot])

def safe_get_channel(guild: discord.Guild, cid) -> Optional[discord.abc.GuildChannel]:
    try:
        return guild.get_channel(int(cid))
    except Exception:
        return None

# ---------------- HELP ----------------
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    e = discord.Embed(title="🌿 Hoshikuzu — Commandes principales", color=discord.Color.green())
    e.add_field(name="Configuration", value="`+config` — panneau interactif", inline=False)
    e.add_field(name="Salon vocal", value="`+createvoc` — crée un salon vocal temporaire", inline=False)
    e.add_field(name="Verrouillage", value="`+lock` / `+unlock`", inline=False)
    e.add_field(name="Rôles", value="`+role @member @role` • `+rolejoin @role`", inline=False)
    e.add_field(name="Tickets", value="`+ticket` — crée un ticket", inline=False)
    e.set_footer(text="Hoshikuzu")
    await ctx.send(embed=e)

# ---------------- Config View ----------------
class ConfigView(discord.ui.View):
    def __init__(self, guild: discord.Guild, author_id: int, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.guild = guild
        self.author_id = author_id

        # Build channel options (text channels)
        opts = []
        for ch in guild.text_channels[:25]:
            opts.append(discord.SelectOption(label=ch.name, value=str(ch.id)))
        if not opts:
            opts = [discord.SelectOption(label="Aucun", value="0")]

        self.logs_select = discord.ui.Select(placeholder="Salon de logs", options=opts, custom_id="select_logs")
        self.welcome_select = discord.ui.Select(placeholder="Salon de bienvenue", options=opts, custom_id="select_welcome")
        self.leave_select = discord.ui.Select(placeholder="Salon d'au revoir", options=opts, custom_id="select_leave")
        self.invites_select = discord.ui.Select(placeholder="Salon d'invites", options=opts, custom_id="select_invites")

        # role selection - options are roles
        role_opts = []
        for r in guild.roles[-25:]:
            # skip @everyone
            if r.is_default():
                continue
            role_opts.append(discord.SelectOption(label=r.name, value=str(r.id)))
        if not role_opts:
            role_opts = [discord.SelectOption(label="Aucun", value="0")]

        self.role_select = discord.ui.Select(placeholder="Rôle automatique (rolejoin)", options=role_opts, custom_id="select_rolejoin")

        # welcome type select (embed/text/both)
        self.wtype = discord.ui.Select(
            placeholder="Type de bienvenue",
            options=[
                discord.SelectOption(label="Embed", value="embed"),
                discord.SelectOption(label="Texte (emoji + lignes)", value="text"),
                discord.SelectOption(label="Les deux (embed + texte)", value="both"),
            ],
            custom_id="select_wtype"
        )

        # add items
        self.add_item(self.logs_select)
        self.add_item(self.welcome_select)
        self.add_item(self.leave_select)
        self.add_item(self.invites_select)
        self.add_item(self.wtype)
        self.add_item(self.role_select)

        # buttons: edit welcome/leave messages
        self.add_item(discord.ui.Button(label="Modifier message bienvenue (texte)", style=discord.ButtonStyle.blurple, custom_id="btn_edit_welcome_text"))
        self.add_item(discord.ui.Button(label="Modifier message d'au revoir (embed)", style=discord.ButtonStyle.danger, custom_id="btn_edit_leave_embed"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Tu n'es pas autorisé·e à utiliser ce panneau.", ephemeral=True)
            return False
        return True

    # selects callbacks
    @discord.ui.select(custom_id="select_logs")
    async def on_select_logs(self, select: discord.ui.Select, interaction: discord.Interaction):
        try:
            cid = int(select.values[0])
            if cid == 0:
                set_gconf(self.guild.id, "logs_channel", None)
                await interaction.response.send_message("✅ Logs retirés.", ephemeral=True)
            else:
                set_gconf(self.guild.id, "logs_channel", cid)
                await interaction.response.send_message(f"✅ Salon de logs défini : <#{cid}>", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Erreur lors de la configuration.", ephemeral=True)
            print("config logs err", e)

    @discord.ui.select(custom_id="select_welcome")
    async def on_select_welcome(self, select: discord.ui.Select, interaction: discord.Interaction):
        try:
            cid = int(select.values[0])
            if cid == 0:
                set_gconf(self.guild.id, "welcome_channel", None)
                await interaction.response.send_message("✅ Welcome retiré.", ephemeral=True)
            else:
                set_gconf(self.guild.id, "welcome_channel", cid)
                await interaction.response.send_message(f"✅ Salon de bienvenue défini : <#{cid}>", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Erreur.", ephemeral=True)
            print("config welcome err", e)

    @discord.ui.select(custom_id="select_leave")
    async def on_select_leave(self, select: discord.ui.Select, interaction: discord.Interaction):
        try:
            cid = int(select.values[0])
            if cid == 0:
                set_gconf(self.guild.id, "leave_channel", None)
                await interaction.response.send_message("✅ Leave retiré.", ephemeral=True)
            else:
                set_gconf(self.guild.id, "leave_channel", cid)
                await interaction.response.send_message(f"✅ Salon d'au revoir défini : <#{cid}>", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Erreur.", ephemeral=True)
            print("config leave err", e)

    @discord.ui.select(custom_id="select_invites")
    async def on_select_invites(self, select: discord.ui.Select, interaction: discord.Interaction):
        try:
            cid = int(select.values[0])
            if cid == 0:
                set_gconf(self.guild.id, "invites_channel", None)
                await interaction.response.send_message("✅ Salon d'invites retiré.", ephemeral=True)
            else:
                set_gconf(self.guild.id, "invites_channel", cid)
                await interaction.response.send_message(f"✅ Salon d'invites défini : <#{cid}>", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Erreur.", ephemeral=True)
            print("config invites err", e)

    @discord.ui.select(custom_id="select_wtype")
    async def on_select_wtype(self, select: discord.ui.Select, interaction: discord.Interaction):
        try:
            val = select.values[0]
            set_gconf(self.guild.id, "welcome_type", val)  # embed / text / both
            await interaction.response.send_message(f"✅ Type de bienvenue défini : `{val}`", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Erreur.", ephemeral=True)
            print("config wtype err", e)

    @discord.ui.select(custom_id="select_rolejoin")
    async def on_select_rolejoin(self, select: discord.ui.Select, interaction: discord.Interaction):
        try:
            rid = int(select.values[0])
            if rid == 0:
                set_gconf(self.guild.id, "auto_role", None)
                await interaction.response.send_message("✅ Rolejoin retiré.", ephemeral=True)
            else:
                set_gconf(self.guild.id, "auto_role", rid)
                await interaction.response.send_message(f"✅ Rolejoin défini : <@&{rid}>", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Erreur.", ephemeral=True)
            print("config rolejoin err", e)

    # buttons
    @discord.ui.button(custom_id="btn_edit_welcome_text", label="Modifier message bienvenue (texte)", style=discord.ButtonStyle.blurple)
    async def edit_welcome_text(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("📝 Envoie le nouveau message de bienvenue texte dans ce salon (utilise {member} pour mention, {server} pour nom du serveur, {count} pour nombre).", ephemeral=True)
        try:
            def check(m):
                return m.author.id == self.author_id and m.channel == interaction.channel
            msg = await bot.wait_for("message", timeout=120.0, check=check)
            set_gconf(self.guild.id, "welcome_text", msg.content)
            await interaction.followup.send("✅ Message de bienvenue texte mis à jour.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏲️ Temps écoulé — opération annulée.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("Erreur lors de la mise à jour.", ephemeral=True)
            print("edit welcome text err", e)

    @discord.ui.button(custom_id="btn_edit_leave_embed", label="Modifier message d'au revoir (embed)", style=discord.ButtonStyle.danger)
    async def edit_leave_embed(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("📝 Envoie le nouveau contenu (description) du embed d'au revoir dans ce salon. Tu peux utiliser {member}, {server}, {count}.", ephemeral=True)
        try:
            def check(m):
                return m.author.id == self.author_id and m.channel == interaction.channel
            msg = await bot.wait_for("message", timeout=120.0, check=check)
            set_gconf(self.guild.id, "leave_embed_desc", msg.content)
            await interaction.followup.send("✅ Description du embed d'au revoir mise à jour.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏲️ Temps écoulé — opération annulée.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("Erreur lors de la mise à jour.", ephemeral=True)
            print("edit leave embed err", e)

# ---------------- +config command ----------------
@bot.command(name="config")
@commands.has_permissions(manage_guild=True)
async def config_cmd(ctx: commands.Context):
    try:
        view = ConfigView(ctx.guild, ctx.author.id)
        e = discord.Embed(title="⚙️ Panneau de configuration — Hoshikuzu", color=discord.Color.green())
        conf = get_gconf(ctx.guild.id)
        e.add_field(name="Logs", value=(f"<#{conf.get('logs_channel')}>" if conf.get("logs_channel") else "Aucun"), inline=True)
        e.add_field(name="Bienvenue", value=(f"<#{conf.get('welcome_channel')}>" if conf.get("welcome_channel") else "Aucun"), inline=True)
        e.add_field(name="Au revoir", value=(f"<#{conf.get('leave_channel')}>" if conf.get("leave_channel") else "Aucun"), inline=True)
        e.add_field(name="Invites", value=(f"<#{conf.get('invites_channel')}>" if conf.get("invites_channel") else "Aucun"), inline=True)
        e.add_field(name="Rolejoin", value=(f"<@&{conf.get('auto_role')}>" if conf.get("auto_role") else "Aucun"), inline=True)
        e.add_field(name="Welcome type", value=(conf.get("welcome_type") or "both"), inline=True)
        await ctx.send(embed=e, view=view)
    except Exception as e:
        await ctx.send("Erreur lors de l'ouverture du panneau de configuration.")
        print("config_cmd err", e)

# ---------------- createvoc (temporary voice rooms) ----------------
@bot.command(name="createvoc")
@commands.has_permissions(manage_channels=True)
async def createvoc_cmd(ctx: commands.Context):
    try:
        guild = ctx.guild
        cat = discord.utils.get(guild.categories, name="Vocaux Temporaires")
        if not cat:
            cat = await guild.create_category("Vocaux Temporaires")
        # create a "lobby" voice channel that will spawn personal temporary channels when joined
        existing = discord.utils.get(guild.voice_channels, name="Créer ton salon 🔊")
        if existing:
            set_gconf(guild.id, "temp_voice_lobby", existing.id)
            await ctx.send("⚠️ Un salon 'Créer ton salon 🔊' existe déjà, il a été défini comme salon de création.")
            return
        ch = await guild.create_voice_channel("Créer ton salon 🔊", category=cat)
        set_gconf(guild.id, "temp_voice_lobby", ch.id)
        await ctx.send(f"✅ Salon vocal de création créé : {ch.mention}")
    except Exception as e:
        await ctx.send("❌ Erreur création salon vocal.")
        print("createvoc err", e)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    try:
        guild = member.guild
        temp_lobby = get_gconf_key(guild.id, "temp_voice_lobby")
        if after and after.channel and temp_lobby and after.channel.id == int(temp_lobby):
            # create personal voice channel
            cat = after.channel.category
            name = f"🔊 Salon de {member.display_name}"
            new_vc = await guild.create_voice_channel(name, category=cat)
            # set permissions for owner
            await new_vc.set_permissions(member, connect=True, speak=True, manage_channels=True)
            # store mapping
            set_gconf(guild.id, f"temp_voc_{new_vc.id}", {"owner": member.id})
            # move member
            try:
                await member.move_to(new_vc)
            except:
                pass
            return
        # deletion when empty
        if before and before.channel:
            info = get_gconf_key(guild.id, f"temp_voc_{before.channel.id}")
            if info:
                # if channel empty, delete
                if len(before.channel.members) == 0:
                    try:
                        await before.channel.delete()
                    except:
                        pass
                    # remove config entry
                    cfg = get_gconf(guild.id)
                    key = f"temp_voc_{before.channel.id}"
                    if key in cfg:
                        del cfg[key]
                        save_data()
    except Exception as e:
        print("on_voice_state_update err", e)

# ---------------- lock / unlock ----------------
@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock_cmd(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
    ch = channel or ctx.channel
    try:
        await ch.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(embed=discord.Embed(description=f"🔒 {ch.mention} verrouillé.", color=discord.Color.green()))
    except Exception as e:
        await ctx.send("❌ Impossible de verrouiller le salon.")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock_cmd(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
    ch = channel or ctx.channel
    try:
        await ch.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(embed=discord.Embed(description=f"🔓 {ch.mention} déverrouillé.", color=discord.Color.green()))
    except Exception as e:
        await ctx.send("❌ Impossible de déverrouiller le salon.")

# ---------------- role / rolejoin ----------------
@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
async def role_cmd(ctx: commands.Context, member: discord.Member, role: discord.Role):
    try:
        if role in member.roles:
            await member.remove_roles(role)
            await ctx.send(f"✅ {role.name} retiré à {member.mention}")
        else:
            await member.add_roles(role)
            await ctx.send(f"✅ {role.name} ajouté à {member.mention}")
    except Exception as e:
        await ctx.send("❌ Erreur lors de la gestion du rôle.")
        print("role_cmd err", e)

@bot.command(name="rolejoin")
@commands.has_permissions(manage_guild=True)
async def rolejoin_cmd(ctx: commands.Context, role: discord.Role):
    try:
        set_gconf(ctx.guild.id, "auto_role", role.id)
        await ctx.send(f"✅ Rôle automatique à l'arrivée défini : {role.name}")
    except Exception as e:
        await ctx.send("❌ Erreur.")
        print("rolejoin_cmd err", e)

# ---------------- tickets (simple) ----------------
class CloseTicketView(discord.ui.View):
    def __init__(self, chan_id: int):
        super().__init__(timeout=None)
        self.chan_id = chan_id

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.red)
    async def close_ticket(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.channel.id != self.chan_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("Tu ne peux pas fermer ce ticket.", ephemeral=True)
            return
        await interaction.response.send_message("Fermeture du ticket... suppression dans 5s.", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
            tickets = data.get("tickets", {})
            if str(self.chan_id) in tickets:
                del tickets[str(self.chan_id)]
                save_data()
        except Exception as e:
            print("close ticket err", e)

@bot.command(name="ticket")
async def ticket_cmd(ctx: commands.Context, *, reason: Optional[str] = "Support"):
    try:
        guild = ctx.guild
        cat = discord.utils.get(guild.categories, name="Tickets")
        if not cat:
            cat = await guild.create_category("Tickets")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            bot.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        # allow staff roles (manage_guild or manage_messages)
        for role in guild.roles:
            if role.permissions.manage_guild or role.permissions.manage_messages:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        name = f"ticket-{ctx.author.name}".lower()[:90]
        chan = await guild.create_text_channel(name, category=cat, overwrites=overwrites)
        data.setdefault("tickets", {})[str(chan.id)] = {
            "owner": ctx.author.id,
            "reason": reason,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        save_data()
        e = discord.Embed(title="🎫 Ticket créé", description=f"{ctx.author.mention} • {reason}", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        await chan.send(embed=e, view=CloseTicketView(chan.id))
        await ctx.send(f"✅ Ticket créé : {chan.mention}", delete_after=8)
    except Exception as e:
        await ctx.send("❌ Impossible de créer le ticket.")
        print("ticket_cmd err", e)

# ---------------- message link filter ----------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        await bot.process_commands(message)
        return
    if not message.guild:
        await bot.process_commands(message)
        return
    guild = message.guild
    allow_enabled = get_gconf_key(guild.id, "allow_links_enabled")
    allow_list = get_gconf_key(guild.id, "allow_links") or []
    content = message.content or ""
    if ("http://" in content or "https://" in content) and allow_enabled is False:
        try:
            await message.delete()
            await message.channel.send(f"🚫 {message.author.mention}, les liens ne sont pas autorisés ici.", delete_after=6)
        except:
            pass
        return
    if ("http://" in content or "https://" in content) and allow_enabled is True:
        if message.channel.id not in allow_list:
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention}, les liens ne sont pas autorisés dans ce salon.", delete_after=6)
            except:
                pass
            return
    await bot.process_commands(message)

# ---------------- logs: delete/edit/ban/unban ----------------
@bot.event
async def on_message_delete(message: discord.Message):
    try:
        if not message.guild:
            return
        lid = get_gconf_key(message.guild.id, "logs_channel")
        if not lid:
            return
        ch = message.guild.get_channel(int(lid))
        if not ch:
            return
        e = discord.Embed(title="🗑️ Message supprimé", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Auteur", value=f"{message.author} ({message.author.id})", inline=False)
        e.add_field(name="Salon", value=message.channel.mention, inline=False)
        e.add_field(name="Contenu", value=message.content or "[embed/attachment]", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("on_message_delete err", e)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    try:
        if not before.guild:
            return
        lid = get_gconf_key(before.guild.id, "logs_channel")
        if not lid:
            return
        if before.content == after.content:
            return
        ch = before.guild.get_channel(int(lid))
        if not ch:
            return
        e = discord.Embed(title="✏️ Message édité", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Auteur", value=f"{before.author} ({before.author.id})", inline=False)
        e.add_field(name="Avant", value=before.content or "[embed/attachment]", inline=False)
        e.add_field(name="Après", value=after.content or "[embed/attachment]", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("on_message_edit err", e)

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    try:
        lid = get_gconf_key(guild.id, "logs_channel")
        if not lid:
            return
        ch = guild.get_channel(int(lid))
        if not ch:
            return
        e = discord.Embed(title="⛔ Membre banni", color=discord.Color.dark_red(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Utilisateur", value=f"{user} ({user.id})", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("on_member_ban err", e)

@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    try:
        lid = get_gconf_key(guild.id, "logs_channel")
        if not lid:
            return
        ch = guild.get_channel(int(lid))
        if not ch:
            return
        e = discord.Embed(title="✅ Utilisateur débanni", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Utilisateur", value=f"{user} ({user.id})", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("on_member_unban err", e)

# ---------------- invites tracking ----------------
async def cache_guild_invites(guild: discord.Guild):
    try:
        invites = await guild.invites()
        invites_cache[str(guild.id)] = {inv.code: inv.uses for inv in invites}
    except Exception as e:
        print("cache_guild_invites err", e)

@bot.event
async def on_ready():
    print(f"[Hoshikuzu] connecté en tant que {bot.user} ({bot.user.id})")
    # build invites cache for all guilds
    for g in bot.guilds:
        await cache_guild_invites(g)

@bot.event
async def on_guild_join(guild: discord.Guild):
    # cache invites when bot invited to new guild
    await cache_guild_invites(guild)

@bot.event
async def on_invite_create(invite: discord.Invite):
    # update cache
    try:
        gid = str(invite.guild.id)
        invites_cache.setdefault(gid, {})
        invites_cache[gid][invite.code] = invite.uses or 0
    except Exception as e:
        print("on_invite_create err", e)

@bot.event
async def on_invite_delete(invite: discord.Invite):
    try:
        gid = str(invite.guild.id)
        if gid in invites_cache and invite.code in invites_cache[gid]:
            del invites_cache[gid][invite.code]
    except Exception as e:
        print("on_invite_delete err", e)

@bot.event
async def on_member_join(member: discord.Member):
    try:
        guild = member.guild
        gid = str(guild.id)

        # detect used invite by comparing cache
        used_inviter = None
        used_code = None
        try:
            invites_after = await guild.invites()
            old = invites_cache.get(gid, {})
            for inv in invites_after:
                code = inv.code
                uses_after = inv.uses or 0
                uses_before = old.get(code, 0)
                if uses_after > uses_before:
                    # this invite was used
                    used_code = code
                    used_inviter = inv.inviter
                    break
            # update cache
            invites_cache[gid] = {inv.code: inv.uses or 0 for inv in invites_after}
        except Exception as e:
            print("invite detection err", e)

        # automatic role
        try:
            rid = get_gconf_key(guild.id, "auto_role")
            if rid:
                role = guild.get_role(int(rid))
                if role:
                    await member.add_roles(role, reason="auto rolejoin")
        except Exception as e:
            print("auto role err", e)

        # welcome messages
        try:
            wid = get_gconf_key(guild.id, "welcome_channel")
            wtype = get_gconf_key(guild.id, "welcome_type") or "both"
            if wid:
                ch = guild.get_channel(int(wid))
                if ch:
                    # embed welcome
                    try:
                        e = discord.Embed(title="🌿 Bienvenue !",
                                          description=f"{member.mention} a rejoint le serveur !",
                                          color=discord.Color.green(),
                                          timestamp=datetime.datetime.utcnow())
                        e.add_field(name="Membres", value=str(human_member_count(guild)), inline=True)
                        # thumbnail
                        e.set_thumbnail(url=getattr(member, "display_avatar").url if hasattr(member, "display_avatar") else None)
                        await ch.send(embed=e)
                    except Exception as ex:
                        print("welcome embed send err", ex)

                    # text welcome (emoji lines)
                    if wtype in ("text", "both"):
                        try:
                            # use custom welcome_text if set, else default
                            welcome_text = get_gconf_key(guild.id, "welcome_text") or (
                                f"{ARROW_EMOJI} Bienvenue {member.mention} sur **{guild.name}** !\n"
                                f"{ARROW_EMOJI} Nous sommes maintenant {human_member_count(guild)} membres 🎉"
                            )
                            # format placeholders
                            welcome_text = welcome_text.replace("{member}", member.mention).replace("{server}", guild.name).replace("{count}", str(human_member_count(guild)))
                            await ch.send(welcome_text)
                        except Exception as ex:
                            print("welcome text send err", ex)
        except Exception as e:
            print("welcome logic err", e)

        # invites message
        try:
            inv_chid = get_gconf_key(guild.id, "invites_channel")
            if inv_chid:
                inv_ch = guild.get_channel(int(inv_chid))
                if inv_ch:
                    # if used_inviter is found
                    if used_inviter is not None:
                        inviter = used_inviter
                        # increment inviter count in data
                        invites_data = data.setdefault("invites", {}).setdefault(str(guild.id), {})
                        inviter_count = invites_data.get(str(inviter.id), 0) + 1
                        invites_data[str(inviter.id)] = inviter_count
                        save_data()
                        msg = (f"{INVITE_MSG_EMOJI} {member.mention} a été invité par {inviter.mention} !\n"
                               f"{INVITE_MSG_EMOJI} Il a maintenant **{inviter_count}** invitations.")
                        await inv_ch.send(msg)
                    else:
                        # unknown invite (vanity or detection failed)
                        msg = f"{INVITE_MSG_EMOJI} {member.mention} a rejoint — invite introuvable (vanity ou ancien lien)."
                        await inv_ch.send(msg)
        except Exception as e:
            print("invites message err", e)

    except Exception as e:
        print("on_member_join err", e)
        traceback.print_exc()

@bot.event
async def on_member_remove(member: discord.Member):
    try:
        guild = member.guild
        wid = get_gconf_key(guild.id, "leave_channel")
        if wid:
            ch = guild.get_channel(int(wid))
            if ch:
                desc_template = get_gconf_key(guild.id, "leave_embed_desc") or f"{member} a quitté le serveur."
                desc = desc_template.replace("{member}", str(member)).replace("{server}", guild.name).replace("{count}", str(human_member_count(guild)))
                e = discord.Embed(title="👋 Au revoir...", description=desc, color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
                if hasattr(member, "display_avatar"):
                    try:
                        e.set_thumbnail(url=getattr(member, "display_avatar").url)
                    except:
                        pass
                await ch.send(embed=e)
    except Exception as e:
        print("on_member_remove err", e)

# ---------------- logs for startup and invite errors ----------------
@bot.event
async def on_error(event_method, *args, **kwargs):
    print(f"[on_error] {event_method} ->", args, kwargs)
    traceback.print_exc()

# ---------------- Run ----------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ Variable d'environnement DISCORD_BOT_TOKEN manquante.")
else:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print("Bot run err:", e)
        raise
