import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import os
import random
import json
import math 
import urllib.parse # Pour l'encodage des URLs de recherche

ARROW_EMOJI = "<a:caarrow:1433143710094196997>"

import threading, http.server, socketserver, os

def keep_alive():
    """Ouvre un petit serveur HTTP sur le port requis par Render pour éviter l'arrêt automatique."""
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"✅ Serveur keep-alive lancé sur le port {port}")
        httpd.serve_forever()



class DataManager:
    """Gère la lecture et l'écriture des données persistantes (JSON)."""
    
    def __init__(self, filename="bot_data.json"):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        """Charge les données du fichier JSON ou initialise un nouveau dictionnaire."""
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    print("⚠️ Fichier de données JSON corrompu ou vide. Initialisation d'une structure vide.")
                    return {"economy": {}, "warnings": {}, "levels": {}}
        return {"economy": {}, "warnings": {}, "levels": {}}

    def _save_data(self):
        """Sauvegarde les données dans le fichier JSON."""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4)
            
    
    def get_user_warnings(self, user_id):
        user_id_str = str(user_id)
        return self.data.get('warnings', {}).get(user_id_str, [])
        
    def add_warning(self, guild_id, user_id, moderator_id, reason):
        user_id_str = str(user_id)
        moderator_id_str = str(moderator_id)
        
        warn_data = {
            "id": len(self.get_user_warnings(user_id)) + 1,
            "timestamp": datetime.now().isoformat(),
            "moderator_id": moderator_id_str,
            "reason": reason
        }
        
        if user_id_str not in self.data.get('warnings', {}):
            self.data['warnings'][user_id_str] = []
        
        self.data['warnings'][user_id_str].append(warn_data)
        self._save_data()
        return warn_data

    def remove_warning(self, user_id, warn_id):
        user_id_str = str(user_id)
        if user_id_str in self.data.get('warnings', {}):
            initial_count = len(self.data['warnings'][user_id_str])
            self.data['warnings'][user_id_str] = [
                warn for warn in self.data['warnings'][user_id_str] if warn['id'] != warn_id
            ]
            
            if len(self.data['warnings'][user_id_str]) < initial_count:
                self._save_data()
                return True
        return False
        

    def _get_eco_data(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.data.get('economy', {}):
            self.data['economy'][user_id_str] = {"balance": 0, "last_daily": None, "last_work": None}
            self._save_data()
        return self.data['economy'][user_id_str]

    def get_balance(self, user_id):
        return self._get_eco_data(user_id).get("balance", 0)

    def update_balance(self, user_id, amount):
        user_data = self._get_eco_data(user_id)
        user_data['balance'] += amount
        self._save_data()
        return user_data['balance']
        
    def set_balance(self, user_id, amount):
        user_data = self._get_eco_data(user_id)
        user_data['balance'] = amount
        self._save_data()
        return user_data['balance']

    def get_last_daily(self, user_id):
        last_daily_str = self._get_eco_data(user_id).get("last_daily")
        if last_daily_str:
            return datetime.fromisoformat(last_daily_str)
        return None

    def set_last_daily(self, user_id):
        user_data = self._get_eco_data(user_id)
        user_data["last_daily"] = datetime.now().isoformat()
        self._save_data()

    def get_last_work(self, user_id):
        last_work_str = self._get_eco_data(user_id).get("last_work")
        if last_work_str:
            return datetime.fromisoformat(last_work_str)
        return None

    def set_last_work(self, user_id):
        user_data = self._get_eco_data(user_id)
        user_data["last_work"] = datetime.now().isoformat()
        self._save_data()

    
    def _get_level_data(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.data.get('levels', {}):
            self.data['levels'][user_id_str] = {"level": 0, "xp": 0}
            self._save_data()
        return self.data['levels'][user_id_str]

    def get_level_info(self, user_id):
        data = self._get_level_data(user_id)
        return data['level'], data['xp']
        
    def add_xp(self, user_id, xp_amount):
        user_data = self._get_level_data(user_id)
        
        user_data['xp'] += xp_amount
        current_level = user_data['level']
        
        while user_data['xp'] >= self.required_xp(current_level + 1):
            current_level += 1
            user_data['level'] = current_level
            user_data['xp'] -= self.required_xp(current_level) 
            self._save_data() 
            return current_level 
            
        self._save_data()
        return None 
        
    def get_all_levels(self):
        return [
            (user_id, data['level'], data['xp'])
            for user_id, data in self.data.get('levels', {}).items()
        ]

    @staticmethod
    def required_xp(level):
        """Formule d'XP : 5 * level^2 + 50 * level + 100"""
        if level <= 0:
            return 0
        return 5 * level**2 + 50 * level + 100

data_manager = DataManager()



CONFIG_CHANNELS = {
    "WELCOME_CHANNEL_ID": 1433096078311293032,
    "LEAVE_CHANNEL_ID": 1433096160800804894,
    "WELCOME_EMBED_CHANNEL_ID": None, 
    "WELCOME_SIMPLE_CHANNEL_ID": 1433120551865417738,
    "LOGS_CHANNEL_ID": None, 
    "TICKET_CATEGORY_ID": None, 
    "BOOST_CHANNEL_ID": None, 
}

CONFIG_ROLES = {
    "SUPPORT_ROLE_ID": None, 
}

LEVELING_SETTINGS = {
    "COOLDOWN_SECONDS": 60, 
    "XP_RANGE_MIN": 15,     
    "XP_RANGE_MAX": 25,     
}

xp_cooldown_cache = {}

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 
intents.reactions = True 

bot = commands.Bot(command_prefix='+', intents=intents, help_command=None)

def get_channel_by_config(key):
    return bot.get_channel(CONFIG_CHANNELS.get(key))

def get_role_by_config(key):
    role_id = CONFIG_ROLES.get(key)
    if role_id and bot.guilds:
        return discord.utils.get(bot.guilds[0].roles, id=role_id)
    return None

async def send_to_logs(guild, embed):
    logs_channel = get_channel_by_config("LOGS_CHANNEL_ID")
    if logs_channel:
        try:
            await logs_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"❌ Erreur: Le bot ne peut pas envoyer de message dans le salon de logs ({logs_channel.name}).")
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi au salon de logs: {e}")



class RoleButtonView(discord.ui.View):
    """Vue persistante pour gérer l'attribution et le retrait des rôles via boutons."""
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
        """Fonction utilitaire pour ajouter ou retirer un rôle."""
        role = interaction.guild.get_role(role_id)
        
        if not role:
            return await interaction.response.send_message(
                f"❌ Le rôle '**{role_name}**' n'existe pas ou n'est pas configuré. (ID: {role_id})",
                ephemeral=True
            )

        member = interaction.user
        if role in member.roles:
            await member.remove_roles(role, reason="Rôle Retiré via Bouton")
            await interaction.response.send_message(
                f"✅ Le rôle **{role_name}** a été **retiré**.",
                ephemeral=True
            )
        else:
            await member.add_roles(role, reason="Rôle Ajouté via Bouton")
            await interaction.response.send_message(
                f"✅ Le rôle **{role_name}** a été **ajouté**.",
                ephemeral=True
            )


class TicketCreateView(discord.ui.View):
    """Vue contenant le bouton pour ouvrir un ticket."""
    def __init__(self, bot_instance):
        super().__init__(timeout=None) 
        self.bot = bot_instance
        
    @discord.ui.button(label="📩 Ouvrir un Ticket", style=discord.ButtonStyle.blurple, custom_id="ticket_button_create")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        
        category_id = CONFIG_CHANNELS.get("TICKET_CATEGORY_ID")
        support_role = get_role_by_config("SUPPORT_ROLE_ID")
        
        if not category_id or not support_role:
            await interaction.response.send_message(
                "❌ **Erreur Configuration** : La catégorie ou le rôle de support n'est pas configuré. Demandez à un administrateur.", 
                ephemeral=True
            )
            return

        category = self.bot.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ **Erreur Configuration** : La catégorie de ticket est invalide. Demandez à un administrateur.", 
                ephemeral=True
            )
            return

        for channel in category.text_channels:
            if channel.topic and str(user.id) in channel.topic: 
                await interaction.response.send_message(
                    f"❌ Vous avez déjà un ticket ouvert : {channel.mention}", 
                    ephemeral=True
                )
                return
            
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False), 
            user: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True, 
                attach_files=True
            ), 
            support_role: discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True, 
                manage_channels=True 
            ), 
            guild.me: discord.PermissionOverwrite(view_channel=True) 
        }
        
        channel_name = f"ticket-{user.name.lower().replace(' ', '-').replace('.', '')}"[:100]
        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name, 
                category=category, 
                overwrites=overwrites,
                topic=f"Ticket ouvert par {user.name} ({user.id}) le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
            )

            embed = discord.Embed(
                title="🎫 Ticket Ouvert",
                description=f"Bienvenue {user.mention} ! L'équipe de support a été notifiée et vous répondra dès que possible.\n\nDécrivez votre problème en détail ci-dessous.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Rôle Support", value=support_role.mention)
            
            await ticket_channel.send(f"{user.mention} {support_role.mention}", embed=embed, view=TicketCloseView())
            await interaction.response.send_message(f"✅ Votre ticket est ouvert dans {ticket_channel.mention} !", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Je n'ai pas les permissions nécessaires pour créer des canaux (Vérifiez les rôles/catégories).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur inattendue : {e}", ephemeral=True)


class TicketCloseView(discord.ui.View):
    """Vue contenant le bouton pour fermer et supprimer le ticket."""
    def __init__(self):
        super().__init__(timeout=None) 
        
    @discord.ui.button(label="🔒 Fermer le Ticket", style=discord.ButtonStyle.red, custom_id="ticket_button_close")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        support_role = get_role_by_config("SUPPORT_ROLE_ID")
        is_staff = support_role and support_role in interaction.user.roles
        
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ Ce n'est pas un canal de ticket.", ephemeral=True)
            return
        
        is_ticket_owner = False
        if interaction.channel.topic:
            user_id_in_topic = interaction.channel.topic.split('(')[-1].split(')')[0] if interaction.channel.topic else None
            is_ticket_owner = str(interaction.user.id) == user_id_in_topic
            
        if not is_staff and not interaction.user.top_role.permissions.administrator and not is_ticket_owner:
            await interaction.response.send_message("❌ Vous n'avez pas la permission de fermer ce ticket.", ephemeral=True)
            return

        await interaction.response.send_message(f"🔒 Ticket fermé par {interaction.user.mention}. Suppression dans 5 secondes...")
        await asyncio.sleep(5)
        
        try:
            await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user.display_name}")
        except discord.Forbidden:
            logs_channel = get_channel_by_config("LOGS_CHANNEL_ID")
            if logs_channel:
                await logs_channel.send(f"❌ Le bot n'a pas pu supprimer le canal de ticket {interaction.channel.name} par manque de permissions.")
        except Exception as e:
            print(f"Erreur lors de la suppression du ticket: {e}")



