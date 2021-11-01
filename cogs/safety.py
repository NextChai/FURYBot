"""
The MIT License (MIT)

Copyright (c) 2020-present NextChai

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import discord
from discord.ext import commands, tasks


import aiohttp
import logging
from typing import TYPE_CHECKING

from cogs.utils.checks import should_ignore
from cogs.utils import constants
from cogs.utils.enums import Reasons

if TYPE_CHECKING:
    from bot import FuryBot
    
__all__ = (
    'Safety',
)
    
log = logging.getLogger(__name__)


class Safety(commands.Cog):
    """Used to keep the server "safe". 
    
    Determines if:
    
        - A message has links
        - A message has profanity
        - A member has a bad display name
        - A member has updated their display name to an inappropriate one.
        
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot that owns this cog.
    """
    def __init__(self, bot):
        self.bot: FuryBot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession(loop=self.bot.loop)
        
        self.name_checker.start()
        self.load_profanity.start()
        
    @commands.Cog.listener('on_message')
    async def file_checker(self, message: discord.Message):
        """Used to check for message attachments. Any message that has them is deleted without correct perms."""
        if should_ignore(message.author):
            return
        
        if message.attachments:
            files = [att.to_file() for att in message.attachments]
            
            await message.delete()
            
            embed = self.bot.Embed(
                title='Message attachments found',
                description='Please do not post files!'
            )
            await message.channel.send(embed=embed)
            
            embed.description = f'{message.author.mention} has posted an attachment in {message.channel.mention}\n\nI have attached the files for you to view.'
            await self.bot.send_to_logging_channel(embed=embed, files=files)
        
    @commands.Cog.listener('on_message')
    async def message_content_check(self, message: discord.Message):
        """Used to determine if a message's content legnth is too high.
        
        Anything 700 or over will automatically be deleted."""
        if should_ignore(message.author):
            return
        if len(message.clean_content) >= 700:
            await message.delete()
        
            embed = self.bot.Embed(
                title='Message content legnth',
                description='Please do not post messages that long!'
            )
            return await message.channel.send(embed=embed)
        
    @commands.Cog.listener('on_message_edit')
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Used to check if a member edited a message that now contains links / profanity.
        
        Parameters
        ---------
        before: :class:`Message`
            The message before its edit.
        after: :class:`discord.Message`
            The message after its edit.
        
        Returns
        -------
        None
        """
        if before.clean_content == after.clean_content:
            return
        
        self.bot.loop.create_task(self.profanity_checker(after))
        self.bot.loop.create_task(self.link_checker(after))
        
    #@commands.Cog.listener('on_message')
    async def nsfw_image_checker(self, message: discord.Message) -> None:
        """Used to determine if an image a user uploaded is nsfw.
        
        .. NOTE:: NOT IN USE RIGHT NOW!
        
        Parameters
        ----------
        message: :class:`discord.Message`
            The message to check.
        
        Returns
        -------
        None
        """
        if not message.attachments or should_ignore(message.author):
            return
        
        for attachment in message.attachments:
            if (await self.bot.is_nsfw(attachment.url)):
                await message.delete()
                
                e = self.bot.Embed(
                    title='Oh no!',
                    description='You can not upload an image that contains profanity!'
                )
                e.set_image(url=attachment.url)
                e.set_thumbnail(url=attachment.url)
                e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                await self.bot.send_to(message.author, embed=e)
                
                e.title = 'Profane Image detected!'
                e.description = f'{message.author.mention} has uploaded an image that is profane in {message.channel.mention}.'
                await self.bot.send_to_logging_channel(embed=e)
                    
    @commands.Cog.listener('on_message')
    async def profanity_checker(self, message: discord.Message) -> None:
        """Used to check if a message contains profanity.
        
        Parameters
        ----------
        message: :class:`discord.Message`
            The message to check.
        
        Returns
        -------
        None
        """
        if not message.guild or should_ignore(message.author):
            return
        
        if (await self.bot.contains_profanity(message.clean_content)):
            await message.delete()
            
            self.bot.loop.create_task(self.bot.lockdown_for(5*60, member=message.author, reason=Reasons.profanity))
            censored = await self.bot.censor_message(message.clean_content)
            
            e = self.bot.Embed(
                title='Oh no!',
                description='You can not use a message that contains profanity!\n\nI have locked you out of the server for 5 minutes. ' \
                    'You will automatically be unlocked once that time is up.'
            )
            e.add_field(name='Message:', value=message.clean_content)
            e.add_field(name='Censored:', value=censored)
            await self.bot.send_to(message.author, embed=e)
            
            e.title = 'Profanity Found'
            e.description = f'{message.author.mention} has said a word that contains profanity in {message.channel.mention}.'
            e.add_field(name='Action Taken', value='I have locked them out of the server for 5 minutes.')
            await self.bot.send_to_logging_channel(embed=e, ping_staff=False)
        
    @commands.Cog.listener('on_message')
    async def link_checker(self, message: discord.Message) -> None:
        """Used to check if a message contains links in non-valid gif channels.
        
        Parameters
        ----------
        message: :class:`discord.Message`
            The message to check.
        
        Returns
        -------
        None
        """
        if not message.guild or should_ignore(message.author):
            return
        
        if (await self.bot.contains_links(message.clean_content)):
            links = await self.bot.get_links(message.clean_content)
            valid = True
            
            for link in links:
                if not await self.bot.is_valid_link(link):
                    valid = False
                    await message.delete()
                    break
            
            if valid is True:
                return
            
            e = self.bot.Embed(
                title='Oh no!',
                description="Links are not enabled in this server!"
            )
            e.add_field(name="Why aren't links enabled?", value='Due to FLVS Fury being a School Discord, we limit links to keep the server as PG as possible!')
            e.add_field(name='Invalid Links', value=', '.join(links))
            await self.bot.send_to(message.author, embed=e)
            
            # I'm creating a new embed here because I wont want to handle removing fields 
            # from the previous embed.
            e = self.bot.Embed(
                title='Link detected',
                description=f'{message.author.mention} has posted a link in {message.channel.mention}!'
            )
            e.add_field(name='Invalid Links', value=', '.join(links))
            await self.bot.send_to_logging_channel(embed=e)
            
    @commands.Cog.listener('on_user_update')
    async def user_username_update(self, before: discord.User, after: discord.User) -> None:
        """Checks when users update their usernames for profanity.
        
        Parameters
        ----------
        before: :class:`discord.User`
            The user before the update.
        after: :class:`discord.User`
            The user after the update.
            
        Returns
        -------
        None
        """
        if before.name == after.name:
            return
        
        if (await self.bot.contains_profanity(after.name)):
            guild = self.bot.get_guild(constants.FURY_GUILD)
            member = guild.get_member(after.id) or (await guild.fetch_member(after.id))
            await self.bot.lockdown(member, reason=Reasons.displayname)
        else:
            if self.bot.is_locked(after):
                guild = self.bot.get_guild(constants.FURY_GUILD)
                member = guild.get_member(after.id) or (await guild.fetch_member(after.id))
                await self.bot.freedom(member, reason=Reasons.displayname)
                
    @commands.Cog.listener('on_user_update')
    async def user_avatar_update(self, before: discord.User, after: discord.User) -> None:
        """Checks when users update their avatar.
        
        Parameters
        ----------
        before: :class:`discord.User`
            The user before the update.
        after: :class:`discord.User`
            The user after the update.
            
        Returns
        -------
        None
        """
        if before.display_avatar == after.display_avatar:
            return 
        
        if (await self.bot.is_nsfw(after.display_avatar.url)):
            guild = self.bot.get_guild(constants.FURY_GUILD)
            member = guild.get_member(after.id) or (await guild.fetch_member(after.id))
            await self.bot.lockdown(member, reason=Reasons.avatar)
        else:
            if self.bot.is_locked(after):
                guild = self.bot.get_guild(constants.FURY_GUILD)
                member = guild.get_member(after.id) or (await guild.fetch_member(after.id))
                await self.bot.freedom(member, reason=Reasons.avatar)

    @tasks.loop(count=1)
    async def name_checker(self) -> None:
        """Used to pool members and check for bad names and activities.
        
        .. note::
        
            This only gets called once, when the bot comes online.
        
        Returns
        -------
        None
        """
        guild = self.bot.get_guild(constants.FURY_GUILD)
        members = await guild.fetch_members(limit=None).flatten()
        
        for member in members:
            if (await self.bot.contains_profanity(member.display_name)):
                await self.bot.lockdown(member, reason=Reasons.displayname)
                
                censored = await self.bot.censor_message(member.display_name)
                e = self.bot.Embed(
                    title='Lockdown Incoming!',
                    description=f'Member {member.mention} has been locked down for {Reasons.type_to_string(Reasons.displayname)}'
                )
                e.add_field(name='Name:', value=member.display_name)
                e.add_field(name='Censored:', value=censored)
                await self.bot.send_to_logging_channel(embed=e)
                
            if member.activities:
                activity = discord.utils.find(lambda activity: isinstance(activity, discord.CustomActivity), member.activities)
                if activity and activity.name:
                    if (await self.bot.contains_profanity(activity.name)):
                        await self.bot.lockdown(member, reason=Reasons.activity)
                        
                        censored = await self.bot.censor_message(activity.name)
                        e = self.bot.Embed(
                            title='We got a live one!',
                            description=f'{member.mention} has been locked down for a bad status.'
                        )
                        e.add_field(name='Status', value=activity.name)
                        e.add_field(name='Censored', value=censored)
                        await self.bot.send_to_logging_channel(embed=e)
        
        log.info('Name Checker Finished.')
                
                
    @name_checker.before_loop
    async def name_checker_before_loop(self) -> None:
        log.info('Waiting for name checker...')
        await self.bot.wait_until_ready()
        log.info('Name checker started.')
        
    @tasks.loop(count=1)
    async def load_profanity(self) -> None:
        log.info("Loading profanity wordset now.")
        await self.bot.load_clean_words()
        await self.bot.load_dirty_words()
        log.info("Finished loading profanity wordset.")
        
def setup(bot):
    return bot.add_cog(Safety(bot))