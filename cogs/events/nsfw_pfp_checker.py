import logging
from typing import Optional

import discord
from discord.ext import commands

from cogs.utils.constants import NSFW_FILTER_CONSTANT
from cogs.events.base import BaseEvent, mention_staff
from cogs.utils.types import Reasons
from cogs.utils.constants import FURY_GUILD


def setup(bot):
    bot.add_cog(NsfwPfpChecker(bot))


class NsfwPfpChecker(BaseEvent, command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener('on_user_update')
    async def nsfw_pfp_checker(
            self,
            before: discord.User,
            user: discord.User
    ) -> Optional[discord.Message]:
        """
        Looks for Nudity and NSFW within a users' pfp. 
        If a NSFW pfp is detected they will be locked and moderators will be noticed.
        """
        if before.display_avatar == user.display_avatar:
            return

        params = {
            'url': str(user.display_avatar.url),
            'models': 'nudity,wad,offensive,text-content,gore',
            'api_user': '35525582',
            'api_secret': self.bot.nsfwAPI
        }

        async with self.bot.session.get('https://api.sightengine.com/1.0/check.json', params=params) as resp:
            if resp.status != 200:
                logging.warning("STATUS: Api request status not 200.")
                return
            data = await resp.json()

        def check(entry):
            return entry > NSFW_FILTER_CONSTANT
        if any((
                check(data['offensive']['prob']),
                check(data['nudity']['raw']),
                check(data['gore']['prob']),
                check(data['alcohol']),
                check(data['drugs']),
        )):  # Asset is BAD, handle it.
            if self.is_locked(user):  # Member is already locked, add this to the reason of locks.
                return self.increment_extra_if_necessary_for(user, Reasons.pfp)

            logging.warning(f"MEMBER NSFW: {str(user)} has a NSFW pfp, locking them out.")

            e = self.bot.Embed()
            e.title = 'NSFW Pfp Detected'
            e.description = "I've detected your new Pfp to be NSFW. Please change it to be unlocked from FLVS Fury."
            e.add_field(name='How to get it removed?', value='**Change your Pfp!**')
            e.add_field(name='Feel this is incorrect?', value='Contact Trevor F. to get it fixed.')
            try:
                await user.send(embed=e)
                could_dm = True
            except (discord.HTTPException, discord.Forbidden):
                could_dm = False

            # I do this here because I need it for the mention_staff func.
            # Otherwise, it would happen twice in the lockdown_if_necessary_for func.
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            user = guild.get_member(user.id) or (await guild.fetch_member(user.id))

            await self.lockdown_if_necessary_for(
                user,
                reason=Reasons.pfp,
                raw_reason='pfp'
            )

            modEmbed = self.bot.Embed(
                title='NSFW Pfp Detected',
                description=f"I've detected a NSFW pfp on {user.mention}"
            )
            modEmbed.add_field(name='Could DM?', value=could_dm)
            modEmbed.set_thumbnail(url=str(user.display_avatar))
            modEmbed.set_image(url=str(user.display_avatar))
            return await self.bot.send_to_log_channel(embed=modEmbed, content=mention_staff(guild))

        # If we reach here, the asset is fine.
        return await self.remove_lockdown_if_necessary_for(
            user,
            reason=Reasons.pfp,
            raw_reason='pfp'
        )
