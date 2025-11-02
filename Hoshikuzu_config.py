#!/usr/bin/env python3
# Hoshikuzu_config.py
# Bot Discord complet : config interactive, bienvenue, logs, tickets, voc auto, rôle join, allowlink, lock/unlock
# Compatible Render + discord.py==2.3.2

import os, json, asyncio, threading, http.server, socketserver, datetime
from typing import Optional

import discord
from discord.ext import commands

# --- Keep-alive Render ---
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

# --- Data system ---
DATA_FILE = "hoshikuzu_data.json"
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("load_data error:", e)
    return {"config": {}, "tickets": {}}

def save_data(d):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("save_data error:", e)

data = load_data()
def set_conf(gid, k, v):
    data.setdefault("config", {}).setdefault(str(gid), {})[k] = v
    save_data(data)
def get_conf(gid, k, default=None):
    return data.get("config", {}).get(str(gid), {}).get(k, default)

# --- Bot init ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

EMOJI = "<a:caarrow:1433143710094196997>"

def member_count(g):
    try:
        return g.member_count
    except:
        return len([m for m in g.members if not m.bot])

# --- Help ---
@bot.command(name="help")
async def help_cmd(ctx):
    e = discord.Embed(title="🌿 Hoshikuzu — Aide", color=discord.Color.green())
    e.add_field(name="⚙️ Config", value="`+config` (panneau interactif)", inline=False)
    e.add_field(name="🔗 Liens", value="`+allowlink #salon` / `+disallowlink #salon`", inline=False)
    e.add_field(name="🎙️ Vocale", value="`+createvoc`", inline=False)
    e.add_field(name="🔒 Lock/Unlock", value="`+lock` / `+unlock`", inline=False)
    e.add_field(name="🧩 Rôles", value="`+role @user @role` / `+rolejoin @role`", inline=False)
    e.add_field(name="🎫 Tickets", value="`+ticket`", inline=False)
    await ctx.send(embed=e)

# --- Config panel ---
class ConfigView(discord.ui.View):
    def __init__(self, guild, author_id, timeout=180):
        super().__init__(timeout=timeout)
        self.guild = guild
        self.author_id = author_id

        opts = [discord.SelectOption(label=c.name, value=str(c.id)) for c in guild.text_channels[:25]]
        if not opts:
            opts = [discord.SelectOption(label="Aucun", value="0")]

        self.logs_select = discord.ui.Select(placeholder="Salon de logs", options=opts, custom_id="logs_select")
        self.welcome_select = discord.ui.Select(placeholder="Salon de bienvenue", options=opts, custom_id="welcome_select")
        self.voc_select = discord.ui.Select(placeholder="Salon vocal auto", options=opts, custom_id="voc_select")

        self.add_item(self.logs_select)
        self.add_item(self.welcome_select)
        self.add_item(self.voc_select)

        self.add_item(discord.ui.Button(label="Activer allow_links", style=discord.ButtonStyle.green, custom_id="enable_links"))
        self.add_item(discord.ui.Button(label="Désactiver allow_links", style=discord.ButtonStyle.gray, custom_id="disable_links"))
        self.add_item(discord.ui.Button(label="Définir role join", style=discord.ButtonStyle.blurple, custom_id="set_rolejoin"))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Tu n'es pas autorisé·e.", ephemeral=True)
            return False
        return True

@bot.command(name="config")
@commands.has_permissions(manage_guild=True)
async def config_cmd(ctx):
    view = ConfigView(ctx.guild, ctx.author.id)
    e = discord.Embed(title="⚙️ Panneau de configuration", color=discord.Color.green())
    e.add_field(name="Logs", value=f"<#{get_conf(ctx.guild.id,'logs_channel')}>" if get_conf(ctx.guild.id,'logs_channel') else "Aucun", inline=True)
    e.add_field(name="Bienvenue", value=f"<#{get_conf(ctx.guild.id,'welcome_channel')}>" if get_conf(ctx.guild.id,'welcome_channel') else "Aucun", inline=True)
    e.add_field(name="Voc auto", value=f"<#{get_conf(ctx.guild.id,'temp_voice_lobby')}>" if get_conf(ctx.guild.id,'temp_voice_lobby') else "Aucun", inline=True)
    await ctx.send(embed=e, view=view)

