import discord
import logging
import random
import string
from typing import Optional

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.console')


class Console(commands.Cog):
    """Carl's Console Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.command(name='echo', aliases=['print', 'println'])
    async def echo_command(self, ctx: commands.Context, *, echo_string: str):
        await ctx.send(echo_string, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name='rand', aliases=['random'])
    async def rand_command(self, ctx: commands.Context, string_length: Optional[int] = 24,
                           number_of_strings: Optional[int] = 1):
        passwords = []
        for _ in range(number_of_strings):
            choices = (string.ascii_uppercase + string.ascii_lowercase + string.digits)
            for char in 'iIlLoO01':
                choices = choices.replace(char, '')
            passwords.append(''.join(random.choice(choices) for _ in range(string_length)))
        content = cf.box('\n'.join(passwords))
        await ctx.send(content, allowed_mentions=discord.AllowedMentions.none())

