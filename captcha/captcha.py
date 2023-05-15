import asyncio
import discord
import logging

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter

log = logging.getLogger('red.captcha')

GUILD_SETTINGS = {
    'enabled': False,
    'role': None,
    'bots': True,
}


class Captcha(commands.Cog):
    """Carl's Server CAPTCHA Cog."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**GUILD_SETTINGS)

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load Start')
        log.info(f'{self.__cog_name__}: Cog Load Finish')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message) -> None:
        """Listens for messages."""

        # log.debug('-'*40)
        # tolog = message.type
        # log.debug(dir(tolog))
        # log.debug(type(tolog))
        # log.debug(tolog)
        #
        # log.debug('-'*40)
        # tolog = message.id
        # log.debug(dir(tolog))
        # log.debug(type(tolog))
        # log.debug(tolog)
        #
        # log.debug('-'*40)
        # tolog = message.author
        # log.debug(dir(tolog))
        # log.debug(type(tolog))
        # log.debug(tolog)

        conf = await self.config.guild(message.guild).all()
        if not conf['enabled']:
            return

        if message.author.bot:
            if not conf['bots']:
                return

        if conf['role'] in message.author.roles:
            return

        # User needs CAPTCHA verification - Need Web API
        channel = await message.author.create_dm()
        await channel.send('CAPTCHA Verification Required.')


    @commands.command(name='cc', aliases=['ccc'])
    @commands.is_owner()
    async def captcha_command(self, ctx: commands.Context):
        """I am MyComM 2m!"""

        # tolog = ctx
        # log.debug(dir(tolog))
        # log.debug(type(tolog))
        # log.debug(tolog)

        await ctx.send('thefuck')
