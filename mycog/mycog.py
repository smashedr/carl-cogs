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

    @staticmethod
    def hex_to_dis(hex_id):
        return discord.Colour(int(hex_id.lstrip('#'), base=16))

    @commands.command(name='mycom', aliases=['m'])
    @commands.is_owner()
    async def mycom(self, ctx):
        """I am MyCom!"""
        # guild = self.bot.get_guild(ctx.guild.id)
        # log = ctx
        # logger.debug(dir(log))
        # logger.debug(type(log))
        # logger.debug(log)
        # embed = discord.Embed()
        # embed.description = 'I can do stuff! yes'
        # embed.color = self.from_hex_id('#00ff00')
        # await ctx.send(embed=embed)
        # guild = self.bot.get_guild(188145201879973889)
        # dm_channel = await ctx.author.create_dm()
        # message = await dm_channel.send('PASSWORD!')
        # pred = MessagePredicate.same_context(channel=dm_channel, user=ctx.author)
        # try:
        #     response = await self.bot.wait_for("message", check=pred, timeout=30)
        # except asyncio.TimeoutError:
        #     await dm_channel.send(f'Request timed out. You need to start over.')
        #     return
        # logger.debug(response.content)
        logger.debug(ctx.guild.bitrate_limit)
        await ctx.send("I hack you now...")
