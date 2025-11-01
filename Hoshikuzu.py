# Hoshikuzu_ultimate.py
# Version Ultimate — Hoshikuzu Bot
# Préfixe: +
# Configure DISCORD_TOKEN and (optionally) OPENAI_API_KEY in environment variables for Render.

import os
import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import random
import json
import math
import threading, http.server, socketserver
# --- Correction manuelle Hoshikuzu Config Deluxe (global definition) ---
import discord
from discord.ext import commands
from keep_alive import keep_alive
keep_alive()


def setup_config_commands(bot, data_manager):

    class ConfigModal(discord.ui.Modal):
        def __init__(self, field_key: str, label: str):
            super().__init__(title=f"Configurer {label}")
            self.field_key = field_key
            self.add_item(discord.ui.InputText(label=f"Salon ou rôle pour {label}", placeholder="Mentionne un salon ou un rôle", required=True))

        async def callback(self, interaction: discord.Interaction):
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ Seuls les administrateurs peuvent modifier la configuration.", ephemeral=True)
            value = self.children[0].value
            if value.startswith("<#"):
                value = value.strip("<#>")
            elif value.startswith("<@&"):
                value = value.strip("<@&>")
            data_manager.set_guild_config(interaction.guild.id, self.field_key, str(value))
            await interaction.response.send_message(f"✅ **{self.field_key}** mis à jour avec succès !", ephemeral=True)

    class ConfigView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="🪵 Logs", style=discord.ButtonStyle.blurple)
        async def logs(self, button, interaction): 
            await interaction.response.send_modal(ConfigModal("LOGS_CHANNEL_ID", "Salon de logs"))

        @discord.ui.button(label="💎 Boost", style=discord.ButtonStyle.blurple)
        async def boost(self, button, interaction): 
            await interaction.response.send_modal(ConfigModal("BOOST_CHANNEL_ID", "Salon de boost"))

        @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.blurple)
        async def tickets(self, button, interaction): 
            await interaction.response.send_modal(ConfigModal("TICKET_CATEGORY_ID", "Catégorie de tickets"))

        @discord.ui.button(label="👥 Support", style=discord.ButtonStyle.blurple)
        async def support(self, button, interaction): 
            await interaction.response.send_modal(ConfigModal("SUPPORT_ROLE_ID", "Rôle support"))

        @discord.ui.button(label="🌸 Welcome", style=discord.ButtonStyle.secondary)
        async def welcome(self, button, interaction): 
            await interaction.response.send_modal(ConfigModal("WELCOME_EMBED_CHANNEL_ID", "Salon de bienvenue"))

        @discord.ui.button(label="🚪 Leave", style=discord.ButtonStyle.secondary)
        async def leave(self, button, interaction): 
            await interaction.response.send_modal(ConfigModal("LEAVE_CHANNEL_ID", "Salon de départ"))

        @discord.ui.button(label="🪄 Panneau Tickets", style=discord.ButtonStyle.success)
        async def send_ticket(self, button, interaction): 
            await interaction.response.send_message("Utilisez `+sendticketpanel` pour envoyer le panneau ici.", ephemeral=True)

        @discord.ui.button(label="🎭 Panneau Rôles", style=discord.ButtonStyle.success)
        async def send_roles(self, button, interaction): 
            await interaction.response.send_message("Utilisez `+sendrolespanel` pour envoyer le panneau ici.", ephemeral=True)

    
    @commands.has_permissions(administrator=True)
    async def config_cmd(ctx):
        embed = discord.Embed(
            title="⚙️ Configuration du serveur Hoshikuzu ✨",
            description="Utilisez les boutons ci-dessous pour configurer les salons et rôles.\n*(Visible par tous, modification admin seulement)*",
            color=discord.Color.dark_purple()
        )
        embed.set_footer(text="Hoshikuzu System ©")
        await ctx.send(embed=embed, view=ConfigView())

    
    async def test_cmd(ctx, type: str = None):
        if type == "welcomesimple":
            await ctx.send(f"👋 Bienvenue {ctx.author.mention} sur le serveur Hoshikuzu ! 🌸 (simulation)")
        elif type == "welcomeembed":
            embed = discord.Embed(
                title="🌸 Bienvenue sur Hoshikuzu !",
                description=f"Salut {ctx.author.mention}, ravi de t’accueillir ici 💫 (simulation)",
                color=discord.Color.magenta()
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            embed.set_footer(text="Hoshikuzu System ©")
            await ctx.send(embed=embed)
        elif type == "leave":
            await ctx.send(f"👋 {ctx.author.display_name} a quitté le serveur... 😢 (simulation)")
        elif type == "boost":
            embed = discord.Embed(
                title="💎 Merci pour le boost !",
                description=f"{ctx.author.mention} a soutenu le serveur ✨ Merci infiniment 🌸 (simulation)",
                color=discord.Color.purple()
            )
            embed.set_footer(text="Hoshikuzu System ©")
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Types disponibles : welcomesimple | welcomeembed | leave | boost")

# --- Fin de la correction manuelle ---



# --- Configuration Deluxe Definition (global) ---



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
                print("⚠️ JSON corrompu — réinitialisation.")
        # default structure
        return {"economy": {}, "warnings": {}, "levels": {}, "config": {}, "giveaways": [], "shop": {}, "inventories": {}, "badges": {}, "stats": {}, "automod": {"enabled": False, "words": []}}

    def _save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    # Guild config
    def get_guild_config(self, guild_id):
        gid = str(guild_id)
        return self.data.setdefault("config", {}).setdefault(gid, {})

    def set_guild_config(self, guild_id, key, value):
        cfg = self.get_guild_config(guild_id)
        cfg[key] = value
        self._save()
        return cfg

    # Economy
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

    # Inventory / shop
    def get_shop(self):
        # return shop dict; initialize with defaults if empty
        shop = self.data.setdefault("shop", {})
        if not shop:
            shop.update({
                "VIP Role": {"price": 5000, "desc": "Rôle VIP temporaire (à donner manuellement)"},
                "XP Booster": {"price": 2000, "desc": "Double XP pour une période (admin doit appliquer)"},
                "Custom Title": {"price": 1000, "desc": "Titre personnalisé (stockage seulement)"}
            })
            self._save()
        return shop

    def get_inventory(self, user_id):
        uid = str(user_id)
        return self.data.setdefault("inventories", {}).setdefault(uid, {})

    def add_inventory_item(self, user_id, item, qty=1):
        inv = self.get_inventory(user_id)
        inv[item] = inv.get(item, 0) + qty
        self._save()

    def remove_inventory_item(self, user_id, item, qty=1):
        inv = self.get_inventory(user_id)
        if inv.get(item,0) >= qty:
            inv[item] -= qty
            if inv[item] <= 0:
                del inv[item]
            self._save()
            return True
        return False

    # Warnings
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

    # Leveling & stats
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
        # track messages count in stats
        stats = self.data.setdefault("stats", {}).setdefault(str(user_id), {"messages":0, "tickets":0})
        self._save()
        return leveled

    def incr_stat(self, user_id, key, amount=1):
        s = self.data.setdefault("stats", {}).setdefault(str(user_id), {"messages":0, "tickets":0})
        s[key] = s.get(key,0) + amount
        self._save()
        return s[key]

    # Badges
    def get_badges(self, user_id):
        return self.data.setdefault("badges", {}).setdefault(str(user_id), [])

    def add_badge(self, user_id, badge_name):
        badges = self.get_badges(user_id)
        if badge_name not in badges:
            badges.append(badge_name)
            self._save()
            return True
        return False

    # Automod
    def automod_enabled(self):
        return self.data.get("automod", {}).get("enabled", False)

    def automod_words(self):
        return self.data.get("automod", {}).get("words", [])

    def add_automod_word(self, word):
        words = self.data.setdefault("automod", {}).setdefault("words", [])
        if word not in words:
            words.append(word)
            self._save()
            return True
        return False

    def del_automod_word(self, word):
        words = self.data.setdefault("automod", {}).setdefault("words", [])
        if word in words:
            words.remove(word)
            self._save()
            return True
        return False

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


# --- Inlined Hoshikuzu_config_deluxe (merged) ---
# ----- Modal de configuration -----
class ConfigModal(discord.ui.Modal):
    def __init__(self, field_key: str, label: str):
        super().__init__(title=f"Configurer {label}")
        self.field_key = field_key
        self.add_item(discord.ui.InputText(label=f"Salon ou rôle pour {label}", placeholder="Mentionne un salon ou un rôle", required=True))

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Seuls les administrateurs peuvent modifier la configuration.", ephemeral=True)
        value = self.children[0].value
        if value.startswith("<#"):
            value = value.strip("<#>")
        elif value.startswith("<@&"):
            value = value.strip("<@&>")
        data_manager.set_guild_config(interaction.guild.id, self.field_key, str(value))
        await interaction.response.send_message(f"✅ **{self.field_key}** mis à jour avec succès !", ephemeral=True)

# ----- Vue principale -----
class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🪵 Logs", style=discord.ButtonStyle.blurple)
    async def logs(self, button, interaction): 
        await interaction.response.send_modal(ConfigModal("LOGS_CHANNEL_ID", "Salon de logs"))

    @discord.ui.button(label="💎 Boost", style=discord.ButtonStyle.blurple)
    async def boost(self, button, interaction): 
        await interaction.response.send_modal(ConfigModal("BOOST_CHANNEL_ID", "Salon de boost"))

    @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.blurple)
    async def tickets(self, button, interaction): 
        await interaction.response.send_modal(ConfigModal("TICKET_CATEGORY_ID", "Catégorie de tickets"))

    @discord.ui.button(label="👥 Support", style=discord.ButtonStyle.blurple)
    async def support(self, button, interaction): 
        await interaction.response.send_modal(ConfigModal("SUPPORT_ROLE_ID", "Rôle support"))

    @discord.ui.button(label="🌸 Welcome", style=discord.ButtonStyle.secondary)
    async def welcome(self, button, interaction): 
        await interaction.response.send_modal(ConfigModal("WELCOME_EMBED_CHANNEL_ID", "Salon de bienvenue"))

    @discord.ui.button(label="🚪 Leave", style=discord.ButtonStyle.secondary)
    async def leave(self, button, interaction): 
        await interaction.response.send_modal(ConfigModal("LEAVE_CHANNEL_ID", "Salon de départ"))

    @discord.ui.button(label="🪄 Panneau Tickets", style=discord.ButtonStyle.success)
    async def send_ticket(self, button, interaction): 
        await interaction.response.send_message("Utilisez `+sendticketpanel` pour envoyer le panneau ici.", ephemeral=True)

    @discord.ui.button(label="🎭 Panneau Rôles", style=discord.ButtonStyle.success)
    async def send_roles(self, button, interaction): 
        await interaction.response.send_message("Utilisez `+sendrolespanel` pour envoyer le panneau ici.", ephemeral=True)

