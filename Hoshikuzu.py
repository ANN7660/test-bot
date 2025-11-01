#!/usr/bin/env python3
# Hoshikuzu_help_voc_antilink.py
# Bot with:
# - +help interactive (pages with arrows)
# - +createvoc: lobby + creation/removal of temporary voice channels
# - keep-alive HTTP for Render
# - DataManager JSON simple for saving voc/config
# - Anti-link system: deletes messages with links (except admins) and warns the author
# Configure DISCORD_BOT_TOKEN in environment variables before running.

import os
import re
import discord
from discord.ext import commands, tasks
import asyncio
import json
import datetime
import threading
import http.server
import socketserver
from typing import Optional

# ------------------------------
# Keep-alive (useful for Render web services)
# ------------------------------
def keep_alive():
    try:
        port = int(os.environ.get("PORT", 8080))
    except Exception:
        port = 8080

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            return

    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        print(f"[keep-alive] HTTP server running on port {port}")
        httpd.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# ------------------------------
# Simple DataManager using JSON (async-safe with asyncio.Lock)
# ------------------------------
class DataManager:
    def __init__(self, filename="hoshikuzu_data.json"):
        self.filename = filename
        self.lock = asyncio.Lock()
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[DataManager] failed to read JSON: {e}")
        # default structure
        return {"voc": {}, "config": {}}

    async def save(self):
        async with self.lock:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    # voc registry
    async def register_temp_vc(self, channel_id, owner_id):
        cid = str(channel_id)
        self.data.setdefault("voc", {})[cid] = {
            "owner": str(owner_id),
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        await self.save()

    async def unregister_temp_vc(self, channel_id):
        cid = str(channel_id)
        if cid in self.data.get("voc", {}):
            del self.data["voc"][cid]
            await self.save()

    def is_temp_vc(self, channel_id):
        return str(channel_id) in self.data.get("voc", {})

    # config helpers
    async def set_config(self, guild_id, key, value):
        gid = str(guild_id)
        self.data.setdefault("config", {}).setdefault(gid, {})[key] = value
        await self.save()

    def get_config(self, guild_id, key, default=None):
        gid = str(guild_id)
        return self.data.get("config", {}).get(gid, {}).get(key, default)

data_manager = DataManager()

# ------------------------------
# Bot init
# ------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)
bot.data_manager = data_manager

# ------------------------------
# Help (paged) view
# ------------------------------
HELP_PAGES = [
    {
        "title": "🎙️ Vocaux - Page 1/5",
        "desc": "`+createvoc` — crée le salon principal (Créer ton salon 🔊)\n`+lockvoc` — verrouille un vocal (à ajouter)\n`+renamevoc` — renommer un vocal (à ajouter)\n`+limitvoc` — limiter un vocal (à ajouter)"
    },
    {
        "title": "💰 Économie - Page 2/5",
        "desc": "`+balance` `+daily` `+work` `+give @user amount` `+coinflip` `+slots` (implémentations exemples)"
    },
    {
        "title": "🧾 Modération - Page 3/5",
        "desc": "`+warn @user reason` `+warnings @user` `+delwarn @user id` `+clear <n>` `+kick` `+ban`"
    },
    {
        "title": "🎉 Fun - Page 4/5",
        "desc": "`+meme` `+hug @user` `+avatar @user` `+8ball` `+ship`"
    },
    {
        "title": "⚙️ Config & Utilitaires - Page 5/5",
        "desc": "`+config` — menu interactif (logs, welcome, suggestions, auto-role)\n`+userinfo` `+serverinfo` `+say`"
    }
]

class HelpView(discord.ui.View):
    def __init__(self, author_id: int, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.page = 0
        self.author_id = author_id

    async def update_message(self, interaction: discord.Interaction):
        page = HELP_PAGES[self.page]
        embed = discord.Embed(title=page["title"], description=page["desc"], color=discord.Color.blurple())
        embed.set_footer(text=f"Page {self.page+1}/{len(HELP_PAGES)} • Utilisateur: {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # only allow the author or admins to use the view to prevent hijack
        if interaction.user.id != self.author_id and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ Tu n'es pas autorisé·e à utiliser ce menu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.page = (self.page - 1) % len(HELP_PAGES)
        await self.update_message(interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.page = (self.page + 1) % len(HELP_PAGES)
        await self.update_message(interaction)

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
    """Affiche l'aide paginée avec boutons"""
    view = HelpView(author_id=ctx.author.id, timeout=180)
    page = HELP_PAGES[0]
    embed = discord.Embed(title=page["title"], description=page["desc"], color=discord.Color.blurple())
    embed.set_footer(text=f"Page 1/{len(HELP_PAGES)} • Utilisateur: {ctx.author.display_name}")
    await ctx.send(embed=embed, view=view)

# ------------------------------
# createvoc command and voice handling
# ------------------------------
@bot.command(name="createvoc")
@commands.has_permissions(manage_channels=True)
async def create_voc(ctx: commands.Context):
    """Crée le salon 'Créer ton salon 🔊' dans une catégorie dédiée"""
    guild = ctx.guild
    category_name = "Vocaux Temporaires 🔊"
    # find or create category
    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        try:
            category = await guild.create_category(category_name)
        except Exception as e:
            await ctx.send("❌ Erreur lors de la création de la catégorie.")
            print("create_voc: could not create category:", e)
            return
    # avoid duplicate
    existing = discord.utils.get(guild.voice_channels, name="Créer ton salon 🔊")
    if existing:
        await ctx.send("⚠️ Le salon 'Créer ton salon 🔊' existe déjà.")
        bot.temp_voice_lobby = existing.id
        return
    try:
        channel = await guild.create_voice_channel("Créer ton salon 🔊", category=category)
        bot.temp_voice_lobby = channel.id
        await ctx.send(f"✅ Salon vocal créé : {channel.mention}")
    except Exception as e:
        await ctx.send("❌ Impossible de créer le salon vocal.")
        print("create_voc error:", e)

@bot.event
async def on_voice_state_update(member, before, after):
    """Créer un salon temporaire quand quelqu'un rejoint le lobby, et supprimer s'il devient vide"""
    try:
        # someone joined the lobby -> create private temp VC and move them
        if after.channel and hasattr(bot, "temp_voice_lobby") and after.channel.id == getattr(bot, "temp_voice_lobby"):
            guild = member.guild
            category = after.channel.category
            # create a personal voice channel
            chan_name = f"🔊 Salon de {member.display_name}"
            temp = await guild.create_voice_channel(chan_name, category=category)
            # set permissions so only the member (and mods) can manage (common pattern)
            try:
                await temp.set_permissions(member, connect=True, speak=True, manage_channels=True)
            except Exception:
                pass
            await data_manager.register_temp_vc(temp.id, member.id)
            # move member
            try:
                await member.move_to(temp)
            except Exception:
                pass
            return

        # someone left a channel : if it was a temp vc and is now empty -> delete it
        if before.channel and data_manager.is_temp_vc(before.channel.id):
            ch = before.channel
            if len(ch.members) == 0:
                try:
                    await ch.delete()
                except Exception:
                    pass
                await data_manager.unregister_temp_vc(ch.id)
    except Exception as e:
        print("on_voice_state_update error:", e)

# ------------------------------
# Anti-link: delete messages containing links (except admins/mods)
# ------------------------------
URL_REGEX = re.compile(r"(https?://\S+)|(\bdiscord\.gg/\S+)", re.IGNORECASE)

@bot.event
async def on_message(message: discord.Message):
    # Don't process bot messages
    if message.author.bot:
        return

    # Allow admins/mods to post links
    if message.author.guild_permissions.manage_guild or message.author.guild_permissions.manage_messages or message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    # Option: allow links in specific channels (config 'allow_links' as list of channel ids)
    allow_list = data_manager.get_config(message.guild.id, "allow_links", [])
    try:
        allow_list = [int(x) for x in allow_list] if allow_list else []
    except Exception:
        allow_list = []

    if message.channel.id in allow_list:
        await bot.process_commands(message)
        return

    # Check for URLs
    if URL_REGEX.search(message.content):
        try:
            await message.delete()
        except Exception:
            pass
        try:
            warn_msg = await message.channel.send(f"🚫 {message.author.mention} — Les liens ne sont pas autorisés ici. Merci de ne pas en poster.", delete_after=8)
        except Exception:
            pass
        # (Optionally) store a warning in data_manager (simple counter)
        gid = str(message.guild.id)
        uid = str(message.author.id)
        # store warn counter under config/warn_counts
        cfg = data_manager.data.setdefault("config", {}).setdefault(gid, {})
        wc = cfg.get("link_warns", {})
        wc[uid] = wc.get(uid, 0) + 1
        cfg["link_warns"] = wc
        # save asynchronously
        try:
            await data_manager.save()
        except Exception:
            pass
        return

    # process other commands normally
    await bot.process_commands(message)

# ------------------------------
# small utility commands (placeholders)
# ------------------------------
@bot.command(name="ping")
async def ping_cmd(ctx: commands.Context):
    await ctx.send(f"🏓 Pong — {round(bot.latency * 1000)} ms")

@bot.command(name="say")
@commands.has_permissions(manage_messages=True)
async def say_cmd(ctx: commands.Context, channel: discord.TextChannel, *, text: str):
    await channel.send(text)
    try:
        await ctx.message.delete()
    except:
        pass

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

# ------------------------------
# Startup and run
# ------------------------------
@bot.event
async def on_ready():
    print(f"[BOT] Connecté comme {bot.user} ({bot.user.id})")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ DISCORD_BOT_TOKEN non défini — ajoute la variable d'environnement et relance.")
else:
    bot.run(TOKEN)
