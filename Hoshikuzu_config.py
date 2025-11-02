#!/usr/bin/env python3
# Hoshikuzu_config.py
# Compact full-featured config bot: interactive +config, welcome/leave embed, logs, tickets, createvoc, lock/unlock, role/rolejoin, allowlink
# Requires discord.py==2.3.2. Set DISCORD_BOT_TOKEN env var.

import os, json, asyncio, threading, http.server, socketserver, datetime, traceback
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands

# Keep-alive for Render
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

# Data
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
    data.setdefault("config", {}).setdefault(str(gid), {})[k]=v; save_data(data)
def get_conf(gid, k, default=None):
    return data.get("config", {}).get(str(gid), {}).get(k, default)

# Bot init
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

EMOJI = "<a:caarrow:1433143710094196997>"

def member_count(g): 
    try: return g.member_count
    except: return len([m for m in g.members if not m.bot])

# Help embed (green)
@bot.command(name="help")
async def help_cmd(ctx):
    e = discord.Embed(title="🌿 Hoshikuzu — Config", color=discord.Color.green())
    e.add_field(name="Config", value="`+config` (panneau interactif)", inline=False)
    e.add_field(name="Liens", value="`+allowlink #channel` / `+disallowlink #channel`", inline=False)
    e.add_field(name="Vocale", value="`+createvoc`", inline=False)
    e.add_field(name="Lock", value="`+lock` / `+unlock`", inline=False)
    e.add_field(name="Roles", value="`+role @user @role` / `+rolejoin @role`", inline=False)
    e.add_field(name="Tickets", value="`+ticket`", inline=False)
    await ctx.send(embed=e)

# Config panel view
class ConfigView(discord.ui.View):
    def __init__(self, guild, author_id, timeout=180):
        super().__init__(timeout=timeout)
        self.guild=guild; self.author_id=author_id
        opts=[discord.SelectOption(label=c.name, value=str(c.id)) for c in guild.text_channels[:25]]
        if not opts: opts=[discord.SelectOption(label="Aucun", value="0")]
        self.logs = discord.ui.Select(placeholder="Salon de logs", options=opts)
        self.welcome = discord.ui.Select(placeholder="Salon de bienvenue", options=opts)
        self.voc = discord.ui.Select(placeholder="Salon vocal auto", options=opts)
        self.add_item(self.logs); self.add_item(self.welcome); self.add_item(self.voc)
        self.add_item(discord.ui.Button(label="Activer allow_links", style=discord.ButtonStyle.green, custom_id="enable_links"))
        self.add_item(discord.ui.Button(label="Désactiver allow_links", style=discord.ButtonStyle.gray, custom_id="disable_links"))
        self.add_item(discord.ui.Button(label="Définir role join", style=discord.ButtonStyle.blurple, custom_id="set_rolejoin"))

    async def interaction_check(self, interaction):
        if interaction.user.id!=self.author_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Tu n'es pas autorisé·e.", ephemeral=True); return False
        return True

    @discord.ui.select()
    async def select_callback(self, select, interaction):
        try:
            val = int(select.values[0])
            if select==self.logs: set_conf(self.guild.id, "logs_channel", val); await interaction.response.send_message(f"✅ Logs: <#{val}>", ephemeral=True)
            elif select==self.welcome: set_conf(self.guild.id, "welcome_channel", val); await interaction.response.send_message(f"✅ Welcome: <#{val}>", ephemeral=True)
            elif select==self.voc: set_conf(self.guild.id, "temp_voice_lobby", val); await interaction.response.send_message(f"✅ Voc auto: <#{val}>", ephemeral=True)
            else: await interaction.response.send_message("Sélection inconnue.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Erreur.", ephemeral=True); print("select err", e)

    @discord.ui.button(custom_id="enable_links", label="Activer allow_links", style=discord.ButtonStyle.green)
    async def enable_links(self, b, interaction): set_conf(self.guild.id,"allow_links_enabled",True); await interaction.response.send_message("✅ allow_links activé.", ephemeral=True)
    @discord.ui.button(custom_id="disable_links", label="Désactiver allow_links", style=discord.ButtonStyle.gray)
    async def disable_links(self, b, interaction): set_conf(self.guild.id,"allow_links_enabled",False); set_conf(self.guild.id,"allow_links",[]); await interaction.response.send_message("✅ allow_links désactivé.", ephemeral=True)
    @discord.ui.button(custom_id="set_rolejoin", label="Définir role join", style=discord.ButtonStyle.blurple)
    async def set_rolejoin(self, b, interaction): await interaction.response.send_message("ℹ️ Utilise `+rolejoin @Role`.", ephemeral=True)

