# Hoshikuzu_complete.py
# Bot Hoshikuzu — version complète pour Render
# Préfixe: +
# DISCORD_TOKEN must be set in environment variables on Render

import os
import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import random
import json
import math
import threading, http.server, socketserver

# -------------------- Constants --------------------
PREFIX = "+"
DATA_FILE = "bot_data.json"
ARROW_EMOJI = "<a:caarrow:1433143710094196997>"

# -------------------- Data manager --------------------
class DataManager:
    def __init__(self, filename=DATA_FILE):
        self.filename = filename
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("⚠️ JSON corrompu, réinitialisation.")
        return {"economy": {}, "warnings": {}, "levels": {}, "config": {}, "giveaways": []}

    def _save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    # --- config per guild ---
    def get_guild_config(self, guild_id):
        gid = str(guild_id)
        return self.data.setdefault("config", {}).setdefault(gid, {})

    def set_guild_config(self, guild_id, key, value):
        cfg = self.get_guild_config(guild_id)
        cfg[key] = value
        self._save()
        return cfg

    # --- economy ---
    def _eco(self, user_id):
        uid = str(user_id)
        return self.data.setdefault("economy", {}).setdefault(uid, {"balance":0,"last_daily":None,"last_work":None})

    def get_balance(self, user_id):
        return self._eco(user_id).get("balance", 0)

    def update_balance(self, user_id, amount):
        eco = self._eco(user_id)
        eco["balance"] = eco.get("balance",0) + amount
        self._save()
        return eco["balance"]

    def set_balance(self, user_id, amount):
        eco = self._eco(user_id)
        eco["balance"] = amount
        self._save()
        return eco["balance"]

    def get_last_daily(self, user_id):
        s = self._eco(user_id).get("last_daily")
        return datetime.fromisoformat(s) if s else None

    def set_last_daily(self, user_id):
        eco = self._eco(user_id)
        eco["last_daily"] = datetime.now().isoformat()
        self._save()

    def get_last_work(self, user_id):
        s = self._eco(user_id).get("last_work")
        return datetime.fromisoformat(s) if s else None

    def set_last_work(self, user_id):
        eco = self._eco(user_id)
        eco["last_work"] = datetime.now().isoformat()
        self._save()

    # --- warnings ---
    def get_user_warnings(self, user_id):
        return self.data.get("warnings", {}).get(str(user_id), [])

    def add_warning(self, guild_id, user_id, moderator_id, reason):
        uid = str(user_id)
        warns = self.data.setdefault("warnings", {}).setdefault(uid, [])
        wid = len(warns)+1
        warn = {"id": wid, "timestamp": datetime.now().isoformat(), "moderator_id": str(moderator_id), "reason": reason}
        warns.append(warn)
        self._save()
        return warn

    def remove_warning(self, user_id, warn_id):
        uid = str(user_id)
        warns = self.data.get("warnings", {}).get(uid, [])
        new = [w for w in warns if w.get("id") != warn_id]
        if len(new) < len(warns):
            self.data["warnings"][uid] = new
            self._save()
            return True
        return False

    # --- leveling ---
    def _level(self, user_id):
        uid = str(user_id)
        return self.data.setdefault("levels", {}).setdefault(uid, {"level":0,"xp":0})

    def add_xp(self, user_id, xp_amount):
        user = self._level(user_id)
        user["xp"] += xp_amount
        leveled = None
        def req(l): return 1000 + l*250
        while user["xp"] >= req(user["level"]+1):
            user["xp"] -= req(user["level"]+1)
            user["level"] += 1
            leveled = user["level"]
        self._save()
        return leveled

data_manager = DataManager()

# -------------------- Keep-alive (Render) --------------------
def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"✅ Keep-alive on port {port}")
        httpd.serve_forever()

# -------------------- Helpers --------------------
def parse_mention_id(text):
    if not text: return None
    s = str(text).strip()
    s = s.replace("<#","").replace("<@&","").replace("<@","").replace(">","")
    s = s.strip()
    try:
        return int(s)
    except:
        return None

def format_channel_mention(guild, val):
    try:
        return f"<#{int(val)}>"
    except:
        return str(val)

def format_role_mention(guild, val):
    try:
        return f"<@&{int(val)}>"
    except:
        return str(val)

# -------------------- Bot init --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
bot.remove_command("help")
bot.xp_cooldown_cache = {}

