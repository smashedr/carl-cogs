import discord
import logging
import pathlib
import re
from typing import Dict, List

from redbot.core import commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.miscog')


class Miscog(commands.Cog):
    """Carl's Miscog"""

    global_default = {
        'recent': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.cog_dir = pathlib.Path(__file__).parent.resolve()

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        """Listens for Messages"""
        if message.author.bot or not message.content or not message.guild:
            return
        await self.process_basic_auth_message(message)

    @commands.Cog.listener(name='on_message_delete')
    async def on_message_delete(self, message: discord.Message):
        """Listens for Message Deletions"""
        if message.author.bot or not message.content or not message.guild:
            return
        await self.process_basic_auth_delete(message)

    async def process_basic_auth_message(self, message: discord.Message):
        """Basic Auth ON MESSAGE"""
        match = re.search(r'(https?://\S+:\S+@\S+)', message.content)
        if not match:
            return
        reply = await message.reply(cf.box(match.group(1)))
        recent: List[Dict[str, int]] = await self.config.recent()
        recent.insert(0, {str(message.id): reply.id})
        await self.config.recent.set(recent[:50])

    async def process_basic_auth_delete(self, message: discord.Message):
        """Basic Auth ON DELETE"""
        recent: List[Dict[str, int]] = await self.config.recent()
        keys = [list(x.keys())[0] for x in recent]
        if str(message.id) not in keys:
            return
        reply_id: int = [x[str(message.id)] for x in recent if str(message.id) in x][0]
        message: discord.Message = await message.channel.fetch_message(reply_id)
        await message.delete()

