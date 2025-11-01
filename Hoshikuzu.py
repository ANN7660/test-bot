# Hoshikuzu_final.py
# Version nettoyée et consolidée pour déploiement sur Render.
# Préfixe : +
# Token attendu dans la variable d'environnement DISCORD_TOKEN

import os
import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import random
import json
import math
import threading, http.server, socketserver

# -------------------- Configuration minimale --------------------
ARROW_EMOJI = "<a:caarrow:1433143710094196997>"

# Dictionnaires de config en mémoire (peuvent être persistés via DataManager)
CONFIG_CHANNELS = {}
CONFIG_ROLES = {}

# -------------------- Keep-alive (Render) --------------------
def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"✅ Serveur keep-alive lancé sur le port {port}")
        httpd.serve_forever()

# -------------------- Data manager --------------------
class DataManager:
    def __init__(self, filename="bot_data.json"):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("⚠️ JSON corrompu, réinitialisation.")
        # structure par défaut
        return {"economy": {}, "warnings": {}, "levels": {}, "config": {}}

    def _save_data(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    # warnings
    def get_user_warnings(self, user_id):
        return self.data.get("warnings", {}).get(str(user_id), [])

    def add_warning(self, guild_id, user_id, moderator_id, reason):
        uid = str(user_id)
        warn_list = self.data.setdefault("warnings", {}).setdefault(uid, [])
        warn_id = len(warn_list) + 1
        warn = {"id": warn_id, "timestamp": datetime.now().isoformat(), "moderator_id": str(moderator_id), "reason": reason}
        warn_list.append(warn)
        self._save_data()
        return warn

    def remove_warning(self, user_id, warn_id):
        uid = str(user_id)
        warns = self.data.get("warnings", {}).get(uid, [])
        new = [w for w in warns if w.get("id") != warn_id]
        if len(new) < len(warns):
            self.data["warnings"][uid] = new
            self._save_data()
            return True
        return False

    # economy
    def _get_eco(self, user_id):
        uid = str(user_id)
        econ = self.data.setdefault("economy", {}).setdefault(uid, {"balance": 0, "last_daily": None, "last_work": None})
        return econ

    def get_balance(self, user_id):
        return self._get_eco(user_id).get("balance", 0)

    def update_balance(self, user_id, amount):
        eco = self._get_eco(user_id)
        eco["balance"] = eco.get("balance", 0) + amount
        self._save_data()
        return eco["balance"]

    def set_balance(self, user_id, amount):
        eco = self._get_eco(user_id)
        eco["balance"] = amount
        self._save_data()
        return eco["balance"]

    def get_last_daily(self, user_id):
        s = self._get_eco(user_id).get("last_daily")
        return datetime.fromisoformat(s) if s else None

    def set_last_daily(self, user_id):
        eco = self._get_eco(user_id)
        eco["last_daily"] = datetime.now().isoformat()
        self._save_data()

    def get_last_work(self, user_id):
        s = self._get_eco(user_id).get("last_work")
        return datetime.fromisoformat(s) if s else None

    def set_last_work(self, user_id):
        eco = self._get_eco(user_id)
        eco["last_work"] = datetime.now().isoformat()
        self._save_data()

    # leveling
    def _get_level(self, user_id):
        uid = str(user_id)
        return self.data.setdefault("levels", {}).setdefault(uid, {"level": 0, "xp": 0})

    def add_xp(self, user_id, xp_amount):
        user = self._get_level(user_id)
        user["xp"] += xp_amount
        lvl = user["level"]
        # simple formule d'XP
        def req(l): return 1000 + l * 250
        leveled = None
        while user["xp"] >= req(lvl + 1):
            user["xp"] -= req(lvl + 1)
            lvl += 1
            user["level"] = lvl
            leveled = lvl
        self._save_data()
        return leveled

data_manager = DataManager()

# -------------------- Helpers --------------------
def get_channel_by_config(key):
    cid = CONFIG_CHANNELS.get(key) or data_manager.data.get("config", {}).get(key)
    if cid is None: 
        return None
    try:
        cid = int(cid)
    except:
        return None
    # returned at runtime by bot.get_channel
    return cid

def get_role_by_config(key):
    rid = CONFIG_ROLES.get(key) or data_manager.data.get("config", {}).get(key)
    if rid is None: 
        return None
    try:
        rid = int(rid)
    except:
        return None
    return rid

# cache pour cooldowns leveling
xp_cooldown_cache = {}

# -------------------- Bot init --------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="+", intents=intents)
bot.remove_command('help')  # on remplace par notre propre help

# -------------------- Views --------------------
class RoleButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📢 Annonces", style=discord.ButtonStyle.secondary, custom_id="role_annonces_id")
    async def role_annonces_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ROLE_ID = 1433143710094196998
        await self.toggle_role(interaction, ROLE_ID, "Annonces")

    @discord.ui.button(label="🎉 Événements", style=discord.ButtonStyle.secondary, custom_id="role_evenements_id")
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

    @discord.ui.button(label="📩 Ouvrir un Ticket", style=discord.ButtonStyle.blurple, custom_id="ticket_button_create")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        category_id = CONFIG_CHANNELS.get("TICKET_CATEGORY_ID") or data_manager.data.get("config", {}).get("TICKET_CATEGORY_ID")
        support_role_id = CONFIG_ROLES.get("SUPPORT_ROLE_ID") or data_manager.data.get("config", {}).get("SUPPORT_ROLE_ID")
        support_role = guild.get_role(int(support_role_id)) if support_role_id else None

        if not category_id or not support_role:
            await interaction.response.send_message("❌ Configuration manquante : catégorie ou rôle de support.", ephemeral=True)
            return

        category = guild.get_channel(int(category_id))
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ La catégorie de ticket est invalide.", ephemeral=True)
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

    @discord.ui.button(label="🔒 Fermer le Ticket", style=discord.ButtonStyle.red, custom_id="ticket_button_close")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ Ce n'est pas un canal de ticket.", ephemeral=True)
            return
        # check permissions
        await interaction.response.send_message("🔒 Ticket fermé. Suppression dans 5s...", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user.display_name}")
        except discord.Forbidden:
            logs = get_channel_by_config("LOGS_CHANNEL_ID")
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
    # register persistent views
    bot.add_view(TicketCreateView(bot))
    bot.add_view(TicketCloseView())
    bot.add_view(RoleButtonView())
    giveaway_task.start()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    user_id = message.author.id
    now = datetime.now()
    last = xp_cooldown_cache.get(user_id)
    if last is None or (now - last).total_seconds() >= 60:
        xp = random.randint(5, 15)
        new_lvl = data_manager.add_xp(user_id, xp)
        xp_cooldown_cache[user_id] = now
        if new_lvl:
            await message.channel.send(f"✨ {message.author.mention} passe niveau {new_lvl} !")
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    # welcome embed
    try:
        embed_channel = None
        cid = get_channel_by_config("WELCOME_EMBED_CHANNEL_ID")
        if cid:
            embed_channel = bot.get_channel(int(cid))
        if embed_channel:
            member_count = member.guild.member_count
            we = discord.Embed(title="🌸 Bienvenue sur Hoshikuzu !", description=f"Salut {member.mention} !", color=discord.Color.purple(), timestamp=datetime.now())
            we.set_thumbnail(url=member.display_avatar.url)
            await embed_channel.send(embed=we)
        # DM welcome
        try:
            dm = discord.Embed(title="🎉 Bienvenue !", description="Amuse-toi bien !", color=discord.Color.green())
            await member.send(embed=dm)
        except discord.Forbidden:
            pass
    except Exception as e:
        print("Erreur on_member_join:", e)

@bot.event
async def on_message_edit(before, after):
    # simple log example
    try:
        logs = get_channel_by_config("LOGS_CHANNEL_ID")
        if logs:
            ch = bot.get_channel(int(logs))
            if ch:
                embed = discord.Embed(title="📝 Message Modifié", color=discord.Color.dark_teal(), timestamp=datetime.now())
                embed.add_field(name="Auteur", value=before.author.mention)
                embed.add_field(name="Avant", value=(before.content[:500] or "—"))
                embed.add_field(name="Après", value=(after.content[:500] or "—"))
                await ch.send(embed=embed)
    except Exception:
        pass

@bot.event
async def on_member_ban(guild, user):
    try:
        logs = get_channel_by_config("LOGS_CHANNEL_ID")
        if logs:
            ch = bot.get_channel(int(logs))
            if ch:
                embed = discord.Embed(title="🔨 Membre Banni", description=f"{user}", color=discord.Color.red(), timestamp=datetime.now())
                await ch.send(embed=embed)
    except Exception:
        pass

# -------------------- Background tasks --------------------
active_giveaways = []

@tasks.loop(seconds=5)
async def giveaway_task():
    now = datetime.now()
    for g in active_giveaways[:]:
        if now >= g.get("end_time"):
            active_giveaways.remove(g)
            await end_giveaway(g)

async def end_giveaway(g):
    channel = bot.get_channel(g.get("channel_id"))
    if not channel: return
    try:
        msg = await channel.fetch_message(g.get("message_id"))
    except:
        return
    reaction = discord.utils.get(msg.reactions, emoji='🎁')
    if reaction:
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            await channel.send("❌ Aucun participant valide.")
            return
        winners = random.sample(users, min(g.get("winners",1), len(users)))
        mentions = ", ".join([w.mention for w in winners])
        await channel.send(f"🎉 Gagnant(s): {mentions} — {g.get('prize')}")

# -------------------- Commands --------------------
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="Hoshikuzu - Commandes", color=discord.Color.blue())
    embed.add_field(name="🎙️ Vocaux", value="`+createvoc` `+lockvoc` `+renamevoc`", inline=False)
    embed.add_field(name="💰 Économie", value="`+balance` `+daily` `+work` `+give @user amount`", inline=False)
    embed.add_field(name="🧾 Modération", value="`+warn @user reason` `+warnings @user` `+delwarn @user id` `+clear`", inline=False)
    embed.add_field(name="🎉 Fun", value="`+meme` `+hug @user` `+avatar @user`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="balance")
async def show_balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = data_manager.get_balance(member.id)
    await ctx.send(embed=discord.Embed(title=f"💰 Solde de {member.display_name}", description=f"**{bal}** ⭐", color=discord.Color.gold()))

@bot.command(name="daily")
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily_money(ctx):
    amount = 500
    data_manager.update_balance(ctx.author.id, amount)
    data_manager.set_last_daily(ctx.author.id)
    bal = data_manager.get_balance(ctx.author.id)
    await ctx.send(embed=discord.Embed(title="🎁 Récompense Quotidienne", description=f"Tu as reçu {amount} ⭐. Nouveau solde: {bal}"))

@daily_money.error
async def daily_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        rem = int(error.retry_after)
        h = rem//3600; m = (rem%3600)//60; s = rem%60
        await ctx.send(f"⏳ Reviens dans {h}h {m}m {s}s.")
    else:
        raise error

@bot.command(name="work")
@commands.cooldown(1, 14400, commands.BucketType.user)
async def work_command(ctx):
    gain = random.randint(150, 450)
    data_manager.update_balance(ctx.author.id, gain)
    await ctx.send(embed=discord.Embed(title="💼 Travail", description=f"Tu as gagné {gain} ⭐. Nouveau solde: {data_manager.get_balance(ctx.author.id)}"))

@bot.command(name="warn")
@commands.has_permissions(kick_members=True)
async def warn_member(ctx, member: discord.Member, *, raison: str):
    if member.bot: return await ctx.send("❌ Cannot warn bots.")
    if member == ctx.author: return await ctx.send("❌ Tu ne peux pas te warn toi-même.")
    w = data_manager.add_warning(ctx.guild.id, member.id, ctx.author.id, raison)
    await ctx.send(embed=discord.Embed(title="🚨 Avertissement", description=f"{member.mention} a été averti. Raison: {raison}"))

@bot.command(name="warnings")
@commands.has_permissions(kick_members=True)
async def check_warnings(ctx, member: discord.Member):
    warns = data_manager.get_user_warnings(member.id)
    if not warns: return await ctx.send(f"✅ {member.display_name} n'a aucun avertissement.")
    txt = ""
    for w in warns:
        date = datetime.fromisoformat(w["timestamp"]).strftime("%d/%m/%Y %H:%M")
        mod = await bot.fetch_user(int(w["moderator_id"]))
        txt += f"ID {w['id']} — {date} — {mod.name}: {w['reason']}\n"
    await ctx.send(embed=discord.Embed(title=f"Avertissements de {member.display_name}", description=txt[:1900]))

@bot.command(name="delwarn")
@commands.has_permissions(administrator=True)
async def del_warn(ctx, member: discord.Member, warn_id: int):
    ok = data_manager.remove_warning(member.id, warn_id)
    if ok:
        await ctx.send("✅ Avertissement supprimé.")
    else:
        await ctx.send("❌ Avertissement introuvable.")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latence: {round(bot.latency*1000)}ms")

@bot.command(name="hug")
async def hug(ctx, member: discord.Member = None):
    gifs = ["https://i.imgur.com/k3qA04l.png","https://i.imgur.com/gD68k80.png"]
    target = member or ctx.author
    if member and member.bot:
        await ctx.send("🤖 Tu ne peux pas faire un câlin à un bot.")
    else:
        await ctx.send(embed=discord.Embed(description=f"🫂 {ctx.author.display_name} fait un câlin à {target.display_name}", color=discord.Color.red()).set_image(url=random.choice(gifs)))

@bot.command(name="meme")
async def meme(ctx):
    await ctx.send("😂 Voici un mème !")
    await ctx.send("https://i.imgur.com/gD68k80.png")

@bot.command(name="avatar")
async def avatar(ctx, member: discord.Member = None):
    m = member or ctx.author
    await ctx.send(embed=discord.Embed(title=f"Avatar de {m.display_name}").set_image(url=m.display_avatar.url))

@bot.command(name="say")
@commands.has_permissions(manage_messages=True)
async def say_message(ctx, channel: discord.TextChannel, *, message: str):
    try:
        await channel.send(message)
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission d'envoyer dans ce salon.")

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    if amount > 100: return await ctx.send("❌ Max 100 messages.")
    deleted = await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"✅ {len(deleted)-1} messages supprimés.", delete_after=5)

# -------------------- Startup --------------------
if __name__ == "__main__":
    # démarrage du keep-alive dans un thread (Render)
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN non défini dans les variables d'environnement.")
    else:
        print("🚀 Démarrage du bot...")
        bot.run(TOKEN)
