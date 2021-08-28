import discord

from cogs.utils.constants import (
    ROCKETLEAGUE,
    LEAGUEOFLEGENDS,
    SUPERSMASH,
    FORTNITE,
    OVERWATCH,
    RL_ROLE,
    LOL_ROLE,
    SMASH_ROLE,
    FORTNITE_ROLE,
    OVERWATCH_ROLE
)

async def _handle_role(interaction: discord.Interaction, id: int):
    guild = interaction.guild
    
    role = discord.utils.get(guild.roles, id=id)
    if not role:
        roles = await guild.fetch_roles()
        role = discord.utils.get(roles, id=id)
    
    if not isinstance(interaction.user, discord.Member):
        member = guild.get_member(interaction.user.id) or (await guild.fetch_member(interaction.user.id))
    else:
        member = interaction.user
    
    await member.add_roles(*[role], reason='Reaction Roles')
    return await interaction.response.send_message(f'Added the {role.mention} role to you :)', ephemeral=True)


class ReactionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(emoji=ROCKETLEAGUE, custom_id='reactionroles:rocketleague')
    async def rocketleague(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await _handle_role(interaction, RL_ROLE)
    
    @discord.ui.button(emoji=LEAGUEOFLEGENDS, custom_id='reactionroles:leagueoflegends')
    async def lol(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await _handle_role(interaction, LOL_ROLE)
    
    @discord.ui.button(emoji=SUPERSMASH, custom_id='reactionroles:supersmash')
    async def supersmash(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await _handle_role(interaction, SMASH_ROLE)
    
    @discord.ui.button(emoji=FORTNITE, custom_id='reactionroles:fortnite')
    async def fortnite(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await _handle_role(interaction, FORTNITE_ROLE)
    
    @discord.ui.button(emoji=OVERWATCH, custom_id='reactionroles:overwatch')
    async def overwatch(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await _handle_role(interaction, OVERWATCH_ROLE)
    
    
        