import asyncio
import discord
import logging

from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate


logger = logging.getLogger('red.carlcog')


class MyCog(commands.Cog):
    """Carl's Carlcog Cog"""
    def __init__(self, bot):
        self.bot = bot

    async def initialize(self) -> None:
        logger.info('Initializing Carlcog Cog')

    @commands.command(name='roleaddmulti', aliases=['ram'])
    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def roleaddmulti(self, ctx, role: discord.Role, *, members: str):
        """Adds a `role` to multiple users, without sucking..."""
        members = members.split(' ')
        logger.debug(members)
        num_members = len(ctx.guild.members)
        message = await ctx.send(f'Will process **{num_members}** guild '
                                 f'members for role `@{role.name}` \n'
                                 f'Minimum ETA **{num_members//5}** sec. '
                                 f'Proceed?')

        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send('Request timed out. Aborting.', delete_after=60)
            await message.delete()
            return

        if not pred.result:
            await ctx.send('Aborting...', delete_after=5)
            await message.delete()
            return

        await ctx.send('Processing now. Please wait...')
        users = []
        for member in await AsyncIter(ctx.guild.members, delay=1, steps=5):
            for m in await AsyncIter(members):
                if (member.name and m.lower() == member.name.lower()) or \
                        (member.nick and m.lower() == member.nick.lower()):
                    if role not in member.roles:
                        await member.add_roles(role, reason=f'{ctx.author} roleaddmulti')
                        users.append(member.name)
                        await asyncio.sleep(3)
        await ctx.send(f'Done! Added `@{role.name}` to:\n{users}')
        await message.delete()
