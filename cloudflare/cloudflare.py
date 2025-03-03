import asyncio
import discord
import httpx
import logging
import redis.asyncio as redis
from typing import Optional, Dict, Any

from redbot.core import commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.cloudflare')


class Cloudflare(commands.Cog):
    """Carl's Cloudflare Cog"""

    base_url = 'https://api.cloudflare.com/client/v4/{0}'
    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }
    user_default = {
        'token': None,
        'zones': [],
        'users': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        # self.config.register_global(**self.global_default)
        self.config.register_user(**self.user_default)
        self.loop: Optional[asyncio.Task] = None
        self.redis: Optional[redis.Redis] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        redis_data: dict = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=redis_data.get('host', 'redis'),
            port=int(redis_data.get('port', 6379)),
            db=int(redis_data.get('db', 0)),
            password=redis_data.get('pass', None),
        )
        await self.redis.ping()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    async def get_user_zones(self, user_id):
        all_users: Dict[str, Any] = await self.config.all_users()
        zones = []
        for _user_id, data in all_users.items():
            if user_id == _user_id:
                zones.append(data['zones'])
            if user_id == data['users']:
                zones.append(data['zones'])
        return zones

    @commands.group(name='cloudflare', aliases=['cf'])
    async def _cloudflare(self, ctx):
        """Manage Cloudflare Options"""

    @_cloudflare.command(name='update', aliases=['zones'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _cloudflare_update(self, ctx: commands.Context):
        """Update Cloudflare Zone Cache"""
        user_conf: Dict[str, Any] = await self.config.user(ctx.author).all()
        if not user_conf['token']:
            view = ModalView(self)
            return await view.send_message(ctx)

        url = self.base_url.format('zones')
        headers = {'Authorization': f"Bearer {user_conf['token']}"}
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, headers=headers, params={'per_page': 50})
        r.raise_for_status()
        result = r.json()['result']
        await self.config.user(ctx.author).zones.set(result)
        zones = []
        for zone in result:
            zones.append(zone['name'])
        return await ctx.send(f'Zones Updated:\n{cf.humanize_list(zones)}')

    @_cloudflare.command(name='purge', aliases=['flush'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _cloudflare_purge(self, ctx: commands.Context, zone: str):
        """Purge Cloudflare Cache for <zone>"""
        log.debug('zone: %s', zone)
        all_users: Dict[str, Any] = await self.config.all_users()
        log.debug(all_users)
        await ctx.send('WIP')
        # user_conf: Dict[str, Any] = await self.config.user(ctx.author).all()
        # if not user_conf['token']:
        #     view = ModalView(self)
        #     return await view.send_message(ctx)
        #
        # url = self.base_url.format('zones')
        # log.debug('url: %s', url)
        # headers = {'Authorization': f"Bearer {user_conf['token']}"}
        # log.debug('headers: %s', headers)
        # async with httpx.AsyncClient(**self.http_options) as client:
        #     r = await client.get(url, headers=headers, params={'per_page': 50})
        # log.debug('r.status_code: %s', r.status_code)
        # log.debug('r.content: %s', r.content)
        # r.raise_for_status()
        # # TODO: Cache Zones Here
        # result = r.json()['result']
        # for _zone in result:
        #     if _zone['name'] == zone:
        #         break
        # else:
        #     return await ctx.send(f'Zone Not Found: `{zone}`')
        # log.debug('_zone: %s', _zone)
        # url = self.base_url.format(f"zones/{_zone['id']}/purge_cache")
        # log.debug('url: %s', url)
        # async with httpx.AsyncClient(**self.http_options) as client:
        #     r = await client.post(url, headers=headers, json={'purge_everything': True})
        # log.debug('r.status_code: %s', r.status_code)
        # log.debug('r.content: %s', r.content)
        # r.raise_for_status()
        # log.debug('r.text: %s', r.text)
        # return await ctx.send(f'Cache Flush Response: *{r.status_code}*')

    @_cloudflare.command(name='token', aliases=['auth', 'access', 'authorization'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _cloudflare_token(self, ctx: commands.Context):
        """Set Cloudflare Access Token"""
        view = ModalView(self)
        content = 'Press the Button to set your Access Token.'
        return await ctx.send(content, view=view, ephemeral=True,
                              allowed_mentions=discord.AllowedMentions.none())


class ModalView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def send_message(self, ctx):
        msg = (f'⛔ No Cloudflare Access Token found for {ctx.author.mention}\n'
               f'Click the button to set Access Token.')
        return await ctx.send(msg, view=self, ephemeral=True,
                              allowed_mentions=discord.AllowedMentions.none())

    @discord.ui.button(label='Set Cloudflare Access Token', style=discord.ButtonStyle.blurple, emoji='🔐')
    async def set_cloudflare(self, interaction, button):
        log.debug(interaction)
        log.debug(button)
        modal = DataModal(view=self)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View):
        super().__init__(title='Set Cloudflare Access Token')
        self.view = view
        self.access_token = discord.ui.TextInput(
            label='Cloudflare Access Token',
            placeholder='ghp_xxx',
            style=discord.TextStyle.short,
            max_length=40,
            min_length=40,
        )
        self.add_item(self.access_token)

    async def on_submit(self, interaction: discord.Interaction):
        # discord.interactions.InteractionResponse
        log.debug('ReplyModal - on_submit')
        user: discord.Member = interaction.user
        log.debug('self.access_token.value: %s', self.access_token.value)
        await self.view.cog.config.user(user).token.set(self.access_token.value)
        msg = '✅ Cloudflare Access Token Updated Successfully...'
        await interaction.response.send_message(msg, ephemeral=True)
