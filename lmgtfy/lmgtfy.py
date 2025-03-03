import discord
import logging
import urllib.parse

from redbot.core import commands

log = logging.getLogger('red.lmgtfy')


class Lmgtfy(commands.Cog):
    """Carl's LMGTFY Cog"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        """Listens for lmgtfy."""
        channel: discord.TextChannel = message.channel

        trigger = 'lmgtfy'
        if message.author.bot or message.content.lower() != trigger:
            return

        await message.delete()
        msg = None
        async for m in message.channel.history(limit=5):
            if m.author.bot:
                continue
            if m.id == message.id:
                continue
            if m.author.id == message.author.id:
                continue
            msg = m
            break

        if not msg:
            return await channel.send('No recent queries found...', delete_after=5)

        safe_string = urllib.parse.quote_plus(msg.content)
        # response = f'https://lmgtfy.app/?q={safe_string}'
        response = f'<https://www.google.com/search?q={safe_string}>'
        await msg.reply(response)