# --- Allow link ---
@bot.command(name="allowlink")
@commands.has_permissions(administrator=True)
async def allowlink_cmd(ctx, channel: discord.TextChannel):
    allow = get_conf(ctx.guild.id, "allow_links") or []
    if channel.id in allow:
        return await ctx.send("✅ Déjà autorisé.")
    allow.append(channel.id)
    set_conf(ctx.guild.id, "allow_links", allow)
    await ctx.send(f"✅ {channel.mention} autorisé pour les liens.")

@bot.command(name="disallowlink")
@commands.has_permissions(administrator=True)
async def disallowlink_cmd(ctx, channel: discord.TextChannel):
    allow = get_conf(ctx.guild.id, "allow_links") or []
    if channel.id not in allow:
        return await ctx.send("❌ Ce salon n'est pas autorisé.")
    allow.remove(channel.id)
    set_conf(ctx.guild.id, "allow_links", allow)
    await ctx.send(f"✅ {channel.mention} retiré de la liste.")

# --- Voc auto ---
@bot.command(name="createvoc")
@commands.has_permissions(manage_channels=True)
async def createvoc_cmd(ctx):
    guild = ctx.guild
    cat = discord.utils.get(guild.categories, name="Vocaux Temporaires")
    if not cat:
        cat = await guild.create_category("Vocaux Temporaires")

    existing = discord.utils.get(guild.voice_channels, name="Créer ton salon 🔊")
    if existing:
        set_conf(guild.id, "temp_voice_lobby", existing.id)
        return await ctx.send("⚠️ Salon existant défini comme vocal auto.")
    ch = await guild.create_voice_channel("Créer ton salon 🔊", category=cat)
    set_conf(guild.id, "temp_voice_lobby", ch.id)
    await ctx.send(f"✅ {ch.mention} créé pour les salons vocaux automatiques.")

@bot.event
async def on_voice_state_update(member, before, after):
    try:
        temp = get_conf(member.guild.id, "temp_voice_lobby")
        if after.channel and temp and after.channel.id == int(temp):
            guild = member.guild
            cat = after.channel.category
            temp_ch = await guild.create_voice_channel(f"🔊 Salon de {member.display_name}", category=cat)
            await temp_ch.set_permissions(member, connect=True, speak=True, manage_channels=True)
            set_conf(guild.id, f"temp_voc_{temp_ch.id}", {"owner": member.id})
            await member.move_to(temp_ch)
        if before.channel:
            info = get_conf(member.guild.id, f"temp_voc_{before.channel.id}")
            if info and len(before.channel.members) == 0:
                await before.channel.delete()
                cfg = data["config"].get(str(member.guild.id), {})
                cfg.pop(f"temp_voc_{before.channel.id}", None)
                save_data(data)
    except Exception as e:
        print("voice update err:", e)

# --- Lock/unlock ---
@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock_cmd(ctx, channel: Optional[discord.TextChannel] = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 {channel.mention} verrouillé.")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock_cmd(ctx, channel: Optional[discord.TextChannel] = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"🔓 {channel.mention} déverrouillé.")

# --- Rôles ---
@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
async def role_cmd(ctx, member: discord.Member, role: discord.Role):
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"✅ {role.name} retiré.")
    else:
        await member.add_roles(role)
        await ctx.send(f"✅ {role.name} ajouté.")

@bot.command(name="rolejoin")
@commands.has_permissions(manage_guild=True)
async def rolejoin_cmd(ctx, role: discord.Role):
    set_conf(ctx.guild.id, "auto_role", role.id)
    await ctx.send(f"✅ Role auto défini : {role.name}")

