import logging
import re

import discord
import better_profanity
from discord.ext import commands
import urlextract

BYPASS_FURY = 802948019376488511
VALID_GIF_CHANNELS = (
    757664675864248363,
    757665839263514705,
    807407126275686430,
    807404099095101491,
    807407050685677589,
    809527472609558548,
    807407098442416139
)


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.profanity = better_profanity.profanity

        with open(f"{self.bot.DEFAULT_BASE_PATH}/txt/profanity.txt", 'r') as f:
            extra_profanity = f.readlines()
            extra_profanity = list(dict.fromkeys(extra_profanity))  # clear up duplicates
            self.profanity.add_censor_words(extra_profanity)

        self.extractor = urlextract.URLExtract()
        self.extractor.update()

    @staticmethod
    def moderator_check(member):
        return True if BYPASS_FURY in [role.id for role in member.roles] else False

    @commands.Cog.listener("on_message")
    async def profanity_filter(self, message):
        member = message.author
        if not isinstance(member, discord.Member) \
                or member.bot \
                or self.moderator_check(member):
            return

        if self.moderator_check(member):  # member is a moderator
            return

        swears = self.profanity.contains_profanity(message.clean_content.lower())
        if not swears:  # the member said something fine
            return
        await message.delete()

        could_dm = True
        e = discord.Embed(color=discord.Color.red(),
                          title="Noo!",
                          description=f"You can't be using that language in this server! You need to remember that it is a school discord. Don't say anything here that you wouldn't say in front of your parents or teacher.")
        e.set_author(name=str(member), icon_url=member.avatar_url)
        e.add_field(name=f"Original message:", value=message.clean_content)
        e.add_field(name="Clean message:", value=self.profanity.censor(message.clean_content))

        try:
            await member.send(embed=e)
        except (discord.HTTPException, discord.Forbidden):
            e.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=e)
            could_dm = False

        embed = discord.Embed(color=discord.Color.red(),
                              description=f'{str(member)} ({member.mention}) has used terms that contained profanity.\n**Channel:** {message.channel.mention}\n**Member nick:** {member.nick}')
        embed.set_author(name=str(member), icon_url=member.avatar_url)
        embed.add_field(name=f"Original message:", value=message.clean_content)
        embed.add_field(name="Clean message:", value=self.profanity.censor(message.clean_content))
        embed.add_field(name="Could DM member:", value=str(could_dm))
        return await self.bot.send_to_log_channel(embed=embed)

    @commands.Cog.listener('on_message')
    async def link_checker(self, message):
        member = message.author
        if not isinstance(member, discord.Member):
            return
        if member.bot:
            return

        if self.moderator_check(member):  # member is a moderator
            return

        urls = list(self.extractor.gen_urls(message.clean_content))
        if not urls:  # no urls in message
            # we can run a second check LMAO
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                              message.clean_content.replace(" ", ''))
            if not urls:
                return

        is_fine = False
        could_dm = True

        if message.channel.id not in VALID_GIF_CHANNELS:  # the user isn't allowed to post links in not main chats
            print("Not valid channel.")
            await message.delete()
        else:
            check = [url for url in urls if re.findall('gifyourgame', url)]  # check for gif your game
            logging.info(f"Check for allowed urls: {check}")

            if not check:  # no gif your game messages
                await message.delete()
            else:  # all links are gif your game
                if message.channel.id not in VALID_GIF_CHANNELS:  # channel is not valid
                    await message.delete()
                else:
                    is_fine = True

        if is_fine:
            return

        embed = discord.Embed(color=discord.Color.red(),
                              title="Nooo!",
                              description=f"We don't use links in this server!")
        embed.add_field(name="When can I use links?",
                        value="You can use links when posting from [Gif Your Game](https://www.gifyourgame.com/) in any of the game specific general chats. All other links must stay disabled.")
        embed.add_field(name="Links sent:",
                        value=', '.join(urls))

        try:
            await member.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            embed.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=embed)
            could_dm = False

        embed = discord.Embed(color=discord.Color.red(), title=f'{str(member)} has sent messages that contain links.')
        embed.add_field(name=f"Original message:", value=message.clean_content)
        embed.add_field(name="Links sent:", value=', '.join([f'`{entry}`' for entry in urls]))
        embed.add_field(name="Could DM member:", value=str(could_dm))
        return await self.bot.send_to_log_channel(embed=embed)


def setup(bot):
    bot.add_cog(Events(bot))
