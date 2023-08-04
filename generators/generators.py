import discord
import httpx
import io
import logging
import random
from faker import Faker
from typing import Optional

from redbot.core import app_commands, commands, Config

log = logging.getLogger('red.generators')


class Generators(commands.Cog):
    """Carl's Generators Cog"""

    http_options = {'follow_redirects': True, 'timeout': 6}

    guild_default = {
        'enabled': False,
        'channels': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.fake = Faker()

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_command(name='orly', aliases=['oreilly'], description='ORLy Cover Generator')
    @app_commands.describe(title='Main Title', sub_title='Sub-Title', header='Top Text', author='Author',
                           color='Color Hex (or random)', animal='Animal Number (1-41 or random)')
    @commands.guild_only()
    async def _orly(self, ctx: commands.Context, title: str, sub_title: str, header: str,
                    author: Optional[str], color: Optional[str], animal: Optional[int]):
        """ORLy Cover Generator"""
        url = 'https://orly.nanmu.me/api/generate'
        params = {
            'title': title,
            'g_text': sub_title,
            'top_text': header,
            'author': author or self.fake.name(),
            'color': (color or self.fake.color()).lstrip('#'),
            'img_id': animal or random.randint(0, 41),
            'g_loc': 'US',
        }
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
        file = discord.File(io.BytesIO(r.content), filename=f'{title}-{sub_title}-{author}.png')
        await ctx.send(file=file)
