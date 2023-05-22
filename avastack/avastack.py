import asyncio
import discord
import logging

from redbot.core import commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from .menus import MenuView

log = logging.getLogger('red.captcha')


class Avastack(commands.Cog):
    """Carl's Avastack Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.group(name='captcha', aliases=['cap'])
    @commands.guild_only()
    @commands.admin()
    async def avastack(self, ctx: commands.Context):
        """Avastack Commands."""

    @avastack.command(name='flight', aliases=['f'])
    async def avastack_flight(self, ctx: commands.Context):
        """Get Avastack Flight."""
        await ctx.send('WIP')
