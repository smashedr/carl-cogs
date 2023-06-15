import datetime
import discord
import httpx
import logging
from bs4 import BeautifulSoup
from faker import Faker
from typing import Optional, Union, Dict, List, Any, Tuple

from redbot.core import commands

log = logging.getLogger('red.coolbirbs')


class Coolbirbs(commands.Cog):
    """Carl's Coolbirbs Cog"""

    base_url = 'https://coolbirbs.com'
    static_url = 'https://static.coolbirbs.com'

    def __init__(self, bot):
        self.bot = bot
        self.fake = Faker()

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_command(name='coolbirbs',
                             aliases=['coolbirb', 'birb', 'birbs'],
                             description='Get a Random Cool Birb')
    async def coolbirbs_command(self, ctx: commands.Context):
        """Get a Random Cool Birb"""
        await ctx.typing()
        username: str = ctx.author.display_name or ctx.author.name
        number, name = await self.get_birb()
        static_url = f'{self.static_url}/birds/{number}.png'
        embed = discord.Embed(
            title=name,
            url=f'{self.base_url}/bird/{number}',
            timestamp=datetime.datetime.now(),
            description=self.fake.text(),
        )
        embed.set_author(name=self.base_url.split('/')[2], url=self.base_url)
        embed.set_image(url=static_url)
        embed.set_footer(text=f'@{username} /coolbirbs')
        await ctx.send(embed=embed)

    async def get_birb(self) -> Tuple[str, str]:
        async with httpx.AsyncClient() as client:
            r = await client.get(self.base_url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        number: str = soup.find('a')['href'].split('/')[2]
        bird_name: str = soup.find('b').text
        return number, bird_name