@bot.command(name="config")
@commands.has_permissions(manage_guild=True)
async def config_cmd(ctx):
    view = ConfigView(ctx.guild, ctx.author.id)
    e = discord.Embed(title="⚙️ Panneau de configuration", color=discord.Color.green())
    e.add_field(name="Logs", value=get_conf(ctx.guild.id,"logs_channel") and f"<#{get_conf(ctx.guild.id,'logs_channel')}>" or "Aucun", inline=True)
    e.add_field(name="Bienvenue", value=get_conf(ctx.guild.id,"welcome_channel") and f"<#{get_conf(ctx.guild.id,'welcome_channel')}>" or "Aucun", inline=True)
    e.add_field(name="Voc auto", value=get_conf(ctx.guild.id,"temp_voice_lobby") and f"<#{get_conf(ctx.guild.id,'temp_voice_lobby')}>" or "Aucun", inline=True)
    await ctx.send(embed=e, view=view)

# allowlink commands
@bot.command(name="allowlink")
@commands.has_permissions(administrator=True)
async def allowlink_cmd(ctx, channel: discord.TextChannel):
    allow = get_conf(ctx.guild.id,"allow_links") or []
    if channel.id in allow: return await ctx.send("✅ Salon déjà autorisé.")
    allow.append(channel.id); set_conf(ctx.guild.id,"allow_links",allow); await ctx.send(f"✅ {channel.mention} autorisé.")

@bot.command(name="disallowlink")
@commands.has_permissions(administrator=True)
async def disallowlink_cmd(ctx, channel: discord.TextChannel):
    allow = get_conf(ctx.guild.id,"allow_links") or []
    if channel.id not in allow: return await ctx.send("❌ Non dans la liste.")
    allow=[c for c in allow if c!=channel.id]; set_conf(ctx.guild.id,"allow_links",allow); await ctx.send(f"✅ {channel.mention} retiré.")

# createvoc
@bot.command(name="createvoc")
@commands.has_permissions(manage_channels=True)
async def createvoc_cmd(ctx):
    guild=ctx.guild; cat = discord.utils.get(guild.categories, name="Vocaux Temporaires")
    if not cat: cat = await guild.create_category("Vocaux Temporaires")
    existing = discord.utils.get(guild.voice_channels, name="Créer ton salon 🔊")
    if existing:
        set_conf(guild.id,"temp_voice_lobby", existing.id); save_data(data); return await ctx.send("⚠️ Salon existant défini.")
    ch = await guild.create_voice_channel("Créer ton salon 🔊", category=cat)
    set_conf(guild.id,"temp_voice_lobby", ch.id); save_data(data); await ctx.send(f"✅ {ch.mention} créé.")

@bot.event
async def on_voice_state_update(member, before, after):
    try:
        temp = get_conf(member.guild.id,"temp_voice_lobby")
        if after and after.channel and temp and after.channel.id==int(temp):
            guild=member.guild; cat=after.channel.category
            temp_ch = await guild.create_voice_channel(f"🔊 Salon de {member.display_name}", category=cat)
            await temp_ch.set_permissions(member, connect=True, speak=True, manage_channels=True)
            set_conf(guild.id,f"temp_voc_{temp_ch.id}",{"owner":member.id}); save_data(data)
            try: await member.move_to(temp_ch)
            except: pass
            return
        if before and before.channel:
            info = get_conf(member.guild.id,f"temp_voc_{before.channel.id}")
            if info and len(before.channel.members)==0:
                try: await before.channel.delete()
                except: pass
                cfg = data.get("config",{}).get(str(member.guild.id),{})
                if f"temp_voc_{before.channel.id}" in cfg: del cfg[f"temp_voc_{before.channel.id}"]; save_data(data)
    except Exception as e:
        print("voice update err", e)