# -------------------- Views & Modals for Config --------------------
class ConfigModal(discord.ui.Modal):
    def __init__(self, field_key, title):
        super().__init__(title=title)
        self.field_key = field_key
        self.add_item(discord.ui.InputText(label="Mention ou ID (ex: #salon ou 123456)", placeholder="Entrez la mention du salon/role ou son ID", required=True))

    async def callback(self, interaction: discord.Interaction):
        value = self.children[0].value
        parsed = parse_mention_id(value)
        if parsed is None:
            await interaction.response.send_message("❌ ID/mention invalide.", ephemeral=True)
            return
        data_manager.set_guild_config(interaction.guild.id, self.field_key, str(parsed))
        await interaction.response.send_message(f"✅ `{self.field_key}` mis à jour.", ephemeral=True)

class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Logs", style=discord.ButtonStyle.primary, custom_id="cfg_logs")
    async def btn_logs(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigModal("LOGS_CHANNEL_ID", "Configurer le salon de logs"))

    @discord.ui.button(label="Boost", style=discord.ButtonStyle.primary, custom_id="cfg_boost")
    async def btn_boost(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigModal("BOOST_CHANNEL_ID", "Configurer le salon de boost"))

    @discord.ui.button(label="Ticket Cat", style=discord.ButtonStyle.primary, custom_id="cfg_ticket_cat")
    async def btn_ticket_cat(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigModal("TICKET_CATEGORY_ID", "Configurer la catégorie des tickets"))

    @discord.ui.button(label="Rôle Support", style=discord.ButtonStyle.primary, custom_id="cfg_support_role")
    async def btn_support(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigModal("SUPPORT_ROLE_ID", "Configurer le rôle support"))

    @discord.ui.button(label="Welcome Embed", style=discord.ButtonStyle.secondary, custom_id="cfg_welcome")
    async def btn_welcome(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigModal("WELCOME_EMBED_CHANNEL_ID", "Configurer le salon de bienvenue (embed)"))

    @discord.ui.button(label="Welcome Simple", style=discord.ButtonStyle.secondary, custom_id="cfg_welcome_s")
    async def btn_welcome_s(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigModal("WELCOME_SIMPLE_CHANNEL_ID", "Configurer le salon de bienvenue (simple)"))

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary, custom_id="cfg_leave")
    async def btn_leave(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigModal("LEAVE_CHANNEL_ID", "Configurer le salon des départs"))

    @discord.ui.button(label="Envoyer panneau Tickets", style=discord.ButtonStyle.success, custom_id="cfg_send_ticket_panel")
    async def btn_send_ticket_panel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Utilisez la commande `+sendticketpanel` pour envoyer le panneau ici.", ephemeral=True)

# -------------------- Ticket & Role Views --------------------
class RoleButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Annonces", style=discord.ButtonStyle.secondary, custom_id="role_annonces_id")
    async def role_annonces_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ROLE_ID = 1433143710094196998
        await self.toggle_role(interaction, ROLE_ID, "Annonces")

    @discord.ui.button(label="Événements", style=discord.ButtonStyle.secondary, custom_id="role_evenements_id")
    async def role_evenements_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ROLE_ID = 1433143710094196999
        await self.toggle_role(interaction, ROLE_ID, "Événements")

    async def toggle_role(self, interaction: discord.Interaction, role_id: int, role_name: str):
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message(f"❌ Le rôle '**{role_name}**' n'existe pas. (ID: {role_id})", ephemeral=True)
        member = interaction.user
        if role in member.roles:
            await member.remove_roles(role, reason="Rôle retiré via bouton")
            await interaction.response.send_message(f"✅ Le rôle **{role_name}** a été **retiré**.", ephemeral=True)
        else:
            await member.add_roles(role, reason="Rôle ajouté via bouton")
            await interaction.response.send_message(f"✅ Le rôle **{role_name}** a été **ajouté**.", ephemeral=True)

