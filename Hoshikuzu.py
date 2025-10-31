# ==========================
# Hoshikuzu.py — version avec système de salons vocaux temporaires
# ==========================

import discord
from discord.ext import commands, tasks
import asyncio
import random
import datetime
import json
import os
from itertools import cycle

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents)
bot.remove_command("help")

# ---------------------------------------------------------------------------
# 🔧 ÉVÉNEMENT DE DÉMARRAGE
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")
    await bot.change_presence(activity=discord.Game("+help | connecté !"))

# ---------------------------------------------------------------------------
# 🔊 SYSTÈME VOCAL TEMPORAIRE
# ---------------------------------------------------------------------------

temporary_vcs = {}  # Dictionnaire pour suivre les salons temporaires

@bot.command(name="createvoc")
@commands.has_permissions(manage_channels=True)
async def create_voc_lobby(ctx):
    """Crée le salon 'Créer ton salon 🔊' dans la catégorie 'Vocaux Temporaires 🔊'"""
    guild = ctx.guild

    # Vérifie si la catégorie existe, sinon la crée
    category_name = "Vocaux Temporaires 🔊"
    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        category = await guild.create_category(category_name)
        await ctx.send(f"📁 Catégorie **{category_name}** créée automatiquement.")

    # Vérifie si le salon existe déjà
    existing = discord.utils.get(guild.voice_channels, name="Créer ton salon 🔊")
    if existing:
        await ctx.send("⚠️ Le salon vocal **Créer ton salon 🔊** existe déjà !")
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=True, speak=True)
    }

    lobby = await guild.create_voice_channel(
        "Créer ton salon 🔊",
        category=category,
        overwrites=overwrites
    )
    await ctx.send(f"✅ Salon vocal temporaire créé : {lobby.mention}")


@bot.event
async def on_voice_state_update(member, before, after):
    """Gère la création et la suppression automatique des salons vocaux temporaires"""
    guild = member.guild

    # Si un membre rejoint le salon "Créer ton salon 🔊"
    if after.channel and after.channel.name == "Créer ton salon 🔊":
        category = after.channel.category
        temp_vc = await guild.create_voice_channel(
            name=f"🔊 Salon de {member.display_name}",
            category=category
        )

        # Déplace le membre dedans
        await member.move_to(temp_vc)
        temporary_vcs[temp_vc.id] = member.id
        print(f"[TEMP VC] {member.display_name} → {temp_vc.name}")

    # Si un salon temporaire devient vide → suppression
    if before.channel and before.channel.id in temporary_vcs:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            del temporary_vcs[before.channel.id]
            print(f"[TEMP VC] Salon supprimé : {before.channel.name}")

# ---------------------------------------------------------------------------
# 🔚 Lancement du bot (Render utilise la variable d'environnement DISCORD_BOT_TOKEN)
# ---------------------------------------------------------------------------
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
