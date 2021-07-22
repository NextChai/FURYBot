from asyncio.tasks import Task
import logging

import discord
from discord.ext import commands, tasks


class Tasks(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.update_status.start()
        
    def cog_unload(self):
        self.update_status.cancel()

    @tasks.loop(minutes=30) 
    async def update_status(self) -> None:
        await self.bot.change_presence(activity=discord.Activity(type=self.bot.ACTIVITY_TYPE, name=self.bot.ACTIVITY_MESSAGE))
        
    @update_status.before_loop
    async def update_status_before_loop(self) -> None:
        logging.info("TASK WAIT: Waiting for task update_status inside of tasks.py")
        await self.bot.wait_until_ready()
        
def setup(bot):
    bot.add_cog(Tasks(bot))