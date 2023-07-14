import datetime
import discord
import httpx
import io
import logging
import os
import xml.etree.ElementTree as ElementTree
from typing import Any, Dict, List, Optional, Union

from redbot.core import Config, commands, checks
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils import menus

log = logging.getLogger('red.wolfram')


class Wolfram(commands.Cog):
    """Carl's Wolfram Cog"""

    app_msg = ('⛔ No App ID set. Set it with the `wolfram set` command.\n'
               'Create one at: <http://products.wolframalpha.com/api/>')

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    global_default = {
        'app_id': None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337)
        self.config.register_global(**self.global_default)
        self.app_id: Optional[str] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.app_id: str = await self.config.app_id()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_group(name='wolfram', aliases=['wolf'])
    async def _wolf(self, ctx):
        """Wolfram Alpha Command."""

    @_wolf.command(name='ask', aliases=['query'])
    async def _wolf_ask(self, ctx, *, query: str):
        """Query Wolfram Alpha."""
        if not self.app_id:
            return await ctx.send(self.app_msg, ephemeral=True, delete_after=30)

        await ctx.typing()
        url = 'http://api.wolframalpha.com/v2/query'
        params = {
            'appid': self.app_id,
            'input': query,
        }
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()

        log.debug('r.text: %s', r.text)
        root = ElementTree.fromstring(r.text)
        lines = []
        for pt in root.findall('.//plaintext'):
            if pt.text:
                lines.append(pt.text.capitalize())

        if not lines:
            return await ctx.send('Invalid response.')

        message = '\n'.join(lines[0:3])
        if 'Current geoip location' in message:
            return await ctx.send('Invalid response.')

        if len(message) > 1990:
            menu_pages = []
            for page in cf.pagify(message, delims=[' | ', '\n'], page_length=1990):
                menu_pages.append(cf.box(page))
            await menus.menu(ctx, menu_pages, menus.DEFAULT_CONTROLS)
        else:
            await ctx.send(cf.box(message))

    @_wolf.command(name='image')
    async def _wolf_image(self, ctx, *, query: str):
        """Query Wolfram Alpha. Returns an image."""
        if not self.app_id:
            return await ctx.send(self.app_msg, ephemeral=True, delete_after=30)

        await ctx.typing()
        url = 'http://api.wolframalpha.com/v1/simple'
        params = {
            'appid':  self.app_id,
            'i':  query,
            'width':  800,
            'fontsize':  30,
            'layout':  'labelbar',
            'background':  '193555',
            'foreground':  'white',
            'units':  'metric',
        }
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()

        log.debug('r.text: %s', r.text)
        if len(r.text) == 43:
            return await ctx.send('Invalid response.')

        file = discord.File(io.BytesIO(r.content), f'wolfram-{self.get_ts()}.png')
        await ctx.channel.send(file=file)

    @_wolf.command(name='solve')
    async def _wolf_solve(self, ctx, *, query: str):
        """Query Wolfram Alpha. Returns step by step answers."""
        if not self.app_id:
            return await ctx.send(self.app_msg, ephemeral=True, delete_after=30)

        await ctx.typing()
        url = 'http://api.wolframalpha.com/v2/query'
        params = {
            'appid': self.app_id,
            'input': query,
            'podstate': 'Step-by-step solution',
            'format': 'plaintext',
        }
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()

        log.debug('r.text: %s', r.text)
        root = ElementTree.fromstring(r.text)
        msg = ''
        for pod in root.findall('.//pod'):
            if pod.attrib['title'] == 'Number line':
                continue
            msg += f"{pod.attrib['title']}\n"
            for pt in pod.findall('.//plaintext'):
                if pt.text:
                    strip = pt.text.replace(' | ', ' ').replace('| ', ' ')
                    msg += f'- {strip}\n\n'
        if not msg:
            return await ctx.send('Invalid response.')
        for text in cf.pagify(msg):
            await ctx.send(cf.box(text))

    @_wolf.command(name='set', aliases=['setapi'])
    @checks.is_owner()
    async def _wolf_set(self, ctx):
        """Set Wolfram Alpha App ID."""
        owners: List[int] = await self.get_owners(self.bot, ids=True)
        view = ModalView(self, owners)
        await view.send_initial_message(ctx)

    @staticmethod
    async def get_owners(bot, ids=False) -> List[Union[discord.User, int]]:
        app_info = await bot.application_info()
        owners: List[discord.User] = [app_info.owner]
        if os.environ.get('CO_OWNER'):
            for owner_id in os.environ.get('CO_OWNER').split(','):
                owners.append(bot.get_user(int(owner_id)))
        if ids:
            return [x.id for x in owners]
        return owners

    @staticmethod
    def get_ts(stamp: Optional[str] = '%Y%m%d-%H%M%S',
               prefix: Optional[str] = '',
               suffix: Optional[str] = '') -> str:
        ts = datetime.datetime.now().strftime(stamp)
        return f'{prefix}{ts}{suffix}'


class ModalView(discord.ui.View):
    delete_after = 30
    ephemeral = False

    def __init__(self, cog: commands.Cog,
                 user_ids: Optional[List[int]] = None,
                 timeout: Optional[int] = 60*60*1):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_ids: Optional[List[int]] = user_ids
        self.message: Optional[discord.Message] = None

    async def on_timeout(self):
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction):
        if not self.user_ids:
            return True
        if interaction.user.id in self.user_ids:
            return True
        msg = '⛔ Sorry, you are not authorized to use this interaction.'
        await interaction.response.send_message(msg, ephemeral=True,
                                                delete_after=self.delete_after)
        return False

    async def send_initial_message(self, ctx, message: Optional[str] = None,
                                   ephemeral: Optional[bool] = False,
                                   **kwargs) -> discord.Message:
        self.ephemeral = ephemeral
        self.message = await ctx.send(content=message, view=self,
                                      ephemeral=self.ephemeral, **kwargs)
        return self.message

    @discord.ui.button(label='Set Wolfram Details', emoji='📝', style=discord.ButtonStyle.blurple)
    async def set_button(self, interaction: discord.interactions.Interaction, button: discord.Button):
        # log.debug(interaction)
        # log.debug(button)
        # user = interaction.user
        data: Dict[str, Any] = await self.cog.config.all()
        modal = DataModal(view=self, data=data)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View, data: Dict[str, Any]):
        super().__init__(title='Set Wolfram Details')
        self.view: discord.ui.View = view
        self.data: Dict[str, Any] = data
        self.app_id = discord.ui.TextInput(
            label='Wolfram App ID',
            placeholder='xxxxxx-xxxxxxxxxx',
            default=self.data['app_id'],
            style=discord.TextStyle.short,
            max_length=17,
            min_length=17,
            required=False,
        )
        self.add_item(self.app_id)

    async def on_submit(self, interaction: discord.Interaction):
        log.debug('ReplyModal - on_submit')
        # message: discord.Message = interaction.message
        user: discord.Member = interaction.user
        # TODO: Verify Settings Here
        data = {
            'app_id': self.app_id.value.strip(),
        }
        await self.view.cog.config.set(data)
        self.view.cog.app_id = data['app_id']
        log.debug(data)
        msg = "✅ Wolfram Details Updated Successfully..."
        await interaction.response.send_message(msg, ephemeral=True)
