import re
from typing import Union

import discord
from discord.ext import commands

from cogs.events.base import BaseEvent, moderator_check
from cogs.utils.constants import VALID_GIF_CHANNELS


def setup(bot):
    bot.add_cog(LinkChecker(bot))

class LinkChecker(BaseEvent, command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        super().__init__(bot)
        
    @commands.Cog.listener('on_message')
    async def link_checker(
        self, 
        message: discord.Message
    ) -> Union[discord.Message, None]:
        """
        Catch links sent by users. If a link is detected it will be deleted automatically.
        """
        member = message.author
        if not isinstance(member, discord.Member) or member.bot or moderator_check(member):
            return

        urls = await self.get_links(message.clean_content) or re.findall(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            message.clean_content.replace(" ", '')
        )
        if not urls: # No urls within the user's message, do nothing.
            return

        if message.channel.id not in VALID_GIF_CHANNELS:  # The user posted a link in a non-valid channel
            await message.delete()
        else:
            # The user posted a link, but we need to check if it's in a valid channel, and
            # if the link is a valid link.
            
            check = [url for url in urls if re.findall(r'gifyourgame|streamable|lowkey.gg', url)]  # check for gif your game links
            if not check:  # no gif your game links were sent
                await message.delete()
            elif len(check) != len(urls):  # The user sent a non-valid link alongside a gif your game link, delete it.
                await message.delete()
            else:  
                # We can confirm that all links sent in the users message has gifyourgame in it. 
                # Now we'll check if the channel is valid.
                if message.channel.id not in VALID_GIF_CHANNELS: # The channel is valid, delete message.
                    await message.delete()
                else: 
                    # Everything is ok, do nothing.
                    return

        embed = self.bot.Embed(
            title="Nooo!",
            description=f"We don't use links in this server!"
        )
        embed.add_field(
            name="When can I use links?", 
            value="You can use links when posting from [Gif Your Game](https://www.gifyourgame.com/) in " \
            "any of the game specific general chats. All other links must stay disabled.")
        embed.add_field(name="Links sent:", value=', '.join(urls))

        try:
            await member.send(embed=embed)
            could_dm = True
        except (discord.HTTPException, discord.Forbidden):
            embed.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=embed)
            could_dm = False

        embed = self.bot.Embed(
            color=discord.Color.red(), 
            description=f'**{str(member)} ({member.mention})** has sent messages that contain links.',
            title='Links detected')
        embed.add_field(name=f"Original message:", value=message.clean_content)
        embed.add_field(name="Links sent:", value=', '.join([f'`{entry}`' for entry in urls]))
        embed.add_field(name="Could DM member:", value=str(could_dm))
        return await self.bot.send_to_log_channel(embed=embed)