class TicketCreateView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(label="Ouvrir un Ticket", style=discord.ButtonStyle.blurple, custom_id="ticket_button_create")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        cfg = data_manager.get_guild_config(guild.id)
        category_id = cfg.get("TICKET_CATEGORY_ID")
        support_role_id = cfg.get("SUPPORT_ROLE_ID")
        support_role = guild.get_role(int(support_role_id)) if support_role_id else None

        if not category_id or not support_role:
            await interaction.response.send_message("❌ Configuration manquante : catégorie ou rôle support.", ephemeral=True)
            return

        category = guild.get_channel(int(category_id))
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Catégorie invalide.", ephemeral=True)
            return

        for channel in category.text_channels:
            if channel.topic and str(user.id) in channel.topic:
                await interaction.response.send_message(f"❌ Vous avez déjà un ticket ouvert : {channel.mention}", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }
        name = f"ticket-{user.name}".lower()[:90]
        ticket_channel = await guild.create_text_channel(name=name, category=category, overwrites=overwrites, topic=f"Ticket ouvert par {user.name} ({user.id})")
        embed = discord.Embed(title="🎫 Ticket Ouvert", description=f"{user.mention} a ouvert un ticket.", color=discord.Color.blue())
        await ticket_channel.send(f"{user.mention} {support_role.mention}", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Ticket créé : {ticket_channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le Ticket", style=discord.ButtonStyle.red, custom_id="ticket_button_close")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ Ce n'est pas un canal de ticket.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Ticket fermé. Suppression dans 5s...", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user.display_name}")
        except discord.Forbidden:
            cfg = data_manager.get_guild_config(interaction.guild.id)
            logs = cfg.get("LOGS_CHANNEL_ID")
            if logs:
                ch = bot.get_channel(int(logs))
                if ch: await ch.send(f"❌ Je n'ai pas pu supprimer le canal {interaction.channel.name}")

# -------------------- Events --------------------
@bot.event
async def on_ready():
    print("="*40)
    print(f"🤖 Bot connecté: {bot.user} (ID: {bot.user.id})")
    print(f"📊 Serveurs: {len(bot.guilds)}")
    print("="*40)
    bot.add_view(ConfigView())
    bot.add_view(TicketCreateView(bot))
    bot.add_view(TicketCloseView())
    bot.add_view(RoleButtonView())
    # start background tasks if needed

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    # leveling XP
    uid = message.author.id
    now = datetime.now()
    last = bot.xp_cooldown_cache.get(uid)
    if last is None or (now - last).total_seconds() >= 60:
        xp = random.randint(5,15)
        new_lvl = data_manager.add_xp(uid, xp)
        bot.xp_cooldown_cache[uid] = now
        if new_lvl:
            await message.channel.send(f"✨ {message.author.mention} est passé au niveau {new_lvl} !")
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    try:
        cfg = data_manager.get_guild_config(member.guild.id)
        ch_id = cfg.get("WELCOME_EMBED_CHANNEL_ID") or cfg.get("WELCOME_CHANNEL_ID")
        if ch_id:
            ch = member.guild.get_channel(int(ch_id))
            if ch:
                member_count = member.guild.member_count
                embed = discord.Embed(title="🌸 Bienvenue sur Hoshikuzu !", description=f"Salut {member.mention} ! Tu es notre {member_count}ème membre.", color=discord.Color.purple(), timestamp=datetime.now())
                embed.set_thumbnail(url=member.display_avatar.url)
                await ch.send(embed=embed)
        try:
            await member.send(embed=discord.Embed(title="🎉 Bienvenue !", description="Amuse-toi bien !", color=discord.Color.green()))
        except discord.Forbidden:
            pass
    except Exception as e:
        print("on_member_join error:", e)

@bot.event
async def on_message_edit(before, after):
    try:
        cfg = data_manager.get_guild_config(before.guild.id)
        logs = cfg.get("LOGS_CHANNEL_ID")
        if logs:
            ch = bot.get_channel(int(logs))
            if ch:
                embed = discord.Embed(title="📝 Message Modifié", description=f"Auteur: {before.author.mention}", color=discord.Color.dark_teal(), timestamp=datetime.now())
                embed.add_field(name="Avant", value=(before.content[:500] or "—"), inline=False)
                embed.add_field(name="Après", value=(after.content[:500] or "—"), inline=False)
                await ch.send(embed=embed)
    except Exception:
        pass

@bot.event
async def on_member_ban(guild, user):
    try:
        cfg = data_manager.get_guild_config(guild.id)
        logs = cfg.get("LOGS_CHANNEL_ID")
        if logs:
            ch = bot.get_channel(int(logs))
            if ch:
                embed = discord.Embed(title="🔨 Membre Banni", description=f"{user}", color=discord.Color.red(), timestamp=datetime.now())
                await ch.send(embed=embed)
    except Exception:
        pass

# -------------------- Giveaways task (simple) --------------------
active_giveaways = []

@tasks.loop(seconds=5)
async def giveaway_task():
    now = datetime.now()
    for g in active_giveaways[:]:
        if now >= g.get("end_time"):
            active_giveaways.remove(g)
            await end_giveaway(g)

async def end_giveaway(g):
    ch = bot.get_channel(g.get("channel_id"))
    if not ch: return
    try:
        msg = await ch.fetch_message(g.get("message_id"))
    except:
        return
    reaction = discord.utils.get(msg.reactions, emoji='🎁')
    if reaction:
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            await ch.send("❌ Aucun participant valide.")
            return
        winners = random.sample(users, min(g.get("winners",1), len(users)))
        mentions = ", ".join([w.mention for w in winners])
        await ch.send(f"🎉 Gagnant(s): {mentions} — {g.get('prize')}")

# -------------------- Commands: Config & Setup --------------------
@bot.command(name="config")
@commands.has_permissions(administrator=True)
async def config_cmd(ctx):
    cfg = data_manager.get_guild_config(ctx.guild.id)
    def fmt(key, label):
        v = cfg.get(key)
        if v:
            if key.endswith("_ROLE_ID"):
                return f"{label} : <@&{v}>"
            return f"{label} : <#{v}>"
        return f"{label} : ❌ Non configuré"
    embed = discord.Embed(title="⚙️ Configuration du Serveur", color=discord.Color.blue())
    embed.add_field(name="Logs", value=fmt("LOGS_CHANNEL_ID", "Logs"), inline=False)
    embed.add_field(name="Boost", value=fmt("BOOST_CHANNEL_ID", "Boost"), inline=False)
    embed.add_field(name="Tickets", value=fmt("TICKET_CATEGORY_ID", "Catégorie Tickets"), inline=False)
    embed.add_field(name="Rôle Support", value=fmt("SUPPORT_ROLE_ID", "Rôle Support"), inline=False)
    embed.add_field(name="Welcome (embed)", value=fmt("WELCOME_EMBED_CHANNEL_ID", "Welcome Embed"), inline=False)
    embed.add_field(name="Welcome (simple)", value=fmt("WELCOME_SIMPLE_CHANNEL_ID", "Welcome Simple"), inline=False)
    embed.add_field(name="Leave", value=fmt("LEAVE_CHANNEL_ID", "Leave"), inline=False)
    await ctx.send(embed=embed, view=ConfigView())

@bot.command(name="setlogs")
@commands.has_permissions(administrator=True)
async def set_logs(ctx, channel: discord.TextChannel):
    data_manager.set_guild_config(ctx.guild.id, "LOGS_CHANNEL_ID", str(channel.id))
    await ctx.send(f"✅ Salon de logs configuré sur {channel.mention}")

@bot.command(name="setboostchannel")
@commands.has_permissions(administrator=True)
async def set_boost(ctx, channel: discord.TextChannel):
    data_manager.set_guild_config(ctx.guild.id, "BOOST_CHANNEL_ID", str(channel.id))
    await ctx.send(f"✅ Salon de boost configuré sur {channel.mention}")

@bot.command(name="setticketcategory")
@commands.has_permissions(administrator=True)
async def set_ticket_cat(ctx, category: discord.CategoryChannel):
    data_manager.set_guild_config(ctx.guild.id, "TICKET_CATEGORY_ID", str(category.id))
    await ctx.send(f"✅ Catégorie de tickets configurée : **{category.name}**")

@bot.command(name="setticketrole")
@commands.has_permissions(administrator=True)
async def set_ticket_role(ctx, role: discord.Role):
    data_manager.set_guild_config(ctx.guild.id, "SUPPORT_ROLE_ID", str(role.id))
    await ctx.send(f"✅ Rôle support configuré : {role.mention}")

@bot.command(name="sendticketpanel")
@commands.has_permissions(administrator=True)
async def send_ticket_panel(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    embed = discord.Embed(title="Centre d'Aide 📩", description="Cliquez pour ouvrir un ticket privé", color=discord.Color.dark_purple())
    await target.send(embed=embed, view=TicketCreateView(bot))
    await ctx.send(f"✅ Panneau de tickets envoyé dans {target.mention}", delete_after=5)

@bot.command(name="sendrolespanel")
@commands.has_permissions(administrator=True)
async def send_roles_panel(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    embed = discord.Embed(title="Choisissez vos Rôles", description="Cliquez pour gérer vos rôles", color=discord.Color.from_rgb(255,105,180))
    await target.send(embed=embed, view=RoleButtonView())
    await ctx.send(f"✅ Panneau de rôles envoyé dans {target.mention}", delete_after=5)

@bot.command(name="sendrules")
@commands.has_permissions(administrator=True)
async def send_rules(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    embed = discord.Embed(title="📜 Règles", description="Respecte les règles svp.", color=discord.Color.blue())
    await target.send(embed=embed)
    await ctx.send(f"✅ Règles envoyées dans {target.mention}", delete_after=5)

@bot.command(name="welcomeembed")
@commands.has_permissions(administrator=True)
async def set_welcome_embed(ctx, channel: discord.TextChannel):
    data_manager.set_guild_config(ctx.guild.id, "WELCOME_EMBED_CHANNEL_ID", str(channel.id))
    await ctx.send(f"✅ Welcome (embed) défini sur {channel.mention}")

@bot.command(name="welcomesimple")
@commands.has_permissions(administrator=True)
async def set_welcome_simple(ctx, channel: discord.TextChannel):
    data_manager.set_guild_config(ctx.guild.id, "WELCOME_SIMPLE_CHANNEL_ID", str(channel.id))
    await ctx.send(f"✅ Welcome (simple) défini sur {channel.mention}")

@bot.command(name="leavechat")
@commands.has_permissions(administrator=True)
async def set_leave(ctx, channel: discord.TextChannel):
    data_manager.set_guild_config(ctx.guild.id, "LEAVE_CHANNEL_ID", str(channel.id))
    await ctx.send(f"✅ Salon des départs défini sur {channel.mention}")

# -------------------- Moderation --------------------
@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_member(ctx, member: discord.Member, *, raison: str = "Aucune raison fournie"):
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    try:
        await member.ban(reason=f"Par {ctx.author} - {raison}")
        await ctx.send(embed=discord.Embed(title="🔨 Membre banni", description=f"{member.display_name} a été banni.\nRaison: {raison}", color=discord.Color.red()))
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de bannir ce membre.")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, raison: str = "Aucune raison fournie"):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas t'expulser toi-même !")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    try:
        await member.kick(reason=f"Par {ctx.author} - {raison}")
        await ctx.send(embed=discord.Embed(title="👢 Membre expulsé", description=f"{member.display_name} expulsé. Raison: {raison}", color=discord.Color.orange()))
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission d'expulser ce membre.")

@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute_member(ctx, member: discord.Member, duration: int = 10, *, raison: str = "Aucune raison fournie"):
    if duration > 40320:
        return await ctx.send("❌ Durée maximale : 40320 minutes (28 jours) !")
    try:
        until = datetime.utcnow() + timedelta(minutes=duration)
        await member.timeout(until, reason=f"Par {ctx.author} - {raison}")
        await ctx.send(embed=discord.Embed(title="🔇 Membre timeout", description=f"{member.display_name} timeout pour {duration} minutes.", color=discord.Color.orange()))
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission pour timeout ce membre.")

@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute_member(ctx, member: discord.Member):
    if member.timed_out_until is None:
        return await ctx.send("❌ Ce membre n'est pas en timeout.")
    try:
        await member.timeout(None, reason=f"Démuté par {ctx.author}")
        await ctx.send(embed=discord.Embed(title="🔊 Membre démuté", description=f"{member.display_name} peut de nouveau parler.", color=discord.Color.green()))
    except Exception as e:
        await ctx.send(f"❌ Erreur: {e}")

@bot.command(name="clear", aliases=["purge","clean"])
@commands.has_permissions(manage_messages=True)
async def clear_cmd(ctx, amount: int = 10):
    if amount > 100:
        return await ctx.send("❌ Maximum 100 messages.")
    deleted = await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"✅ {len(deleted)-1} messages supprimés.", delete_after=5)

@bot.command(name="warn")
@commands.has_permissions(kick_members=True)
async def warn_member(ctx, member: discord.Member, *, raison: str):
    if member.bot:
        return await ctx.send("❌ Tu ne peux pas avertir un bot.")
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas t'avertir toi-même.")
    w = data_manager.add_warning(ctx.guild.id, member.id, ctx.author.id, raison)
    await ctx.send(embed=discord.Embed(title="🚨 Avertissement", description=f"{member.mention} averti. Raison: {raison}", color=discord.Color.orange()))
    try:
        await member.send(f"🚨 Avertissement sur {ctx.guild.name}: Raison: {raison}")
    except discord.Forbidden:
        pass

@bot.command(name="warnings")
@commands.has_permissions(kick_members=True)
async def warnings_cmd(ctx, member: discord.Member):
    warns = data_manager.get_user_warnings(member.id)
    if not warns:
        return await ctx.send(f"✅ {member.display_name} n'a aucun avertissement.")
    txt = ""
    for w in warns:
        date = datetime.fromisoformat(w["timestamp"]).strftime("%d/%m/%Y %H:%M")
        mod = await bot.fetch_user(int(w["moderator_id"]))
        txt += f"ID {w['id']} — {date} — {mod.name}: {w['reason']}\n"
    await ctx.send(embed=discord.Embed(title=f"Avertissements de {member.display_name}", description=txt[:1900]))

@bot.command(name="delwarn", aliases=["unwarn","remwarn"])
@commands.has_permissions(administrator=True)
async def delwarn_cmd(ctx, member: discord.Member, warn_id: int):
    ok = data_manager.remove_warning(member.id, warn_id)
    if ok:
        await ctx.send("✅ Avertissement supprimé.")
    else:
        await ctx.send("❌ Avertissement introuvable.")

@bot.command(name="say")
@commands.has_permissions(manage_messages=True)
async def say_cmd(ctx, channel: discord.TextChannel, *, message: str):
    try:
        await channel.send(message)
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission d'envoyer dans ce salon.")

@bot.command(name="embed")
@commands.has_permissions(administrator=True)
async def embed_cmd(ctx, channel: discord.TextChannel, *, content: str):
    if '|' not in content:
        return await ctx.send("❌ Format invalide. Utilisez: Titre | Description")
    title, desc = content.split('|',1)
    embed = discord.Embed(title=title.strip(), description=desc.strip(), color=discord.Color.blue(), timestamp=datetime.now())
    await channel.send(embed=embed)
    await ctx.message.delete()

# -------------------- Voice commands (createvoc fixed) --------------------
@bot.command(name="createvoc")
@commands.has_permissions(manage_channels=True)
async def create_voc(ctx, *, name: str = None):
    guild = ctx.guild
    author = ctx.author
    name = name or f"Vocal de {author.display_name}"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True),
        author: discord.PermissionOverwrite(connect=True, manage_channels=True, view_channel=True),
        guild.me: discord.PermissionOverwrite(view_channel=True)
    }
    try:
        channel = await guild.create_voice_channel(name=name, overwrites=overwrites, reason=f"Créé par {author}")
        await ctx.send(f"✅ Salon vocal créé : **{channel.name}** ({channel.id})")
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de créer des salons vocaux.")
    except Exception as e:
        await ctx.send(f"⚠️ Erreur: {e}")

