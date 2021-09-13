import logging
from typing import Union

import discord
from discord.ext import commands

from cogs.events.base import BaseEvent, moderator_check, mention_staff

def setup(bot):
    bot.add_cog(ProfanityFilter(bot))

class ProfanityFilter(BaseEvent, command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        super().__init__(bot)
    
    @commands.Cog.listener("on_message")
    async def profanity_filter(
        self, 
        message: discord.Message
    ) -> Union[discord.Message, None]:
        """
        Catch for any profanity sent by users.
        """
        member = message.author
        if not isinstance(member, discord.Member) or member.bot or moderator_check(member):
            return 

        if not await self.contains_profanity(message.clean_content.lower()):  # the member said something fine
            return 
        
        logging.warning(f"PROFANITY FOUND: Profanity found from {str(message.author)}")
        
        await message.delete()

        e = self.bot.Embed(
            title="Noo!",
            description=f"You can't be using that language in this server! You need to remember " \
                "that it is a school discord. Don't say anything here that you wouldn't say in front of your parents or teacher."
        )
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
        e.add_field(name=f"Original message:", value=message.clean_content)
        e.add_field(name="Clean message:", value=await self.bot.profanity.censor(message.clean_content))

        try:
            await member.send(embed=e)
            could_dm = True
        except (discord.HTTPException, discord.Forbidden):
            e.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=e)
            could_dm = False

        log_embed = self.bot.Embed(
            description=f'**{str(member)}** ({member.mention}) has used terms that contained profanity.\n' \
                f'**Channel:** {message.channel.mention}\n**Member nick:** {member.nick}'
        )
        log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        log_embed.add_field(name=f"Original message:", value=message.clean_content)
        log_embed.add_field(name="Clean message:", value=await self.bot.profanity.censor(message.clean_content))
        log_embed.add_field(name="Could DM member:", value=str(could_dm))
        return await self.bot.send_to_log_channel(content=mention_staff(member.guild), embed=log_embed)