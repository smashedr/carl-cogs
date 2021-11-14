import asyncio
import discord
import logging
import json

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate

from .messages import Message

logger = logging.getLogger('red.mycog')


class MyCog(commands.Cog):
    """My custom cog"""
    def __init__(self, bot):
        self.bot = bot
        # self.config = Config.get_conf(self, 1337, True)
        # self.config.register_guild(**DEFAULT_SETTINGS)

    async def initialize(self) -> None:
        logger.info('Initializing MyCog Cog')

    @commands.command(name='mycom', aliases=['m'])
    @commands.is_owner()
    async def mycom(self, ctx):
        """I am MyCom!"""
        # guild = self.bot.get_guild(ctx.guild.id)

        # log = ctx
        # logger.debug(dir(log))
        # logger.debug(type(log))
        # logger.debug(log)

        await ctx.send('I hack you now...')