@bot.command(name="lockvoc")
@commands.has_permissions(manage_channels=True)
async def lock_voc(ctx, channel: discord.VoiceChannel = None):
    channel = channel or ctx.author.voice.channel if ctx.author.voice else None
    if not channel:
        return await ctx.send("❌ Aucun salon vocal spécifié ou vous n'êtes pas en vocal.")
    try:
        await channel.set_permissions(ctx.guild.default_role, connect=False)
        await ctx.send(f"🔒 Salon vocal **{channel.name}** verrouillé.")
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de modifier les permissions du salon.")
    except Exception as e:
        await ctx.send(f"⚠️ Erreur: {e}")

@bot.command(name="renamevoc")
@commands.has_permissions(manage_channels=True)
async def rename_voc(ctx, channel: discord.VoiceChannel = None, *, new_name: str = None):
    channel = channel or ctx.author.voice.channel if ctx.author.voice else None
    if not channel or not new_name:
        return await ctx.send("❌ Usage: +renamevoc [#vocal] NouveauNom")
    try:
        await channel.edit(name=new_name, reason=f"Renommé par {ctx.author}")
        await ctx.send(f"✏️ Salon renommé en **{new_name}**.")
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de renommer ce salon.")
    except Exception as e:
        await ctx.send(f"⚠️ Erreur: {e}")

