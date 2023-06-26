import datetime
import discord
import httpx
import logging
from typing import Optional

from redbot.core import app_commands, commands, Config

log = logging.getLogger('red.ocrimage')


class Ocrimage(commands.Cog):
    """Carl's Ocrimage Cog"""

    ocr_url = 'https://api.flowery.pw/v1/ocr'
    http_options = {
        'follow_redirects': True,
        'timeout': 6,
    }

    guild_default = {
        'channels': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_command(name='ocr', aliases=['ocrimage'])
    @commands.guild_only()
    @commands.cooldown(3, 20, commands.BucketType.user)
    @commands.max_concurrency(1, commands.BucketType.user)
    @app_commands.describe(link='Optional: Link of Image to OCR')
    async def ocr_command(self, ctx: commands.Context, link: Optional[str]):
        async with ctx.typing():
            if not link and not ctx.message.attachments:
                return await ctx.send('⛔ Requires Image Link or Attachment.', delete_after=60)
            if not link:
                link = ctx.message.attachments[0].url
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=self.ocr_url, params={'url': link})
            if not r.is_success:
                return await ctx.send(f'⛔ OCR Request Failed: {r.status_code}', delete_after=60)
            embed = discord.Embed(
                title='OCR Results',
                url=link,
                description=r.json()['text'][:4000],
                color=discord.Color.dark_green(),
                timestamp=datetime.datetime.now(),
            )
            embed.set_author(
                name=f'@{ctx.author.display_name or ctx.author.name}'
            )
            await ctx.send(embed=embed)
