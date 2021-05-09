import discord
from discord.ext import commands

import re, datetime

from better_profanity import profanity
from urlextract import URLExtract

BYPASS_FURY = 802948019376488511
VALID_GIF_CHANNELS = ( 
    757664675864248363,
    757665839263514705,
    807407126275686430,
    807404099095101491,
    807407050685677589,
    809527472609558548,
)


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.extractor = URLExtract()
        self.extractor.update()
        
    def moderator_check(self, author):
        author_roles = [role.id for role in author.roles]
        if BYPASS_FURY in author_roles:
            return True
        return False

    @commands.Cog.listener("on_message")
    async def profanity_filter(self, message):
        member = message.author
        could_dm = True
    
        if self.moderator_check(member): # member is a moderator
            return
        if not profanity.contains_profanity(message.clean_content):  # the member said something fine
            return
        
        await message.delete()
        
        e = discord.Embed(color=discord.Color.red(),
                            title="Noo!",
                            description=f"You can't be using that language in this server! You need to remember that it is a school discord. Don't say anything here that you wouldn't say in front of your parents or teacher.")
        try:
            await member.send(embed=e)
        except:
            e.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=e)
            could_dm = False
        
        embed = discord.Embed(color=discord.Color.red(), title=f'{str(member)} has used terms that contained profanity.')
        embed.add_field(name=f"Original message:", value=message.clean_content)
        embed.add_field(name="Clean message:", value=profanity.censor(message.clean_content))
        embed.add_field(name="Could DM member:", value=could_dm)
        return await self.bot.send_to_log_channel(embed=embed)
    
    @commands.Cog.listener('on_message')
    async def link_checker(self, message):
        member = message.author
        if self.moderator_check(member): # member is a moderator
            return
        
        urls = self.extractor.gen_urls(message.clean_content)
        if not urls: # no urls in message
            return
        
        is_fine = True
        could_dm = True
        
        if message.channel.id not in VALID_GIF_CHANNELS: # the user isn't allowed to post links in not main general chats
            await message.delete()
            is_fine = False   
        else: 
            for url in urls:
                if not url.startswith("https://www.gifyourgame.com/"):  # delete the message, it isnt supported
                    is_fine = False
                    await message.delete()
                    break
        
        if is_fine:
            return
        
        embed = discord.Embed(color=discord.Color.red(), 
                              title="Nooo!",
                              description=f"We don't use links in this server!")
        embed.add_field(name="When can I use links?",
                        value="You can use links when posting from [Gif Your Game](https://www.gifyourgame.com/) in any of the game specific general chats. All other links must stay disabled.")
        try:
            await member.send(embed=embed)
        except:
            embed.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=embed)
            could_dm = False
        
        embed = discord.Embed(color=discord.Color.red(), title=f'{str(member)} has sent messages that contain links.')
        embed.add_field(name=f"Original message:", value=message.clean_content)
        embed.add_field(name="Links sent:", value=', '.join([f'`{entry}`'for entry in urls]))
        embed.add_field(name="Could DM member:", value=could_dm)
        return await self.bot.send_to_log_channel(embed=embed)
        
        
        
        
        
            

def setup(bot):
    bot.add_cog(Events(bot))