# -------------------- Leveling commands --------------------
@bot.command(name="rank", aliases=["niveau"])
async def rank_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = data_manager._level(member.id)
    level = data.get("level",0)
    xp = data.get("xp",0)
    req = 1000 + level*250
    progress = int((xp / req) * 15) if req else 15
    bar = "🟦"*progress + "⬜"*(15-progress)
    embed = discord.Embed(title=f"📈 Niveau de {member.display_name}", color=discord.Color.purple())
    embed.add_field(name="Niveau", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp}/{req}", inline=True)
    embed.add_field(name="Progression", value=f"{bar}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb","top"])
async def leaderboard_cmd(ctx):
    levels = data_manager.data.get("levels", {})
    if not levels:
        return await ctx.send("❌ Aucun utilisateur n'a encore d'XP.")
    sorted_users = sorted(levels.items(), key=lambda kv: (kv[1].get("level",0), kv[1].get("xp",0)), reverse=True)
    top10 = sorted_users[:10]
    text = ""
    rank = 1
    for uid, info in top10:
        try:
            user = await bot.fetch_user(int(uid))
            name = user.name
        except:
            name = f"Utilisateur {uid}"
        text += f"`#{rank}` **{name}** — Niveau {info.get('level',0)} ({info.get('xp',0)} XP)\n"
        rank += 1
    await ctx.send(embed=discord.Embed(title="🏆 Top Niveaux", description=text, color=discord.Color.gold()))