# --- Bienvenue & Au revoir ---
@bot.event
async def on_member_join(member):
    try:
        rid = get_conf(member.guild.id, "auto_role")
        if rid:
            role = member.guild.get_role(int(rid))
            if role:
                await member.add_roles(role)
        wid = get_conf(member.guild.id, "welcome_channel")
        if wid:
            ch = member.guild.get_channel(int(wid))
            if ch:
                e = discord.Embed(title="🌿 Bienvenue !", description=f"{EMOJI} Bienvenue à {member.mention} sur **{member.guild.name}** !", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
                e.add_field(name="👥 Membres", value=str(member_count(member.guild)), inline=True)
                e.set_thumbnail(url=member.display_avatar.url)
                await ch.send(embed=e)
    except Exception as e:
        print("join err:", e)

@bot.event
async def on_member_remove(member):
    try:
        wid = get_conf(member.guild.id, "welcome_channel")
        if wid:
            ch = member.guild.get_channel(int(wid))
            if ch:
                e = discord.Embed(title="👋 Au revoir...", description=f"{member} a quitté le serveur.", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
                e.add_field(name="👥 Membres restants", value=str(member_count(member.guild)), inline=True)
                e.set_thumbnail(url=member.display_avatar.url)
                await ch.send(embed=e)
    except Exception as e:
        print("leave err:", e)

# --- Logs ---
@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return
    lid = get_conf(message.guild.id, "logs_channel")
    if not lid:
        return
    ch = message.guild.get_channel(int(lid))
    if ch:
        e = discord.Embed(title="🗑️ Message supprimé", color=discord.Color.orange())
        e.add_field(name="Auteur", value=f"{message.author} ({message.author.id})", inline=False)
        e.add_field(name="Salon", value=message.channel.mention, inline=False)
        e.add_field(name="Contenu", value=message.content or "[Embed/Fichier]", inline=False)
        await ch.send(embed=e)

# --- Tickets ---
class CloseTicket(discord.ui.View):
    def __init__(self, chan_id):
        super().__init__(timeout=None)
        self.chan_id = chan_id

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.red)
    async def close(self, button, interaction):
        if interaction.channel.id != self.chan_id:
            return await interaction.response.send_message("🚫 Tu ne peux pas fermer ce ticket.", ephemeral=True)
        await interaction.response.send_message("🔒 Fermeture dans 5 secondes...", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete()
        data["tickets"].pop(str(self.chan_id), None)
        save_data(data)

@bot.command(name="ticket")
async def ticket_cmd(ctx, *, reason="Support"):
    guild = ctx.guild
    cat = discord.utils.get(guild.categories, name="Tickets")
    if not cat:
        cat = await guild.create_category("Tickets")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        bot.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    chan = await guild.create_text_channel(f"ticket-{ctx.author.name}".lower()[:90], category=cat, overwrites=overwrites)
    data["tickets"][str(chan.id)] = {"owner": ctx.author.id, "reason": reason}
    save_data(data)

    e = discord.Embed(title="🎫 Ticket ouvert", description=f"{ctx.author.mention} — {reason}", color=discord.Color.green())
    await chan.send(embed=e, view=CloseTicket(chan.id))
    await ctx.send(f"✅ Ticket créé : {chan.mention}")

# --- Link filter ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return await bot.process_commands(message)

    guild = message.guild
    allow_enabled = get_conf(guild.id, "allow_links_enabled")
    allow_list = get_conf(guild.id, "allow_links") or []

    if ("http://" in message.content or "https://" in message.content):
        if allow_enabled and message.channel.id in allow_list:
            pass
        else:
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention}, les liens ne sont pas autorisés ici.", delete_after=5)
                return
            except:
                pass
    await bot.process_commands(message)

# --- Ready ---
@bot.event
async def on_ready():
    print(f"[Hoshikuzu] Connecté comme {bot.user} ({bot.user.id})")

# --- Run ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini.")
else:
    bot.run(TOKEN)