@bot.event
async def on_ready():
    """Se déclenche lorsque le bot est prêt."""
    print('=' * 60)
    print(f"🤖 Bot connecté: {bot.user.name}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"📊 Serveurs: {len(bot.guilds)}")
    print(f"👥 Utilisateurs globaux: {len(bot.users)}") 
    print('=' * 60)

    bot.add_view(TicketCreateView(bot))
    bot.add_view(TicketCloseView())
    bot.add_view(RoleButtonView())
    
    await bot.change_presence(
        activity=discord.Game(name="Hoshikuzu | +help"),
        status=discord.Status.dnd
    )
    giveaway_task.start()

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """Gestion d'erreur globale pour les commandes."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ **Argument manquant** : Il manque un argument. Vérifie la commande `+help`.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ **Membre introuvable** : Impossible de trouver ce membre.")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ **Rôle introuvable** : Impossible de trouver ce rôle.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ **Salon introuvable** : Impossible de trouver ce salon.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ **Mauvais argument** : Un argument n'est pas au format attendu.")
    elif isinstance(error, commands.MissingPermissions):
        perms_needed = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ **Permissions manquantes** : Tu n'as pas la permission de `{perms_needed}`.")
    elif isinstance(error, commands.BotMissingPermissions):
        perms_needed = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ **Permissions du Bot manquantes** : Le bot a besoin de la permission de `{perms_needed}`.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Cette commande est en **cooldown**. Réessaie dans {error.retry_after:.2f}s.")
    else:
        cmd_name = ctx.command.name if ctx.command else "inconnue"
    print(f"Erreur non gérée dans la commande {cmd_name}: {error}")

@bot.event
async def on_message(message: discord.Message):
    """Gère l'attribution d'XP et le traitement des commandes."""
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = datetime.now()
    
    last_xp_time = xp_cooldown_cache.get(user_id)
    if last_xp_time is None or (now - last_xp_time).total_seconds() >= LEVELING_SETTINGS["COOLDOWN_SECONDS"]:
        
        xp_gained = random.randint(LEVELING_SETTINGS["XP_RANGE_MIN"], LEVELING_SETTINGS["XP_RANGE_MAX"])
        new_level = data_manager.add_xp(user_id, xp_gained)
        
        xp_cooldown_cache[user_id] = now 

        if new_level is not None:
            await message.channel.send(f"✨ **Félicitations** {message.author.mention} ! Vous êtes passé au **Niveau {new_level}** ! 🎉")

    await bot.process_commands(message)


@bot.event
async def on_member_join(member: discord.Member):
    """Message de bienvenue élégant avec embed et message simple"""
    
    embed_channel = get_channel_by_config("WELCOME_EMBED_CHANNEL_ID")
    simple_channel = get_channel_by_config("WELCOME_SIMPLE_CHANNEL_ID")
    
    if embed_channel:
        member_count = len(member.guild.members)
        welcome_embed = discord.Embed(
            title="🌸 Bienvenue sur Hoshikuzu !",
            description=f"Salut {member.mention} ! 👋\nTu es notre **{member_count}ème** membre ! 🎉",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        welcome_embed.set_thumbnail(url=member.display_avatar.url)
        welcome_embed.set_footer(text="Équipe Hoshikuzu", icon_url=member.guild.icon.url if member.guild.icon else None)
        await embed_channel.send(embed=welcome_embed)
    
    if simple_channel:
        member_count = len(member.guild.members)
        message = (
            f"Bienvenue {member.mention} sur Hoshikuzu ! Nous sommes ravis de t'accueillir ! 🎉\n"
            f"Nous sommes désormais **{member_count}** membres sur Hoshikuzu ! ✨"
        )
        await simple_channel.send(message)
    
    try:
        dm_embed = discord.Embed(
            title="🎉 Bienvenue sur Hoshikuzu !",
            description=f"Salut **{member.display_name}** ! 👋 Nous sommes ravis de t'accueillir !",
            color=discord.Color.green(),
        )
        dm_embed.add_field(name="📝 Pour bien commencer", value="• Lis les règles\n• Amuse-toi bien !", inline=False)
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        pass

@bot.event
async def on_member_remove(member: discord.Member):
    """Message d'au revoir élégant avec embed"""
    leave_channel = get_channel_by_config("LEAVE_CHANNEL_ID")

    if leave_channel:
        member_count = len(member.guild.members)
        leave_embed = discord.Embed(
            title="👋 Au revoir...",
            description=f"**{member.display_name}** vient de quitter **Hoshikuzu**\nNous sommes maintenant **{member_count}** membres.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        leave_embed.set_thumbnail(url=member.display_avatar.url)
        joined_date = member.joined_at.strftime('%d/%m/%Y') if member.joined_at else "Inconnue"
        leave_embed.set_footer(text=f"Membre depuis le {joined_date}", icon_url=member.guild.icon.url if member.guild.icon else None)
        await leave_channel.send(embed=leave_embed)


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Détecte si un membre commence à booster le serveur."""
    


@bot.event
async def on_member_join(member: discord.Member):
    """Message de bienvenue élégant avec embed et message simple"""
    
    embed_channel = get_channel_by_config("WELCOME_EMBED_CHANNEL_ID")
    simple_channel = get_channel_by_config("WELCOME_SIMPLE_CHANNEL_ID")
    member_count = len(member.guild.members) # Récupération du compte une seule fois
    
    if embed_channel:
        welcome_embed = discord.Embed(
            title="🌸 Bienvenue sur Hoshikuzu !",
            description=f"Salut {member.mention} ! 👋\nTu es notre **{member_count}ème** membre ! 🎉",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        welcome_embed.set_thumbnail(url=member.display_avatar.url)
        welcome_embed.set_footer(text="Équipe Hoshikuzu", icon_url=member.guild.icon.url if member.guild.icon else None)
        await embed_channel.send(embed=welcome_embed)
    
    if simple_channel:
        message = (
            f"{ARROW_EMOJI} Bienvenue {member.mention} sur Hoshikuzu ! Nous sommes ravis de t'accueillir ! 🎉\n"
            f"{ARROW_EMOJI} Nous sommes désormais **{member_count}** membres sur Hoshikuzu ! ✨"
        )
        await simple_channel.send(message)

    dm_embed = discord.Embed(
        title="🎉 Bienvenue sur Hoshikuzu !",
        description=(
            f"{ARROW_EMOJI} Salut {member.mention} ! 👋\n"
            f"{ARROW_EMOJI} Tu es notre **{member_count}ème** membre ! 🎉"
        ),
        color=discord.Color.green(),
    )
    dm_embed.add_field(name="📝 Pour bien commencer", value="• Lis les règles\n• Amuse-toi bien !", inline=False)
    
    try:
        await member.send(embed=dm_embed)
        print(f"DM de bienvenue envoyé avec succès à {member.name}.")
        
    except discord.Forbidden:
        print(f"Échec du DM à {member.name}. (DMs désactivés par l'utilisateur)")
        pass 
        
    except discord.HTTPException as e:
        if e.code == 40003: # Code 40003: Rate Limit
            print(f"Discord Rate Limit (40003): Impossible d'envoyer un DM à {member.name}. Trop de DMs ouverts trop rapidement.")
        else:
            print(f"Une erreur HTTP inattendue est survenue lors de l'envoi du DM à {member.name}: {e}")
        pass

    embed = discord.Embed(
        title="📝 Message Modifié",
        color=discord.Color.dark_teal(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Auteur", value=before.author.mention, inline=True)
    embed.add_field(name="Salon", value=before.channel.mention, inline=True)
    
    embed.add_field(name="Avant", value=f"```\n{before.content[:500]}\n```", inline=False)
    embed.add_field(name="Après", value=f"```\n{after.content[:500]}\n```", inline=False)
    embed.set_footer(text=f"ID: {before.id}")
    
    await send_to_logs(before.guild, embed)

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    """Log les bannissements"""
    embed = discord.Embed(
        title="🔨 Membre Banni",
        description=f"**{user.display_name}** a été banni du serveur.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="ID", value=user.id, inline=False)
    
    await send_to_logs(guild, embed)

@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    """Log les débannissements"""
    embed = discord.Embed(
        title="🔓 Membre Débanni",
        description=f"**{user.display_name}** a été débanni du serveur.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="ID", value=user.id, inline=False)
    
    await send_to_logs(guild, embed)



@bot.command(name='setlogs')
@commands.has_permissions(administrator=True)
async def set_logs_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon de logs pour la journalisation"""
    CONFIG_CHANNELS["LOGS_CHANNEL_ID"] = channel.id

    embed = discord.Embed(
        description=f"✅ Le salon de **Logs** a été configuré sur {channel.mention}. Les messages supprimés/modifiés, bans, etc. y seront envoyés.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='setboostchannel')
@commands.has_permissions(administrator=True)
async def set_boost_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon pour les messages de remerciement de boost."""
    CONFIG_CHANNELS["BOOST_CHANNEL_ID"] = channel.id
    embed = discord.Embed(description=f"✅ Le salon des **Remerciements de Boost** a été configuré sur {channel.mention}.", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='setticketcategory')
@commands.has_permissions(administrator=True)
async def set_ticket_category(ctx: commands.Context, category: discord.CategoryChannel):
    """Configure la catégorie où les tickets seront créés."""
    CONFIG_CHANNELS["TICKET_CATEGORY_ID"] = category.id
    embed = discord.Embed(description=f"✅ La **Catégorie de Tickets** a été configurée sur **{category.name}**.", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='setticketrole')
@commands.has_permissions(administrator=True)
async def set_ticket_role(ctx: commands.Context, role: discord.Role):
    """Configure le rôle qui aura accès aux tickets."""
    CONFIG_ROLES["SUPPORT_ROLE_ID"] = role.id
    embed = discord.Embed(description=f"✅ Le **Rôle de Support/Staff** a été configuré sur {role.mention}.", color=discord.Color.green())
    await ctx.send(embed=embed)


@bot.command(name='sendticketpanel')
@commands.has_permissions(administrator=True)
async def send_ticket_panel(ctx: commands.Context, channel: discord.TextChannel = None):
    """Envoie le message avec le bouton pour ouvrir un ticket."""
    
    if not CONFIG_CHANNELS.get("TICKET_CATEGORY_ID") or not CONFIG_ROLES.get("SUPPORT_ROLE_ID"):
        return await ctx.send("❌ Vous devez d'abord configurer la catégorie et le rôle de support avec `+setticketcategory` et `+setticketrole`.")
        
    target_channel = channel or ctx.channel
    
    embed = discord.Embed(
        title="Centre d'Aide et Support 📩",
        description="Cliquez sur le bouton ci-dessous pour ouvrir un **ticket privé** avec l'équipe de modération/support.\n\n*Veuillez décrire votre problème en détail.*",
        color=discord.Color.dark_purple()
    )
    
    await target_channel.send(embed=embed, view=TicketCreateView(bot))
    if target_channel != ctx.channel:
        await ctx.send(f"✅ Le panneau de tickets a été envoyé dans {target_channel.mention}", delete_after=5)
        
@bot.command(name='sendrolespanel')
@commands.has_permissions(administrator=True)
async def send_roles_panel(ctx: commands.Context, channel: discord.TextChannel = None):
    """Envoie le panneau des Rôles par Réaction avec des boutons."""
    target_channel = channel or ctx.channel

    embed = discord.Embed(
        title="✨ Choisissez vos Rôles de Notification",
        description="Cliquez sur les boutons ci-dessous pour vous attribuer ou retirer le rôle correspondant.",
        color=discord.Color.from_rgb(255, 105, 180) # Rose vif
    )

    await target_channel.send(embed=embed, view=RoleButtonView())
    if target_channel != ctx.channel:
        await ctx.send(f"✅ Le panneau de Rôles par Réaction a été envoyé dans {target_channel.mention}", delete_after=5)


@bot.command(name='sendrules')
@commands.has_permissions(administrator=True)
async def send_rules_panel(ctx: commands.Context, channel: discord.TextChannel = None):
    """Envoie l'embed des règles dans un salon spécifié."""
    
    target_channel = channel or ctx.channel
    
    embed = discord.Embed(
        title="📜 Règlement du Serveur Hoshikuzu",
        description="Bienvenue sur le serveur Hoshikuzu ! 👋\nAvant de plonger dans la communauté, merci de lire attentivement les règles ci-dessous 👇",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )

    embed.add_field(
        name="🤝 Respect & Politesse",
        value="""
        ➜ **Aucune insulte, provocation, harcèlement** ou **discrimination** ne sera toléré(e).
        ➜ Sois **poli(e) et bienveillant(e)** envers tout le monde.
        """,
        inline=False
    )

    embed.add_field(
        name="🚫 Spam, Pub & Contenu Interdit",
        value="""
        ➜ Pas de **spam, flood** ou **pub** sans autorisation.
        ➜ **Évite les sujets sensibles** (politique, religion, etc.).
        ➜ **Interdiction de poster du contenu NSFW, choquant ou illégal** sous peine de **BAN DEF**.
        ➜ Les memes et images sont autorisés tant qu’ils restent **respectueux**.
        ➜ **Garde les discussions dans les bons canaux** (ex : ⁠#média, #commandes).
        """,
        inline=False
    )
    
    embed.add_field(
        name="🚨 Sécurité et Staff",
        value="""
        ➜ Ne partage **pas d’informations personnelles**.
        ➜ Aucune **arnaque, phishing, lien suspect ou piratage**.
        ➜ Les **modérateurs** sont là pour aider et maintenir l'ordre.
        ➜ **Respecte leurs décisions**, elles sont prises pour le bien de tous.
        ➜ Les **tickets** sont mis à disposition si vous avez un problème.
        """,
        inline=False
    )

    embed.set_footer(text="En restant ici, tu acceptes ces règles. Amuse-toi bien et sois le/la bienvenu(e) parmi nous !")
    
    await target_channel.send(embed=embed)
    
    if target_channel != ctx.channel:
        await ctx.send(f"✅ L'embed des règles a été envoyé dans {target_channel.mention}", delete_after=5)


@bot.command(name='welcomechat')
@commands.has_permissions(administrator=True)
async def set_welcome_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon de bienvenue (ancien système)"""
    CONFIG_CHANNELS["WELCOME_CHANNEL_ID"] = channel.id
    await ctx.send(f"✅ Les messages de bienvenue (ancien ID) seront envoyés dans {channel.mention}")

@bot.command(name='welcomeembed')
@commands.has_permissions(administrator=True)
async def set_welcome_embed_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon pour le message de bienvenue avec embed"""
    CONFIG_CHANNELS["WELCOME_EMBED_CHANNEL_ID"] = channel.id
    embed = discord.Embed(description=f"✅ Le message de bienvenue **avec embed** sera envoyé dans {channel.mention}", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='welcomesimple')
@commands.has_permissions(administrator=True)
async def set_welcome_simple_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon pour le message de bienvenue simple"""
    CONFIG_CHANNELS["WELCOME_SIMPLE_CHANNEL_ID"] = channel.id
    embed = discord.Embed(description=f"✅ Le message de bienvenue **simple** sera envoyé dans {channel.mention}", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='leavechat')
@commands.has_permissions(administrator=True)  
async def set_leave_channel(ctx: commands.Context, channel: discord.TextChannel):
    """Configure le salon des départs"""
    CONFIG_CHANNELS["LEAVE_CHANNEL_ID"] = channel.id
    await ctx.send(f"✅ Les messages de départ seront envoyés dans {channel.mention}")

@bot.command(name='config')
@commands.has_permissions(administrator=True)
async def show_config(ctx: commands.Context):
    """Affiche la configuration des salons (Mise à jour pour les tickets et boost)."""
    embed_channel = get_channel_by_config("WELCOME_EMBED_CHANNEL_ID")
    simple_channel = get_channel_by_config("WELCOME_SIMPLE_CHANNEL_ID")
    leave_channel = get_channel_by_config("LEAVE_CHANNEL_ID")
    logs_channel = get_channel_by_config("LOGS_CHANNEL_ID") 
    ticket_category = get_channel_by_config("TICKET_CATEGORY_ID") 
    support_role = get_role_by_config("SUPPORT_ROLE_ID") 
    boost_channel = get_channel_by_config("BOOST_CHANNEL_ID")

    embed = discord.Embed(title="⚙️ Configuration du Bot", color=discord.Color.blue(), timestamp=datetime.now())

    embed.add_field(name="--- Bienvenue/Départ/Boost ---", value=" ", inline=False)
    embed.add_field(name="🏠 Bienvenue (Embed)", value=embed_channel.mention if embed_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="💬 Bienvenue (Simple)", value=simple_channel.mention if simple_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="👋 Salons des départs", value=leave_channel.mention if leave_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="✨ Salon de Boost", value=boost_channel.mention if boost_channel else "❌ Non configuré", inline=False)
    
    embed.add_field(name="--- Tickets et Logs ---", value=" ", inline=False) 
    embed.add_field(name="📝 Salon de Logs", value=logs_channel.mention if logs_channel else "❌ Non configuré", inline=False)
    embed.add_field(name="🎫 Catégorie Ticket", value=ticket_category.mention if ticket_category else "❌ Non configuré", inline=False)
    embed.add_field(name="👮 Rôle Support", value=support_role.mention if support_role else "❌ Non configuré", inline=False)


    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    await ctx.send(embed=embed)



@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban_member(ctx: commands.Context, member: discord.Member, *, raison="Aucune raison fournie"):
    """Bannit un membre du serveur"""
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    
    try:
        await member.ban(reason=f"Par {ctx.author} - {raison}")
        embed = discord.Embed(title="🔨 Membre banni", description=f"**{member.display_name}** a été banni", color=discord.Color.red())
        embed.add_field(name="📝 Raison", value=raison)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour bannir ce membre !")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, raison="Aucune raison fournie"):
    """Expulse un membre du serveur"""
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas t'expulser toi-même !")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Ce membre a un rôle supérieur ou égal au tien !")
    try:
        await member.kick(reason=f"Par {ctx.author} - {raison}")
        embed = discord.Embed(title="👢 Membre expulsé", description=f"**{member.display_name}** a été expulsé", color=discord.Color.orange())
        embed.add_field(name="📝 Raison", value=raison)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour expulser ce membre !")

@bot.command(name='mute')
@commands.has_permissions(moderate_members=True)
async def mute_member(ctx, member: discord.Member, duration: int = 10, *, raison="Aucune raison fournie"):
    """Timeout un membre (durée en minutes)"""
    if duration > 40320: return await ctx.send("❌ Durée maximale : 40320 minutes (28 jours) !")
    try:
        timeout_duration = timedelta(minutes=duration)
        await member.timeout(timeout_duration, reason=f"Par {ctx.author} - {raison}")
        embed = discord.Embed(title="🔇 Membre timeout", description=f"**{member.display_name}** mis en timeout pour {duration} min", color=discord.Color.orange())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour timeout ce membre !")

@bot.command(name='unmute')
@commands.has_permissions(moderate_members=True)
async def unmute_member(ctx, member: discord.Member):
    """Retire le timeout d'un membre"""
    if member.timed_out_until is None: return await ctx.send("❌ Ce membre n'est pas en timeout !")
    try:
        await member.timeout(None, reason=f"Démuté par {ctx.author}")
        embed = discord.Embed(title="🔊 Membre démuté", description=f"**{member.display_name}** peut de nouveau parler", color=discord.Color.green())
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}")

@bot.command(name='clear', aliases=['purge', 'clean'])
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 10):
    """Supprime un nombre de messages"""
    if amount > 100: return await ctx.send("❌ Maximum 100 messages à la fois !")
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f"✅ **{len(deleted) - 1}** messages supprimés !", delete_after=3)
        embed = discord.Embed(
            title="🧹 Purge de messages",
            description=f"**{len(deleted) - 1}** messages supprimés par {ctx.author.mention} dans {ctx.channel.mention}.",
            color=discord.Color.blue()
        )
        await send_to_logs(ctx.guild, embed)
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas les permissions pour supprimer des messages !")