# -------------------- Economy & Giveaways --------------------
@bot.command(name="balance", aliases=["bal","money"])
async def balance_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = data_manager.get_balance(member.id)
    await ctx.send(embed=discord.Embed(title=f"💰 Solde de {member.display_name}", description=f"**{bal}** ⭐", color=discord.Color.gold()))

@bot.command(name="daily")
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily_cmd(ctx):
    amount = 500
    data_manager.update_balance(ctx.author.id, amount)
    data_manager.set_last_daily(ctx.author.id)
    bal = data_manager.get_balance(ctx.author.id)
    await ctx.send(embed=discord.Embed(title="🎁 Daily", description=f"Tu as reçu {amount} ⭐. Nouveau solde: {bal}"))

@bot.command(name="work")
@commands.cooldown(1, 14400, commands.BucketType.user)
async def work_cmd(ctx):
    gain = random.randint(150,450)
    data_manager.update_balance(ctx.author.id, gain)
    data_manager.set_last_work(ctx.author.id)
    await ctx.send(embed=discord.Embed(title="💼 Work", description=f"Tu as gagné {gain} ⭐. Nouveau solde: {data_manager.get_balance(ctx.author.id)}"))

@bot.command(name="gstart", aliases=["giveaway","startgiveaway"])
@commands.has_permissions(administrator=True)
async def gstart_cmd(ctx, duration: str, winners: int, *, prize: str):
    try:
        unit = duration[-1]
        val = int(duration[:-1])
        if unit == "s": delta = timedelta(seconds=val)
        elif unit == "m": delta = timedelta(minutes=val)
        elif unit == "h": delta = timedelta(hours=val)
        elif unit == "d": delta = timedelta(days=val)
        else:
            return await ctx.send("❌ Format durée invalide. Ex: 1h, 30m, 5s")
    except:
        return await ctx.send("❌ Format durée invalide. Ex: 1h, 30m, 5s")
    end_time = datetime.now() + delta
    embed = discord.Embed(title=f"🎉 Giveaway: {prize}", description=f"Réagissez avec 🎁 pour participer!\nGagnants: {winners}\nFin: {end_time.isoformat()}", color=discord.Color.dark_magenta(), timestamp=end_time)
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎁")
    active_giveaways.append({"message_id": msg.id, "channel_id": ctx.channel.id, "end_time": end_time, "winners": winners, "prize": prize, "host": ctx.author.id})