# lock/unlock
@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock_cmd(ctx, channel: Optional[discord.TextChannel]=None):
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"🔒 {channel.mention} verrouillé.")
    except Exception as e:
        await ctx.send("❌ Impossible de verrouiller.")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock_cmd(ctx, channel: Optional[discord.TextChannel]=None):
    channel = channel or ctx.channel
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(f"🔓 {channel.mention} déverrouillé.")
    except Exception as e:
        await ctx.send("❌ Impossible de déverrouiller.")

# role/rolejoin
@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
async def role_cmd(ctx, member: discord.Member, role: discord.Role):
    try:
        if role in member.roles:
            await member.remove_roles(role); await ctx.send(f"✅ {role.name} retiré.")
        else:
            await member.add_roles(role); await ctx.send(f"✅ {role.name} ajouté.")
    except Exception as e:
        await ctx.send("❌ erreur role.")

@bot.command(name="rolejoin")
@commands.has_permissions(manage_guild=True)
async def rolejoin_cmd(ctx, role: discord.Role):
    set_conf(ctx.guild.id,"auto_role", role.id); await ctx.send(f"✅ rolejoin défini : {role.name}")

@bot.event
async def on_member_join(member):
    try:
        rid = get_conf(member.guild.id,"auto_role")
        if rid:
            role = member.guild.get_role(int(rid))
            if role:
                try: await member.add_roles(role, reason="auto rolejoin")
                except: pass
        wid = get_conf(member.guild.id,"welcome_channel")
        if wid:
            ch = member.guild.get_channel(int(wid))
            if ch:
                # single embed welcome
                try:
                    e = discord.Embed(title="🌿 Bienvenue !", description=f"{EMOJI} Bienvenue à {member.mention} sur **{member.guild.name}** !", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
                    e.add_field(name="Membres", value=str(member_count(member.guild)), inline=True)
                    e.set_thumbnail(url=getattr(member, "display_avatar").url if hasattr(member, "display_avatar") else None)
                    await ch.send(embed=e)
                except Exception as ex:
                    print("welcome send err", ex)
    except Exception as e:
        print("on_member_join err", e)

@bot.event
async def on_member_remove(member):
    try:
        wid = get_conf(member.guild.id,"welcome_channel")
        if wid:
            ch = member.guild.get_channel(int(wid))
            if ch:
                try:
                    e = discord.Embed(title="👋 Au revoir...", description=f"{member} a quitté le serveur.", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
                    e.add_field(name="Membres restants", value=str(member_count(member.guild)), inline=True)
                    e.set_thumbnail(url=getattr(member, "display_avatar").url if hasattr(member, "display_avatar") else None)
                    await ch.send(embed=e)
                except Exception as ex:
                    print("goodbye err", ex)
    except Exception as e:
        print("on_member_remove err", e)

# logs
@bot.event
async def on_message_delete(message):
    try:
        if not message.guild: return
        lid = get_conf(message.guild.id,"logs_channel")
        if not lid: return
        ch = message.guild.get_channel(int(lid))
        if not ch: return
        e = discord.Embed(title="🗑️ Message supprimé", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Auteur", value=f"{message.author} ({message.author.id})", inline=False)
        e.add_field(name="Salon", value=message.channel.mention, inline=False)
        e.add_field(name="Contenu", value=message.content or "[embed/attachment]", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("del log err", e)

@bot.event
async def on_message_edit(before, after):
    try:
        if not before.guild: return
        lid = get_conf(before.guild.id,"logs_channel")
        if not lid: return
        if before.content == after.content: return
        ch = before.guild.get_channel(int(lid))
        if not ch: return
        e = discord.Embed(title="✏️ Message édité", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Auteur", value=f"{before.author} ({before.author.id})", inline=False)
        e.add_field(name="Avant", value=before.content or "[embed/attachment]", inline=False)
        e.add_field(name="Après", value=after.content or "[embed/attachment]", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("edit log err", e)

@bot.event
async def on_member_ban(guild, user):
    try:
        lid = get_conf(guild.id,"logs_channel"); 
        if not lid: return
        ch = guild.get_channel(int(lid)); 
        if not ch: return
        e = discord.Embed(title="⛔ Membre banni", color=discord.Color.dark_red(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Utilisateur", value=f"{user} ({user.id})", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("ban log err", e)

@bot.event
async def on_member_unban(guild, user):
    try:
        lid = get_conf(guild.id,"logs_channel"); 
        if not lid: return
        ch = guild.get_channel(int(lid)); 
        if not ch: return
        e = discord.Embed(title="✅ Utilisateur débanni", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="Utilisateur", value=f"{user} ({user.id})", inline=False)
        await ch.send(embed=e)
    except Exception as e:
        print("unban log err", e)

# tickets
class CloseTicket(discord.ui.View):
    def __init__(self, chan_id):
        super().__init__(timeout=None); self.chan_id=chan_id
    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.red)
    async def close(self, button, interaction):
        if interaction.channel.id!=self.chan_id and not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Tu ne peux pas fermer.", ephemeral=True)
        await interaction.response.send_message("🔒 Fermeture... suppression dans 5s", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
            if str(self.chan_id) in data.get("tickets",{}): del data["tickets"][str(self.chan_id)]; save_data(data)
        except Exception as e:
            print("close ticket err", e)

@bot.command(name="ticket")
async def ticket_cmd(ctx, *, reason: Optional[str]="Support"):
    guild=ctx.guild
    cat=discord.utils.get(guild.categories, name="Tickets")
    if not cat: cat=await guild.create_category("Tickets")
    overwrites={guild.default_role:discord.PermissionOverwrite(view_channel=False)}
    overwrites[bot.user]=discord.PermissionOverwrite(view_channel=True, send_messages=True)
    overwrites[ctx.author]=discord.PermissionOverwrite(view_channel=True, send_messages=True)
    for role in guild.roles:
        if role.permissions.manage_guild or role.permissions.manage_messages:
            overwrites[role]=discord.PermissionOverwrite(view_channel=True, send_messages=True)
    chan = await guild.create_text_channel(f"ticket-{ctx.author.name}".lower()[:90], category=cat, overwrites=overwrites)
    data.setdefault("tickets",{})[str(chan.id)]={"owner":ctx.author.id,"reason":reason,"created":datetime.datetime.utcnow().isoformat()}
    save_data(data)
    e = discord.Embed(title="🎫 Ticket créé", description=f"{ctx.author.mention} • {reason}", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
    await chan.send(embed=e, view=CloseTicket(chan.id))
    await ctx.send(f"✅ Ticket créé : {chan.mention}", delete_after=8)

# message link filter
@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message); return
    guild = message.guild
    if not guild:
        await bot.process_commands(message); return
    allow_enabled = get_conf(guild.id,"allow_links_enabled")
    allow_list = get_conf(guild.id,"allow_links") or []
    if allow_enabled is False:
        if "http://" in message.content or "https://" in message.content:
            try: await message.delete(); await message.channel.send(f"🚫 {message.author.mention}, les liens ne sont pas autorisés ici.", delete_after=5)
            except: pass; return
    elif allow_enabled is True:
        if "http://" in message.content or "https://" in message.content:
            if message.channel.id not in allow_list:
                try: await message.delete(); await message.channel.send(f"🚫 {message.author.mention}, les liens ne sont pas autorisés dans ce salon.", delete_after=5)
                except: pass; return
    await bot.process_commands(message)

# on_ready
@bot.event
async def on_ready():
    print(f"[Hoshikuzu Config] connecté comme {bot.user} ({bot.user.id})")

# run
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini.")
else:
    bot.run(TOKEN)