@bot.command(name='close', aliases=['fermer'])
@commands.has_permissions(manage_channels=True)
async def close_ticket_command(ctx: commands.Context):
    """Ferme le ticket actuel (doit être utilisé dans un canal de ticket)"""
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
    
    await ctx.send(f"🔒 Ticket fermé par {ctx.author.mention}. Suppression du canal dans 5 secondes...")
    await asyncio.sleep(5)
    await ctx.channel.delete(reason=f"Ticket fermé par commande par {ctx.author.display_name}")

@bot.command(name='add')
@commands.has_permissions(manage_channels=True)
async def add_member_to_ticket(ctx: commands.Context, member: discord.Member):
    """Ajoute un membre au ticket actuel."""
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
    
    try:
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
        await ctx.send(f"✅ {member.mention} a été ajouté au ticket.")
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de modifier les permissions du canal.")
        


@bot.command(name='warn')
@commands.has_permissions(kick_members=True) # Permission généralement utilisée pour le warn
async def warn_member(ctx: commands.Context, member: discord.Member, *, raison: str):
    """Donne un avertissement à un membre et l'enregistre."""
    if member.bot: return await ctx.send("❌ Vous ne pouvez pas donner d'avertissement à un bot.")
    if member == ctx.author: return await ctx.send("❌ Vous ne pouvez pas vous avertir vous-même.")

    warn_data = data_manager.add_warning(ctx.guild.id, member.id, ctx.author.id, raison)
    warn_count = len(data_manager.get_user_warnings(member.id))

    embed = discord.Embed(
        title="🚨 Avertissement Enregistré",
        description=f"**{member.display_name}** a reçu un avertissement.",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
    embed.add_field(name="Total Warns", value=warn_count, inline=True)
    embed.add_field(name="Raison", value=raison, inline=False)

    await ctx.send(embed=embed)
    
    try:
        await member.send(f"🚨 **AVERTISSEMENT** sur le serveur **{ctx.guild.name}**:\nModérateur: {ctx.author.name}\nRaison: {raison}\nTotal: {warn_count}")
    except discord.Forbidden:
        pass
    
    await send_to_logs(ctx.guild, embed)
    
@bot.command(name='warnings', aliases=['warns'])
@commands.has_permissions(kick_members=True)
async def check_warnings(ctx: commands.Context, member: discord.Member):
    """Affiche tous les avertissements d'un membre."""
    warnings = data_manager.get_user_warnings(member.id)
    
    if not warnings:
        return await ctx.send(f"✅ **{member.display_name}** n'a aucun avertissement actif.")
        
    description = f"**Total : {len(warnings)}**\n\n"
    
    for warn in warnings:
        moderator = await bot.fetch_user(warn['moderator_id'])
        date = datetime.fromisoformat(warn['timestamp']).strftime('%d/%m/%Y à %H:%M')
        description += (
            f"**ID: #{warn['id']}**\n"
            f"➜ **Date :** {date}\n"
            f"➜ **Modérateur :** {moderator.display_name}\n"
            f"➜ **Raison :** {warn['reason']}\n"
            f"----\n"
        )
        
    embed = discord.Embed(
        title=f"📋 Avertissements de {member.display_name}",
        description=description[:2048], # Limite à 2048 caractères
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='delwarn', aliases=['unwarn', 'remwarn'])
@commands.has_permissions(administrator=True) # Nécessite l'admin pour supprimer un warn
async def delete_warning(ctx: commands.Context, member: discord.Member, warn_id: int):
    """Supprime un avertissement par son ID."""
    if data_manager.remove_warning(member.id, warn_id):
        embed = discord.Embed(
            description=f"✅ L'avertissement **#{warn_id}** de {member.mention} a été **supprimé**.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        log_embed = discord.Embed(
            title="✅ Avertissement Supprimé",
            description=f"**Warn ID #{warn_id}** supprimé pour {member.mention} par {ctx.author.mention}.",
            color=discord.Color.green()
        )
        await send_to_logs(ctx.guild, log_embed)
    else:
        await ctx.send(f"❌ Avertissement **#{warn_id}** non trouvé pour {member.mention}.")



@bot.command(name='balance', aliases=['bal', 'money'])
async def show_balance(ctx: commands.Context, member: discord.Member = None):
    """Affiche le solde (la balance) d'un membre."""
    member = member or ctx.author
    balance = data_manager.get_balance(member.id)
    
    emoji = "⭐" # Monnaie du serveur
    
    embed = discord.Embed(
        title=f"💰 Solde de {member.display_name}",
        description=f"**{member.display_name}** possède **{balance} {emoji}**.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name='daily')
@commands.cooldown(1, 86400, commands.BucketType.user) # 86400 secondes = 24 heures
async def daily_money(ctx: commands.Context):
    """Récupère la récompense quotidienne."""
    DAILY_AMOUNT = 500
    
    data_manager.update_balance(ctx.author.id, DAILY_AMOUNT)
    data_manager.set_last_daily(ctx.author.id)
    
    balance = data_manager.get_balance(ctx.author.id)
    emoji = "⭐"
    
    embed = discord.Embed(
        title="🎁 Récompense Quotidienne !",
        description=f"🎉 Vous avez gagné **{DAILY_AMOUNT} {emoji}** !\nVotre nouveau solde est de **{balance} {emoji}**.",
        color=discord.Color.yellow()
    )
    await ctx.send(embed=embed)

@daily_money.error
async def daily_money_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandOnCooldown):
        remaining = error.retry_after
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        
        await ctx.send(f"⏳ Vous avez déjà récupéré votre récompense quotidienne. Revenez dans **{hours}h {minutes}m {seconds}s**.", ephemeral=True)
    else:
        await on_command_error(ctx, error) # Renvoie à la gestion d'erreur globale


@bot.command(name='work')
@commands.cooldown(1, 14400, commands.BucketType.user) # 14400 secondes = 4 heures
async def work_command(ctx: commands.Context):
    """Permet aux membres de "travailler" pour gagner de l'argent."""
    
    WORK_MIN = 150
    WORK_MAX = 450
    gain = random.randint(WORK_MIN, WORK_MAX)
    emoji = "⭐"
    
    jobs = [
        f"Vous avez codé une fonctionnalité complexe pour {gain} {emoji}.",
        f"Vous avez trié les données du serveur pour {gain} {emoji}.",
        f"Vous avez livré des pizzas spatiales pour un gain de {gain} {emoji}.",
        f"Vous avez aidé un admin à déboguer un script et avez gagné {gain} {emoji}.",
        f"Vous avez organisé la bibliothèque du serveur et reçu {gain} {emoji}."
    ]
    job_message = random.choice(jobs)

    data_manager.update_balance(ctx.author.id, gain)
    data_manager.set_last_work(ctx.author.id) 
    
    balance = data_manager.get_balance(ctx.author.id)
    
    embed = discord.Embed(
        title="💼 Travail Accompli !",
        description=f"{job_message}\n\nVotre nouveau solde est de **{balance} {emoji}**.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@work_command.error
async def work_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandOnCooldown):
        remaining = error.retry_after
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        
        await ctx.send(f"⏳ Vous êtes fatigué. Revenez au travail dans **{hours}h {minutes}m**.", ephemeral=True)
    else:
        await on_command_error(ctx, error)

@bot.command(name='addmoney')
@commands.has_permissions(administrator=True)
async def add_money(ctx: commands.Context, member: discord.Member, amount: int):
    """Ajoute de la monnaie à un membre."""
    if amount <= 0: return await ctx.send("❌ Le montant doit être positif.")
    
    new_balance = data_manager.update_balance(member.id, amount)
    emoji = "⭐"
    
    embed = discord.Embed(
        title="➕ Monnaie Ajoutée",
        description=f"**{amount} {emoji}** ont été ajoutés à {member.mention} par {ctx.author.mention}.",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Nouveau solde : {new_balance} {emoji}")
    await ctx.send(embed=embed)

@bot.command(name='setmoney')
@commands.has_permissions(administrator=True)
async def set_money(ctx: commands.Context, member: discord.Member, amount: int):
    """Définit la monnaie d'un membre à un montant précis."""
    if amount < 0: return await ctx.send("❌ Le montant ne peut pas être négatif (utilisez 0 pour réinitialiser).")
    
    old_balance = data_manager.get_balance(member.id)
    new_balance = data_manager.set_balance(member.id, amount)
    emoji = "⭐"
    
    embed = discord.Embed(
        title="✏️ Solde Modifié",
        description=f"Le solde de {member.mention} a été défini à **{amount} {emoji}** par {ctx.author.mention}.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Ancien Solde", value=f"{old_balance} {emoji}", inline=True)
    embed.add_field(name="Nouveau Solde", value=f"{new_balance} {emoji}", inline=True)
    await ctx.send(embed=embed)



@bot.command(name='rank', aliases=['niveau'])
async def show_rank(ctx: commands.Context, member: discord.Member = None):
    """Affiche le niveau et l'expérience d'un membre."""
    member = member or ctx.author
    level, current_xp = data_manager.get_level_info(member.id)
    
    xp_required_next = data_manager.required_xp(level + 1)
    
    progress_percent = (current_xp / xp_required_next) * 100 if xp_required_next > 0 else 100
    
    bar_length = 15
    filled_blocks = math.floor(progress_percent / (100 / bar_length))
    empty_blocks = bar_length - filled_blocks
    progress_bar = "🟦" * filled_blocks + "⬜" * empty_blocks
    
    embed = discord.Embed(
        title=f"📈 Profil de Niveau de {member.display_name}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Niveau Actuel", value=f"**{level}**", inline=True)
    embed.add_field(name="XP Actuelle", value=f"**{current_xp} XP**", inline=True)
    embed.add_field(name="XP Prochain Niveau", value=f"**{xp_required_next} XP**", inline=True)
    
    embed.add_field(
        name=f"Progression ({current_xp}/{xp_required_next} XP)",
        value=f"{progress_bar} **{progress_percent:.2f}%**",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def show_leaderboard(ctx: commands.Context):
    """Affiche le classement des membres les plus actifs."""
    all_levels = data_manager.get_all_levels()
    
    sorted_users = sorted(all_levels, key=lambda x: (x[1], x[2]), reverse=True)
    
    top_10 = sorted_users[:10]
    
    if not top_10:
        return await ctx.send("❌ Aucun utilisateur n'a encore d'XP.")

    leaderboard_text = ""
    rank = 1
    
    for user_id_str, level, xp in top_10:
        member = ctx.guild.get_member(int(user_id_str))
        
        if member:
            display_name = member.display_name
        else:
            try:
                user = await bot.fetch_user(int(user_id_str))
                display_name = user.name + " (Quitté)"
            except:
                display_name = f"Utilisateur Inconnu ({user_id_str})"
            
        leaderboard_text += f"`#{rank}` **{display_name}** — **Niveau {level}** ({xp} XP)\n"
        rank += 1
        
    embed = discord.Embed(
        title="🏆 Classement des Niveaux (Top 10)",
        description=leaderboard_text,
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    author_id_str = str(ctx.author.id)
    author_rank = next(((i + 1) for i, (uid, _, _) in enumerate(sorted_users) if uid == author_id_str), "N/A")
    
    embed.set_footer(text=f"Votre classement : #{author_rank}")
    await ctx.send(embed=embed)



active_giveaways = [] 

@tasks.loop(seconds=5) 
async def giveaway_task():
    """Tâche d'arrière-plan pour vérifier et terminer les giveaways."""
    global active_giveaways
    now = datetime.now()
    
    for giveaway in active_giveaways[:]:
        end_time = giveaway['end_time']
        if now >= end_time:
            active_giveaways.remove(giveaway)
            await end_giveaway(giveaway)
            
async def end_giveaway(giveaway):
    """Effectue le tirage au sort et annonce le gagnant."""
    channel = bot.get_channel(giveaway['channel_id'])
    
    try:
        message = await channel.fetch_message(giveaway['message_id'])
    except:
        return

    reaction = discord.utils.get(message.reactions, emoji='🎁')
    
    if reaction:
        users = [user async for user in reaction.users() if not user.bot]
        
        if not users:
            embed = discord.Embed(title="❌ Cadeau Terminé", description="Aucun participant valide pour le tirage au sort.", color=discord.Color.red())
            await channel.send(embed=embed)
            return
            
        num_winners = giveaway['winners']
        winners = random.sample(users, min(num_winners, len(users)))
        
        winner_mentions = ", ".join([w.mention for w in winners])
        
        embed = discord.Embed(
            title=f"🎉 CADEAU TERMINÉ : {giveaway['prize']}",
            description=f"Félicitations au(x) gagnant(s) : {winner_mentions} !",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Gagnant(s): {num_winners} | Organisé par {giveaway['host_name']}")
        
        await message.edit(embed=embed)
        await channel.send(f"🎉 **Félicitations** {winner_mentions} ! Vous avez gagné **{giveaway['prize']}** !")
        
    else:
        embed = discord.Embed(title="❌ Cadeau Terminé", description="Aucun participant valide (problème de réaction du bot).", color=discord.Color.red())
        await channel.send(embed=embed)


@bot.command(name='gstart', aliases=['giveaway', 'startgiveaway'])
@commands.has_permissions(administrator=True)
async def start_giveaway(ctx: commands.Context, duration: str, winners: int, *, prize: str):
    """Démarre un cadeau (giveaway). Format: +gstart 1h 1 Prix du cadeau"""
    try:
        time_unit = duration[-1]
        time_val = int(duration[:-1])
        
        if time_unit == 's': delta = timedelta(seconds=time_val)
        elif time_unit == 'm': delta = timedelta(minutes=time_val)
        elif time_unit == 'h': delta = timedelta(hours=time_val)
        elif time_unit == 'd': delta = timedelta(days=time_val)
        else: raise ValueError
            
        if delta.total_seconds() < 10 or delta.total_seconds() > 604800: # Max 7 jours
            return await ctx.send("❌ Durée invalide. Utilisez 's', 'm', 'h' ou 'd' (min 10s, max 7j).")
            
    except:
        return await ctx.send("❌ Format de durée invalide. Exemples : `1h`, `30m`, `5s`. Utilisez : `+gstart <durée> <gagnants> <prix>`")

    end_time = datetime.now() + delta
    
    embed = discord.Embed(
        title=f"🎉 CADEAU : {prize}",
        description=f"Réagissez avec 🎁 pour participer !\n\nOrganisateur : {ctx.author.mention}\n\n**Gagnant(s) :** {winners}\n**Termine :** {discord.utils.format_dt(end_time, 'R')}",
        color=discord.Color.dark_magenta(),
        timestamp=end_time
    )
    embed.set_footer(text="Cliquez sur 🎁 pour participer")
    
    giveaway_message = await ctx.send(embed=embed)
    await giveaway_message.add_reaction('🎁')
    await ctx.message.delete()
    
    active_giveaways.append({
        'message_id': giveaway_message.id,
        'channel_id': ctx.channel.id,
        'end_time': end_time,
        'winners': winners,
        'prize': prize,
        'host_name': ctx.author.display_name
    })


@bot.command(name='hug')
async def hug_member(ctx: commands.Context, member: discord.Member = None):
    """Fait un câlin à un membre ou à soi-même."""
    
    HUG_GIFS = [
        "https://media.giphy.com/media/GMFURg5r4QJ8X8TjYJ/giphy.gif",
        "https://media.giphy.com/media/V8YgR6yWwJ2k3K3u7d/giphy.gif",
        "https://media.giphy.com/media/Y4yR144L0R8nO/giphy.gif",
        "https://media.giphy.com/media/V8YgR6yWwJ2k3K3u7d/giphy.gif",
        "https://media.giphy.com/media/MDJ9IbxxvFEjEw6V1S/giphy.gif"
    ]
    
    gif_url = random.choice(HUG_GIFS)
    
    if member is None:
        message = f"🫂 **{ctx.author.display_name}** se fait un énorme câlin à lui-même ! Vous le méritez."
    elif member == ctx.author:
        message = f"🫂 **{ctx.author.display_name}** se fait un énorme câlin à lui-même ! Vous le méritez."
    elif member.bot:
        message = f"🤖 **{ctx.author.display_name}** essaie de faire un câlin à un bot... C'est mignon !"
    else:
        message = f"💖 **{ctx.author.display_name}** fait un gros câlin à **{member.display_name}** !"
        
    embed = discord.Embed(
        description=message,
        color=discord.Color.red()
    )
    embed.set_image(url=gif_url)
    
    await ctx.send(embed=embed)

@bot.command(name='meme')
async def get_meme(ctx: commands.Context):
    """Récupère un mème aléatoire. (Simulé par une recherche)"""
    
    await ctx.send("⏳ Recherche d'un mème sur Internet...")
    
    
        
    meme_subjects = ["funny programming meme", "spongebob meme", "classic internet meme", "cat meme"]
    query = random.choice(meme_subjects)
    
    try:
        search_result = await google_search(query=f"image {query}")
        
        
        if search_result and search_result[0].get('image'):
            image_url = search_result[0]['image']['url']
            title = f"😂 Mème : {query.replace('image', '').strip().title()}"
        elif search_result and search_result[0].get('url'):
            image_url = "https://i.imgur.com/k3qA04l.png" # Image par défaut si l'API est complexe
            title = f"😂 Mème trouvé (lien de page) : {query.replace('image', '').strip().title()}"
        else:
            raise Exception("No direct image link found.")

    except Exception:
        image_url = "https://i.imgur.com/gD68k80.png" # Image de secours
        title = "❌ Erreur de Mème (Image par défaut)"
        
    embed = discord.Embed(
        title=title,
        description="Voici un mème aléatoire !",
        color=discord.Color.teal()
    )
    embed.set_image(url=image_url)
    await ctx.send(embed=embed)



@bot.command(name='ping')
async def ping(ctx: commands.Context):
    """Affiche la latence du bot."""
    await ctx.send(f'🏓 Pong! Latence: **{round(bot.latency * 1000)}ms**')

@bot.command(name='avatar', aliases=['pfp', 'pp'])
async def avatar(ctx: commands.Context, member: discord.Member = None):
    """Affiche l'avatar du membre mentionné ou de l'auteur."""
    member = member or ctx.author
    embed = discord.Embed(
        title=f"🖼️ Avatar de {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.blue()
    )
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name='userinfo', aliases=['ui'])
async def user_info(ctx: commands.Context, member: discord.Member = None):
    """Affiche les informations sur l'utilisateur."""
    member = member or ctx.author
    
    roles = [role.mention for role in member.roles if role.name != "@everyone"]
    if not roles:
        roles_value = "Aucun rôle spécifique."
    else:
        roles_value = ", ".join(roles[:10])
        if len(roles) > 10:
            roles_value += f", et {len(roles) - 10} de plus..."
            
    embed = discord.Embed(
        title=f"👤 Informations sur {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.dark_grey(),
        timestamp=datetime.now()
    )
    
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=False)
    embed.add_field(name="Nom d'utilisateur", value=member.name, inline=True)
    embed.add_field(name="Surnom (serveur)", value=member.nick or "Aucun", inline=True)
    embed.add_field(name="Compte créé le", value=member.created_at.strftime("%d/%m/%Y à %H:%M"), inline=False)
    embed.add_field(name="A rejoint le", value=member.joined_at.strftime("%d/%m/%Y à %H:%M") if member.joined_at else "Inconnu", inline=False)
    embed.add_field(name=f"Rôles ({len(roles)})", value=roles_value, inline=False)
    
    await ctx.send(embed=embed)
    
@bot.command(name='serverinfo', aliases=['si'])
async def server_info(ctx: commands.Context):
    """Affiche les informations sur le serveur."""
    guild = ctx.guild
    embed = discord.Embed(
        title=f"📊 Informations sur le Serveur {guild.name}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="ID du Serveur", value=guild.id, inline=False)
    embed.add_field(name="Propriétaire", value=guild.owner.mention, inline=True)
    embed.add_field(name="Région", value=str(guild.preferred_locale), inline=True)
    embed.add_field(name="Membres", value=guild.member_count, inline=True)
    embed.add_field(name="Canaux Texte", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Canaux Vocaux", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="Rôles", value=len(guild.roles), inline=True)
    embed.add_field(name="Niveau Boost", value=f"Niveau {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
    embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"), inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='coin', aliases=['flip'])
async def coin_flip(ctx: commands.Context):
    """Lance une pièce à pile ou face."""
    result = random.choice(["Pile (Tails)", "Face (Heads)"])
    await ctx.send(f"👑 **{ctx.author.display_name}** a lancé une pièce. Résultat : **{result}**")


@bot.command(name='dice', aliases=['dé', 'roll'])
async def roll_dice(ctx, faces: int = 6):
    """Lance un dé avec le nombre de faces spécifié (max 100)."""
    if faces < 2 or faces > 100:
        return await ctx.send("❌ Veuillez spécifier un nombre de faces entre 2 et 100.")

    result = random.randint(1, faces)
    await ctx.send(f"🎲 **{ctx.author.display_name}** a lancé un dé à {faces} faces. Résultat : **{result}**")

@bot.command(name='8ball')
async def eight_ball(ctx, *, question: str):
    """Répond à une question par un oui, un non, ou une réponse vague."""
    responses = [
        "Oui, absolument.", "C'est certain.", "Sans aucun doute.", "Très probablement.",
        "Oui.", "Les signes pointent vers le oui.", "La réponse est non.",
        "Non.", "N'y compte pas.", "Mes sources disent non.",
        "Je ne suis pas sûr. Essaie plus tard.", "Mieux vaut ne pas te le dire maintenant.", "Concentrez-vous et redemandez.",
    ]
    embed = discord.Embed(
        title="🎱 Magic 8 Ball",
        description=f"**Question :** {question}\n\n**Réponse :** {random.choice(responses)}",
        color=discord.Color.dark_purple()
    )
    await ctx.send(embed=embed)
    
@bot.command(name='roleinfo', aliases=['ri'])
async def role_info(ctx, role: discord.Role):
    """Affiche les informations d'un rôle."""
    members_with_role = len(role.members)
    
    embed = discord.Embed(
        title=f"🏷️ Informations sur le rôle {role.name}",
        color=role.color if role.color != discord.Color.default() else discord.Color.greyple(),
        timestamp=datetime.now()
    )
    embed.add_field(name="ID", value=role.id, inline=False)
    embed.add_field(name="Couleur", value=str(role.color), inline=True)
    embed.add_field(name="Membres", value=members_with_role, inline=True)
    embed.add_field(name="Position", value=f"#{role.position}", inline=True)
    embed.add_field(name="Créé le", value=role.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Mentionnable", value="✅ Oui" if role.mentionable else "❌ Non", inline=True)
    
    await ctx.send(embed=embed)


@bot.command(name='traduction', aliases=['translate'])
async def translate_text(ctx: commands.Context, target_lang: str, *, text: str):
    """Traduit un texte donné vers une langue cible. (+traduction fr Hello)"""
    
    target_lang = target_lang.lower()
    
    LANG_MAP = {
        "fr": "Français", "en": "Anglais", "es": "Espagnol", "de": "Allemand", "it": "Italien"
    }
    
    if target_lang not in LANG_MAP:
        return await ctx.send(f"❌ Langue cible non supportée ou format invalide. Exemples : `fr`, `en`, `es`.")

    await ctx.send("⏳ Traduction en cours...")
    
    
    query = f"traduire '{text}' en {LANG_MAP[target_lang]}"
    
    try:
        search_result = await google_search(query=query)
        
        translated_text = "Désolé, la traduction n'a pas pu être extraite."
        if search_result and search_result[0].get('snippet'):
            snippet = search_result[0]['snippet'].strip()
            translated_text = snippet if len(snippet) < 500 else snippet[:500] + "..." 
            
    except Exception:
        translated_text = "Erreur de connexion à l'outil de traduction simulé."
        
    embed = discord.Embed(
        title=f"🌐 Traduction vers le {LANG_MAP[target_lang]}",
        color=discord.Color.dark_green()
    )
    embed.add_field(name="Texte Original", value=f"```\n{text}\n```", inline=False)
    embed.add_field(name="Texte Traduit", value=f"```\n{translated_text}\n```", inline=False)
    
    await ctx.send(embed=embed)


@bot.command(name='say')
@commands.has_permissions(manage_messages=True)
async def say_message(ctx, channel: discord.TextChannel, *, message: str):
    """Fait parler le bot dans le salon spécifié et supprime le message de commande."""
    try:
        await channel.send(message)
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission d'envoyer un message dans ce salon.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de l'envoi du message : {e}")

@bot.command(name='embed')
@commands.has_permissions(administrator=True)
async def create_embed(ctx, channel: discord.TextChannel, *, content: str):
    """Crée et envoie un embed simple dans un salon. Format: Titre | Description"""
    
    if '|' not in content:
        return await ctx.send("❌ Format invalide. Utilisez : `+embed #salon Titre | Description`")
    
    try:
        title, description = content.split('|', 1)
    except ValueError:
        return await ctx.send("❌ Veuillez fournir à la fois un titre et une description séparés par `|`.")

    embed = discord.Embed(
        title=title.strip(),
        description=description.strip(),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    await channel.send(embed=embed)
    await ctx.message.delete()



@bot.command(name='help', aliases=['aide', 'h'])
async def help_command(ctx: commands.Context):
    """Affiche la liste des commandes et leur description."""
    embed = discord.Embed(
        title="🌟 Commandes du Bot Hoshikuzu 🌟",
        description="Liste complète des commandes disponibles.",
        color=discord.Color.from_rgb(255, 192, 203), # Rose pâle
        timestamp=datetime.now()
    )

    embed.add_field(
        name="⚙️ Configuration (Admin)",
        value="""
        `+config` - Affiche la configuration actuelle
        `+setlogs #salon` - Salon pour la journalisation
        `+setboostchannel #salon` - Salon des remerciements de boost ✨
        `+setticketcategory #catégorie` - Catégorie des tickets
        `+setticketrole @rôle` - Rôle support pour les tickets
        `+sendticketpanel #salon` - Envoie le bouton de ticket
        `+sendrules #salon` - Envoie l'embed des règles 📜
        `+sendrolespanel #salon` - Envoie le panneau de Rôles par Réaction 💫
        `+welcomeembed #salon` - Salon de bienvenue (embed)
        `+welcomesimple #salon` - Salon de bienvenue (simple)
        `+leavechat #salon` - Salon des départs
        """,
        inline=False
    )

    embed.add_field(
        name="👮 Modération (Admin/Staff)",
        value="""
        `+ban @membre [raison]` - Bannit un membre 🔨
        `+kick @membre [raison]` - Expulse un membre 👢
        `+mute @membre [durée en min]` - Met un membre en timeout 🔇
        `+unmute @membre` - Retire le timeout 🔊
        `+clear [nombre]` - Supprime des messages 🧹
        `+close` - Ferme le ticket actuel
        `+add @membre` - Ajoute un membre au ticket
        `+say #salon [message]` - Fait parler le bot
        `+embed #salon [Titre | Description]` - Envoie un embed
        `+warn @membre [raison]` - Donne un avertissement 🚨
        `+warnings @membre` - Affiche les avertissements 📋
        `+delwarn @membre [ID]` - Supprime un avertissement
        """,
        inline=False
    )
    
    embed.add_field(
        name="📈 Niveaux (Leveling)",
        value="""
        `+rank [@membre]` - Affiche le niveau et l'XP 📊
        `+leaderboard` - Affiche le classement des niveaux 🏆
        """,
        inline=False
    )

    embed.add_field(
        name="💰 Économie & Cadeaux",
        value="""
        `+balance [@membre]` - Affiche le solde ⭐
        `+daily` - Récompense quotidienne 🎁
        `+work` - Permet de travailler pour de l'argent 💼
        `+gstart <durée> <gagnants> <prix>` - Démarre un cadeau 🎉
        `+addmoney @membre [montant]` - Ajoute de la monnaie (Admin)
        `+setmoney @membre [montant]` - Définit le solde (Admin)
        """,
        inline=False
    )

    embed.add_field(
        name="😂 Fun & Interaction",
        value="""
        `+hug [@membre]` - Fait un gros câlin 💖
        `+meme` - Affiche un mème aléatoire 😂
        `+coin` - Lance une pièce 👑
        `+dice [faces]` - Lance un dé 🎲
        `+8ball [question]` - Pose une question 🔮
        """,
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Utilitaires",
        value="""
        `+ping` - Affiche la latence du bot 🏓
        `+traduction <langue> <texte>` - Traduit un texte 🌐
        `+avatar [@membre]` - Affiche l'avatar
        `+userinfo [@membre]` - Infos du membre 👤
        `+serverinfo` - Infos du serveur 📊
        `+roleinfo @rôle` - Infos d'un rôle 🏷️
        """,
        inline=False
    )
    
    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    await ctx.send(embed=embed)






if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ Erreur: La variable d'environnement 'DISCORD_BOT_TOKEN' n'est pas définie.")
    else:
        threading.Thread(target=keep_alive, daemon=True).start()

        try:
            bot.run(TOKEN) # OU asyncio.run(main())
        except Exception as e:
            print(f"❌ Erreur inattendue avant le lancement du serveur : {e}")


import threading, http.server, socketserver, os

def keep_alive():
    """
    Ouvre un petit serveur HTTP sur le port requis par Render pour éviter l'arrêt automatique.
    """
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"✅ Serveur keep-alive lancé sur le port {port}")
        httpd.serve_forever()

if not os.getenv("DISCORD_BOT_TOKEN"):
    print("❌ Erreur: La variable d'environnement 'DISCORD_BOT_TOKEN' n'est pas définie.")
else:
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    threading.Thread(target=keep_alive, daemon=True).start()

    try:
        bot.run(TOKEN)
    except discord.HTTPException as e:
        if e.status == 429:
            print("❌ Erreur : Trop de requêtes (Rate Limit). Attends avant de relancer.")
        else:
            raise e
    except KeyboardInterrupt:
        print("🛑 Bot arrêté manuellement.")

@bot.event
async def on_voice_state_update(member, before, after):
    """Crée automatiquement un salon vocal temporaire quand un membre rejoint 'Créer un vocal'."""
    try:
        if after.channel and after.channel.name.lower() == "créer un vocal":
            category = after.channel.category
            guild = after.channel.guild

            # Créer un salon vocal temporaire
            new_vc = await guild.create_voice_channel(
                name=f"🎤 Salon de {member.display_name}",
                category=category,
                reason="Salon vocal temporaire créé automatiquement"
            )

            # Déplacer le membre dans le nouveau salon
            await member.move_to(new_vc)
            print(f"🎤 Salon temporaire créé : {new_vc.name} pour {member.display_name}")

            # Supprimer automatiquement le salon quand il devient vide
            async def check_empty():
                await asyncio.sleep(10)
                while True:
                    if len(new_vc.members) == 0:
                        await new_vc.delete(reason="Salon temporaire vide - suppression automatique")
                        print(f"🗑️ Salon temporaire supprimé : {new_vc.name}")
                        break
                    await asyncio.sleep(10)

            bot.loop.create_task(check_empty())

    except Exception as e:
        print(f"❌ Erreur système voc: {e}")

# === AJOUT SÛR : auto-role config, createvoc, lock/unlock, auto-temp-voice, help stylisé ===
import json, os, asyncio
from discord.ext import commands

CONFIG_FILE = "data/config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_config(cfg):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

_config = load_config()

# register aurole if not already registered
if "aurole" not in bot.all_commands:
    @bot.command(name="aurole")
    @commands.has_permissions(manage_roles=True)
    async def set_auto_role(ctx, role: discord.Role):
        _config["auto_role_id"] = role.id
        save_config(_config)
        await ctx.send(f"✅ Le rôle automatique a été défini sur {role.mention}")

# add auto-role listener (uses add_listener so it doesn't override existing handlers)
async def _auto_role_on_join(member: discord.Member):
    try:
        auto_role_id = _config.get("auto_role_id")
        if auto_role_id:
            role = member.guild.get_role(auto_role_id)
            if role:
                await member.add_roles(role)
                print(f"✅ Rôle automatique '{role.name}' attribué à {member.name}")
    except Exception as e:
        print(f"❌ Erreur attribution auto-rôle : {e}")

# ensure we don't register twice
if "_auto_role_on_join" not in [h.__name__ for h in bot.listeners.get('on_member_join', [])]:
    bot.add_listener(_auto_role_on_join, 'on_member_join')

# createvoc command
if "createvoc" not in bot.all_commands:
    @bot.command(name="createvoc")
    @commands.has_permissions(manage_channels=True)
    async def createvoc(ctx):
        guild = ctx.guild
        category = None
        for cat in guild.categories:
            if "vocal" in cat.name.lower() or "voice" in cat.name.lower():
                category = cat
                break

        existing = discord.utils.get(guild.voice_channels, name="Créer un vocal")
        if existing:
            await ctx.send("🔊 Le salon 'Créer un vocal' existe déjà.")
            return

        new_channel = await guild.create_voice_channel("Créer un vocal", category=category)
        await ctx.send(f"✅ Salon vocal **{new_channel.name}** créé avec succès !")
        print(f"Salon 'Créer un vocal' créé dans {guild.name}")

# lock/unlock commands
if "lock" not in bot.all_commands:
    @bot.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(ctx, target: str = None):
        if target == "vocal":
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.connect = False
                await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
                await ctx.send(f"🔒 Salon vocal **{channel.name}** verrouillé.")
            else:
                await ctx.send("❌ Tu dois être dans un salon vocal pour le verrouiller.")
        else:
            channel = ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"🔒 Salon texte **{channel.name}** verrouillé.")

if "unlock" not in bot.all_commands:
    @bot.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(ctx, target: str = None):
        if target == "vocal":
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.connect = True
                await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
                await ctx.send(f"🔓 Salon vocal **{channel.name}** déverrouillé.")
            else:
                await ctx.send("❌ Tu dois être dans un salon vocal pour le déverrouiller.")
        else:
            channel = ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = True
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"🔓 Salon texte **{channel.name}** déverrouillé.")

# auto temporary voice channels listener
async def _auto_temp_vc(member, before, after):
    try:
        if after and after.channel and after.channel.name and after.channel.name.lower() == "créer un vocal":
            guild = member.guild
            category = after.channel.category
            channel_name = f"🎤 Salon de {member.display_name}"
            new_vc = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                reason="Salon vocal temporaire créé automatiquement"
            )

            try:
                await member.move_to(new_vc)
            except Exception as e:
                print(f"⚠️ Impossible de déplacer {member.display_name} vers {new_vc.name}: {e}")

            print(f"🎤 Salon temporaire créé : {new_vc.name} pour {member.display_name}")

            async def monitor_and_delete(vc_id, guild_id):
                await asyncio.sleep(8)
                g = bot.get_guild(guild_id)
                while True:
                    ch = g.get_channel(vc_id) if g else None
                    if ch is None:
                        break
                    if len(ch.members) == 0:
                        try:
                            await ch.delete(reason="Salon temporaire vide - suppression automatique")
                            print(f"🗑️ Salon temporaire supprimé : {vc_id}")
                        except Exception as e:
                            print(f"Erreur suppression salon temporaire: {e}")
                        break
                    await asyncio.sleep(8)

            bot.loop.create_task(monitor_and_delete(new_vc.id, guild.id))
    except Exception as e:
        print(f"❌ Erreur système voc: {e}")

# ensure listener not registered twice
if "_auto_temp_vc" not in [h.__name__ for h in bot.listeners.get('on_voice_state_update', [])]:
    bot.add_listener(_auto_temp_vc, 'on_voice_state_update')

# replace help command with stylized version
try:
    bot.remove_command("help")
except Exception:
    pass

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="🌌 Aide — Commandes de Hoshikuzu",
        description="Voici toutes les commandes disponibles ✨",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="⚙️ Configuration",
        value="`+aurole @rôle` — Définit le rôle attribué automatiquement aux nouveaux membres\n"
              "`+help` — Affiche ce message d’aide",
        inline=False
    )

    embed.add_field(
        name="🔊 Vocaux",
        value="`+createvoc` — Crée le salon spécial **Créer un vocal** (pour vocaux temporaires)\n"
              "`+lock [vocal]` — Verrouille un salon texte ou vocal\n"
              "`+unlock [vocal]` — Déverrouille un salon texte ou vocal",
        inline=False
    )

    embed.add_field(
        name="🎧 Automatique",
        value="🪄 Quand quelqu’un rejoint **Créer un vocal**, un salon temporaire est créé automatiquement et supprimé lorsqu’il est vide.\n"
              "🧍 Les nouveaux membres reçoivent automatiquement le rôle défini avec `+aurole`.",
        inline=False
    )

    embed.set_footer(text="✨ Hoshikuzu — by your starry bot 🌙")
    await ctx.send(embed=embed)

# end addon


# ======== AJOUTS GPT (NE RIEN SUPPRIMER AU-DESSUS) ========
import asyncio, json, os
from discord.ext import commands

# Configuration file for auto-role
_GPT_CONFIG_FILE = "data/gpt_config.json"

def _gpt_load_config():
    if os.path.exists(_GPT_CONFIG_FILE):
        with open(_GPT_CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def _gpt_save_config(cfg):
    os.makedirs("data", exist_ok=True)
    with open(_GPT_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

_gpt_config = _gpt_load_config()

# Safe registration helpers to avoid duplicate commands/listeners
def _register_command_if_missing(name):
    return name not in getattr(bot, "all_commands", {})

# +aurole: set automatic role for newcomers
if _register_command_if_missing("aurole"):
    @bot.command(name="aurole")
    @commands.has_permissions(manage_roles=True)
    async def _gpt_set_auto_role(ctx, role: discord.Role):
        _gpt_config["auto_role_id"] = role.id
        _gpt_save_config(_gpt_config)
        await ctx.send(f"✅ Le rôle automatique a été défini sur {role.mention}")

# Auto-assign role on join (listener added safely)
async def _gpt_auto_role_on_join(member: discord.Member):
    try:
        auto_role_id = _gpt_config.get("auto_role_id")
        if auto_role_id:
            role = member.guild.get_role(auto_role_id)
            if role:
                await member.add_roles(role)
                print(f"✅ Rôle automatique '{role.name}' attribué à {member.name}")
    except Exception as e:
        print(f"❌ Erreur attribution auto-rôle : {e}")

# add listener if not already present
_existing = [h.__name__ for h in bot.listeners.get('on_member_join', [])] if getattr(bot, "listeners", None) else []
if "_gpt_auto_role_on_join" not in _existing:
    bot.add_listener(_gpt_auto_role_on_join, 'on_member_join')

# +createvoc: create the trigger voice channel "Créer un vocal"
if _register_command_if_missing("createvoc"):
    @bot.command(name="createvoc")
    @commands.has_permissions(manage_channels=True)
    async def _gpt_createvoc(ctx):
        guild = ctx.guild
        category = None
        for cat in guild.categories:
            if "vocal" in cat.name.lower() or "voice" in cat.name.lower():
                category = cat
                break

        existing = discord.utils.get(guild.voice_channels, name="Créer un vocal")
        if existing:
            await ctx.send("🔊 Le salon 'Créer un vocal' existe déjà.")
            return

        new_channel = await guild.create_voice_channel("Créer un vocal", category=category)
        await ctx.send(f"✅ Salon vocal **{new_channel.name}** créé avec succès !")
        print(f"Salon 'Créer un vocal' créé dans {guild.name}")

# +lock / +unlock commands
if _register_command_if_missing("lock"):
    @bot.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def _gpt_lock(ctx, target: str = None):
        if target == "vocal":
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.connect = False
                await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
                await ctx.send(f"🔒 Salon vocal **{channel.name}** verrouillé.")
            else:
                await ctx.send("❌ Tu dois être dans un salon vocal pour le verrouiller.")
        else:
            channel = ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"🔒 Salon texte **{channel.name}** verrouillé.")

if _register_command_if_missing("unlock"):
    @bot.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def _gpt_unlock(ctx, target: str = None):
        if target == "vocal":
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
                overwrite = channel.overwrites_for(ctx.guild.default_role)
                overwrite.connect = True
                await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
                await ctx.send(f"🔓 Salon vocal **{channel.name}** déverrouillé.")
            else:
                await ctx.send("❌ Tu dois être dans un salon vocal pour le déverrouiller.")
        else:
            channel = ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = True
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"🔓 Salon texte **{channel.name}** déverrouillé.")

# Auto temporary voice channel creator: listener
async def _gpt_auto_temp_vc(member, before, after):
    try:
        if after and getattr(after, "channel", None) and getattr(after.channel, "name", "").lower() == "créer un vocal":
            guild = member.guild
            category = after.channel.category
            channel_name = f"🎤 Salon de {member.display_name}"
            new_vc = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                reason="Salon vocal temporaire créé automatiquement"
            )
            try:
                await member.move_to(new_vc)
            except Exception as e:
                print(f"⚠️ Impossible de déplacer {member.display_name} vers {new_vc.name}: {e}")
            print(f"🎤 Salon temporaire créé : {new_vc.name} pour {member.display_name}")

            async def _gpt_monitor(vc_id, guild_id):
                await asyncio.sleep(8)
                g = bot.get_guild(guild_id)
                while True:
                    ch = g.get_channel(vc_id) if g else None
                    if ch is None:
                        break
                    if len(ch.members) == 0:
                        try:
                            await ch.delete(reason="Salon temporaire vide - suppression automatique")
                            print(f"🗑️ Salon temporaire supprimé : {vc_id}")
                        except Exception as e:
                            print(f"Erreur suppression salon temporaire: {e}")
                        break
                    await asyncio.sleep(8)

            bot.loop.create_task(_gpt_monitor(new_vc.id, guild.id))
    except Exception as e:
        print(f"❌ Erreur système voc: {e}")

_existing_vc = [h.__name__ for h in bot.listeners.get('on_voice_state_update', [])] if getattr(bot, "listeners", None) else []
if "_gpt_auto_temp_vc" not in _existing_vc:
    bot.add_listener(_gpt_auto_temp_vc, 'on_voice_state_update')

# Replace help with stylized version, but only if not already provided by the bot
try:
    bot.remove_command("help")
except Exception:
    pass

@bot.command(name="help")
async def _gpt_help(ctx):
    embed = discord.Embed(
        title="🌌 Aide — Commandes de Hoshikuzu",
        description="Voici toutes les commandes disponibles ✨",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="⚙️ Configuration",
        value="`+aurole @rôle` — Définit le rôle attribué automatiquement aux nouveaux membres\n"
              "`+help` — Affiche ce message d’aide",
        inline=False
    )
    embed.add_field(
        name="🔊 Vocaux",
        value="`+createvoc` — Crée le salon spécial **Créer un vocal** (pour vocaux temporaires)\n"
              "`+lock [vocal]` — Verrouille un salon texte ou vocal\n"
              "`+unlock [vocal]` — Déverrouille un salon texte ou vocal",
        inline=False
    )
    embed.add_field(
        name="🎧 Automatique",
        value="🪄 Quand quelqu’un rejoint **Créer un vocal**, un salon temporaire est créé automatiquement et supprimé lorsqu’il est vide.\n"
              "🧍 Les nouveaux membres reçoivent automatiquement le rôle défini avec `+aurole`.",
        inline=False
    )
    embed.set_footer(text="✨ Hoshikuzu — by your starry bot 🌙")
    await ctx.send(embed=embed)

# ======== FIN AJOUTS GPT ========


# ======== AJOUTS ET CORRECTIONS GPT ========

import discord
from discord.ext import commands
import asyncio
import json
import os

# === Initialisation du bot ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents)

# === CONFIG AUTO-ROLE ===
CONFIG_FILE = "data/config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_config(cfg):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

config = load_config()

@bot.command()
@commands.has_permissions(manage_roles=True)
async def aurole(ctx, role: discord.Role):
    """Définit le rôle automatique attribué aux nouveaux membres."""
    config["auto_role_id"] = role.id
    save_config(config)
    await ctx.send(f"✅ Le rôle automatique a été défini sur {role.mention}")

@bot.event
async def on_member_join(member: discord.Member):
    """Assigne automatiquement le rôle défini et envoie un message d'accueil."""
    try:
        # Rôle automatique
        auto_role_id = config.get("auto_role_id")
        if auto_role_id:
            role = member.guild.get_role(auto_role_id)
            if role:
                await member.add_roles(role)
                print(f"✅ Rôle automatique '{role.name}' attribué à {member.name}")

        # Message d'accueil
        embed = discord.Embed(
            title="🎉 Nouveau membre !",
            description=f"{member.mention} a rejoint le serveur ✨",
            color=discord.Color.purple()
        )
        embed.add_field(name="Auteur", value=member.mention, inline=True)
        embed.set_thumbnail(
            url=member.avatar.url if member.avatar else member.default_avatar.url
        )
        if member.guild.system_channel:
            await member.guild.system_channel.send(embed=embed)
        print(f"✅ Nouveau membre détecté : {member.name}")
    except Exception as e:
        print(f"Erreur dans on_member_join : {e}")

# === COMMANDES VOCALES ===
@bot.command()
@commands.has_permissions(manage_channels=True)
async def createvoc(ctx):
    """Crée le salon vocal 'Créer un vocal'."""
    guild = ctx.guild
    existing = discord.utils.get(guild.voice_channels, name="Créer un vocal")
    if existing:
        await ctx.send("🔊 Le salon 'Créer un vocal' existe déjà.")
        return

    category = None
    for cat in guild.categories:
        if "vocal" in cat.name.lower() or "voice" in cat.name.lower():
            category = cat
            break

    new_channel = await guild.create_voice_channel("Créer un vocal", category=category)
    await ctx.send(f"✅ Salon vocal **{new_channel.name}** créé avec succès !")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, target: str = None):
    """Verrouille un salon texte ou vocal."""
    if target == "vocal":
        if ctx.author.voice and ctx.author.voice.channel:
            channel = ctx.author.voice.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.connect = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"🔒 Salon vocal **{channel.name}** verrouillé.")
        else:
            await ctx.send("❌ Tu dois être dans un salon vocal pour le verrouiller.")
    else:
        channel = ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔒 Salon texte **{channel.name}** verrouillé.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, target: str = None):
    """Déverrouille un salon texte ou vocal."""
    if target == "vocal":
        if ctx.author.voice and ctx.author.voice.channel:
            channel = ctx.author.voice.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.connect = True
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(f"🔓 Salon vocal **{channel.name}** déverrouillé.")
        else:
            await ctx.send("❌ Tu dois être dans un salon vocal pour le déverrouiller.")
    else:
        channel = ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔓 Salon texte **{channel.name}** déverrouillé.")