@bot.command(name="addmoney")
@commands.has_permissions(administrator=True)
async def addmoney_cmd(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("❌ Le montant doit être positif.")
    new = data_manager.update_balance(member.id, amount)
    await ctx.send(f"✅ {amount} ⭐ ajoutés à {member.mention}. Nouveau solde: {new}")

@bot.command(name="setmoney")
@commands.has_permissions(administrator=True)
async def setmoney_cmd(ctx, member: discord.Member, amount: int):
    if amount < 0:
        return await ctx.send("❌ Le montant ne peut pas être négatif.")
    old = data_manager.set_balance(member.id, amount)
    await ctx.send(f"✅ Solde de {member.mention} défini à {amount} ⭐")

# -------------------- Fun & Utilities --------------------
@bot.command(name="hug")
async def hug_cmd(ctx, member: discord.Member = None):
    gifs = ["https://i.imgur.com/k3qA04l.png","https://i.imgur.com/gD68k80.png"]
    target = member or ctx.author
    if member and member.bot:
        return await ctx.send("🤖 Tu ne peux pas faire un câlin à un bot.")
    embed = discord.Embed(description=f"🫂 {ctx.author.display_name} fait un câlin à {target.display_name}", color=discord.Color.red())
    embed.set_image(url=random.choice(gifs))
    await ctx.send(embed=embed)

@bot.command(name="meme")
async def meme_cmd(ctx):
    await ctx.send("😂 Mème aléatoire")
    await ctx.send("https://i.imgur.com/gD68k80.png")

@bot.command(name="coin", aliases=["flip"])
async def coin_cmd(ctx):
    result = random.choice(["Pile","Face"])
    await ctx.send(f"👑 {ctx.author.display_name} a lancé une pièce : **{result}**")

@bot.command(name="dice", aliases=["dé","roll"])
async def dice_cmd(ctx, faces: int = 6):
    if faces < 2 or faces > 100:
        return await ctx.send("❌ Nombre de faces entre 2 et 100.")
    await ctx.send(f"🎲 {ctx.author.display_name} a lancé un dé ({faces} faces). Résultat: **{random.randint(1,faces)}**")

@bot.command(name="8ball")
async def eightball_cmd(ctx, *, question: str):
    responses = ["Oui.", "Non.", "Peut-être.", "Réessaie plus tard.", "Les signes pointent vers oui.", "Mes sources disent non."]
    await ctx.send(embed=discord.Embed(title="🎱 8Ball", description=f"**Question:** {question}\n**Réponse:** {random.choice(responses)}"))

@bot.command(name="ping")
async def ping_cmd(ctx):
    await ctx.send(f"🏓 Pong! Latence: {round(bot.latency*1000)}ms")

@bot.command(name="avatar", aliases=["pfp","pp"])
async def avatar_cmd(ctx, member: discord.Member = None):
    m = member or ctx.author
    await ctx.send(embed=discord.Embed(title=f"Avatar de {m.display_name}").set_image(url=m.display_avatar.url))

@bot.command(name="userinfo", aliases=["ui"])
async def userinfo_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    roles_val = ", ".join(roles[:10]) + (f", et {len(roles)-10} de plus..." if len(roles) > 10 else "")
    embed = discord.Embed(title=f"👤 {member.display_name}", color=member.color, timestamp=datetime.now())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Nom", value=member.name)
    embed.add_field(name="Surnom", value=member.nick or "—")
    embed.add_field(name="Créé le", value=member.created_at.strftime("%d/%m/%Y %H:%M"))
    embed.add_field(name="A rejoint", value=member.joined_at.strftime("%d/%m/%Y %H:%M") if member.joined_at else "—")
    embed.add_field(name=f"Rôles ({len(roles)})", value=roles_val, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="serverinfo", aliases=["si"])
async def serverinfo_cmd(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"📊 {g.name}", color=discord.Color.blue(), timestamp=datetime.now())
    embed.set_thumbnail(url=g.icon.url if g.icon else None)
    embed.add_field(name="ID", value=g.id)
    embed.add_field(name="Propriétaire", value=g.owner.mention if g.owner else "—")
    embed.add_field(name="Membres", value=g.member_count)
    embed.add_field(name="Canaux texte", value=len(g.text_channels))
    embed.add_field(name="Canaux vocaux", value=len(g.voice_channels))
    embed.add_field(name="Rôles", value=len(g.roles))
    embed.add_field(name="Boosts", value=g.premium_subscription_count)
    embed.add_field(name="Créé le", value=g.created_at.strftime("%d/%m/%Y"))
    await ctx.send(embed=embed)

@bot.command(name="traduction", aliases=["translate"])
async def translate_cmd(ctx, target_lang: str, *, text: str):
    # Simulé (pas d'API) : retourne le texte préfixé
    await ctx.send(embed=discord.Embed(title=f"🌐 Traduction ({target_lang})", description=f"```\n{text}\n```", color=discord.Color.green()))

# -------------------- Misc: create roles panel, rules --------------------
@bot.command(name="sendrules")
@commands.has_permissions(administrator=True)
async def send_rules_cmd(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    embed = discord.Embed(title="📜 Règles du serveur", description="Respecte les règles. Pas de spam.", color=discord.Color.blue())
    await target.send(embed=embed)
    await ctx.send(f"✅ Règles envoyées dans {target.mention}", delete_after=5)

# -------------------- Startup --------------------
if __name__ == "__main__":
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN non défini.")
    else:
        print("🚀 Démarrage du bot...")
        try:
            giveaway_task.start()
        except RuntimeError:
            pass
        bot.run(TOKEN)
