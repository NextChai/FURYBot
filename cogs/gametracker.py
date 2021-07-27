import discord
from discord.ext import commands

class PracTrack(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot