import asyncio
import discord
import httpx
import logging
# import redis.asyncio as redis
from typing import Optional, Dict, Any

from redbot.core import commands, Config
# from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.jarvis')


class Jarvis(commands.Cog):
    """Carl's Jarvis Cog"""

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }
    user_default = {
        'token': None,
        'url': None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        # self.config.register_global(**self.global_default)
        self.config.register_user(**self.user_default)
        # self.loop: Optional[asyncio.Task] = None
        # self.redis: Optional[redis.Redis] = None

    async def cog_load(self):
        # log.info('%s: Cog Load Start', self.__cog_name__)
        # redis_data: dict = await self.bot.get_shared_api_tokens('redis')
        # self.redis = redis.Redis(
        #     host=redis_data.get('host', 'redis'),
        #     port=int(redis_data.get('port', 6379)),
        #     db=int(redis_data.get('db', 0)),
        #     password=redis_data.get('pass', None),
        # )
        # await self.redis.ping()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot or message.content.lower() == 'jarvis':
            return
        if message.content.lower().startswith('jarvis'):
            request = message.content.split(' ', 1)[1]
            await self.process_jarvis(message.author, message.channel, message, request)


    @commands.hybrid_command(name='jarvis', description='Chat with Jarvis')
    async def jarvis_chat(self, ctx: commands.Context, *, request: str):
        """Continue or Start ChatGPT Session with <question>"""
        log.debug('request: %s', request)
        await self.process_jarvis(ctx.author, ctx.channel, ctx.message, request)


    async def process_jarvis(self, user: discord.User, channel: discord.TextChannel, message: discord.Message,
                             request: str):
        """Continue or Start ChatGPT Session with <question>"""
        log.debug('process_jarvis: request: %s', request)
        user_conf: Dict[str, Any] = await self.config.user(user).all()
        log.debug('user_conf: %s', user_conf)

        if not user_conf['token'] or not user_conf['url']:
            log.debug('USER CONF MISSING TOKEN OR URL')
            view = ModalView(self)
            return await view.send_token_prompt(channel)

        if request.lower() in ['token', 'url', 'set', 'set url', 'set token', 'config', 'setup', 'settings']:
            log.debug('TOKEN/URL REQUEST!')
            view = ModalView(self)
            return await view.send_token_prompt(channel)
            # content = 'Press the Button to set your Access Token and URL.'
            # return await channel.send(content, view=view, allowed_mentions=discord.AllowedMentions.none())

        r = await self.post_jarvis(user_conf, request)
        if not r.is_success:
            # msg = f'⛔ API Error {r.status_code}: {r.text}'
            # return await channel.send(msg, delete_after=30)
            view = ModalView(self)
            # return await view.send_token_prompt(channel)
            content = f'⛔ API Error: {r.status_code}. Verify your URL and Token.'
            return await channel.send(content, view=view, allowed_mentions=discord.AllowedMentions.none(),
                                      delete_after=300)

        data = r.json()
        log.debug('data: %s', data)
        log.debug('response_type: %s', data['response']['response_type']) # action_done, query_answer, error
        response = data['response']['speech']['plain']['speech']
        log.debug('response: %s', response)
        if response:
            await channel.send(f"{data['response']['speech']['plain']['speech']}")
        else:
            log.debug('No response, what to do, what to do...')
            await self.temporary_react(message,'\U00002705')


    async def post_jarvis(self, user_data: dict, text: str) -> httpx.Response:
        url = user_data['url'] + '/api/conversation/process'
        log.debug('url: %s', url)
        headers = {'Authorization': f"Bearer {user_data['token']}"}
        log.debug('headers: %s', headers)
        body = {
            'text': text,
            'language': 'en',
        }
        log.debug('body: %s', body)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url, json=body, headers=headers)
        return r

    async def temporary_react(self, message: discord.Message, emoji: str, delay: float = 5.0) -> None:
        await message.add_reaction(emoji)
        await asyncio.sleep(delay)
        await message.remove_reaction(emoji, self.bot.user)

class ModalView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def send_token_prompt(self, channel: discord.TextChannel):
        msg = '⛔ Missing Jarvis Token or URL...'
        return await channel.send(msg, view=self, allowed_mentions=discord.AllowedMentions.none(), delete_after=300)

    @discord.ui.button(label='Set Jarvis Token/URL', style=discord.ButtonStyle.blurple, emoji='🐦')
    async def set_jarvis(self, interaction, button):
        log.debug(interaction)
        log.debug(button)
        log.debug('interaction.user: %s', interaction.user)
        user_conf: Dict[str, Any] = await self.cog.config.user(interaction.user).all()
        log.debug('user_conf: %s', user_conf)
        modal = DataModal(view=self, user_conf=user_conf)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View, user_conf: dict):
        super().__init__(title='Set Jarvis Access Data')
        self.view = view
        self.user_conf = user_conf
        log.debug('user_conf: %s', user_conf)
        self.access_url = discord.ui.TextInput(
            label='Jarvis URL',
            default=user_conf['url'] if user_conf['url'] else '',
            placeholder='Home Assistant URL',
            style=discord.TextStyle.short,
            max_length=255,
            #min_length=12,
            required=not bool(user_conf['url']),
        )
        self.add_item(self.access_url)
        self.access_token = discord.ui.TextInput(
            label='Jarvis Token',
            placeholder='**********' if user_conf['token'] else 'Home Assistant API Token',
            style=discord.TextStyle.short,
            max_length=255,
            #min_length=160,
            required=not bool(user_conf['token']),
        )
        self.add_item(self.access_token)

    async def on_submit(self, interaction: discord.Interaction):
        # discord.interactions.InteractionResponse
        log.debug('ReplyModal - on_submit')
        log.debug('self.user_conf: %s', self.user_conf)

        if not self.access_token.value and not self.access_url.value:
            #msg = '⛔ Nothing Data Provided!'
            #return await interaction.response.send_message(msg, ephemeral=True)
            return

        user: discord.Member = interaction.user
        updated = []

        log.debug('self.access_token.value: %s', self.access_token.value)
        if self.access_token.value:
            log.debug('ACCESS TOKEN PROVIDED!')
            updated.append('Token')
            await self.view.cog.config.user(user).token.set(self.access_token.value)

        log.debug('self.access_url.value: %s', self.access_url.value)
        if self.access_url.value and self.access_url.value != self.user_conf['url']:
            log.debug('ACCESS URL PROVIDED OR CHANGED!')
            updated.append('URL')
            _t = self.access_url.value.rstrip('/').rstrip('/api')
            await self.view.cog.config.user(user).url.set(_t)

        if not updated:
            log.debug('NO DATA PROVIDED AND URL NOT CHANGED!')
            return await interaction.response.defer()
        msg = f'✅ Successfully Updated: {",".join(updated)}'
        await interaction.response.send_message(msg, ephemeral=True, delete_after=15)