# === GESTION DES VOCAUX TEMPORAIRES ===
@bot.event
async def on_voice_state_update(member, before, after):
    """Crée un salon vocal temporaire quand un membre rejoint 'Créer un vocal'."""
    try:
        if after.channel and after.channel.name.lower() == "créer un vocal":
            guild = member.guild
            category = after.channel.category
            new_vc = await guild.create_voice_channel(
                name=f"🎤 Salon de {member.display_name}",
                category=category,
                reason="Salon vocal temporaire créé automatiquement"
            )
            await member.move_to(new_vc)
            print(f"🎧 Salon temporaire créé : {new_vc.name}")

            async def monitor_vc(vc):
                await asyncio.sleep(10)
                while True:
                    if len(vc.members) == 0:
                        await vc.delete(reason="Salon temporaire vide - suppression automatique")
                        print(f"🗑️ Salon temporaire supprimé : {vc.name}")
                        break
                    await asyncio.sleep(10)

            bot.loop.create_task(monitor_vc(new_vc))
    except Exception as e:
        print(f"❌ Erreur système voc: {e}")

# === HELP STYLISÉ ===
@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🌌 Aide — Commandes de Hoshikuzu",
        description="Voici toutes les commandes disponibles ✨",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="⚙️ Configuration",
        value="`+aurole @rôle` — Définit le rôle auto pour les nouveaux membres",
        inline=False
    )
    embed.add_field(
        name="🔊 Vocaux",
        value="`+createvoc` — Crée le salon spécial 'Créer un vocal'\n"
              "`+lock [vocal]` — Verrouille un salon texte ou vocal\n"
              "`+unlock [vocal]` — Déverrouille un salon texte ou vocal",
        inline=False
    )
    embed.add_field(
        name="🎧 Automatique",
        value="🪄 Quand quelqu’un rejoint 'Créer un vocal', un salon temporaire est créé automatiquement.\n"
              "🧍 Les nouveaux membres reçoivent automatiquement le rôle défini avec `+aurole`.",
        inline=False
    )
    embed.set_footer(text="✨ Hoshikuzu — by your starry bot 🌙")
    await ctx.send(embed=embed)

# === LANCEMENT DU BOT ===
bot.run(os.getenv("DISCORD_BOT_TOKEN"))


# ======== FIN DES AJOUTS GPT ========
