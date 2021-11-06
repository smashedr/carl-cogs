import discord
import logging
import json
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import box, humanize_list, pagify
from typing import cast

logger = logging.getLogger('red.mycog')

DEFAULT_WELCOME = "Welcome {user.name} to {guild.name}!"


class MyCog(commands.Cog):
    """My custom cog"""

    def __init__(self, bot):
        self.bot = bot
        # self.config = Config.get_conf(
        #     self, identifier=1337, force_registration=True
        # )
        # self.config.register_guild(
        #     message=DEFAULT_WELCOME,
        #     enabled=False,
        #     channel=None,
        # )

    async def initialize(self) -> None:
        logger.debug('WINNING - Initializing MyCog Cog')

    @commands.command(name='mycom', aliases=['m'])
    async def mycom(self, ctx):
        """This does stuff!"""
        # logger.debug(dir(ctx))
        # logger.debug('ctx: %s', ctx)
        # logger.debug('ctx.author: %s', ctx.author)
        # logger.debug('ctx.guild: %s', ctx.guild)

        guild = self.bot.get_guild(ctx.guild.id)
        logger.debug(guild.members)
        m = guild.members[0]
        l = m.avatar_url
        logger.debug(type(l))
        logger.debug(l)
        logger.debug(dir(l))

        # members = self.process_members(guild.members)
        # # logger.info(members)
        # j = json.dumps(members, default=str)
        # logger.info(j)

        # print(self.bot.guilds)
        # print(self.bot.guilds[0])
        # print(dir(self.bot.guilds[0]))
        # print(self.bot.guilds[0].roles)
        # guild = self.bot.get_guild(188145201879973889)
        # print(dir(guild.channels[0]))
        # print(guild.channels[0])
        await ctx.send('I can do stuff! yes')