# ----- Commande +config -----

@commands.has_permissions(administrator=True)
async def config_cmd(ctx):
    cfg = data_manager.get_guild_config(ctx.guild.id)
    embed = discord.Embed(
        title="⚙️ Configuration du serveur Hoshikuzu ✨",
        description="Utilisez les boutons ci-dessous pour configurer les salons et rôles.\n*(Visible par tous, modification admin seulement)*",
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text="Hoshikuzu System ©")
    await ctx.send(embed=embed, view=ConfigView())

# ----- Commande +test -----

async def test_cmd(ctx, type: str = None):
    if type == "welcomesimple":
        await ctx.send(f"👋 Bienvenue {ctx.author.mention} sur le serveur Hoshikuzu ! 🌸 (simulation)")
    elif type == "welcomeembed":
        embed = discord.Embed(
            title="🌸 Bienvenue sur Hoshikuzu !",
            description=f"Salut {ctx.author.mention}, ravi de t’accueillir ici 💫 (simulation)",
            color=discord.Color.magenta()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text="Hoshikuzu System ©")
        await ctx.send(embed=embed)
    elif type == "leave":
        await ctx.send(f"👋 {ctx.author.display_name} a quitté le serveur... 😢 (simulation)")
    elif type == "boost":
        embed = discord.Embed(
            title="💎 Merci pour le boost !",
            description=f"{ctx.author.mention} a soutenu le serveur ✨ Merci infiniment 🌸 (simulation)",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Hoshikuzu System ©")
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Types disponibles : welcomesimple | welcomeembed | leave | boost")


# Register config commands (inlined)
bot.xp_cooldown_cache = {}

# -------------------- Config UI --------------------
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
        user = interaction.user; guild = interaction.guild
        cfg = data_manager.get_guild_config(guild.id)
        category_id = cfg.get("TICKET_CATEGORY_ID"); support_role_id = cfg.get("SUPPORT_ROLE_ID")
        support_role = guild.get_role(int(support_role_id)) if support_role_id else None
        if not category_id or not support_role:
            await interaction.response.send_message("❌ Configuration manquante : catégorie ou rôle support.", ephemeral=True); return
        category = guild.get_channel(int(category_id))
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Catégorie invalide.", ephemeral=True); return
        for channel in category.text_channels:
            if channel.topic and str(user.id) in channel.topic:
                await interaction.response.send_message(f"❌ Vous avez déjà un ticket ouvert : {channel.mention}", ephemeral=True); return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }
        name = f"ticket-{user.name}".lower()[:90]
        ticket_channel = await guild.create_text_channel(name=name, category=category, overwrites=overwrites, topic=f"Ticket ouvert par {user.name} ({user.id})")
        data_manager.incr_stat(user.id, "tickets", 1)
        data_manager.add_badge(user.id, "Helper")  # give helper badge on ticket open
        embed = discord.Embed(title="🎫 Ticket Ouvert", description=f"{user.mention} a ouvert un ticket.", color=discord.Color.blue())
        await ticket_channel.send(f"{user.mention} {support_role.mention}", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Ticket créé : {ticket_channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Fermer le Ticket", style=discord.ButtonStyle.red, custom_id="ticket_button_close")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ Ce n'est pas un canal de ticket.", ephemeral=True); return
        await interaction.response.send_message("🔒 Ticket fermé. Suppression dans 5s...", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user.display_name}")
        except discord.Forbidden:
            cfg = data_manager.get_guild_config(interaction.guild.id); logs = cfg.get("LOGS_CHANNEL_ID")
            if logs:
                ch = bot.get_channel(int(logs)); 
                if ch: await ch.send(f"❌ Je n'ai pas pu supprimer le canal {interaction.channel.name}")

# -------------------- Events --------------------
@bot.event
async def on_ready():
    print("="*40); print(f"🤖 Bot connecté: {bot.user} (ID: {bot.user.id})"); print(f"📊 Serveurs: {len(bot.guilds)}"); print("="*40)
    bot.add_view(ConfigView()); bot.add_view(TicketCreateView(bot)); bot.add_view(TicketCloseView()); bot.add_view(RoleButtonView())

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    # automod check
    if data_manager.automod_enabled():
        words = data_manager.automod_words()
        content = message.content.lower()
        for w in words:
            if w.lower() in content:
                try:
                    await message.delete()
                except:
                    pass
                await message.channel.send(f"❌ Mot interdit détecté, {message.author.mention}", delete_after=5)
                data_manager.add_warning(message.guild.id, message.author.id, bot.user.id, f"Automod: mot interdit `{w}`")
                return
    # leveling xp and stats
    uid = message.author.id
    now = datetime.now()
    last = bot.xp_cooldown_cache.get(uid)
    if last is None or (now - last).total_seconds() >= 60:
        xp = random.randint(5,15)
        new_lvl = data_manager.add_xp(uid, xp)
        bot.xp_cooldown_cache[uid] = now
        data_manager.incr_stat(uid, "messages", 1)
        # badges by messages
        msgs = data_manager.data.get("stats", {}).get(str(uid), {}).get("messages",0)
        if msgs >= 100:
            data_manager.add_badge(uid, "Parleur Actif")
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

# -------------------- Giveaways task --------------------
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
            await ch.send("❌ Aucun participant valide."); return
        winners = random.sample(users, min(g.get("winners",1), len(users)))
        mentions = ", ".join([w.mention for w in winners])
        await ch.send(f"🎉 Gagnant(s): {mentions} — {g.get('prize')}")

# -------------------- Commands: Config & Setup --------------------

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
    embed = discord.Embed(title="⚙️ Configuration du Serveur", color=discord.Color.blurple())
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
async def ban_member(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    try:
        await member.ban(reason=f"Par {ctx.author} - {reason}")
        await ctx.send(embed=discord.Embed(title="🔨 Membre banni", description=f"{member.display_name} a été banni.\nRaison: {reason}", color=discord.Color.red()))
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de bannir ce membre.")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas t'expulser toi-même !")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    try:
        await member.kick(reason=f"Par {ctx.author} - {reason}")
        await ctx.send(embed=discord.Embed(title="👢 Membre expulsé", description=f"{member.display_name} expulsé. Raison: {reason}", color=discord.Color.orange()))
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission d'expulser ce membre.")

# ... (file continues below, truncated here for display)

# Register config commands (fixed placement)
# --- Ensure no duplicate commands before registering config deluxe ---
try:
    # remove old commands if present to avoid CommandRegistrationError
    if bot.all_commands.get('config'):
        try:
            bot.remove_command('config')
        except Exception:
            pass
    if bot.all_commands.get('test'):
        try:
            bot.remove_command('test')
        except Exception:
            pass
    setup_config_commands(bot, data_manager)
except Exception as e:
    print("Erreur lors de l'initialisation de la config deluxe:", e)
    print("Erreur lors de l'initialisation de la config deluxe:", e)

# Initialize config deluxe commands
try:
    setup_config_commands(bot, data_manager)
except Exception as e:
    print('Erreur lors de l\'initialisation de la config deluxe:', e)

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🌸 Menu d’aide — Hoshikuzu Bot",
        description="Voici toutes les commandes disponibles sur le bot ✨",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="⚙️ Configuration",
        value=(
            "`+config` — Affiche la configuration actuelle\n"
            "`+setlogs #salon` — Définit le salon de logs\n"
            "`+setboostchannel #salon` — Salon des remerciements de boost ✨\n"
            "`+setticketcategory #catégorie` — Catégorie des tickets\n"
            "`+setticketrole @rôle` — Rôle support\n"
            "`+sendticketpanel #salon` — Envoie le bouton de ticket\n"
            "`+sendrules #salon` — Envoie l'embed des règles 📜\n"
            "`+sendrolespanel #salon` — Panneau de rôles par réaction 💫\n"
            "`+welcomeembed #salon` — Salon de bienvenue (embed)\n"
            "`+welcomesimple #salon` — Salon de bienvenue (simple)\n"
            "`+leavechat #salon` — Salon des départs"
        ),
        inline=False
    )

    embed.add_field(
        name="👮 Modération",
        value=(
            "`+ban @membre [raison]` — Bannir un membre 🔨\n"
            "`+kick @membre [raison]` — Expulser un membre 👢\n"
            "`+mute @membre [durée]` — Timeout 🔇\n"
            "`+unmute @membre` — Retirer le timeout 🔊\n"
            "`+clear [nombre]` — Supprimer des messages 🧹\n"
            "`+close` — Fermer le ticket actuel\n"
            "`+add @membre` — Ajouter un membre au ticket\n"
            "`+say #salon [message]` — Faire parler le bot\n"
            "`+embed #salon [Titre | Description]` — Envoyer un embed\n"
            "`+warn @membre [raison]` — Avertir un membre 🚨\n"
            "`+warnings @membre` — Voir ses avertissements 📋\n"
            "`+delwarn @membre [ID]` — Supprimer un avertissement"
        ),
        inline=False
    )

    embed.add_field(
        name="📈 Niveaux",
        value=(
            "`+rank [@membre]` — Voir le niveau et l’XP 📊\n"
            "`+leaderboard` — Classement des niveaux 🏆"
        ),
        inline=False
    )

    embed.add_field(
        name="💰 Économie & Cadeaux",
        value=(
            "`+balance [@membre]` — Voir le solde ⭐\n"
            "`+daily` — Récompense quotidienne 🎁\n"
            "`+work` — Travailler pour gagner de l’argent 💼\n"
            "`+gstart <durée> <gagnants> <prix>` — Lancer un giveaway 🎉\n"
            "`+addmoney @membre [montant]` — Ajouter de la monnaie (Admin)\n"
            "`+setmoney @membre [montant]` — Définir un solde (Admin)"
        ),
        inline=False
    )

    embed.add_field(
        name="😂 Fun & Interaction",
        value=(
            "`+hug [@membre]` — Faire un câlin 💖\n"
            "`+meme` — Mème aléatoire 😂\n"
            "`+coin` — Pile ou face 👑\n"
            "`+dice [faces]` — Lancer un dé 🎲\n"
            "`+8ball [question]` — Poser une question magique 🔮"
        ),
        inline=False
    )

    embed.add_field(
        name="🛠️ Utilitaires",
        value=(
            "`+ping` — Voir la latence 🏓\n"
            "`+traduction <langue> <texte>` — Traduire du texte 🌐\n"
            "`+avatar [@membre]` — Afficher un avatar\n"
            "`+userinfo [@membre]` — Infos sur un membre 👤\n"
            "`+serverinfo` — Infos sur le serveur 📊"
        ),
        inline=False
    )

    embed.set_footer(text="Hoshikuzu System © | Créé avec amour 💜", icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None)
    await ctx.send(embed=embed)
