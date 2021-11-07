import discord
import logging
import json
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import box, humanize_list, pagify
from typing import cast

from .messages import Message

logger = logging.getLogger('red.mycog')


class MyCog(commands.Cog):
    """My custom cog"""
    def __init__(self, bot):
        self.bot = bot
        self.msg = Message
        # self.config = Config.get_conf(self, 1337, True)
        # self.config.register_guild(**DEFAULT_SETTINGS)

    async def initialize(self) -> None:
        logger.debug('WINNING - Initializing MyCog Cog')

    @staticmethod
    def from_hex_id(hex_id):
        return discord.Colour(int(hex_id.lstrip('#'), base=16))

    @commands.command(name='mycom', aliases=['m'])
    async def mycom(self, ctx):
        """This does stuff!"""
        # guild = self.bot.get_guild(ctx.guild.id)

        # logger.debug(dir(self))
        # logger.debug(dir(self.bot))
        # embed = discord.Embed()
        # embed.description = 'I can do stuff! yes'
        # embed.color = self.from_hex_id('#00ff00')
        # await ctx.send(embed=embed)

        # guild = self.bot.get_guild(188145201879973889)
        # await ctx.send('I can do stuff! yes')
        await ctx.send(embed=self.msg.ok('Winning'))
